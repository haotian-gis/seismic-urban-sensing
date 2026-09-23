"""
Environmental and transport data used to validate / explain seismic noise.

    wind_by_station()   NOAA hourly observations -> nearest weather station
                        for each seismic station             -> WIND_CLEAN_CSV
    hourly_flights()    hourly departures + arrivals at DFW airport (OpenSky)
    snow_depth_mean()   mean SNODAS snow depth over the storm period (GeoTIFF)

Run ``python environment.py`` to build the wind table and the snow-depth raster.
"""
import os

import numpy as np
import pandas as pd

import config

AIRPORT = "KDFW"

# SNODAS masked-grid metadata (SNODAS user guide)
SNODAS_NCOLS, SNODAS_NROWS = 6935, 3351
SNODAS_CELL = 0.008333                   # ~1 km
SNODAS_XLL, SNODAS_YLL = -124.7333, 24.9500
SNODAS_NODATA = -9999
SNODAS_SCALE = 1000                      # mm -> m


def to_local(ts):
    """UTC -> local (CST) timestamps."""
    return ts + pd.Timedelta(hours=config.UTC_TO_LOCAL_HOURS)


# =============================================================================
# Wind
# =============================================================================
def nearest_station(points_lonlat, candidates_lonlat, candidate_ids):
    """Id of the nearest candidate (planar distance in degrees) for each point."""
    p = np.asarray(points_lonlat, dtype=float)[:, None, :]
    c = np.asarray(candidates_lonlat, dtype=float)[None, :, :]
    idx = np.sqrt(((p - c) ** 2).sum(axis=2)).argmin(axis=1)
    return np.asarray(candidate_ids)[idx]


def wind_by_station():
    """Hourly-mean NOAA observations, joined to each seismic station's nearest weather station."""
    wind = pd.read_csv(config.WIND_RAW_CSV)
    wind["DATE_hourly"] = pd.to_datetime(wind["DATE"]).dt.round("h")
    wind = wind.groupby(["STATION", "DATE_hourly"]).mean(numeric_only=True).reset_index()

    wx = wind.drop_duplicates(subset=["STATION"])
    seismic = pd.read_csv(config.STATIONS_CSV)
    seismic["nearest_wind_station"] = nearest_station(
        seismic[["longitude", "latitude"]], wx[["LONGITUDE", "LATITUDE"]], wx["STATION"])

    wind = wind[(wind["DATE_hourly"] >= "2021-02-04 00:00:00") & (wind["DATE_hourly"] <= "2021-02-27 23:00:00")]
    out = wind.merge(seismic[["station_id", "nearest_wind_station"]],
                     left_on="STATION", right_on="nearest_wind_station", how="inner")
    out.to_csv(config.WIND_CLEAN_CSV, index=False)
    print(f"Saved {config.WIND_CLEAN_CSV}")
    return out


# =============================================================================
# Flights
# =============================================================================
def hourly_flights(airport=AIRPORT):
    """Hourly departures, arrivals and total flights at ``airport`` in local time (Feb 4-27)."""
    fl = pd.read_csv(config.FLIGHTS_CSV, parse_dates=["firstseen", "lastseen"])
    dep = fl[(fl["origin"] == airport) & (fl["destination"] != airport)]
    arr = fl[(fl["destination"] == airport) & (fl["origin"] != airport)]
    dep = dep.groupby(dep["firstseen"].dt.floor("h")).size().rename("departures")
    arr = arr.groupby(arr["lastseen"].dt.floor("h")).size().rename("arrivals")

    hourly = pd.concat([dep, arr], axis=1).fillna(0).rename_axis("hour").reset_index()
    hourly["total_flights"] = hourly["departures"] + hourly["arrivals"]
    hourly["timestamp"] = pd.to_datetime(to_local(hourly["hour"]).dt.strftime("%Y-%m-%d %H:%M:%S"))  # drop tz
    hourly = hourly[(hourly["timestamp"] >= "2021-02-04 00:00:00") & (hourly["timestamp"] <= "2021-02-27 23:00:00")]
    return hourly[["timestamp", "departures", "arrivals", "total_flights"]].reset_index(drop=True)


# =============================================================================
# Snow depth
# =============================================================================
def snow_depth_mean(input_dir=config.SNODAS_DIR, output_tif=None):
    """Average all SNODAS ``.dat`` snow-depth grids in ``input_dir`` into a GeoTIFF."""
    from osgeo import gdal, osr

    output_tif = output_tif or os.path.join(input_dir, "average.tif")
    total = np.zeros((SNODAS_NROWS, SNODAS_NCOLS), dtype=np.float32)
    n = 0
    for name in sorted(os.listdir(input_dir)):
        if name.endswith(".dat"):
            grid = np.fromfile(os.path.join(input_dir, name), dtype=">i2").reshape(SNODAS_NROWS, SNODAS_NCOLS)
            grid = np.where(grid == SNODAS_NODATA, np.nan, grid) / SNODAS_SCALE
            total = np.nansum([total, grid], axis=0)
            n += 1
    mean = total / n
    mean = np.where(np.isnan(mean), SNODAS_NODATA, mean)

    ds = gdal.GetDriverByName("GTiff").Create(str(output_tif), SNODAS_NCOLS, SNODAS_NROWS, 1, gdal.GDT_Float32)
    ds.SetGeoTransform((SNODAS_XLL, SNODAS_CELL, 0, SNODAS_YLL + SNODAS_NROWS * SNODAS_CELL, 0, -SNODAS_CELL))
    srs = osr.SpatialReference()
    srs.ImportFromEPSG(4326)
    ds.SetProjection(srs.ExportToWkt())
    band = ds.GetRasterBand(1)
    band.WriteArray(mean)
    band.SetNoDataValue(SNODAS_NODATA)
    band.FlushCache()
    ds = None
    print(f"Mean snow depth of {n} grids saved to {output_tif}")


if __name__ == "__main__":
    wind_by_station()
    snow_depth_mean()
