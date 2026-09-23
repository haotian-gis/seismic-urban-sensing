"""
Step 7 - Hourly total POI visits around each station for buffer radii
0.5-10 km (step 0.5 km), used in the spatial sensitivity analysis (Fig. 7a).
Output: ``MOBILITY_BUFFERS_CSV`` with columns ``buffer_<radius_m>``.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import geopandas as gpd
import pandas as pd

import config
from utils.mobility import load_stations, load_study_area_cbgs, load_weekly_patterns, weekly_to_hourly

BUFFER_LIST = list(range(500, 10500, 500))


def main():
    cbgs = load_study_area_cbgs()
    mobility = load_weekly_patterns(cbgs["CensusBlockGroup"].tolist())
    stations = load_stations().to_crs("EPSG:3857")
    hours = pd.date_range(start="2021-02-04 00:00:00", end="2021-02-27 23:00:00", freq="h")

    all_mobility = []
    for station in stations["station_id"]:
        out = pd.DataFrame({"station": [station] * len(hours),
                            "timestamp": hours.strftime("%Y-%m-%d %H:%M:%S")})
        for buffer in BUFFER_LIST:
            sel = stations[stations["station_id"] == station].copy()
            sel["geometry"] = sel.buffer(buffer)
            sel = sel.to_crs("EPSG:4326")
            pois = gpd.sjoin(mobility, sel, predicate="within")
            pois = pois[pois["visits_by_each_hour"].notna()]
            col = f"buffer_{buffer}"
            if pois.empty:
                out[col] = None
                continue
            hourly = weekly_to_hourly(pois)
            hourly = hourly[(hourly["timestamp"] >= "2021-02-04") & (hourly["timestamp"] < "2021-02-28")]
            out[col] = hourly["hourly_visits"].reset_index(drop=True)
        all_mobility.append(out)
        print(f"Done {station}")

    pd.concat(all_mobility, ignore_index=True).to_csv(config.MOBILITY_BUFFERS_CSV, index=False)
    print(f"Saved {config.MOBILITY_BUFFERS_CSV}")


if __name__ == "__main__":
    main()
