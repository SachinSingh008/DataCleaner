"""
RefineFlow — Unified Engine Loader
Loads datasets using selected engine backend and normalizes to a Pandas DataFrame.
"""

from typing import Optional
import pandas as pd
from refineflow.logger import RefineLogger
from refineflow.engine.pandas_engine import PandasEngine
from refineflow.engine.polars_engine import PolarsEngine
from refineflow.engine.dask_engine import DaskEngine
from refineflow.engine.spark_engine import SparkEngine, _SPARK_AVAILABLE


def load_as_pandas(filepath: str, engine_name: str, scan_report: dict, log: Optional[RefineLogger] = None) -> pd.DataFrame:
    """
    Loads data using the specified engine backend, converts it to a Pandas DataFrame, and returns it.
    """
    log = log or RefineLogger()
    engine_name = engine_name.strip().lower()

    if engine_name == "pandas":
        engine = PandasEngine(log=log)
        return engine.load(filepath, scan_report)

    elif engine_name == "polars":
        engine = PolarsEngine(log=log)
        pl_df = engine.load(filepath, scan_report)
        log.info("Converting Polars DataFrame to Pandas DataFrame")
        return pl_df.to_pandas()

    elif engine_name == "dask":
        engine = DaskEngine(log=log)
        dd_df = engine.load(filepath, scan_report)
        log.info("Computing Dask DataFrame to Pandas DataFrame")
        return dd_df.compute()

    elif engine_name == "spark":
        if not _SPARK_AVAILABLE:
            log.warning("Spark not installed, falling back to Polars for conversion")
            return load_as_pandas(filepath, "polars", scan_report, log=log)
        engine = SparkEngine(log=log)
        spark_df = engine.load(filepath, scan_report)
        return engine.to_pandas(spark_df)

    else:
        raise ValueError(f"Unknown engine name: {engine_name}")
