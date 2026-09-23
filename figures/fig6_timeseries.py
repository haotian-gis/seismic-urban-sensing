"""
Fig. 6 / Fig. S3 - Seismic noise (RMS displacement change, 2-20 Hz) compared with
(a) POI visits, (b) flights at DFW airport, (c) wind gusts at rural stations.

Usage:
    python figures/fig6_timeseries.py
    python figures/fig6_timeseries.py --mobility-station TX.FW04.00.HH --wind-station TX.FW14.00.HH
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

import config
from utils.plotting import add_storm_lines, format_daily_axis, shade_weekends, to_local

VISIT_COLS = ["all_visits", "restaurant_visits", "shopping_visits",
              "healthcare_visits", "education_visits", "manufacturing_visits"]
AIRPORT = "KDFW"


def short(station_id):
    return station_id.replace(".00.HH", "")


def load_data():
    rms = pd.read_csv(config.RMS_2_20_CSV).rename(columns={"station_id": "station", "start_time": "timestamp"})
    mobility = pd.read_csv(config.MOBILITY_5KM_CSV)
    wind = pd.read_csv(config.WIND_CLEAN_CSV).rename(columns={"station_id": "station", "DATE_hourly": "timestamp"})
    for df in (rms, mobility, wind):
        df["timestamp"] = pd.to_datetime(df["timestamp"])

    data = pd.merge(rms, mobility, on=["timestamp", "station"], how="inner")
    data = pd.merge(data, wind, on=["timestamp", "station"], how="left")
    data["windgust"] = data["windgust"].fillna(data["windgust"].rolling(24, min_periods=1).mean())
    data["timestamp"] = to_local(data["timestamp"])
    return data[(data["timestamp"] >= config.STUDY_START) & (data["timestamp"] < config.STUDY_END)]


def add_percentage_change(df):
    """% change of RMS and visits relative to the pre-storm baseline mean."""
    df = df.copy()
    base = df[(df["timestamp"] >= "2021-02-04") & (df["timestamp"] < "2021-02-11")]
    for col in VISIT_COLS:
        df[f"{col}_change"] = (df[col] - base[col].mean()) / base[col].mean() * 100
    df["drms_change"] = (df["drms"] - base["drms"].mean()) / base["drms"].mean() * 100
    return df


def finish(ax1, x_min, x_max, out_file, ax2=None):
    format_daily_axis(ax1, x_min, x_max)
    ax1.grid(True, linestyle="--", alpha=0.5, color="#B0B0B0")
    ax1.set_ylabel("Percentage Change", fontsize=14, color="black")
    ax1.legend(loc="center left", fontsize=10, bbox_to_anchor=(1.05, 0.5), borderaxespad=0.)
    if ax2 is not None:
        ax2.legend(loc="center left", fontsize=10, bbox_to_anchor=(1.05, 0.5), borderaxespad=0.)
        ax2.spines["top"].set_visible(False)
    ax1.spines["top"].set_visible(False)
    ax1.spines["right"].set_visible(False)
    plt.tight_layout()
    plt.savefig(out_file, dpi=300, bbox_inches="tight")
    plt.close()


def plot_mobility(data, station, out_dir):
    df = add_percentage_change(data[data["station"] == station])
    r = np.corrcoef(df["all_visits_change"], df["drms_change"])[0, 1]
    x_min, x_max = df["timestamp"].min(), df["timestamp"].max()

    fig, ax1 = plt.subplots(figsize=(15, 5))
    ax1.plot(df["timestamp"], df["all_visits_change"], label=f"Total Visits (r={r:.2f})",
             color="#E41A1C", linewidth=1.3, alpha=0.9)
    ax1.plot(df["timestamp"], df["drms_change"], label=f"{short(station)} Seismic Noise",
             color="#000000", linewidth=2.0)
    shade_weekends(ax1, x_min, x_max, *ax1.get_ylim())
    add_storm_lines(ax1)
    finish(ax1, x_min, x_max, out_dir / f"fig6_mobility_{short(station)}.pdf")


def plot_wind(data, station, out_dir):
    df = add_percentage_change(data[data["station"] == station])
    r = np.corrcoef(df["drms_change"], df["windgust"])[0, 1]
    x_min, x_max = df["timestamp"].min(), df["timestamp"].max()

    fig, ax1 = plt.subplots(figsize=(15, 5))
    ax2 = ax1.twinx()
    ax2.plot(df["timestamp"], df["windgust"], label="Wind Gust", color="green", linewidth=1.2, alpha=0.8)
    ax1.plot(df["timestamp"], df["drms_change"], label=f"{short(station)} Seismic Noise (r={r:.2f})",
             color="black", linewidth=1.2, alpha=0.8)
    shade_weekends(ax1, x_min, x_max, *ax1.get_ylim())
    add_storm_lines(ax1)
    ax2.set_ylabel("Wind Gust (kt)", fontsize=14, color="#9e0059")
    finish(ax1, x_min, x_max, out_dir / f"fig6_wind_{short(station)}.pdf", ax2)


def hourly_flights():
    flight = pd.read_csv(config.FLIGHTS_CSV)
    flight["firstseen"] = pd.to_datetime(flight["firstseen"])
    flight["lastseen"] = pd.to_datetime(flight["lastseen"])
    dep = flight[(flight["origin"] == AIRPORT) & (flight["destination"] != AIRPORT)]
    arr = flight[(flight["destination"] == AIRPORT) & (flight["origin"] != AIRPORT)]
    dep = dep.groupby(dep["firstseen"].dt.floor("h")).size().rename("departures")
    arr = arr.groupby(arr["lastseen"].dt.floor("h")).size().rename("arrivals")
    hourly = pd.concat([dep, arr], axis=1).fillna(0).rename_axis("hour").reset_index()
    hourly["total_flights"] = hourly["departures"] + hourly["arrivals"]
    hourly["hour"] = to_local(hourly["hour"])
    hourly = hourly[(hourly["hour"] >= "2021-02-04 00:00:00") & (hourly["hour"] <= "2021-02-27 23:00:00")]
    hourly["timestamp"] = pd.to_datetime(hourly["hour"].dt.strftime("%Y-%m-%d %H:%M:%S"))
    return hourly


def plot_flights(data, station, out_dir):
    df = add_percentage_change(data[data["station"] == station])
    df = pd.merge(df, hourly_flights(), on="timestamp", how="left")
    df["total_flights"] = df["total_flights"].fillna(0)
    r_all = np.corrcoef(df["all_visits_change"], df["drms_change"])[0, 1]
    r_edu = np.corrcoef(df["education_visits_change"], df["drms_change"])[0, 1]
    r_flight = np.corrcoef(df["total_flights"], df["drms_change"])[0, 1]
    x_min, x_max = df["timestamp"].min(), df["timestamp"].max()

    fig, ax1 = plt.subplots(figsize=(15, 5))
    ax2 = ax1.twinx()
    ax1.plot(df["timestamp"], df["all_visits_change"], label=f"Total Visits (r={r_all:.2f})",
             color="#E41A1C", linewidth=1.5, alpha=0.9)
    ax1.plot(df["timestamp"], df["education_visits_change"], label=f"Education Visits (r={r_edu:.2f})",
             color="#FF7F00", linewidth=1.5, alpha=0.9)
    ax1.plot(df["timestamp"], df["drms_change"], label=f"{short(station)} Seismic Noise",
             color="#000000", linewidth=2.5)
    ax2.plot(df["timestamp"], df["total_flights"], label=f"Total Flights (r={r_flight:.2f})",
             color="#507dbc", linewidth=1.5)
    ax2.set_ylabel("Number of Flights", fontsize=14, color="#507dbc")
    shade_weekends(ax1, x_min, x_max, *ax1.get_ylim())
    add_storm_lines(ax1)
    finish(ax1, x_min, x_max, out_dir / f"fig6_flights_{short(station)}.pdf", ax2)


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--mobility-station", default="TX.FW06.00.HH")
    p.add_argument("--wind-station", default="TX.FW06.00.HH")
    p.add_argument("--airport-station", default="TX.FW04.00.HH")
    args = p.parse_args()

    out_dir = config.ensure_dir(config.FIG_DIR)
    data = load_data()
    plot_mobility(data, args.mobility_station, out_dir)
    plot_wind(data, args.wind_station, out_dir)
    plot_flights(data, args.airport_station, out_dir)
    print(f"Saved Fig. 6 panels to {out_dir}")


if __name__ == "__main__":
    main()
