"""
RefineFlow — Pandas Engine Wrapper
"""

import os
import pandas as pd
from typing import Optional
from refineflow.logger import RefineLogger


class PandasEngine:
    """
    Wrapper for Pandas-based reading and saving of files.
    """

    def __init__(self, log: Optional[RefineLogger] = None):
        self.log = log or RefineLogger()

    def load(self, filepath: str, scan_report: dict) -> pd.DataFrame:
        """
        Loads the dataset into a Pandas DataFrame using report settings (format, encoding).
        """
        fmt = scan_report.get("format", "csv").lower()
        encoding = scan_report.get("encoding", "utf-8")
        self.log.info(f"[Pandas] Loading file '{filepath}' with encoding '{encoding}'")

        if fmt in ("csv", "tsv"):
            sep = "\t" if fmt == "tsv" else ","
            size_gb = scan_report.get("size_gb", 0.0)
            if 1.0 <= size_gb < 10.0:
                self.log.info(f"[Pandas] File size is {size_gb:.2f} GB (>= 1.0 GB). Utilizing chunked loader to optimize memory spikes.")
                chunks = []
                # Use chunksize of 100,000 rows
                for chunk in pd.read_csv(filepath, encoding=encoding, sep=sep, low_memory=False, chunksize=100000):
                    chunks.append(chunk)
                return pd.concat(chunks, ignore_index=True)
            return pd.read_csv(filepath, encoding=encoding, sep=sep, low_memory=False)
        elif fmt == "parquet":
            return pd.read_parquet(filepath)
        elif fmt in ("xlsx", "xls"):
            return pd.read_excel(filepath)
        elif fmt == "json":
            return pd.read_json(filepath)
        else:
            raise ValueError(f"Pandas backend does not support format: {fmt}")

    def save(self, df: pd.DataFrame, filepath: str, format: str) -> None:
        """
        Saves a DataFrame to disk.
        """
        format = format.lower().strip()
        self.log.info(f"[Pandas] Saving dataframe to '{filepath}' as format '{format}'")

        if format == "csv":
            df.to_csv(filepath, index=False, encoding="utf-8-sig")
        elif format == "parquet":
            df.to_parquet(filepath, index=False)
        elif format in ("xlsx", "xls"):
            df.to_excel(filepath, index=False)
        elif format == "json":
            df.to_json(filepath, orient="records", indent=2)
        else:
            raise ValueError(f"Pandas backend does not support saving to format: {format}")
