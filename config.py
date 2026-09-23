"""
Central configuration for the seismic-noise / urban-sensing workflow.

All input and output locations are derived from a single data root, which is
read from the environment variable ``SEISMIC_DATA_ROOT`` (default: ``./data``).
Edit the constants below rather than hard-coding paths inside the scripts.
"""
import os
from pathlib import Path

# -----------------------------------------------------------------------------
# Paths
# -----------------------------------------------------------------------------
REPO_ROOT = Path(__file__).resolve().parent
DATA_ROOT = Path(os.environ.get("SEISMIC_DATA_ROOT", REPO_ROOT / "data"))
OUTPUT_DIR = Path(os.environ.get("SEISMIC_OUTPUT_DIR", REPO_ROOT / "outputs"))  # analysis result tables

# Seismic data (IRIS FDSN)
WAVEFORM_DIR = DATA_ROOT / "waveforms"            # raw MiniSEED
STATIONXML_DIR = DATA_ROOT / "stations"           # StationXML (instrument response)
PSD_DIR = DATA_ROOT / "psd"                       # per-window PSD .txt + per-station .feather
DISPLACEMENT_DIR = DATA_ROOT / "displacement"     # displacement power spectra (.feather)

# Derived tables
RMS_2_20_CSV = DATA_ROOT / "RMS_2_20.csv"                     # hourly RMS displacement, 2-20 Hz
RMS_BANDS_CSV = DATA_ROOT / "rms_bands_results.csv"           # hourly RMS displacement, sliding bands
MOBILITY_5KM_CSV = DATA_ROOT / "mobility_data_5km.csv"        # hourly POI visits within 5 km, by category
MOBILITY_BUFFERS_CSV = DATA_ROOT / "mobility_buffers_10km.csv"  # hourly POI visits, 0.5-10 km buffers
MOBILITY_POIS_CSV = DATA_ROOT / "mobility_buffers_pois.csv"   # POIs within 5 km, with category
WIND_RAW_CSV = DATA_ROOT / "wind.csv"                         # NOAA hourly observations (raw)
WIND_CLEAN_CSV = DATA_ROOT / "wind_cleaned.csv"               # wind matched to nearest seismic station
FLIGHTS_CSV = DATA_ROOT / "flightlist_20210201_20210228.csv"  # OpenSky flight list

# Auxiliary inputs
STATIONS_CSV = DATA_ROOT / "stations_for_plot.csv"   # columns: station_id, station, latitude, longitude
CBG_GEOJSON = DATA_ROOT / "gis" / "cbg_2010" / "cbg.geojson"   # 2010 census block groups
DALLAS_BOUNDARY_SHP = DATA_ROOT / "gis" / "Dallas_boundary.shp"
DALLAS_UNION_SHP = DATA_ROOT / "gis" / "dallas_union.shp"
CBG_POPULATION_CSV = DATA_ROOT / "social_result.csv"  # columns: bg2010ge, Weighted Total Population
SNODAS_DIR = DATA_ROOT / "snodas" / "Snowdepth"       # SNODAS snow-depth .dat files

# SafeGraph / Advan weekly patterns stored in a local MongoDB
MONGO_URI = os.environ.get("MONGO_URI", "mongodb://localhost:27017/")
MONGO_DB = "safegraph"
MONGO_COLLECTION = "weekly2021"

# -----------------------------------------------------------------------------
# Study design
# -----------------------------------------------------------------------------
# Download window (UTC) and study area bounding box (Dallas-Fort Worth)
DOWNLOAD_START = (2021, 2, 4)
DOWNLOAD_END = (2021, 2, 28)
BBOX = dict(minlatitude=32.04, maxlatitude=33.45, minlongitude=-98.04, maxlongitude=-95.84)

# Seismic timestamps are UTC; shift to US Central Standard Time for analysis
UTC_TO_LOCAL_HOURS = -6

STUDY_START = "2021-02-04 00:00:00"
STUDY_END = "2021-02-27 00:00:00"
BASELINE = ("2021-02-04 00:00:00", "2021-02-11 00:00:00")
PHASE_1 = ("2021-02-11 00:00:00", "2021-02-14 00:00:00")
PHASE_2 = ("2021-02-14 00:00:00", "2021-02-20 00:00:00")
STORM_DATES = ["2021-02-11", "2021-02-14", "2021-02-20"]  # onset P1, onset P2, end

# PSD parameters
RESAMPLE_HZ = 100
PSD_WINDOW_S = 60 * 30  # 30-min windows, 50 % overlap
PSD_FMIN, PSD_FMAX = 0.01, 40.0
N_JOBS = int(os.environ.get("N_JOBS", 24))

# Human-activity frequency band used throughout the paper
HUMAN_BAND = (2.0, 20.0)

# Sensitivity analysis
BUFFER_RADII_M = list(range(500, 10500, 500))   # 0.5-10 km
DEFAULT_BUFFER_M = 5000
SLIDING_BANDS = [(lo, lo + 2) for lo in range(1, 39)]  # 1-3 Hz ... 38-40 Hz

# Station groups
URBAN_STATIONS = ["TX.FW01.00.HH", "TX.FW04.00.HH", "TX.FW05.00.HH",
                  "TX.FW09.00.HH", "TX.FW15.00.HH", "ZW.IFDF.00.HH"]
RURAL_STATIONS = ["N4.Z35B.00.HH", "TX.FW02.00.HH", "TX.FW06.00.HH", "TX.FW07.00.HH",
                  "TX.FW14.00.HH", "TX.FW16.00.HH", "TX.TREL.00.HH"]


def ensure_dir(path):
    """Create a directory (and parents) if needed and return it as a Path."""
    path = Path(path)
    path.mkdir(parents=True, exist_ok=True)
    return path
