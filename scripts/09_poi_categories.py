"""
Step 9 - List unique POIs within 5 km of each station and assign each to a
functional group (Table S1). Output: ``MOBILITY_POIS_CSV``.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import geopandas as gpd
import pandas as pd

import config
from utils.mobility import load_stations, load_study_area_cbgs, load_weekly_patterns
from utils.poi_categories import FUNCTIONAL_GROUPS, categorize

BUFFER_M = 5000


def pois_near_stations(mobility, stations):
    projected = stations.to_crs("EPSG:3857")
    results = []
    for station_id in projected["station_id"]:
        sel = projected[projected["station_id"] == station_id].copy()
        sel["geometry"] = sel.buffer(BUFFER_M)
        sel = sel.to_crs("EPSG:4326")
        pois = gpd.sjoin(mobility, sel, predicate="within")
        results.append(pois.drop_duplicates(subset="placekey"))
    return pd.concat(results, ignore_index=True)


def main():
    cbgs = load_study_area_cbgs()
    mobility = load_weekly_patterns(cbgs["CensusBlockGroup"].tolist())
    pois = pois_near_stations(mobility, load_stations())
    pois["category"] = pois["top_category"].apply(lambda c: categorize(c, FUNCTIONAL_GROUPS, default="Others"))
    pois.to_csv(config.MOBILITY_POIS_CSV, index=False)
    print(f"Saved {config.MOBILITY_POIS_CSV}")
    print("Uncategorised top_category values:")
    print(pois.loc[pois["category"] == "Others", "top_category"].unique())


if __name__ == "__main__":
    main()
