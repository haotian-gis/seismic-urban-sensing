"""
Step 6 - Hourly POI visits within a 5 km buffer of each seismic station,
in total and by activity group (restaurant, shopping, healthcare, education,
manufacturing). Output: ``MOBILITY_5KM_CSV``.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import geopandas as gpd
import pandas as pd

import config
from utils.mobility import load_stations, load_study_area_cbgs, load_weekly_patterns, weekly_to_hourly
from utils.poi_categories import ACTIVITY_GROUPS, categorize

BUFFER_M = 5000


def hourly_visits_per_station(mobility, station_buffers):
    results = []
    for station in station_buffers["station_id"]:
        buf = station_buffers[station_buffers["station_id"] == station]
        pois = gpd.sjoin(mobility, buf, predicate="within")
        pois = pois[pois["visits_by_each_hour"].notna()]
        if pois.empty:
            continue
        hourly = weekly_to_hourly(pois)
        hourly = hourly[(hourly["timestamp"] >= "2021-02-04") & (hourly["timestamp"] < "2021-02-28")].copy()
        hourly["station"] = station
        results.append(hourly)
    return pd.concat(results, ignore_index=True)


def main():
    cbgs = load_study_area_cbgs()
    mobility = load_weekly_patterns(cbgs["CensusBlockGroup"].tolist())
    mobility["category"] = mobility["top_category"].apply(
        lambda c: categorize(c, ACTIVITY_GROUPS, default="others"))

    stations = load_stations().to_crs("EPSG:3857")
    stations["geometry"] = stations.buffer(BUFFER_M)
    stations = stations.to_crs("EPSG:4326")

    final = hourly_visits_per_station(mobility, stations).rename(columns={"hourly_visits": "all_visits"})
    for group in ACTIVITY_GROUPS:
        subset = mobility[mobility["category"] == group]
        col = f"{group.lower()}_visits"
        part = hourly_visits_per_station(subset, stations).rename(columns={"hourly_visits": col})
        final = final.merge(part, on=["timestamp", "station"], how="left")

    final.to_csv(config.MOBILITY_5KM_CSV, index=False)
    print(f"Saved {config.MOBILITY_5KM_CSV}")


if __name__ == "__main__":
    main()
