"""
Step 10 - Average SNODAS daily snow-depth grids over the storm period and
write a GeoTIFF (background of Fig. 2).
"""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import numpy as np
from osgeo import gdal, osr

import config

# SNODAS masked-grid metadata (see SNODAS user guide)
NCOLS, NROWS = 6935, 3351
CELL_SIZE = 0.008333          # ~1 km
XLLCORNER, YLLCORNER = -124.7333, 24.9500
NODATA = -9999
SCALE_FACTOR = 1000           # stored in mm -> m


def main():
    input_dir = config.SNODAS_DIR
    output_tif = input_dir / "average.tif"

    cumulative = np.zeros((NROWS, NCOLS), dtype=np.float32)
    n_files = 0
    for name in sorted(os.listdir(input_dir)):
        if not name.endswith(".dat"):
            continue
        print(f"Processing {name}...")
        data = np.fromfile(input_dir / name, dtype=">i2").reshape(NROWS, NCOLS)  # big-endian int16
        data = np.where(data == NODATA, np.nan, data) / SCALE_FACTOR
        cumulative = np.nansum([cumulative, data], axis=0)
        n_files += 1

    average = cumulative / n_files
    average = np.where(np.isnan(average), NODATA, average)

    ds = gdal.GetDriverByName("GTiff").Create(str(output_tif), NCOLS, NROWS, 1, gdal.GDT_Float32)
    ds.SetGeoTransform((XLLCORNER, CELL_SIZE, 0, YLLCORNER + NROWS * CELL_SIZE, 0, -CELL_SIZE))
    srs = osr.SpatialReference()
    srs.ImportFromEPSG(4326)
    ds.SetProjection(srs.ExportToWkt())
    band = ds.GetRasterBand(1)
    band.WriteArray(average)
    band.SetNoDataValue(NODATA)
    band.FlushCache()
    ds = None
    print(f"Average snow depth saved to {output_tif}")


if __name__ == "__main__":
    main()
