"""
Run the full workflow, or selected stages.

    python run_pipeline.py                       # everything
    python run_pipeline.py --stages rms analysis # selected stages
"""
import argparse

STAGES = ["download", "psd", "rms", "mobility", "environment", "analysis", "sensitivity"]


def run(stage):
    if stage == "download":
        import seismic_processing as sp
        sp.download_waveforms()
    elif stage == "psd":
        import seismic_processing as sp
        sp.compute_psd()
        sp.merge_psd()
    elif stage == "rms":
        import seismic_processing as sp
        sp.compute_displacement()
        sp.compute_rms()
    elif stage == "mobility":
        import mobility
        patterns = mobility.load_weekly_patterns()
        mobility.hourly_visits_by_category(patterns)
        mobility.hourly_visits_by_buffer(patterns)
        mobility.poi_composition(patterns)
    elif stage == "environment":
        import environment
        environment.wind_by_station()
        environment.snow_depth_mean()
    elif stage == "analysis":
        import analysis
        analysis.main()
    elif stage == "sensitivity":
        import sensitivity
        sensitivity.main()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--stages", nargs="+", choices=STAGES, default=STAGES)
    for s in parser.parse_args().stages:
        print(f"=== {s} ===")
        run(s)
