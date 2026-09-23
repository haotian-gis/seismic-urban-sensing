"""
Human-mobility data from SafeGraph / Advan weekly patterns (Framework step 1).

    hourly_visits_by_category()  hourly POI visits within 5 km of each station,
                                 total and per activity group  -> MOBILITY_5KM_CSV
    hourly_visits_by_buffer()    hourly total visits for 0.5-10 km buffers
                                                               -> MOBILITY_BUFFERS_CSV
    poi_composition()            unique POIs within 5 km, with functional group
                                                               -> MOBILITY_POIS_CSV

The weekly-patterns records are read from a local MongoDB
(``config.MONGO_DB`` / ``config.MONGO_COLLECTION``). Run all three with
``python mobility.py``.
"""
import json

import geopandas as gpd
import pandas as pd

import config
from poi_categories import ACTIVITY_GROUPS, FUNCTIONAL_GROUPS, categorize

WEEK_HOURS = 168
DATE_MIN, DATE_MAX = "2021-02-04", "2021-02-28"


# =============================================================================
# Loading
# =============================================================================
def load_study_area_cbgs(boundary_shp=config.DALLAS_UNION_SHP):
    """2010 census block groups intersecting the DFW study boundary."""
    cbgs = gpd.read_file(config.CBG_GEOJSON)
    boundary = gpd.read_file(boundary_shp).to_crs(cbgs.crs)
    return gpd.overlay(cbgs, boundary, how="intersection")


def load_weekly_patterns(cbg_ids=None, month_prefix="2021-02"):
    """Weekly-patterns records (Feb 2021) for POIs in the study area, as points."""
    from pymongo import MongoClient

    if cbg_ids is None:
        cbg_ids = load_study_area_cbgs()["CensusBlockGroup"].tolist()
    weekly = MongoClient(config.MONGO_URI)[config.MONGO_DB][config.MONGO_COLLECTION]
    query = {"date_range_start": {"$regex": f"^({month_prefix})"}, "poi_cbg": {"$in": list(cbg_ids)}}
    df = pd.DataFrame(list(weekly.find(query)))
    return gpd.GeoDataFrame(df, geometry=gpd.points_from_xy(df.longitude, df.latitude), crs="EPSG:4326")


def load_stations():
    """Seismic stations (``station_id, station, latitude, longitude``) as points."""
    st = pd.read_csv(config.STATIONS_CSV)
    return gpd.GeoDataFrame(st, geometry=gpd.points_from_xy(st.longitude, st.latitude), crs="EPSG:4326")


def station_buffer(stations, station_id, radius_m):
    """Circular buffer (EPSG:4326) of ``radius_m`` around one station."""
    sel = stations[stations["station_id"] == station_id].to_crs("EPSG:3857").copy()
    sel["geometry"] = sel.buffer(radius_m)
    return sel.to_crs("EPSG:4326")


# =============================================================================
# Weekly -> hourly
# =============================================================================
def weekly_to_hourly(pois):
    """
    Sum ``visits_by_each_hour`` (168 values per week) over all POIs and expand
    to an hourly series. Returns ``timestamp`` (UTC, ``YYYY-MM-DD HH:MM:SS``)
    and ``hourly_visits``.
    """
    pois = pois.copy()
    pois["date_range_start"] = pd.to_datetime(pois["date_range_start"]).dt.tz_convert("UTC")
    visits = pois["visits_by_each_hour"].apply(json.loads).apply(
        lambda x: x + [0] * (WEEK_HOURS - len(x)) if len(x) < WEEK_HOURS else x)

    rows = []
    for week_start, v in visits.groupby(pois["date_range_start"]):
        total = pd.DataFrame(v.tolist()).sum(axis=0)
        ts = week_start + pd.to_timedelta(range(len(total)), unit="h")
        rows.append(pd.DataFrame({"timestamp": ts.strftime("%Y-%m-%d %H:%M:%S"),
                                  "hourly_visits": total.values}))
    return pd.concat(rows, ignore_index=True)


