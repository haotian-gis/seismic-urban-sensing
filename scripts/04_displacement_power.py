"""
Step 4 - Convert velocity PSD (dB) to displacement power spectra:
P_disp(f) = P_vel(f) / (2*pi*f)^2.
Output: ``DISPLACEMENT_DIR/<station_id>_displacement_power.feather``.
"""
import glob
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import numpy as np
import pandas as pd

import config


def main():
    config.ensure_dir(config.DISPLACEMENT_DIR)
    for file in glob.glob(f"{config.PSD_DIR}/*.feather"):
        df = pd.read_feather(file)
        station_id = df["station_id"].iloc[0]
        freq_cols = [c for c in df.columns if c.startswith("freq_")]
        freqs = np.array([float(c.split("_")[1]) for c in freq_cols])

        psd_linear = 10 ** (df[freq_cols].to_numpy(dtype=float) / 10)
        disp_pow = psd_linear / (2 * np.pi * freqs) ** 2

        out = pd.DataFrame(disp_pow, columns=[f"disp_pow_{f:.4f}" for f in freqs])
        out.insert(0, "end_time", df["end_time"].values)
        out.insert(0, "start_time", df["start_time"].values)
        out.insert(0, "station_id", df["station_id"].values)
        out_file = config.DISPLACEMENT_DIR / f"{station_id}_displacement_power.feather"
        out.to_feather(out_file)
        print(f"Saved displacement power for {station_id} -> {out_file}")


if __name__ == "__main__":
    main()
