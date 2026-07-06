"""
RefineFlow — Engine Selector
Selects the optimal processing engine based on dataset characteristics.
"""

from typing import Optional
from refineflow.config import (
    SMALL_DATA_THRESHOLD_GB,
    BIG_DATA_THRESHOLD_GB,
    MEDIUM_ROW_THRESHOLD,
)
from refineflow.logger import RefineLogger


class EngineSelector:
    """
    Selects the best processing engine: Pandas, Polars, Dask, or Spark.
    Can be overridden by backend_override.
    """

    def __init__(self, scan_report: dict, backend_override: str = "auto", log: Optional[RefineLogger] = None):
        self.scan_report = scan_report
        self.backend_override = backend_override.strip().lower()
        self.log = log or RefineLogger()

    def select(self) -> str:
        """
        Returns one of: 'Pandas', 'Polars', 'Dask', 'Spark'.
        """
        # If user explicitly requested a backend, respect it
        if self.backend_override != "auto":
            mapping = {
                "pandas": "Pandas",
                "polars": "Polars",
                "dask": "Dask",
                "spark": "Spark"
            }
            if self.backend_override in mapping:
                self.log.info(f"Engine selection overridden by user → {mapping[self.backend_override]}")
                return mapping[self.backend_override]
            else:
                self.log.warning(f"Unknown engine override '{self.backend_override}'. Falling back to auto.")

        # Otherwise, decide based on scan report metrics
        size_gb = self.scan_report.get("size_gb", 0.0)
        rows = self.scan_report.get("rows", 0)

        if size_gb >= BIG_DATA_THRESHOLD_GB:
            recommended = "Spark"
        elif size_gb >= SMALL_DATA_THRESHOLD_GB:
            recommended = "Dask"
        elif rows >= MEDIUM_ROW_THRESHOLD or rows == -1:
            # -1 indicates unknown rows in compressed/large files, default to Polars for safety
            recommended = "Polars"
        else:
            recommended = "Pandas"

        self.log.info(f"Auto-selected engine based on metrics (size={size_gb}GB, rows={rows}) → {recommended}")
        return recommended