def visits_in_buffer(mobility, buffer_gdf):
    """Hourly visits (Feb 4-27) summed over POIs falling inside ``buffer_gdf``."""
    pois = gpd.sjoin(mobility, buffer_gdf, predicate="within")
    pois = pois[pois["visits_by_each_hour"].notna()]
    if pois.empty:
        return None
    hourly = weekly_to_hourly(pois)
    return hourly[(hourly["timestamp"] >= DATE_MIN) & (hourly["timestamp"] < DATE_MAX)].reset_index(drop=True)


# =============================================================================
# Outputs
# =============================================================================
def hourly_visits_by_category(mobility=None, radius_m=config.DEFAULT_BUFFER_M):
    """Total and per-activity-group hourly visits around each station."""
    mobility = load_weekly_patterns() if mobility is None else mobility
    mobility = mobility.assign(category=mobility["top_category"].apply(
        lambda c: categorize(c, ACTIVITY_GROUPS, default="others")))
    stations = load_stations()

    groups = {"all_visits": mobility}
    groups.update({f"{g.lower()}_visits": mobility[mobility["category"] == g] for g in ACTIVITY_GROUPS})

    tables = []
    for station_id in stations["station_id"]:
        buf = station_buffer(stations, station_id, radius_m)
        total = visits_in_buffer(groups["all_visits"], buf)
        if total is None:
            continue
        table = total.rename(columns={"hourly_visits": "all_visits"}).assign(station=station_id)
        for col, subset in list(groups.items())[1:]:
            part = visits_in_buffer(subset, buf)
            if part is not None:
                table = table.merge(part.rename(columns={"hourly_visits": col}), on="timestamp", how="left")
            else:
                table[col] = pd.NA
        tables.append(table)

    out = pd.concat(tables, ignore_index=True)
    out.to_csv(config.MOBILITY_5KM_CSV, index=False)
    print(f"Saved {config.MOBILITY_5KM_CSV}")
    return out


def hourly_visits_by_buffer(mobility=None, radii_m=config.BUFFER_RADII_M):
    """Hourly total visits for each buffer radius; columns ``buffer_<radius_m>``."""
    mobility = load_weekly_patterns() if mobility is None else mobility
    stations = load_stations()
    hours = pd.date_range(f"{DATE_MIN} 00:00:00", "2021-02-27 23:00:00", freq="h")

    tables = []
    for station_id in stations["station_id"]:
        table = pd.DataFrame({"station": station_id, "timestamp": hours.strftime("%Y-%m-%d %H:%M:%S")})
        for r in radii_m:
            v = visits_in_buffer(mobility, station_buffer(stations, station_id, r))
            table[f"buffer_{r}"] = None if v is None else v["hourly_visits"]
        tables.append(table)
        print(f"Buffers done: {station_id}")

    out = pd.concat(tables, ignore_index=True)
    out.to_csv(config.MOBILITY_BUFFERS_CSV, index=False)
    print(f"Saved {config.MOBILITY_BUFFERS_CSV}")
    return out


def poi_composition(mobility=None, radius_m=config.DEFAULT_BUFFER_M):
    """Unique POIs within ``radius_m`` of each station with their functional group."""
    mobility = load_weekly_patterns() if mobility is None else mobility
    stations = load_stations()
    parts = []
    for station_id in stations["station_id"]:
        pois = gpd.sjoin(mobility, station_buffer(stations, station_id, radius_m), predicate="within")
        parts.append(pois.drop_duplicates(subset="placekey"))
    pois = pd.concat(parts, ignore_index=True)
    pois["category"] = pois["top_category"].apply(lambda c: categorize(c, FUNCTIONAL_GROUPS, default="Others"))
    pois.to_csv(config.MOBILITY_POIS_CSV, index=False)
    print(f"Saved {config.MOBILITY_POIS_CSV}")
    print("Uncategorised top_category values:", pois.loc[pois["category"] == "Others", "top_category"].unique())
    return pois


if __name__ == "__main__":
    patterns = load_weekly_patterns()
    hourly_visits_by_category(patterns)
    hourly_visits_by_buffer(patterns)
    poi_composition(patterns)
