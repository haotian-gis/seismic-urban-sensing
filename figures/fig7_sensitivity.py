"""
Fig. 7 - Sensitivity of the seismic-noise / mobility correlation to
(a) the buffer radius around each station (0.5-10 km) and
(b) the seismic frequency band.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd
from scipy.stats import pearsonr

import config

matplotlib.rcParams["pdf.fonttype"] = 42

URBAN_COLORS = ["#582707", "#972d07", "#c42348", "#ff4b3e", "#ffb20f", "#ffe548"]
RURAL_COLORS = ["#023e8a", "#5495e1", "#44a75e", "#dbe76a", "#a97cb5", "#7ef29d", "#68e3f9"]

# Buffer radius giving the peak mean correlation (from panel a)
URBAN_BEST_BUFFER = "buffer_4500"
RURAL_BEST_BUFFER = "buffer_9000"


def load_mobility():
    return pd.read_csv(config.MOBILITY_BUFFERS_CSV).rename(
        columns={"timestamp": "start_time", "station": "station_id"})


def two_panel_legend(fig, axes, handles):
    plt.tight_layout(rect=[0, 0, 0.83, 1])
    fig.legend(handles, [h.get_label() for h in handles], title="Station ID",
               bbox_to_anchor=(0.84, 0.5), loc="center left", fontsize=10, title_fontsize=11)
    for ax in axes:
        ax.grid(axis="y", linestyle="--")
        ax.grid(axis="x", visible=False)


def plot_group(ax, df, colors, marker, mean_label, x=None, mean_lw=3):
    x = df.columns if x is None else x
    handles = []
    for idx, station_id in enumerate(df.index):
        line, = ax.plot(x, df.loc[station_id], label=station_id, color=colors[idx % len(colors)],
                        linestyle="--", marker=marker, linewidth=2)
        handles.append(line)
    mean = df.mean()
    ax.plot(x, mean.values, label=mean_label, color="black", linestyle="-", linewidth=mean_lw,
            marker=marker, markersize=6, zorder=10)
    return handles, mean


def panel_a_buffers(out_dir):
    mobility = load_mobility()
    rms = pd.read_csv(config.RMS_2_20_CSV)
    mobility = mobility.merge(rms, on=["start_time", "station_id"], how="left").fillna(0)

    buffer_cols = sorted([c for c in mobility.columns if c.startswith("buffer_")], key=lambda c: int(c.split("_")[1]))
    rms_col = mobility.columns[-1]
    clean = mobility.dropna(subset=buffer_cols + [rms_col])

    corr = pd.DataFrame({station: {b: pearsonr(g[b], g[rms_col])[0] for b in buffer_cols}
                         for station, g in clean.groupby("station_id")}).T
    corr.columns = [c.replace("buffer_", "") for c in corr.columns]
    urban = corr.loc[corr.index.isin(config.URBAN_STATIONS)]
    rural = corr.loc[corr.index.isin(config.RURAL_STATIONS)]
    x_km = [int(c) / 1000 for c in corr.columns]

    fig, axes = plt.subplots(1, 2, figsize=(20, 5), sharey=True)
    handles = []
    for ax, df, colors, title, label, text_dx, text_dy in [
        (axes[0], urban, URBAN_COLORS, "Urban Stations", "Urban", 0.3, -0.5),
        (axes[1], rural, RURAL_COLORS, "Rural Stations", "Rural", -2.2, -0.4),
    ]:
        h, mean = plot_group(ax, df, colors, "o", f"{label} Mean", x=x_km, mean_lw=4)
        handles += h
        i = mean.values.argmax()
        px, py = x_km[i], mean.values[i]
        ax.plot([px, px], [-0.05, py], color="black", linestyle=":", linewidth=2, alpha=0.8, label=f"{label} Peak")
        ax.annotate(f"Peak: {px:.1f} km", xy=(px, py), xytext=(px + text_dx, py + text_dy),
                    arrowprops=dict(arrowstyle="->", color="black"), fontsize=14, color="black")
        ax.set_title(title, fontsize=16)
        ax.set_xlabel("Buffer Distance (km)", fontsize=14)
        ax.tick_params(labelsize=11)
        ax.set_xticks(x_km)
        ax.set_xlim(min(x_km), max(x_km))
        ax.set_ylim(bottom=-0.05)
    axes[0].set_ylabel("Pearson Correlation with RMS", fontsize=14)
    two_panel_legend(fig, axes, handles)
    plt.savefig(out_dir / "fig7a_correlation_buffers.pdf", dpi=300)
    plt.close()


def panel_b_bands(out_dir):
    mobility = load_mobility()
    mobility = mobility[["station_id", "start_time", URBAN_BEST_BUFFER, RURAL_BEST_BUFFER]]
    rms = pd.read_csv(config.RMS_BANDS_CSV)
    band_cols = [c for c in rms.columns if c.startswith("band_")]
    # 2-4 Hz ... 18-20 Hz
    band_cols = [c for c in band_cols if 2 <= int(c.split("_")[1]) and int(c.split("_")[2]) <= 20]
    rms = rms[["start_time", "station_id"] + band_cols]
    mobility = mobility.merge(rms, on=["start_time", "station_id"], how="left").fillna(0)

    def corr_table(stations, buffer):
        sub = mobility[mobility["station_id"].isin(stations)]
        t = pd.DataFrame({s: {b: pearsonr(g[buffer], g[b])[0] for b in band_cols}
                          for s, g in sub.groupby("station_id")}).T
        t.columns = [c.replace("band_", "") for c in t.columns]
        return t

    urban = corr_table(config.URBAN_STATIONS, URBAN_BEST_BUFFER)
    rural = corr_table(config.RURAL_STATIONS, RURAL_BEST_BUFFER)

    fig, axes = plt.subplots(1, 2, figsize=(20, 5), sharey=True)
    h_u, _ = plot_group(axes[0], urban, URBAN_COLORS, "o", "Urban Mean")
    h_r, _ = plot_group(axes[1], rural, RURAL_COLORS, "s", "Rural Mean")
    axes[0].set_title("Urban Stations", fontsize=16)
    axes[1].set_title("Rural Stations", fontsize=16)
    for ax in axes:
        ax.set_xlabel("Seismic Noise Frequency Band (Hz)", fontsize=14)
    axes[0].set_ylabel("Pearson Correlation", fontsize=14)
    two_panel_legend(fig, axes, h_u + h_r)
    plt.savefig(out_dir / "fig7b_correlation_frequency.pdf", dpi=300)
    plt.close()


def main():
    out_dir = config.ensure_dir(config.FIG_DIR)
    panel_a_buffers(out_dir)
    panel_b_bands(out_dir)
    print(f"Saved Fig. 7 panels to {out_dir}")


if __name__ == "__main__":
    main()
