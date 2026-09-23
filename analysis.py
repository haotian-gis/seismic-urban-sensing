"""
Human-activity patterns during Winter Storm Uri from seismic noise
(Framework step 3: temporal analysis, spatial analysis, multi-source validation).

Temporal / spatial
    load_rms()                     hourly 2-20 Hz RMS in local time, study period only
    percentage_change()            % change of RMS vs. each station's baseline mean
    network_mean_change()          mean % change across all stations (Fig. 5a)
    diurnal_profiles()             mean RMS by hour of day per phase (Fig. 5b)
    phase_change_by_station()      baseline / Phase 1 / Phase 2 means per station,
                                   with population density (Fig. 5c)

Validation
    build_hourly_dataset()         RMS + POI visits + wind, joined per station-hour
    relative_change()              % change of RMS and visits vs. baseline
    validation_correlations()      Pearson r of RMS change with visits, wind, flights

``python analysis.py`` writes all result tables to ``config.OUTPUT_DIR``.
"""
import geopandas as gpd
import numpy as np
import pandas as pd

import config
from environment import hourly_flights, to_local

VISIT_COLS = ["all_visits", "restaurant_visits", "shopping_visits",
              "healthcare_visits", "education_visits", "manufacturing_visits"]
PHASES = {"Baseline": config.BASELINE, "Phase 1": config.PHASE_1, "Phase 2": config.PHASE_2}


def _between(ts, period):
    return (ts >= period[0]) & (ts < period[1])


# =============================================================================
# Temporal and spatial patterns
# =============================================================================
def load_rms():
    """Hourly RMS displacement (2-20 Hz), converted to local time and clipped to the study period."""
    df = pd.read_csv(config.RMS_2_20_CSV)
    df["start_time"] = to_local(pd.to_datetime(df["start_time"], format="%Y-%m-%d %H:%M:%S", errors="coerce"))
    return df[(df["start_time"] >= config.STUDY_START) & (df["start_time"] < config.STUDY_END)].reset_index(drop=True)


def baseline_mean(df, value="drms", key="station_id"):
    return (df[_between(df["start_time"], config.BASELINE)]
            .groupby(key)[value].mean().rename(f"baseline_{value}").reset_index())


def percentage_change(df):
    """
    Add ``baseline_drms`` and ``percentage_change`` (RMS vs. station baseline, %).

    Values above 200 % are replaced by a centred 5-h rolling mean of ``drms``,
    exactly as done for the published figures.
    """
    df = df.merge(baseline_mean(df), on="station_id", how="left")
    df["percentage_change"] = (df["drms"] - df["baseline_drms"]) / df["baseline_drms"] * 100
    df["percentage_change"] = df["percentage_change"].where(
        df["percentage_change"] <= 200, df["drms"].rolling(window=5, center=True, min_periods=1).mean())
    return df


def network_mean_change(df):
    """Mean % change across stations at each hour."""
    return df.groupby("start_time")["percentage_change"].mean().reset_index()


def diurnal_profiles(df):
    """Mean RMS for each hour of day (0-23) in the baseline and the two storm phases."""
    hour = df["start_time"].dt.hour
    masks = {
        "Baseline": df["start_time"] < config.BASELINE[1],
        "Phase 1": _between(df["start_time"], config.PHASE_1),
        "Phase 2": _between(df["start_time"], config.PHASE_2),
    }
    return pd.DataFrame({name: df[m].groupby(hour[m])["drms"].mean() for name, m in masks.items()}).rename_axis("hour")


def station_population_density():
    """Population density (persons/km²) of the census block group containing each station."""
    cbgs = gpd.read_file(config.CBG_GEOJSON)
    boundary = gpd.read_file(config.DALLAS_BOUNDARY_SHP).to_crs(cbgs.crs)
    area = gpd.overlay(cbgs, boundary, how="intersection")
    pop = pd.read_csv(config.CBG_POPULATION_CSV)
    pop["bg2010ge"] = pop["bg2010ge"].astype(str)
    area = area.merge(pop[["bg2010ge", "Weighted Total Population"]],
                      left_on="CensusBlockGroup", right_on="bg2010ge", how="left").to_crs(epsg=3857)
    area["population_density"] = area["Weighted Total Population"] / (area.geometry.area / 1e6)

    st = pd.read_csv(config.STATIONS_CSV)
    st = gpd.GeoDataFrame(st, geometry=gpd.points_from_xy(st.longitude, st.latitude), crs="EPSG:4326").to_crs(area.crs)
    st = st.sjoin(area[["population_density", "geometry"]], how="left", predicate="intersects")
    return pd.DataFrame(st[["station_id", "population_density"]])


