"""Time helpers for minute-based dispatch models."""

from __future__ import annotations

import re
from datetime import datetime
from typing import Union


def parse_time_to_minutes(value: Union[str, int]) -> int:
    """Parse HH:MM, HHMM, or a datetime-like string into minutes after day start."""
    if isinstance(value, int):
        return value

    text = str(value).strip()
    if not text:
        raise ValueError("empty time value")

    datetime_match = re.search(r"(\d{1,2}):(\d{2})(?::\d{2})?", text)
    if datetime_match:
        hour = int(datetime_match.group(1))
        minute = int(datetime_match.group(2))
        return hour * 60 + minute

    compact_match = re.fullmatch(r"(\d{1,2})(\d{2})", text)
    if compact_match:
        hour = int(compact_match.group(1))
        minute = int(compact_match.group(2))
        return hour * 60 + minute

    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y/%m/%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y/%m/%d %H:%M"):
        try:
            dt = datetime.strptime(text, fmt)
            return dt.hour * 60 + dt.minute
        except ValueError:
            pass

    raise ValueError(f"unsupported time value: {value!r}")


def format_minutes(minutes: int) -> str:
    """Format minute offset as HH:MM, preserving next-day offsets with +Nd."""
    day_offset, minute_of_day = divmod(int(minutes), 24 * 60)
    hour, minute = divmod(minute_of_day, 60)
    suffix = f"+{day_offset}d " if day_offset else ""
    return f"{suffix}{hour:02d}:{minute:02d}"


def normalize_minute(value: Union[str, int]) -> int:
    """Alias used by JSON loaders."""
    return parse_time_to_minutes(value)
