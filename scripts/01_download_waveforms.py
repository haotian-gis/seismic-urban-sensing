"""
Step 1 - Download continuous vertical-component waveforms and StationXML
for all IRIS stations inside the DFW bounding box (Feb 4-28, 2021).
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import obspy
from obspy.clients.fdsn.mass_downloader import MassDownloader, RectangularDomain, Restrictions

import config

CHUNK_SECONDS = 2 * 3600  # download in 2-hour chunks


def main():
    config.ensure_dir(config.WAVEFORM_DIR)
    config.ensure_dir(config.STATIONXML_DIR)

    domain = RectangularDomain(**config.BBOX)
    restrictions = Restrictions(
        starttime=obspy.UTCDateTime(*config.DOWNLOAD_START),
        endtime=obspy.UTCDateTime(*config.DOWNLOAD_END),
        chunklength_in_sec=CHUNK_SECONDS,
        channel_priorities=["HH[Z]", "BH[Z]"],
        reject_channels_with_gaps=True,
        minimum_length=0.0,
        minimum_interstation_distance_in_m=100.0,
    )
    MassDownloader(providers=["IRIS"]).download(
        domain, restrictions,
        mseed_storage=str(config.WAVEFORM_DIR),
        stationxml_storage=str(config.STATIONXML_DIR),
    )


if __name__ == "__main__":
    main()
