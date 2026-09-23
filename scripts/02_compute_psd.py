"""
Step 2 - Remove instrument response and compute Welch PSDs (velocity) in
30-min windows with 50 % overlap for every station.

Output: ``PSD_DIR/<station_id>/<station_id>_<start>_<end>.txt``
(two rows: frequency [Hz], PSD [(m/s)^2/Hz]).
"""
import glob
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import numpy as np
import obspy
import pandas as pd
from joblib import Parallel, delayed
from scipy.signal import welch

import config

inv = obspy.read_inventory(f"{config.STATIONXML_DIR}/*.xml")


def list_station_ids(inventory):
    rows = []
    for net in inventory:
        for sta in net:
            for cha in sta:
                rows.append({
                    "station_id": f"{net.code}.{sta.code}.{cha.location_code}.{cha.code[:-1]}",
                    "latitude": cha.latitude,
                    "longitude": cha.longitude,
                    "depth_km": cha.depth / 1000,
                    "elevation": cha.elevation,
                })
    stations = pd.DataFrame(rows).drop_duplicates(subset=["station_id"])
    return stations["station_id"].unique()


def process_station(sid):
    network, station, location, channel = sid.split(".")
    inventory = inv.select(network=network, station=station, channel="*Z")
    mseed_files = glob.glob(f"{config.WAVEFORM_DIR}/{sid}*.mseed")
    if not mseed_files:
        print(f"No waveform files found for station {sid}")
        return

    fs = config.RESAMPLE_HZ
    twin = config.PSD_WINDOW_S
    nperseg = int(twin * fs)
    step = nperseg // 2  # 50 % overlap
    out_path = config.ensure_dir(config.PSD_DIR / sid)

    for mseed_file in mseed_files:
        try:
            stream = obspy.read(mseed_file)
            stream = stream.remove_response(inventory, output="VEL")
            stream = stream.resample(fs)
            stream = stream.taper(0.05, type="hann")
            stream = stream.detrend("demean")
            data = stream[0].data
            num_windows = (len(data) - step) // step

            for i in range(num_windows):
                start_idx = i * step
                end_idx = start_idx + nperseg
                if end_idx > len(data):
                    break
                stime = stream[0].stats.starttime + start_idx / fs
                etime = stime + twin

                freqs, psd = welch(data[start_idx:end_idx], fs=fs, nperseg=nperseg)
                mask = (freqs >= config.PSD_FMIN) & (freqs <= config.PSD_FMAX)

                out_file = (out_path / f"{sid}_{stime.strftime('%Y-%m-%dT%H-%M-%S')}"
                                       f"_{etime.strftime('%Y-%m-%dT%H-%M-%S')}.txt")
                np.savetxt(out_file, np.array([freqs[mask], psd[mask]]))
        except Exception as e:  # keep going if a single file is corrupt
            print(f"Error processing file {mseed_file}: {e}")
    print(f"Saved: {sid}")


if __name__ == "__main__":
    Parallel(n_jobs=config.N_JOBS)(delayed(process_station)(sid) for sid in list_station_ids(inv))
