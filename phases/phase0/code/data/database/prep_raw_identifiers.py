"""Create raw-record time and source identifiers."""

from pathlib import Path


def time_to_us(time_utc):
    """Input: UTC datetime
    Output: Unix time in microseconds"""
    return round(time_utc.timestamp() * 1_000_000)


def file_signature(file_path):
    """Input: file path
    Output: size and last-write time"""
    info = Path(file_path).stat()
    return f"{info.st_size}:{info.st_mtime_ns}"
