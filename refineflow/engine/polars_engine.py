"""
RefineFlow — Polars Engine Wrapper
"""

import os
from typing import Optional
import polars as pl
from refineflow.logger import RefineLogger


class PolarsEngine:
    """
    Wrapper for Polars-based lazy scanning and loading.
    """

    def __init__(self, log: Optional[RefineLogger] = None):
        self.log = log or RefineLogger()

    def load(self, filepath: str, scan_report: dict) -> pl.DataFrame:
        """
        Loads the dataset into a Polars DataFrame (using scan/lazy and collecting).
        """
        fmt = scan_report.get("format", "csv").lower()
        encoding = scan_report.get("encoding", "utf-8")
        self.log.info(f"[Polars] Scanning file '{filepath}' with encoding '{encoding}'")

        if fmt in ("csv", "tsv"):
            sep = "\t" if fmt == "tsv" else ","
            # Polars csv scanner uses utf-8/lossy by default, chardet encoding is converted or default
            # Polars scan_csv is lazy, then collect
            lf = pl.scan_csv(filepath, separator=sep, ignore_errors=True)
            return lf.collect()
        elif fmt == "parquet":
            return pl.read_parquet(filepath)
        elif fmt == "json":
            return pl.read_json(filepath)
        else:
            raise ValueError(f"Polars backend does not support format: {fmt}")

    def save(self, df: pl.DataFrame, filepath: str, format: str) -> None:
        """
        Saves a Polars DataFrame to disk.
        """
        format = format.lower().strip()
        self.log.info(f"[Polars] Saving polars dataframe to '{filepath}' as format '{format}'")

        if format == "csv":
            df.write_csv(filepath)
        elif format == "parquet":
            df.write_parquet(filepath)
        elif format == "json":
            df.write_json(filepath, row_oriented=True)
        else:
            raise ValueError(f"Polars backend does not support saving to format: {format}")