def phase_change_by_station(df, with_population=True):
    """Mean RMS per station in each phase and the % change of each storm phase vs. baseline."""
    out = pd.DataFrame({name: df[_between(df["start_time"], p)].groupby("station_id")["drms"].mean()
                        for name, p in PHASES.items()}).reset_index()
    out["change_phase1_pct"] = (out["Phase 1"] - out["Baseline"]) / out["Baseline"] * 100
    out["change_phase2_pct"] = (out["Phase 2"] - out["Baseline"]) / out["Baseline"] * 100
    out["setting"] = np.where(out["station_id"].isin(config.URBAN_STATIONS), "Urban",
                              np.where(out["station_id"].isin(config.RURAL_STATIONS), "Rural", ""))
    out = out.merge(pd.read_csv(config.STATIONS_CSV), on="station_id", how="left")
    if with_population:
        out = out.merge(station_population_density(), on="station_id", how="left")
    return out


# =============================================================================
# Multi-source validation
# =============================================================================
def build_hourly_dataset():
    """RMS, POI visits (5 km) and wind gusts per station-hour, in local time."""
    rms = pd.read_csv(config.RMS_2_20_CSV).rename(columns={"station_id": "station", "start_time": "timestamp"})
    visits = pd.read_csv(config.MOBILITY_5KM_CSV)
    wind = pd.read_csv(config.WIND_CLEAN_CSV).rename(columns={"station_id": "station", "DATE_hourly": "timestamp"})
    for t in (rms, visits, wind):
        t["timestamp"] = pd.to_datetime(t["timestamp"])

    data = rms.merge(visits, on=["timestamp", "station"], how="inner")
    data = data.merge(wind, on=["timestamp", "station"], how="left")
    data["windgust"] = data["windgust"].fillna(data["windgust"].rolling(24, min_periods=1).mean())
    data["timestamp"] = to_local(data["timestamp"])
    return data[(data["timestamp"] >= config.STUDY_START) & (data["timestamp"] < config.STUDY_END)]


def relative_change(station_df):
    """% change of RMS (``drms_change``) and visits (``<col>_change``) vs. the baseline mean of one station."""
    df = station_df.copy()
    base = df[_between(df["timestamp"], config.BASELINE)]
    for col in VISIT_COLS + ["drms"]:
        df[f"{col}_change"] = (df[col] - base[col].mean()) / base[col].mean() * 100
    return df


def validation_correlations(data=None, flights=None):
    """
    Pearson r between each station's RMS change and
    POI-visit change (total and per group), wind gust and DFW flight counts.
    """
    data = build_hourly_dataset() if data is None else data
    flights = hourly_flights() if flights is None else flights
    rows = []
    for station, g in data.groupby("station"):
        g = relative_change(g).merge(flights[["timestamp", "total_flights"]], on="timestamp", how="left")
        g["total_flights"] = g["total_flights"].fillna(0)
        row = {"station_id": station}
        for col in VISIT_COLS:
            row[f"r_{col}"] = np.corrcoef(g[f"{col}_change"], g["drms_change"])[0, 1]
        row["r_windgust"] = np.corrcoef(g["drms_change"], g["windgust"])[0, 1]
        row["r_flights"] = np.corrcoef(g["total_flights"], g["drms_change"])[0, 1]
        rows.append(row)
    return pd.DataFrame(rows)


def main():
    out = config.ensure_dir(config.OUTPUT_DIR)
    rms = percentage_change(load_rms())
    rms.to_csv(out / "rms_percentage_change.csv", index=False)
    network_mean_change(rms).to_csv(out / "rms_network_mean_change.csv", index=False)
    diurnal_profiles(rms).to_csv(out / "rms_diurnal_profiles.csv")
    phase_change_by_station(rms).to_csv(out / "rms_phase_change_by_station.csv", index=False)

    data = build_hourly_dataset()
    data.to_csv(out / "hourly_dataset.csv", index=False)
    validation_correlations(data).to_csv(out / "validation_correlations.csv", index=False)
    print(f"Analysis tables written to {out}")


if __name__ == "__main__":
    main()
