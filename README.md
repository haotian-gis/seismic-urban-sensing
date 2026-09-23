# From Seismic Signals to Urban Sensing

Code for the paper **"From Seismic Signals to Urban Sensing: Leveraging Ambient Seismic Noise to Sense Human Activity Disruptions in Extreme Weather Events."**

Human activity (traffic, movement, industry) produces ground vibrations that seismometers record as high-frequency ambient noise. Using Winter Storm Uri (February 2021) in the Dallas–Fort Worth (DFW) metropolitan area as a case study, this repository shows how noise from 13 seismic stations can track disruptions to urban activity. The noise is quantified as power spectral density (PSD) and RMS displacement in the 2–20 Hz band. It is then validated against mobile-phone mobility (SafeGraph/Advan weekly patterns), flight records, and meteorological observations.

## Repository structure

```
config.py                      # all paths, study periods, station groups, PSD parameters
utils/
  mobility.py                  # SafeGraph loading, weekly → hourly visit expansion
  poi_categories.py            # POI top_category groupings
  plotting.py                  # weekend shading, storm markers, UTC → CST
scripts/                       # processing pipeline (run in order)
  01_download_waveforms.py     # IRIS FDSN mass download (HHZ/BHZ, Feb 4–28 2021)
  02_compute_psd.py            # response removal + Welch PSD, 30-min windows, 50 % overlap
  03_merge_psd.py              # per-station PSD tables (dB) → .feather
  04_displacement_power.py     # velocity PSD → displacement power spectrum
  05_rms_displacement.py       # hourly RMS displacement: 2–20 Hz and sliding 2-Hz bands
  06_mobility_by_category.py   # hourly POI visits within 5 km, by activity group
  07_mobility_buffers.py       # hourly POI visits for 0.5–10 km buffers
  08_wind_nearest_station.py   # NOAA hourly wind matched to nearest seismic station
  09_poi_categories.py         # POI composition around stations (Table S1)
  10_snow_depth.py             # SNODAS mean snow depth during the storm (Fig. 2 background)
figures/                       # paper figures
  fig3_spectrograms.py         # Fig. 3 / S2  spectrograms
  fig4_psd_heatmap.py          # Fig. 4       normalised 2–20 Hz PSD heat map
  fig5_rms_change.py           # Fig. 5       % change, diurnal cycle, spatial pattern
  fig6_timeseries.py           # Fig. 6 / S3  seismic noise vs. visits, flights, wind
  fig7_sensitivity.py          # Fig. 7       buffer-distance and frequency-band sensitivity
  figS1_band_psd.py            # Fig. S1      PSD by frequency band
```

## Setup

```bash
conda create -n seismic python=3.10 -c conda-forge obspy geopandas gdal
conda activate seismic
pip install -r requirements.txt
```

Point the code at your data directory (default `./data`):

```bash
export SEISMIC_DATA_ROOT=/path/to/data
export SEISMIC_FIG_DIR=/path/to/figures   # optional, default ./outputs/figures
export MONGO_URI=mongodb://localhost:27017/   # optional
```

## Data

The raw and derived data are **not** included in this repository. The expected file names are listed in `config.py`.

| Data | Source | Used by |
|---|---|---|
| Continuous waveforms and StationXML (networks TX, N4, ZW) | [IRIS/EarthScope FDSN](https://service.iris.edu/) — downloaded by `scripts/01` | 01–05 |
| Weekly patterns (POI visits) | [SafeGraph / Advan](https://doi.org/10.82551/X1PP-1F65) (licensed; loaded into a local MongoDB `safegraph.weekly2021`) | 06, 07, 09 |
| Hourly surface observations (`windgust`) | NOAA NCEI Local Climatological Data | 08 |
| Flight list (Feb 2021) | OpenSky Network `flightlist_20210201_20210228.csv` | Fig. 6 |
| 2010 census block groups, DFW boundary, block-group population | U.S. Census Bureau | 06, 07, 09, Fig. 5 |
| Daily snow depth | NSIDC SNODAS | 10 |
| `stations_for_plot.csv` (`station_id, station, latitude, longitude`) | derived from StationXML | 06–09, Fig. 5 |

SafeGraph/Advan data cannot be redistributed. Access it through their academic data program.

## Running

```bash
python scripts/01_download_waveforms.py
python scripts/02_compute_psd.py
python scripts/03_merge_psd.py
python scripts/04_displacement_power.py
python scripts/05_rms_displacement.py
python scripts/06_mobility_by_category.py
python scripts/07_mobility_buffers.py
python scripts/08_wind_nearest_station.py
python scripts/09_poi_categories.py
python scripts/10_snow_depth.py

python figures/fig3_spectrograms.py
python figures/fig4_psd_heatmap.py
python figures/fig5_rms_change.py
python figures/fig6_timeseries.py --mobility-station TX.FW04.00.HH
python figures/fig7_sensitivity.py
python figures/figS1_band_psd.py
```

## Key settings

- **Study period:** 2021-02-04 to 2021-02-27 (local time, UTC−6). Baseline: Feb 4–10. Phase 1: Feb 11–13. Phase 2: Feb 14–19.
- **PSD:** 100 Hz resampling, Welch estimate over 30-min windows with 50 % overlap, 0.01–40 Hz.
- **Human-activity band:** 2–20 Hz. RMS displacement is aggregated as the hourly median, in nm.
- **Urban stations:** TX.FW01, FW04, FW05, FW09, FW15, ZW.IFDF. **Rural stations:** N4.Z35B, TX.FW02, FW06, FW07, FW14, FW16, TX.TREL.

## Citation

If you use this code, please cite the paper (citation to be added upon publication).

## License

MIT — see [LICENSE](LICENSE).

## Contact

Hao Tian — Texas A&M University (haotian@tamu.edu)
