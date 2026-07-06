"""
RefineFlow — Memory Optimizer
Reduces memory footprint of Pandas DataFrames by downcasting numeric columns and converting objects to categories.
"""

from typing import Optional
import pandas as pd
from refineflow.config import CATEGORY_UNIQUE_RATIO
from refineflow.logger import RefineLogger


class MemoryOptimizer:
    """
    Optimizes memory usage of a DataFrame by downcasting numeric types
    and converting low-cardinality object types to categories.
    """

    def __init__(self, log: Optional[RefineLogger] = None):
        self.log = log or RefineLogger()
        self.stats = {}

    def run(self, df: pd.DataFrame) -> tuple:
        """
        Optimizes the input DataFrame in-place (or returns a copy) and returns (df, stats).
        """
        df = df.copy()
        mem_before = df.memory_usage(deep=True).sum()

        for col in df.columns:
            col_series = df[col]
            dtype_str = str(col_series.dtype)

            # Skip already categorized columns
            if isinstance(col_series.dtype, pd.CategoricalDtype):
                continue

            # 1. Handle Numeric Dtypes
            if pd.api.types.is_numeric_dtype(col_series):
                # Check if it is boolean
                if pd.api.types.is_bool_dtype(col_series):
                    continue

                has_null = col_series.isnull().any()

                # Check if integer or float
                if pd.api.types.is_integer_dtype(col_series) or (not has_null and (col_series % 1 == 0).all()):
                    # Downcast integers
                    if has_null:
                        # Use pandas nullable integer type to support nulls
                        df[col] = pd.to_numeric(col_series, downcast="integer")
                        # Try to use Nullable Ints if possible
                        try:
                            df[col] = df[col].astype("Int32")
                            # Try Int16/Int8
                            c_max = col_series.max()
                            c_min = col_series.min()
                            if c_min >= -128 and c_max <= 127:
                                df[col] = df[col].astype("Int8")
                            elif c_min >= -32768 and c_max <= 32767:
                                df[col] = df[col].astype("Int16")
                        except Exception:
                            pass
                    else:
                        df[col] = pd.to_numeric(col_series, downcast="integer")
                else:
                    # Downcast floats (float64 -> float32)
                    df[col] = pd.to_numeric(col_series, downcast="float")

            # 2. Handle Object / String types
            elif pd.api.types.is_object_dtype(col_series) or pd.api.types.is_string_dtype(col_series):
                # Count unique values
                num_unique = col_series.nunique()
                num_total = len(col_series)

                if num_total > 0:
                    ratio = num_unique / num_total
                    # Convert to Category if unique values < 50% and unique < 1000
                    if ratio < CATEGORY_UNIQUE_RATIO and num_unique < 1000:
                        df[col] = col_series.astype("category")

        mem_after = df.memory_usage(deep=True).sum()
        reduction = mem_before - mem_after
        reduction_pct = (reduction / mem_before * 100.0) if mem_before > 0 else 0.0

        # Human readable sizes
        before_str = self._format_bytes(mem_before)
        after_str = self._format_bytes(mem_after)

        self.stats = {
            "memory_before_bytes": mem_before,
            "memory_after_bytes": mem_after,
            "reduction_percentage": reduction_pct,
        }

        if reduction > 0:
            self.log.success(
                f"Memory Optimizer: Optimized DataFrame size from {before_str} to {after_str} "
                f"({reduction_pct:.1f}% reduction)"
            )
        else:
            self.log.info(f"Memory Optimizer: No memory size reduction achieved (Current: {after_str})")

        return df, self.stats

    def _format_bytes(self, size: int) -> str:
        """Formats bytes into KB, MB, GB, etc."""
        for unit in ["B", "KB", "MB", "GB"]:
            if size < 1024.0:
                return f"{size:.1f} {unit}"
            size /= 1024.0
        return f"{size:.1f} TB"
