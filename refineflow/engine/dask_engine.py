"""
RefineFlow — Dask Engine Wrapper
"""

import os
import math
from typing import Optional, Generator
import dask.dataframe as dd
import pandas as pd
from refineflow.logger import RefineLogger


class DaskEngine:
    """
    Wrapper for Dask-based reading and partition management.
    """

    def __init__(self, log: Optional[RefineLogger] = None):
        self.log = log or RefineLogger()

    def load(self, filepath: str, scan_report: dict) -> dd.DataFrame:
        """
        Loads the dataset as a Dask DataFrame (lazy).
        """
        fmt = scan_report.get("format", "csv").lower()
        encoding = scan_report.get("encoding", "utf-8")
        size_gb = scan_report.get("size_gb", 0.0)

        # Calculate npartitions
        npartitions = max(4, math.ceil(size_gb / 2.0))
        self.log.info(f"[Dask] Loading file '{filepath}' with encoding '{encoding}', target partitions: {npartitions}")

        if fmt in ("csv", "tsv"):
            sep = "\t" if fmt == "tsv" else ","
            # Dask supports blocksize or sample for CSVs
            # Note: low_memory/low_memory_default can be handled by dask automatically
            # We let Dask choose blocksize but try to align with target partitions if possible
            return dd.read_csv(filepath, encoding=encoding, sep=sep, assume_missing=True, blocksize="16MB")
        elif fmt == "parquet":
            return dd.read_parquet(filepath)
        elif fmt == "json":
            return dd.read_json(filepath)
        else:
            raise ValueError(f"Dask backend does not support format: {fmt}")

    def save(self, df: dd.DataFrame, filepath: str, format: str) -> None:
        """
        Saves a Dask DataFrame to disk.
        """
        format = format.lower().strip()
        self.log.info(f"[Dask] Saving dask dataframe to '{filepath}' as format '{format}'")

        if format == "csv":
            df.to_csv(filepath, single_file=True, index=False, encoding="utf-8-sig")
        elif format == "parquet":
            df.to_parquet(filepath, write_index=False)
        elif format == "json":
            df.to_json(filepath, orient="records")
        else:
            raise ValueError(f"Dask backend does not support saving to format: {format}")

    def to_pandas_chunks(self, df: dd.DataFrame) -> Generator[pd.DataFrame, None, None]:
        """
        Iterates over Dask partitions as regular Pandas DataFrames.
        """
        for i in range(df.npartitions):
            partition = df.get_partition(i).compute()
            yield partition
