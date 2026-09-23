"""
Fig. 5 - Temporal and spatial patterns of RMS displacement change (2-20 Hz).

(a) hourly % change relative to the pre-storm baseline, all stations + mean
(b) diurnal RMS cycle (polar clock) for baseline / Phase 1 / Phase 2
(c) station map of Phase-2 % change on a satellite basemap
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import contextily as ctx
import geopandas as gpd
import matplotlib
matplotlib.use("Agg")
import matplotlib.colors as mcolors
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

import config
from utils.plotting import shade_weekends_span, to_local

matplotlib.rcParams["pdf.fonttype"] = 42


def load_rms():
    df = pd.read_csv(config.RMS_2_20_CSV)
    df["start_time"] = to_local(pd.to_datetime(df["start_time"], format="%Y-%m-%d %H:%M:%S", errors="coerce"))
    df = df[(df["start_time"] >= config.STUDY_START) & (df["start_time"] < config.STUDY_END)]

    baseline = (df[(df["start_time"] >= config.BASELINE[0]) & (df["start_time"] < config.BASELINE[1])]
                .groupby("station_id")["drms"].mean().reset_index()
                .rename(columns={"drms": "baseline_drms"}))
    df = df.merge(baseline, on="station_id", how="left")
    df["percentage_change"] = (df["drms"] - df["baseline_drms"]) / df["baseline_drms"] * 100
    # Outlier handling kept exactly as used for the paper figures.
    df["percentage_change"] = df["percentage_change"].where(
        df["percentage_change"] <= 200, df["drms"].rolling(window=5, center=True, min_periods=1).mean())
    return df, baseline


def plot_timeseries(df, out_dir):
    mean_rms = df.groupby("start_time")["percentage_change"].mean().reset_index()
    x_min, x_max = df["start_time"].min(), df["start_time"].max()

    fig, ax = plt.subplots(figsize=(10, 5))
    for _, sdf in df.groupby("station_id"):
        ax.plot(sdf["start_time"], sdf["percentage_change"], color="gray", alpha=0.4, linewidth=0.8)
    ax.plot(mean_rms["start_time"], mean_rms["percentage_change"], color="blue", linewidth=2, label="Average")
    for date in config.STORM_DATES:
        ax.axvline(x=pd.to_datetime(date), color="red", linestyle="--", linewidth=1.5, alpha=0.8)
    ax.set_xlim(x_min, x_max)
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m-%d"))
    ax.xaxis.set_major_locator(mdates.DayLocator())
    plt.xticks(rotation=45, ha="right")
    shade_weekends_span(ax, x_min, x_max)
    ax.set_ylabel("Percentage Change (%)", fontsize=12)
    plt.legend(loc="upper left")
    ax.grid(True, linestyle="--", alpha=0.6)
    plt.tight_layout()
    plt.savefig(out_dir / "fig5a_percentage_change.pdf", dpi=300)
    plt.close()


def plot_diurnal(df, out_dir):
    df = df.copy()
    df["hour"] = df["start_time"].dt.hour
    periods = {
        "Baseline": (df["start_time"] < config.BASELINE[1], "-", "blue"),
        "Phase 1": ((df["start_time"] >= config.PHASE_1[0]) & (df["start_time"] < config.PHASE_1[1]), "--", "purple"),
        "Phase 2": ((df["start_time"] >= config.PHASE_2[0]) & (df["start_time"] < config.PHASE_2[1]), "--", "red"),
    }
    angles = np.linspace(0, 2 * np.pi, 24, endpoint=False).tolist()
    angles.append(angles[0])

    plt.figure(figsize=(10, 10))
    ax = plt.subplot(111, projection="polar")
    ax.set_theta_zero_location("N")
    ax.set_theta_direction(-1)
    for label, (mask, ls, color) in periods.items():
        values = df[mask].groupby("hour")["drms"].mean().tolist()
        values.append(values[0])
        ax.plot(angles, values, linestyle=ls, linewidth=2, color=color, label=label)
    ax.set_xticks(np.linspace(0, 2 * np.pi, 12, endpoint=False))
    ax.set_xticklabels([f"{h}:00" for h in range(0, 24, 2)], fontsize=16)
    plt.title("Hourly RMS Comparison in Different Phases", fontsize=16)
    plt.legend(loc="upper right", fontsize=14)
    plt.savefig(out_dir / "fig5b_diurnal_rms.pdf", dpi=300)
    plt.close()


def plot_spatial(df, baseline, out_dir):
    def period_mean(start, end, label):
        return (df[(df["start_time"] >= start) & (df["start_time"] < end)]
                .groupby("station_id")["drms"].mean().reset_index().rename(columns={"drms": label}))

    merged = (baseline.merge(period_mean(*config.PHASE_1, "uri_drms"), on="station_id", how="left")
                      .merge(period_mean(*config.PHASE_2, "uri2_drms"), on="station_id", how="left")
                      .merge(pd.read_csv(config.STATIONS_CSV), on="station_id", how="left"))
    merged["percentage_change_1"] = (merged["uri_drms"] - merged["baseline_drms"]) / merged["baseline_drms"] * 100
    merged["percentage_change_2"] = (merged["uri2_drms"] - merged["baseline_drms"]) / merged["baseline_drms"] * 100

    # Population density of the block group containing each station
    cbgs = gpd.read_file(config.CBG_GEOJSON)
    dallas = gpd.read_file(config.DALLAS_BOUNDARY_SHP).to_crs(cbgs.crs)
    area = gpd.overlay(cbgs, dallas, how="intersection")
    social = pd.read_csv(config.CBG_POPULATION_CSV)
    social["bg2010ge"] = social["bg2010ge"].astype(str)
    area = area.merge(social[["bg2010ge", "Weighted Total Population"]],
                      left_on="CensusBlockGroup", right_on="bg2010ge", how="left").to_crs(epsg=3857)
    area["Population Density"] = area["Weighted Total Population"] / (area.geometry.area / 1e6)

    merged = gpd.GeoDataFrame(merged, geometry=gpd.points_from_xy(merged["longitude"], merged["latitude"]),
                              crs="EPSG:4326").to_crs(area.crs)
    merged = merged.sjoin(area[["Population Density", "geometry"]], how="left", predicate="intersects")
    merged = merged.to_crs("EPSG:4326")

    fig, ax = plt.subplots(figsize=(10, 6))
    norm = mcolors.Normalize(vmin=merged["percentage_change_2"].min(), vmax=merged["percentage_change_2"].max())
    sc = ax.scatter(merged.geometry.x, merged.geometry.y, c=merged["percentage_change_2"], cmap=plt.cm.viridis,
                    norm=norm, s=300, edgecolors="k", linewidth=0.5, alpha=0.8)
    for _, row in merged.iterrows():
        ax.text(row.geometry.x, row.geometry.y, str(row["station"]), fontsize=14, ha="right", va="bottom", color="white")
    ctx.add_basemap(ax, source=ctx.providers.Esri.WorldImagery, crs=merged.crs.to_string(), zoom=12, alpha=0.7)
    cbar = fig.colorbar(sc, ax=ax, extend="both")
    cbar.set_label("Change in RMS displacement, Phase 2 (%)")
    ax.set_xlabel("Longitude")
    ax.set_ylabel("Latitude")
    ax.set_title("Spatial Pattern of RMS Displacement Change (2-20Hz) during Winter Storm Uri (Phase 2)")
    plt.tight_layout()
    plt.savefig(out_dir / "fig5c_spatial_pattern.pdf", dpi=300)
    plt.close()
    merged.drop(columns="geometry").to_csv(out_dir / "fig5c_station_changes.csv", index=False)


def main():
    out_dir = config.ensure_dir(config.FIG_DIR)
    df, baseline = load_rms()
    plot_timeseries(df, out_dir)
    plot_diurnal(df, out_dir)
    plot_spatial(df, baseline, out_dir)
    print(f"Saved Fig. 5 panels to {out_dir}")


if __name__ == "__main__":
    main()
