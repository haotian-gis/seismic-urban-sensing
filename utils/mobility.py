"""Helpers for SafeGraph / Advan weekly-patterns mobility data."""
import json

import geopandas as gpd
import pandas as pd

import config


def load_study_area_cbgs(boundary_shp=config.DALLAS_UNION_SHP):
    """Census block groups intersecting the DFW study boundary."""
    cbgs = gpd.read_file(config.CBG_GEOJSON)
    boundary = gpd.read_file(boundary_shp).to_crs(cbgs.crs)
    return gpd.overlay(cbgs, boundary, how="intersection")


def load_weekly_patterns(cbg_ids, month_prefix="2021-02"):
    """Query weekly-patterns records for the given CBGs from MongoDB as a GeoDataFrame."""
    from pymongo import MongoClient

    client = MongoClient(config.MONGO_URI)
    weekly = client[config.MONGO_DB][config.MONGO_COLLECTION]
    query = {"date_range_start": {"$regex": f"^({month_prefix})"},
             "poi_cbg": {"$in": list(cbg_ids)}}
    df = pd.DataFrame(list(weekly.find(query)))
    gdf = gpd.GeoDataFrame(df, geometry=gpd.points_from_xy(df.longitude, df.latitude))
    gdf.set_crs("EPSG:4326", inplace=True)
    return gdf


def load_stations():
    """Seismic station locations as a GeoDataFrame (EPSG:4326)."""
    stations = pd.read_csv(config.STATIONS_CSV)
    gdf = gpd.GeoDataFrame(stations, geometry=gpd.points_from_xy(stations.longitude, stations.latitude))
    gdf.set_crs("EPSG:4326", inplace=True)
    return gdf


def weekly_to_hourly(poi_records):
    """
    Expand ``visits_by_each_hour`` (168 values per week) into an hourly series
    summed over all POIs. Timestamps are kept in UTC and returned as strings
    formatted ``YYYY-MM-DD HH:MM:SS``.
    """
    poi_records = poi_records.copy()
    poi_records["date_range_start"] = pd.to_datetime(poi_records["date_range_start"]).dt.tz_convert("UTC")
    poi_records["visits_by_each_hour"] = poi_records["visits_by_each_hour"].apply(json.loads)
    # pad incomplete weeks to 168 hours
    poi_records["visits_by_each_hour"] = poi_records["visits_by_each_hour"].apply(
        lambda x: x + [0] * (168 - len(x)) if len(x) < 168 else x
    )
    weekly_sum = poi_records.groupby("date_range_start")["visits_by_each_hour"].apply(
        lambda x: pd.DataFrame(x.tolist()).sum(axis=0)
    ).reset_index()
    hourly = weekly_sum.explode("visits_by_each_hour")
    hourly["hour"] = hourly.groupby("date_range_start").cumcount()
    hourly["timestamp"] = hourly.apply(
        lambda row: row["date_range_start"] + pd.to_timedelta(row["hour"], unit="h"), axis=1
    )
    hourly["timestamp"] = hourly["timestamp"].dt.strftime("%Y-%m-%d %H:%M:%S")
    hourly = hourly.rename(columns={"visits_by_each_hour": "hourly_visits"})
    return hourly[["timestamp", "hourly_visits"]]
