"""
Seismic data acquisition and signal processing (Framework steps 1-2).

    download_waveforms()        IRIS FDSN mass download (HHZ/BHZ) + StationXML
    compute_psd()               response removal, Welch PSD in 30-min windows
    merge_psd()                 per-window PSD files -> one table per station (dB)
    compute_displacement()      velocity PSD -> displacement power spectrum
    compute_rms()               hourly RMS displacement, 2-20 Hz and sliding bands

Helpers that summarise the PSD tables (used in the temporal analysis):

    load_psd(), band_mean_psd(), normalized_psd_matrix(), band_psd_timeseries()

Run the whole chain with ``python seismic_processing.py``.
"""
import glob
import os

import numpy as np
import pandas as pd

import config

TIME_FMT = "%Y-%m-%dT%H-%M-%S"   # timestamp format used in PSD file names
SPIKE_THRESHOLD_NM = 200         # hourly RMS above this is replaced by a 5-h rolling mean


# =============================================================================
# 1. Data download
# =============================================================================
def download_waveforms(chunk_seconds=2 * 3600):
    """Download continuous vertical-component data for all stations in the DFW box."""
    import obspy
    from obspy.clients.fdsn.mass_downloader import MassDownloader, RectangularDomain, Restrictions

    config.ensure_dir(config.WAVEFORM_DIR)
    config.ensure_dir(config.STATIONXML_DIR)
    restrictions = Restrictions(
        starttime=obspy.UTCDateTime(*config.DOWNLOAD_START),
        endtime=obspy.UTCDateTime(*config.DOWNLOAD_END),
        chunklength_in_sec=chunk_seconds,
        channel_priorities=["HH[Z]", "BH[Z]"],
        reject_channels_with_gaps=True,
        minimum_length=0.0,
        minimum_interstation_distance_in_m=100.0,
    )
    MassDownloader(providers=["IRIS"]).download(
        RectangularDomain(**config.BBOX), restrictions,
        mseed_storage=str(config.WAVEFORM_DIR),
        stationxml_storage=str(config.STATIONXML_DIR),
    )


# =============================================================================
# 2. Power spectral density
# =============================================================================
def station_ids(inventory):
    """Unique ``NET.STA.LOC.CH`` ids (channel without component) in an inventory."""
    ids = {f"{net.code}.{sta.code}.{cha.location_code}.{cha.code[:-1]}"
           for net in inventory for sta in net for cha in sta}
    return sorted(ids)


