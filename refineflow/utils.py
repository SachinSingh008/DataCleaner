"""
RefineFlow — Shared Utility Functions
"""

import os
import time
import hashlib
import functools
from pathlib import Path
from typing import Any, Callable, Optional

import pandas as pd


# ── File Utilities ────────────────────────────────────────────────────────────

def bytes_to_gb(size_bytes: int) -> float:
    """Convert bytes to gigabytes, rounded to 2 decimal places."""
    return round(size_bytes / (1024 ** 3), 2)


def bytes_to_mb(size_bytes: int) -> float:
    return round(size_bytes / (1024 ** 2), 2)


def format_number(n: int) -> str:
    """Format large integer with commas: 1200000 → '1,200,000'."""
    return f"{n:,}"


def format_size(size_bytes: int) -> str:
    """Human-readable file size: 1536870912 → '1.43 GB'."""
    if size_bytes >= 1024 ** 3:
        return f"{bytes_to_gb(size_bytes)} GB"
    elif size_bytes >= 1024 ** 2:
        return f"{bytes_to_mb(size_bytes)} MB"
    elif size_bytes >= 1024:
        return f"{round(size_bytes / 1024, 1)} KB"
    return f"{size_bytes} B"


def detect_file_format(filepath: str) -> str:
    """Infer file format from extension."""
    suffix = Path(filepath).suffix.lower().lstrip(".")
    # Handle double extensions like .csv.gz
    if suffix in ("gz", "zip", "bz2"):
        inner = Path(Path(filepath).stem).suffix.lower().lstrip(".")
        return inner if inner else suffix
    return suffix


def file_fingerprint(path: str) -> str:
    """Compute MD5 hash of file contents for deduplication."""
    h = hashlib.md5()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def ensure_dir(path: str) -> None:
    """Create directory (and parents) if it doesn't exist."""
    Path(path).mkdir(parents=True, exist_ok=True)


def file_size_gb(path: str) -> float:
    """Return file size in GB."""
    return bytes_to_gb(os.path.getsize(path))


# ── DataFrame Utilities ───────────────────────────────────────────────────────

def safe_sample(df: pd.DataFrame, n: int = 1000) -> pd.DataFrame:
    """
    Sample up to N rows safely (no error if df has fewer rows).
    Uses fixed random_state for reproducibility.
    """
    if len(df) <= n:
        return df.copy()
    return df.sample(n=n, random_state=42).reset_index(drop=True)


def count_csv_rows(filepath: str, encoding: str = "utf-8") -> int:
    """
    Fast row count for CSV without loading into memory.
    Counts newlines in file — subtract 1 for header.
    """
    try:
        with open(filepath, "rb") as f:
            row_count = sum(1 for _ in f)
        return max(0, row_count - 1)   # exclude header
    except Exception:
        return -1   # unknown


def memory_usage_mb(df: pd.DataFrame) -> float:
    """Return DataFrame memory usage in MB (deep=True for object cols)."""
    return round(df.memory_usage(deep=True).sum() / (1024 ** 2), 2)


def memory_usage_gb(df: pd.DataFrame) -> float:
    return round(df.memory_usage(deep=True).sum() / (1024 ** 3), 3)


def column_null_ratio(df: pd.DataFrame, col: str) -> float:
    """Return fraction of null values in a column."""
    return df[col].isnull().mean()


def flatten(nested: list) -> list:
    """Flatten one level of nested list: [[1,2],[3,4]] → [1,2,3,4]."""
    return [item for sublist in nested for item in
            (sublist if isinstance(sublist, list) else [sublist])]


# ── String Utilities ──────────────────────────────────────────────────────────

def normalize_column_name(name: str) -> str:
    """
    Sanitize column name for BI tools and Python usage.
    'Customer Name ($)' → 'customer_name'
    """
    import re
    name = str(name).strip().lower()
    name = re.sub(r"[^a-z0-9_]", "_", name)   # replace non-alphanumeric
    name = re.sub(r"_+", "_", name)            # collapse multiple underscores
    name = name.strip("_")                     # remove leading/trailing
    return name[:64] if name else "col"        # max 64 chars for Power BI


def deduplicate_column_names(columns: list[str]) -> list[str]:
    """
    Append suffix to duplicate column names:
    ['sales', 'sales', 'sales'] → ['sales', 'sales_1', 'sales_2']
    """
    seen: dict[str, int] = {}
    result = []
    for col in columns:
        if col in seen:
            seen[col] += 1
            result.append(f"{col}_{seen[col]}")
        else:
            seen[col] = 0
            result.append(col)
    return result


# ── Timing Utilities ──────────────────────────────────────────────────────────

def timer(func: Callable) -> Callable:
    """Decorator that logs execution time of a function."""
    @functools.wraps(func)
    def wrapper(*args, **kwargs) -> Any:
        start = time.perf_counter()
        result = func(*args, **kwargs)
        elapsed = round(time.perf_counter() - start, 2)
        print(f"[→] {func.__name__} completed in {elapsed}s")
        return result
    return wrapper


class StopWatch:
    """Simple stopwatch for timing pipeline steps."""
    def __init__(self):
        self._start = time.perf_counter()
        self._splits: dict[str, float] = {}

    def split(self, label: str) -> float:
        elapsed = round(time.perf_counter() - self._start, 2)
        self._splits[label] = elapsed
        return elapsed

    def total(self) -> float:
        return round(time.perf_counter() - self._start, 2)

    def report(self) -> dict:
        return {**self._splits, "total": self.total()}


# ── Compression Utilities ─────────────────────────────────────────────────────

def open_file(path: str, encoding: str = "utf-8"):
    """
    Open a plain or compressed file transparently.
    Supports: .gz, .zip, .bz2
    """
    import gzip, bz2, zipfile

    if path.endswith(".gz"):
        return gzip.open(path, "rt", encoding=encoding)
    elif path.endswith(".bz2"):
        return bz2.open(path, "rt", encoding=encoding)
    elif path.endswith(".zip"):
        zf = zipfile.ZipFile(path)
        name = zf.namelist()[0]
        return zf.open(name)
    return open(path, "r", encoding=encoding)


# ── Misc ──────────────────────────────────────────────────────────────────────

def clamp(value: float, lo: float, hi: float) -> float:
    """Clamp value between lo and hi."""
    return max(lo, min(hi, value))


def safe_divide(a: float, b: float, default: float = 0.0) -> float:
    """Division that returns default instead of ZeroDivisionError."""
    return a / b if b != 0 else default
