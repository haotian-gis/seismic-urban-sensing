"""Shared plotting helpers (weekend shading, storm markers, time handling)."""
from datetime import timedelta

import matplotlib.dates as mdates
import pandas as pd
from matplotlib.patches import Rectangle

import config

STORM_LINE_STYLES = [
    ("2021-02-11", "#6A3D9A", "Start of Winter Storm Uri Phase 1"),
    ("2021-02-14", "#E41A1C", "Start of Winter Storm Uri Phase 2"),
    ("2021-02-20", "#4DAF4A", "End of Winter Storm Uri"),
]


def to_local(ts):
    """Shift UTC timestamps to local (CST) time."""
    return ts + pd.Timedelta(hours=config.UTC_TO_LOCAL_HOURS)


def shade_weekends(ax, start, end, y_min, y_max, color="#D9D9D9", alpha=0.3, label="Weekend"):
    """Draw a shaded rectangle over every Saturday/Sunday between start and end."""
    first = True
    for day in pd.date_range(start=start, end=end):
        if day.weekday() in (5, 6):
            ax.add_patch(Rectangle((mdates.date2num(day), y_min), 1, y_max - y_min,
                                   color=color, alpha=alpha, label=label if first else ""))
            first = False


def shade_weekends_span(ax, start, end, color="cyan", alpha=0.2, label="Weekend"):
    """Same as :func:`shade_weekends` but using ``axvspan`` (full axis height)."""
    first = True
    for day in pd.date_range(start=start, end=end, freq="D"):
        if day.weekday() in (5, 6):
            ax.axvspan(day, day + timedelta(days=1), color=color, alpha=alpha,
                       label=label if first else "")
            first = False


def add_storm_lines(ax, linewidth=2, alpha=0.8):
    """Vertical dashed lines marking the phases of Winter Storm Uri."""
    for date, color, label in STORM_LINE_STYLES:
        ax.axvline(pd.to_datetime(date), color=color, linestyle="--",
                   linewidth=linewidth, alpha=alpha, label=label)


def format_daily_axis(ax, x_min, x_max):
    ax.set_xlim(x_min, x_max)
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m-%d"))
    ax.xaxis.set_major_locator(mdates.DayLocator())
    for label in ax.get_xticklabels():
        label.set_rotation(45)
        label.set_ha("right")
