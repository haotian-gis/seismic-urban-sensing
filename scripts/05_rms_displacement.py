"""
Step 5 - Integrate displacement power spectra to RMS displacement (nm) and
aggregate to hourly medians.

Outputs
-------
RMS_2_20_CSV   : one column ``drms`` for the 2-20 Hz human-activity band.
RMS_BANDS_CSV  : columns ``band_<fmin>_<fmax>`` for sliding bands
                 (1-3, 2-4, ..., 38-40 Hz), used in the frequency sensitivity
                 analysis (Fig. 7b).
"""
import glob
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import numpy as np
import pandas as pd

import config

SPIKE_THRESHOLD_NM = 200  # values above are replaced by a centred 5-h rolling mean


def load_displacement(file):
    df = pd.read_feather(file)
    freq_cols = np.array([c for c in df.columns if c.startswith("disp_pow_")])
    freqs = np.array([float(c.split("_")[2]) for c in freq_cols])
    return df, freq_cols, freqs


def to_hourly(rms_df, station_id):
    rms_df["start_time"] = pd.to_datetime(rms_df["start_time"], format="%Y-%m-%dT%H-%M-%S", errors="coerce")
    rms_df = rms_df.dropna(subset=["start_time"])
    hourly = rms_df.drop(columns="station_id").set_index("start_time").resample("h").median().reset_index()
    return hourly.assign(station_id=station_id)


def rms_2_20():
    f_min, f_max = config.HUMAN_BAND
    results = []
    for file in glob.glob(f"{config.DISPLACEMENT_DIR}/*.feather"):
        df, freq_cols, freqs = load_displacement(file)
        station_id = df["station_id"].iloc[0]
        print(f"[2-20 Hz] {station_id}")
        valid = (freqs >= f_min) & (freqs <= f_max)
        freqs_sel, cols_sel = freqs[valid], freq_cols[valid]
        delta_f = np.append(np.diff(freqs_sel), np.diff(freqs_sel)[-1])
        drms = np.sqrt((df[cols_sel].to_numpy(dtype=float) * delta_f).sum(axis=1)) * 1e9  # m -> nm
        rms_df = pd.DataFrame({"station_id": df["station_id"], "start_time": df["start_time"], "drms": drms})
        results.append(to_hourly(rms_df, station_id))

    combined = pd.concat(results)
    combined["drms"] = combined["drms"].where(
        combined["drms"] <= SPIKE_THRESHOLD_NM,
        combined["drms"].rolling(window=5, center=True, min_periods=1).mean(),
    )
    combined = combined[["start_time", "drms", "station_id"]]
    combined.to_csv(config.RMS_2_20_CSV, index=False)
    print(f"Saved {config.RMS_2_20_CSV}")


def rms_bands():
    f_min = np.arange(1, 39)
    bands = np.column_stack((f_min, f_min + 2))
    results = []
    for file in glob.glob(f"{config.DISPLACEMENT_DIR}/*.feather"):
        df, freq_cols, freqs = load_displacement(file)
        station_id = df["station_id"].iloc[0]
        print(f"[bands] {station_id}")
        rms_df = pd.DataFrame({"station_id": df["station_id"], "start_time": df["start_time"]})
        for lo, hi in bands:
            valid = (freqs >= lo) & (freqs <= hi)
            delta_f = np.gradient(freqs[valid])
            rms_df[f"band_{lo}_{hi}"] = np.sqrt(
                (df[freq_cols[valid]].to_numpy(dtype=float) * delta_f).sum(axis=1)) * 1e9
        results.append(to_hourly(rms_df, station_id))
    pd.concat(results, ignore_index=True).to_csv(config.RMS_BANDS_CSV, index=False)
    print(f"Saved {config.RMS_BANDS_CSV}")


if __name__ == "__main__":
    rms_2_20()
    rms_bands()