def _psd_one_station(sid, inventory):
    import obspy
    from scipy.signal import welch

    network, station, _, _ = sid.split(".")
    inv = inventory.select(network=network, station=station, channel="*Z")
    files = glob.glob(f"{config.WAVEFORM_DIR}/{sid}*.mseed")
    if not files:
        print(f"No waveform files found for {sid}")
        return

    fs = config.RESAMPLE_HZ
    twin = config.PSD_WINDOW_S
    nperseg = int(twin * fs)
    step = nperseg // 2                       # 50 % overlap
    out_dir = config.ensure_dir(config.PSD_DIR / sid)

    for f in files:
        try:
            st = obspy.read(f)
            st = st.remove_response(inv, output="VEL")   # counts -> m/s
            st = st.resample(fs).taper(0.05, type="hann").detrend("demean")
            data = st[0].data
            for i in range((len(data) - step) // step):
                start = i * step
                if start + nperseg > len(data):
                    break
                t0 = st[0].stats.starttime + start / fs
                t1 = t0 + twin
                freqs, psd = welch(data[start:start + nperseg], fs=fs, nperseg=nperseg)
                keep = (freqs >= config.PSD_FMIN) & (freqs <= config.PSD_FMAX)
                name = f"{sid}_{t0.strftime(TIME_FMT)}_{t1.strftime(TIME_FMT)}.txt"
                np.savetxt(out_dir / name, np.array([freqs[keep], psd[keep]]))
        except Exception as e:                # skip corrupt files, keep going
            print(f"Error processing {f}: {e}")
    print(f"PSD done: {sid}")


def compute_psd(n_jobs=config.N_JOBS):
    """Welch PSD (velocity) for every station; writes ``PSD_DIR/<sid>/*.txt``."""
    import obspy
    from joblib import Parallel, delayed

    inventory = obspy.read_inventory(f"{config.STATIONXML_DIR}/*.xml")
    Parallel(n_jobs=n_jobs)(delayed(_psd_one_station)(sid, inventory) for sid in station_ids(inventory))


def merge_psd():
    """Merge per-window PSD files into ``PSD_DIR/<sid>.feather`` (PSD in dB)."""
    for folder in glob.glob(f"{config.PSD_DIR}/*/"):
        sid = os.path.basename(os.path.normpath(folder))
        rows, columns = [], None
        for f in sorted(glob.glob(f"{folder}/*.txt")):
            X = np.loadtxt(f)
            station_id, start_time, end_time = os.path.basename(f)[:-4].split("_")
            if columns is None:
                columns = ["station_id", "start_time", "end_time"] + [f"freq_{v:.4f}" for v in X[0]]
            rows.append([station_id, start_time, end_time] + (10 * np.log10(X[1])).tolist())
        pd.DataFrame(rows, columns=columns).to_feather(config.PSD_DIR / f"{sid}.feather")
        print(f"Merged {sid}")


# =============================================================================
# 3. Displacement and RMS
# =============================================================================
def _spectral_columns(df, prefix):
    cols = np.array([c for c in df.columns if c.startswith(prefix)])
    freqs = np.array([float(c[len(prefix):]) for c in cols])
    return cols, freqs


def compute_displacement():
    """P_disp(f) = P_vel(f) / (2*pi*f)^2 ; writes ``DISPLACEMENT_DIR/<sid>_displacement_power.feather``."""
    config.ensure_dir(config.DISPLACEMENT_DIR)
    for f in glob.glob(f"{config.PSD_DIR}/*.feather"):
        df = pd.read_feather(f)
        cols, freqs = _spectral_columns(df, "freq_")
        disp = 10 ** (df[cols].to_numpy(dtype=float) / 10) / (2 * np.pi * freqs) ** 2
        out = pd.DataFrame(disp, columns=[f"disp_pow_{v:.4f}" for v in freqs])
        out.insert(0, "end_time", df["end_time"].values)
        out.insert(0, "start_time", df["start_time"].values)
        out.insert(0, "station_id", df["station_id"].values)
        sid = df["station_id"].iloc[0]
        out.to_feather(config.DISPLACEMENT_DIR / f"{sid}_displacement_power.feather")
        print(f"Displacement done: {sid}")


def rms_displacement(disp_power, freqs, fmin, fmax, delta="diff"):
    """
    RMS displacement (nm) over [fmin, fmax] for each row of ``disp_power``.

    ``delta="diff"`` uses forward differences (last one repeated) for df;
    ``delta="gradient"`` uses ``np.gradient`` (central differences).
    """
    keep = (freqs >= fmin) & (freqs <= fmax)
    f = freqs[keep]
    if delta == "diff":
        df = np.append(np.diff(f), np.diff(f)[-1])
    else:
        df = np.gradient(f)
    return np.sqrt((disp_power[:, keep] * df).sum(axis=1)) * 1e9   # m -> nm


def _hourly_median(frame, sid):
    frame["start_time"] = pd.to_datetime(frame["start_time"], format=TIME_FMT, errors="coerce")
    frame = frame.dropna(subset=["start_time"])
    hourly = frame.set_index("start_time").resample("h").median().reset_index()
    return hourly.assign(station_id=sid)


def compute_rms():
    """
    Hourly (median) RMS displacement per station.

    Writes ``RMS_2_20_CSV`` (column ``drms``, 2-20 Hz, spikes smoothed) and
    ``RMS_BANDS_CSV`` (columns ``band_<lo>_<hi>`` for the sliding bands).
    """
    human, bands = [], []
    for f in glob.glob(f"{config.DISPLACEMENT_DIR}/*.feather"):
        df = pd.read_feather(f)
        sid = df["station_id"].iloc[0]
        cols, freqs = _spectral_columns(df, "disp_pow_")
        P = df[cols].to_numpy(dtype=float)

        drms = rms_displacement(P, freqs, *config.HUMAN_BAND, delta="diff")
        human.append(_hourly_median(pd.DataFrame({"start_time": df["start_time"], "drms": drms}), sid))

        b = pd.DataFrame({"start_time": df["start_time"]})
        for lo, hi in config.SLIDING_BANDS:
            b[f"band_{lo}_{hi}"] = rms_displacement(P, freqs, lo, hi, delta="gradient")
        bands.append(_hourly_median(b, sid))
        print(f"RMS done: {sid}")

    rms = pd.concat(human)
    rms["drms"] = rms["drms"].where(rms["drms"] <= SPIKE_THRESHOLD_NM,
                                    rms["drms"].rolling(window=5, center=True, min_periods=1).mean())
    rms.to_csv(config.RMS_2_20_CSV, index=False)
    pd.concat(bands, ignore_index=True).to_csv(config.RMS_BANDS_CSV, index=False)
    print(f"Saved {config.RMS_2_20_CSV} and {config.RMS_BANDS_CSV}")


# =============================================================================
# 4. PSD summaries (spectral patterns, Fig. 3/4/S1)
# =============================================================================
def load_psd(station_id):
    """PSD table (dB) for one station with parsed UTC ``start_time``."""
    df = pd.read_feather(config.PSD_DIR / f"{station_id}.feather")
    df["start_time"] = pd.to_datetime(df["start_time"], format=TIME_FMT, errors="coerce")
    return df


def band_mean_psd(df, fmin, fmax):
    """Mean PSD (dB) across frequency columns within [fmin, fmax]."""
    cols, freqs = _spectral_columns(df, "freq_")
    return df[cols[(freqs >= fmin) & (freqs <= fmax)]].mean(axis=1)


def normalized_psd_matrix(fmin=config.HUMAN_BAND[0], fmax=config.HUMAN_BAND[1], bin_="3h"):
    """
    Station x time matrix of band-mean PSD, averaged into ``bin_`` bins,
    gap-filled and min-max normalised per station (Fig. 4).
    """
    parts = []
    for f in glob.glob(f"{config.PSD_DIR}/*.feather"):
        df = pd.read_feather(f)
        parts.append(pd.DataFrame({"station_id": df["station_id"], "start_time": df["start_time"],
                                   "psd": band_mean_psd(df, fmin, fmax)}))
    long = pd.concat(parts, ignore_index=True)
    long["start_time"] = pd.to_datetime(long["start_time"], format=TIME_FMT).dt.floor("min")
    wide = long.sort_values(["station_id", "start_time"]).pivot(
        index="station_id", columns="start_time", values="psd")

    binned = wide.T.resample(bin_).mean().T
    rolling = wide.T.rolling(window=5, min_periods=1).mean().T
    filled = binned.fillna(rolling).ffill(axis=1).bfill(axis=1)

    lo = filled.min(axis=1)
    rng = filled.max(axis=1) - lo
    norm = filled.sub(lo, axis=0).div(rng.where(rng > 0), axis=0).fillna(0)
    norm.index = norm.index.str.replace(r"\.00\.HH$", "", regex=True)
    return norm


def band_psd_timeseries(station_id, bands=None, freq="1h"):
    """Hourly mean PSD (dB) in several frequency bands for one station (Fig. S1)."""
    bands = bands or {"0.1-2 Hz": (0.1, 2), "2-5 Hz": (2, 5), "5-10 Hz": (5, 10),
                      "10-20 Hz": (10, 20), "20-40 Hz": (20, 40)}
    df = load_psd(station_id).dropna(subset=["start_time"])
    out = pd.DataFrame({name: band_mean_psd(df, lo, hi) for name, (lo, hi) in bands.items()})
    out.index = df["start_time"].dt.tz_localize("UTC")
    return out.resample(freq).mean()


if __name__ == "__main__":
    download_waveforms()
    compute_psd()
    merge_psd()
    compute_displacement()
    compute_rms()
