"""
RefineFlow — Null Handler
Standardizes hidden null values and imputes missing values based on column type.
"""

from typing import Optional, Dict
import pandas as pd
import numpy as np
from refineflow.config import HIDDEN_NULL_VALUES
from refineflow.logger import RefineLogger


class NullHandler:
    """
    Standardizes hidden null values (e.g. 'N/A', '?') and imputes nulls
    using median, mean, mode, or custom strategies.
    """

    def __init__(self, strategy_config: Optional[Dict[str, str]] = None, log: Optional[RefineLogger] = None):
        self.strategy_config = strategy_config or {}
        self.log = log or RefineLogger()
        self.stats = {}

        # Default strategies per datatype
        self.defaults = {
            "numerical": "median",
            "categorical": "mode",
            "datetime": "ffill",
        }

    def normalize_hidden_nulls(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Replaces standard hidden null strings with np.nan case-insensitively.
        """
        df = df.copy()
        null_count_before = df.isnull().sum().sum()

        # Clean string values first, checking for hidden nulls
        for col in df.columns:
            if pd.api.types.is_string_dtype(df[col]) or isinstance(df[col].dtype, pd.CategoricalDtype):
                # Standardize strings case-insensitively
                s = df[col].astype(str).str.strip().str.lower()
                # Find mask of hidden null matching values
                mask = s.isin(HIDDEN_NULL_VALUES)
                if mask.any():
                    # Set those values to NaN
                    df.loc[mask, col] = np.nan

        null_count_after = df.isnull().sum().sum()
        normalized_count = null_count_after - null_count_before
        if normalized_count > 0:
            self.log.info(f"Normalized {normalized_count:,} hidden null values to NaN")

        return df

    def _detect_type(self, col: str, df: pd.DataFrame) -> str:
        """
        Categorizes column as numerical, datetime, or categorical.
        """
        col_series = df[col]
        if pd.api.types.is_numeric_dtype(col_series) and not pd.api.types.is_bool_dtype(col_series):
            return "numerical"
        elif pd.api.types.is_datetime64_any_dtype(col_series):
            return "datetime"
        else:
            return "categorical"

    def run(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Runs the null normalization and imputation process.
        """
        # First normalize hidden nulls
        df = self.normalize_hidden_nulls(df)

        filled_total = 0
        columns_filled = 0

        for col in df.columns:
            nulls_before = int(df[col].isnull().sum())
            if nulls_before == 0:
                continue

            col_type = self._detect_type(col, df)
            strategy = self.strategy_config.get(col, self.defaults[col_type])

            df = self._apply_strategy(df, col, strategy, col_type)
            nulls_after = int(df[col].isnull().sum())
            filled_count = nulls_before - nulls_after

            if filled_count > 0 or strategy == "drop":
                self.stats[col] = {
                    "nulls_before": nulls_before,
                    "nulls_after": nulls_after,
                    "strategy": strategy,
                }
                filled_total += filled_count
                columns_filled += 1

        if filled_total > 0:
            self.log.success(f"Null Handler: Filled {filled_total:,} nulls across {columns_filled} columns")
        elif columns_filled > 0:
            self.log.success(f"Null Handler: Handled nulls in {columns_filled} columns (dropped rows)")

        return df

    def _apply_strategy(self, df: pd.DataFrame, col: str, strategy: str, col_type: str) -> pd.DataFrame:
        """Imputes missing values in the column based on chosen strategy."""
        strategy = strategy.strip().lower()

        if strategy == "drop":
            df.dropna(subset=[col], inplace=True)
            return df

        # Numerical strategies
        if col_type == "numerical":
            if strategy == "median":
                fill_val = df[col].median()
                if pd.isnull(fill_val):
                    fill_val = 0.0
                df[col] = df[col].fillna(fill_val)
            elif strategy == "mean":
                fill_val = df[col].mean()
                if pd.isnull(fill_val):
                    fill_val = 0.0
                df[col] = df[col].fillna(fill_val)
            elif strategy == "interpolation":
                df[col] = df[col].interpolate(method="linear").ffill().bfill().fillna(0.0)
            else:
                # Default fallback
                df[col] = df[col].fillna(0.0)

        # Categorical strategies
        elif col_type == "categorical":
            if strategy == "mode":
                modes = df[col].mode()
                fill_val = modes[0] if not modes.empty else "Unknown"
                df[col] = df[col].fillna(fill_val)
            else:
                # Custom string fill (e.g. 'Unknown' or user override)
                # If strategy isn't a known keyword, treat it as the fill value
                fill_val = "Unknown" if strategy == "unknown" else strategy
                df[col] = df[col].fillna(fill_val)

        # Datetime strategies
        elif col_type == "datetime":
            if strategy == "ffill":
                df[col] = df[col].ffill().bfill()  # handle leading nulls
            elif strategy == "bfill":
                df[col] = df[col].bfill().ffill()
            elif strategy == "interpolation":
                # Convert to numeric for interpolation, then back to datetime
                s_num = pd.to_numeric(df[col], errors="coerce")
                s_num = s_num.interpolate(method="linear").bfill().ffill()
                df[col] = pd.to_datetime(s_num, errors="coerce")
            else:
                # Fallback ffill
                df[col] = df[col].ffill().bfill()

        return df
