"""
Step 8 - Aggregate NOAA surface observations to hourly means and attach each
seismic station to its nearest weather station. Output: ``WIND_CLEAN_CSV``.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pandas as pd
from shapely.geometry import Point

import config


def nearest_wind_station(seismic, wind_stations):
    nearest = []
    for _, s in seismic.iterrows():
        d = wind_stations["geometry"].apply(lambda g: s["geometry"].distance(g))
        nearest.append(wind_stations.loc[d.idxmin(), "STATION"])
    seismic = seismic.copy()
    seismic["nearest_wind_station"] = nearest
    return seismic


def main():
    wind = pd.read_csv(config.WIND_RAW_CSV)
    wind["DATE"] = pd.to_datetime(wind["DATE"])
    wind["DATE_hourly"] = wind["DATE"].dt.round("h")
    wind = wind.groupby(["STATION", "DATE_hourly"]).mean(numeric_only=True).reset_index()

    wind_stations = wind.drop_duplicates(subset=["STATION"]).copy()
    wind_stations["geometry"] = [Point(x, y) for x, y in zip(wind_stations["LONGITUDE"], wind_stations["LATITUDE"])]

    seismic = pd.read_csv(config.STATIONS_CSV)
    seismic["geometry"] = [Point(x, y) for x, y in zip(seismic["longitude"], seismic["latitude"])]
    seismic = nearest_wind_station(seismic, wind_stations)[["station_id", "nearest_wind_station"]]

    wind = wind[(wind["DATE_hourly"] >= "2021-02-04 00:00:00") & (wind["DATE_hourly"] <= "2021-02-27 23:00:00")]
    out = pd.merge(wind, seismic, left_on="STATION", right_on="nearest_wind_station", how="inner")
    out.to_csv(config.WIND_CLEAN_CSV, index=False)
    print(f"Saved {config.WIND_CLEAN_CSV}")


if __name__ == "__main__":
    main()
