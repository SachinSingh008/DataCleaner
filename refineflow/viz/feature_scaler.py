"""
RefineFlow — Feature Scaler
Enables numeric column scaling using MinMax, Standard, or Robust methods.
Keeps metadata to support inverse transformations.
"""

import re
from typing import List, Optional, Dict
import pandas as pd
import numpy as np
from refineflow.logger import RefineLogger


class FeatureScaler:
    """
    Applies data normalization and feature scaling (MinMax, Standard, or Robust)
    to numerical columns for BI tools or downstream ML pipelines.
    Exposes an inverse_transform method to recover raw values.
    """

    def __init__(
        self,
        df: pd.DataFrame,
        method: str = "minmax",
        columns: Optional[List[str]] = None,
        suffix: str = "_scaled",
        log: Optional[RefineLogger] = None
    ):
        self.df = df.copy()
        self.method = method.lower()
        self.columns = columns
        self.suffix = suffix
        self.log = log or RefineLogger()

        self.scaler_params: Dict[str, dict] = {}

        if self.method not in ["minmax", "standard", "robust", "none"]:
            raise ValueError(f"Unsupported scaling method: {method}")

    def run(self) -> pd.DataFrame:
        """
        Runs the feature scaling transformation.
        Returns:
            pd.DataFrame: The DataFrame with scaled columns.
        """
        if self.method == "none":
            self.log.info("Feature Scaler: method='none', skipping scaling")
            return self.df

        # Auto-select columns if not provided
        if self.columns is None:
            self.columns = self._auto_select_columns()

        if not self.columns:
            self.log.info("Feature Scaler: No numeric columns identified for scaling")
            return self.df

        self.log.section("Feature Scaler")
        scaled_count = 0

        for col in self.columns:
            if col not in self.df.columns:
                self.log.warning(f"Feature Scaler: Column '{col}' not in DataFrame. Skipping.")
                continue
            if not pd.api.types.is_numeric_dtype(self.df[col]):
                self.log.warning(f"Feature Scaler: Column '{col}' is not numeric. Skipping.")
                continue

            series = self.df[col]
            
            if self.method == "minmax":
                c_min = float(series.min())
                c_max = float(series.max())
                diff = c_max - c_min
                if diff == 0:
                    scaled = series * 0.0
                else:
                    scaled = (series - c_min) / diff
                
                self.scaler_params[col] = {
                    "method": "minmax",
                    "min": c_min,
                    "max": c_max
                }

            elif self.method == "standard":
                c_mean = float(series.mean())
                c_std = float(series.std())
                if pd.isna(c_std) or c_std == 0:
                    scaled = series * 0.0
                else:
                    scaled = (series - c_mean) / c_std

                self.scaler_params[col] = {
                    "method": "standard",
                    "mean": c_mean,
                    "std": c_std if not pd.isna(c_std) else 0.0
                }

            elif self.method == "robust":
                c_med = float(series.median())
                q75 = series.quantile(0.75)
                q25 = series.quantile(0.25)
                iqr = float(q75 - q25)
                if pd.isna(iqr) or iqr == 0:
                    scaled = series * 0.0
                else:
                    scaled = (series - c_med) / iqr

                self.scaler_params[col] = {
                    "method": "robust",
                    "median": c_med,
                    "iqr": iqr if not pd.isna(iqr) else 0.0
                }

            # Handle column renaming/suffixing
            target_col = col
            if self.suffix:
                target_col = f"{col}{self.suffix}"

            self.df[target_col] = scaled.astype(np.float64)
            scaled_count += 1

        self.log.success(
            f"Feature Scaler: Scaled {scaled_count} numerical columns ({self.method.title()} method, suffix='{self.suffix}')"
        )
        return self.df

    def inverse_transform(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Reverses the scaling transformation on the input DataFrame.
        Returns:
            pd.DataFrame: The DataFrame with restored original values.
        """
        res_df = df.copy()

        for col, params in self.scaler_params.items():
            method = params["method"]
            target_col = f"{col}{self.suffix}" if self.suffix else col

            if target_col not in res_df.columns:
                continue

            scaled_series = res_df[target_col]

            if method == "minmax":
                c_min = params["min"]
                c_max = params["max"]
                unscaled = scaled_series * (c_max - c_min) + c_min
            elif method == "standard":
                c_mean = params["mean"]
                c_std = params["std"]
                unscaled = scaled_series * c_std + c_mean
            elif method == "robust":
                c_med = params["median"]
                iqr = params["iqr"]
                unscaled = scaled_series * iqr + c_med
            else:
                unscaled = scaled_series

            # Restore to original column name (and drop scaled suffix column if present)
            res_df[col] = unscaled
            if self.suffix and target_col != col:
                res_df.drop(columns=[target_col], inplace=True)

        self.log.info(f"Feature Scaler: Unscaled {len(self.scaler_params)} columns")
        return res_df

    def _auto_select_columns(self) -> List[str]:
        """Auto-selects appropriate columns for feature scaling."""
        candidates = []
        id_patterns = re.compile(r"(id|_id|key|code|number|phone|zip|postal|email|phone)", re.IGNORECASE)

        for col in self.df.columns:
            col_name_lower = col.lower()
            if pd.api.types.is_numeric_dtype(self.df[col]):
                # Skip booleans (including int series containing only 0 and 1)
                unique_vals = self.df[col].dropna().unique()
                if pd.api.types.is_bool_dtype(self.df[col]) or set(unique_vals).issubset({0, 1, 0.0, 1.0}):
                    continue
                # Skip ID patterns
                if id_patterns.search(col_name_lower):
                    continue
                candidates.append(col)
        return candidates
