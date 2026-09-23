"""
Fig. S1 - Hourly PSD in several frequency bands for each station.
"""
import glob
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import matplotlib
matplotlib.use("Agg")
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
from matplotlib import rcParams
from matplotlib.patches import Rectangle

import config

rcParams["pdf.fonttype"] = 42
rcParams["font.family"] = "Arial"

BANDS = {
    "0.1–2 Hz": (0.1, 2),
    "2–5 Hz": (2, 5),
    "5–10 Hz": (5, 10),
    "10–20 Hz": (10, 20),
    "20–40 Hz": (20, 40),
}


def main():
    files = sorted(glob.glob(f"{config.PSD_DIR}/*.feather"))[:13]
    sns.set_style("whitegrid")
    colors = sns.color_palette("husl", n_colors=len(BANDS))
    fig, axs = plt.subplots(5, 3, figsize=(15, 18))
    axs = axs.flatten()

    for i, file in enumerate(files):
        try:
            df = pd.read_feather(file)
            df["start_time"] = df["start_time"].astype(str).str.replace(
                r"T(\d{2})-(\d{2})-(\d{2})", r"T\1:\2:\3", regex=True)
            df["start_time"] = pd.to_datetime(df["start_time"], errors="coerce", utc=True)
            df = df.dropna(subset=["start_time"]).set_index("start_time")
        except Exception as e:
            print(f"Skipping {file}: {e}")
            continue

        freq_cols = [c for c in df.columns if c.startswith("freq_")]
        freqs = np.array([float(c.split("_")[1]) for c in freq_cols])
        for name, (lo, hi) in BANDS.items():
            df[name] = df[[freq_cols[j] for j in np.where((freqs >= lo) & (freqs <= hi))[0]]].mean(axis=1)
        hourly = df.select_dtypes(include=[np.number]).resample("1h").mean()

        ax = axs[i]
        vmin = hourly[list(BANDS)].min().min()
        vmax = hourly[list(BANDS)].max().max()
        margin = (vmax - vmin) * 0.1
        y_min, y_max = vmin - margin, vmax + margin
        for day in pd.date_range(start=hourly.index.min(), end=hourly.index.max()):
            if day.weekday() in (5, 6):
                ax.add_patch(Rectangle((mdates.date2num(day), y_min), 1, y_max - y_min, color="cyan", alpha=0.2))
        for name, color in zip(BANDS, colors):
            ax.plot(hourly.index, hourly[name], label=name, color=color, linestyle="--", linewidth=1.0)
        for date in ["2021-02-11", "2021-02-20"]:
            ax.axvline(x=pd.to_datetime(date), color="red", linestyle="--", linewidth=1.2)

        ax.set_title(df["station_id"].iloc[0], fontsize=14)
        ax.set_xlabel("Date", fontsize=13)
        ax.set_ylabel("PSD (dB)", fontsize=13)
        ax.set_ylim(y_min, y_max)
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
        ax.grid(True, linestyle="-", linewidth=0.4, alpha=0.2)
        ax.tick_params(axis="x", labelrotation=45, labelsize=13)
        ax.tick_params(axis="y", labelsize=13)

    fig.suptitle("PSD Across Frequency Bands for 13 Stations", fontsize=20, y=1.03)
    handles, labels = axs[0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="upper center", ncol=len(labels), fontsize=13, bbox_to_anchor=(0.5, 1.02))
    for j in range(len(files), len(axs)):
        fig.delaxes(axs[j])
    plt.tight_layout(rect=[0, 0, 1, 0.97])
    out = config.ensure_dir(config.FIG_DIR) / "figS1_band_psd.pdf"
    plt.savefig(out, dpi=300, bbox_inches="tight")
    print(f"Saved {out}")


if __name__ == "__main__":
    main()
