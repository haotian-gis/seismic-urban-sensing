"""
Fig. 4 - Normalised 2-20 Hz PSD for all stations (3-hour bins).
"""
import glob
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns

import config

# Display order: urban stations first, then rural
STATION_ORDER = ["TX.FW01", "TX.FW04", "TX.FW05", "TX.FW09", "TX.FW15", "ZW.IFDF", "N4.Z35B",
                 "TX.FW02", "TX.FW06", "TX.FW07", "TX.FW14", "TX.FW16", "TX.TREL"]


def band_mean_psd(file, fmin, fmax):
    df = pd.read_feather(file)
    freq_cols = [c for c in df.columns if c.startswith("freq_")]
    freqs = np.array([float(c.split("_")[1]) for c in freq_cols])
    selected = [c for c, keep in zip(freq_cols, (freqs >= fmin) & (freqs <= fmax)) if keep]
    df["psd_avg_dB"] = df[selected].mean(axis=1)
    return df[["station_id", "start_time", "psd_avg_dB"]]


def min_max(row):
    lo, hi = row.min(), row.max()
    return (row - lo) / (hi - lo) if hi > lo else row * 0


def main():
    fmin, fmax = config.HUMAN_BAND
    combined = pd.concat([band_mean_psd(f, fmin, fmax) for f in glob.glob(f"{config.PSD_DIR}/*.feather")],
                         ignore_index=True)
    combined["start_time"] = pd.to_datetime(combined["start_time"], format="%Y-%m-%dT%H-%M-%S").dt.floor("min")
    combined = combined.sort_values(by=["station_id", "start_time"])
    heat = combined.pivot(index="station_id", columns="start_time", values="psd_avg_dB")
    heat.columns = pd.to_datetime(heat.columns)

    # 3-hour bins; fill gaps with a rolling mean, then forward/back fill
    heat_3h = heat.T.resample("3h").mean().T
    rolling = heat.T.rolling(window=5, min_periods=1).mean().T
    filled = heat_3h.fillna(rolling).ffill(axis=1).bfill(axis=1)

    norm = filled.apply(min_max, axis=1)
    norm.columns = pd.to_datetime(norm.columns)
    norm.index = norm.index.str.replace(r"\.00\.HH$", "", regex=True)
    norm = norm.loc[[s for s in STATION_ORDER if s in norm.index]]

    plt.figure(figsize=(8, 4.5))
    ax = sns.heatmap(norm, cmap="viridis", cbar_kws={"label": "Normalized PSD (2-20 Hz)"}, linewidths=0)
    ticks = [i for i, ts in enumerate(norm.columns) if ts.hour == 0]
    ax.set_xticks(ticks)
    ax.set_xticklabels(norm.columns[ticks].strftime("%Y-%m-%d"), rotation=45)
    ax.xaxis.label.set_visible(False)
    for date, color in [("2021-02-11", "red"), ("2021-02-20", "red"),
                        ("2021-02-06", "white"), ("2021-02-08", "white"), ("2021-02-22", "white")]:
        plt.axvline(x=norm.columns.get_loc(pd.Timestamp(date)), color=color, linestyle="--", linewidth=1.5)
    plt.xticks(rotation=45, ha="right")
    plt.ylabel("Seismic Stations")
    plt.tight_layout()
    out = config.ensure_dir(config.FIG_DIR) / "fig4_psd_heatmap.pdf"
    plt.savefig(out, dpi=300)
    print(f"Saved {out}")


if __name__ == "__main__":
    main()
