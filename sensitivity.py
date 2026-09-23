"""
Sensitivity of the seismic-noise / mobility correlation (Framework step 4).

    buffer_sensitivity()   r(RMS 2-20 Hz, total visits) for buffer radii 0.5-10 km
    peak_buffer()          radius with the highest mean r for urban / rural stations
    band_sensitivity()     r(RMS in sliding bands, visits at the best buffer)

``python sensitivity.py`` writes the tables to ``config.OUTPUT_DIR``.
"""
import pandas as pd
from scipy.stats import pearsonr

import config

# Best-correlated buffer radius per setting, as reported in the paper (Fig. 7a)
BEST_BUFFER = {"Urban": "buffer_4500", "Rural": "buffer_9000"}
BAND_RANGE_HZ = (2, 20)   # bands shown in Fig. 7b: 2-4 Hz ... 18-20 Hz


def _setting(station_id):
    if station_id in config.URBAN_STATIONS:
        return "Urban"
    if station_id in config.RURAL_STATIONS:
        return "Rural"
    return None


def load_buffer_visits():
    return pd.read_csv(config.MOBILITY_BUFFERS_CSV).rename(
        columns={"timestamp": "start_time", "station": "station_id"})


def buffer_sensitivity():
    """Station x buffer-radius table of Pearson r between total visits and 2-20 Hz RMS."""
    data = load_buffer_visits().merge(pd.read_csv(config.RMS_2_20_CSV),
                                      on=["start_time", "station_id"], how="left").fillna(0)
    buffers = sorted([c for c in data.columns if c.startswith("buffer_")], key=lambda c: int(c.split("_")[1]))
    corr = pd.DataFrame({s: {b: pearsonr(g[b], g["drms"])[0] for b in buffers}
                         for s, g in data.groupby("station_id")}).T.rename_axis("station_id")
    corr.insert(0, "setting", corr.index.map(_setting))
    return corr.reset_index()


def peak_buffer(buffer_corr):
    """Radius (km) and r of the peak of the mean curve for each setting."""
    cols = [c for c in buffer_corr.columns if c.startswith("buffer_")]
    mean = buffer_corr.groupby("setting")[cols].mean()
    return pd.DataFrame({"peak_buffer": mean.idxmax(axis=1),
                         "peak_radius_km": mean.idxmax(axis=1).str.split("_").str[1].astype(int) / 1000,
                         "peak_mean_r": mean.max(axis=1)}).reset_index()


def band_sensitivity(best_buffer=BEST_BUFFER):
    """Station x frequency-band table of Pearson r between band RMS and visits at the best buffer."""
    rms = pd.read_csv(config.RMS_BANDS_CSV)
    lo, hi = BAND_RANGE_HZ
    bands = [c for c in rms.columns if c.startswith("band_")
             and int(c.split("_")[1]) >= lo and int(c.split("_")[2]) <= hi]
    visits = load_buffer_visits()[["station_id", "start_time"] + sorted(set(best_buffer.values()))]
    data = visits.merge(rms[["start_time", "station_id"] + bands], on=["start_time", "station_id"],
                        how="left").fillna(0)

    rows = []
    for station, g in data.groupby("station_id"):
        setting = _setting(station)
        if setting is None:
            continue
        buf = best_buffer[setting]
        row = {"station_id": station, "setting": setting, "buffer": buf}
        row.update({b.replace("band_", ""): pearsonr(g[buf], g[b])[0] for b in bands})
        rows.append(row)
    return pd.DataFrame(rows)


def main():
    out = config.ensure_dir(config.OUTPUT_DIR)
    buf = buffer_sensitivity()
    buf.to_csv(out / "sensitivity_buffer.csv", index=False)
    peak = peak_buffer(buf)
    peak.to_csv(out / "sensitivity_buffer_peak.csv", index=False)
    print(peak.to_string(index=False))
    band_sensitivity().to_csv(out / "sensitivity_band.csv", index=False)
    print(f"Sensitivity tables written to {out}")


if __name__ == "__main__":
    main()
