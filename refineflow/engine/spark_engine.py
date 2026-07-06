from __future__ import annotations

import os
from typing import Optional, Any
import pandas as pd
from refineflow.logger import RefineLogger

try:
    from pyspark.sql import SparkSession
    _SPARK_AVAILABLE = True
except ImportError:
    _SPARK_AVAILABLE = False


class SparkEngine:
    """
    Wrapper for Spark-based large-scale reading and saving.
    """

    def __init__(self, log: Optional[RefineLogger] = None):
        self.log = log or RefineLogger()
        self.spark: Optional[SparkSession] = None

    def _init_spark(self) -> SparkSession:
        if not _SPARK_AVAILABLE:
            raise ImportError(
                "pyspark is not installed. Install with 'pip install pyspark' to use the Spark backend."
            )
        if self.spark is None:
            self.log.info("Initializing SparkSession...")
            self.spark = (
                SparkSession.builder.appName("RefineFlow")
                .config("spark.driver.memory", "4g")
                .config("spark.sql.execution.arrow.pyspark.enabled", "true")
                .getOrCreate()
            )
        return self.spark

    def load(self, filepath: str, scan_report: dict) -> any:
        """
        Loads the dataset into a Spark DataFrame.
        """
        spark = self._init_spark()
        fmt = scan_report.get("format", "csv").lower()
        self.log.info(f"[Spark] Loading file '{filepath}' as format '{fmt}'")

        if fmt in ("csv", "tsv"):
            sep = "\t" if fmt == "tsv" else ","
            return spark.read.options(header=True, inferSchema=True, sep=sep).csv(filepath)
        elif fmt == "parquet":
            return spark.read.parquet(filepath)
        elif fmt == "json":
            return spark.read.json(filepath)
        else:
            raise ValueError(f"Spark backend does not support format: {fmt}")

    def save(self, df: any, filepath: str, format: str) -> None:
        """
        Saves a Spark DataFrame to disk.
        """
        format = format.lower().strip()
        self.log.info(f"[Spark] Saving spark dataframe to '{filepath}' as format '{format}'")

        if format == "csv":
            df.write.mode("overwrite").option("header", True).csv(filepath)
        elif format == "parquet":
            df.write.mode("overwrite").parquet(filepath)
        elif format == "json":
            df.write.mode("overwrite").json(filepath)
        else:
            raise ValueError(f"Spark backend does not support saving to format: {format}")

    def to_pandas(self, df: any) -> pd.DataFrame:
        """
        Converts a Spark DataFrame to a Pandas DataFrame.
        """
        self._init_spark()
        self.log.info("Converting Spark DataFrame to Pandas DataFrame...")
        # Use arrow optimization if configured, fallback to standard if not
        return df.toPandas()
