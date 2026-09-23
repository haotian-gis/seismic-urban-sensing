"""
Step 3 - Merge per-window PSD text files into one Feather table per station
(PSD converted to dB). Output: ``PSD_DIR/<station_id>.feather``.
"""
import glob
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import numpy as np
import pandas as pd

import config


def main():
    for folder in glob.glob(f"{config.PSD_DIR}/*/"):
        folder_name = os.path.basename(os.path.normpath(folder))
        rows, columns = [], None
        for file in glob.glob(f"{folder}/*.txt"):
            X = np.loadtxt(file)
            station_id, start_time, end_time = os.path.basename(file).replace(".txt", "").split("_")
            if columns is None:
                columns = ["station_id", "start_time", "end_time"] + [f"freq_{f:.4f}" for f in X[0, :]]
            rows.append([station_id, start_time, end_time] + (10 * np.log10(X[1, :])).tolist())
        pd.DataFrame(rows, columns=columns).to_feather(config.PSD_DIR / f"{folder_name}.feather")
        print(f"Merged {folder_name}")


if __name__ == "__main__":
    main()
