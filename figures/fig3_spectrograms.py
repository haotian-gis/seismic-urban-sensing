"""
Fig. 3 / Fig. S2 - Time-frequency spectrograms (PSD, dB) for every station.
"""
import glob
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import matplotlib
matplotlib.use("Agg")
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import pandas as pd

import config
from utils.plotting import to_local


def plot_station(file, out_dir):
    data = pd.read_feather(file)
    station = data["station_id"].values[0]
    data["start_time"] = to_local(pd.to_datetime(data["start_time"], format="%Y-%m-%dT%H-%M-%S", errors="coerce"))
    freq_cols = [c for c in data.columns if c.startswith("freq_")]
    freqs = [float(c.split("_")[-1]) for c in freq_cols]

    fig, ax = plt.subplots(figsize=(12, 6))
    mesh = ax.pcolormesh(data["start_time"].values, freqs, data[freq_cols].values.T,
                         shading="auto", cmap="jet", vmin=-160, vmax=-90)
    ax.set_ylabel("Frequency (Hz)", fontsize=14)
    ax.set_title(f"Spectrogram for {station}", fontsize=16)
    ax.xaxis_date()
    ax.xaxis.set_major_locator(mdates.DayLocator(interval=1))
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%d-%b-%Y"))
    ax.set_xlim(pd.Timestamp("2021-02-04"), pd.Timestamp("2021-02-27"))
    ax.set_ylim(0, 40)
    plt.setp(ax.xaxis.get_majorticklabels(), rotation=45, ha="right")
    for date in ["2021-02-11", "2021-02-20"]:
        ax.axvline(pd.Timestamp(date), color="red", linestyle="--", linewidth=2)
    cbar = plt.colorbar(mesh, ax=ax, label="PSD (dB)", fraction=0.05, pad=0.07)
    cbar.ax.set_ylabel("PSD (dB)", fontsize=16)
    plt.tight_layout(rect=[0, 0, 0.85, 1])
    plt.savefig(out_dir / f"{station}_Plot.png", dpi=300)
    plt.close()


def main():
    out_dir = config.ensure_dir(config.FIG_DIR / "spectrograms")
    for file in sorted(glob.glob(f"{config.PSD_DIR}/*.feather")):
        plot_station(file, out_dir)
        print(f"Plotted {file}")


if __name__ == "__main__":
    main()
