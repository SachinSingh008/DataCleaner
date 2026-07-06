"""
RefineFlow — Outlier Detector
Handles statistical outlier detection and domain constraint enforcement.
"""

from typing import Optional, Dict
import pandas as pd
import numpy as np
from refineflow.config import (
    MIN_ROWS_FOR_OUTLIER,
    IQR_MULTIPLIER,
    ZSCORE_THRESHOLD,
    PERCENTILE_LOWER,
    PERCENTILE_UPPER,
    DEFAULT_COLUMN_CONSTRAINTS,
)
from refineflow.logger import RefineLogger


class OutlierDetector:
    """
    Identifies and resolves outliers in numerical columns using domain constraints,
    IQR bounds, Z-Score limits, or Percentile ranges.
    """

    def __init__(
        self,
        method: str = "iqr",
        action: str = "clip",
        custom_constraints: Optional[Dict[str, Dict[str, float]]] = None,
        log: Optional[RefineLogger] = None,
    ):
        self.method = method.strip().lower()
        self.action = action.strip().lower()
        self.constraints = DEFAULT_COLUMN_CONSTRAINTS.copy()
        if custom_constraints:
            self.constraints.update(custom_constraints)
        self.log = log or RefineLogger()
        self.stats = {}

    def _is_numeric_target(self, col: str, df: pd.DataFrame) -> bool:
        """Determines if a column is a valid target for outlier detection."""
        s = df[col]
        # Must be numeric, not boolean
        if not pd.api.types.is_numeric_dtype(s) or pd.api.types.is_bool_dtype(s):
            return False
        # Skip ID columns
        name = col.lower()
        if any(kw in name for kw in ["id", "code", "key", "zip", "postal", "phone", "aadhaar", "pan", "ssn"]):
            return False
        return True

    def run(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Detects and handles outliers in numerical columns.
        """
        if len(df) < MIN_ROWS_FOR_OUTLIER:
            self.log.info(
                f"Outlier Detector: Dataset has {len(df)} rows (< {MIN_ROWS_FOR_OUTLIER}). Skipping outlier detection."
            )
            return df

        df = df.copy()
        outliers_total = 0
        columns_modified = 0
        rows_to_drop = set()

        for col in df.columns:
            if not self._is_numeric_target(col, df):
                continue

            # 1. Apply Hard Business/Domain Constraints first
            df, domain_modified_count = self._apply_domain_constraints(df, col)
            outliers_total += domain_modified_count

            # Recalculate series without NaNs for statistical calculations
            s = df[col].dropna()
            if len(s) < MIN_ROWS_FOR_OUTLIER:
                continue

            # 2. Statistical Outlier Detection
            lower_bound, upper_bound = self._calculate_bounds(s)
            outlier_mask = (df[col] < lower_bound) | (df[col] > upper_bound)
            outlier_count = int(outlier_mask.sum())

            if outlier_count > 0:
                outliers_total += outlier_count
                self.stats[col] = {
                    "outliers_found": outlier_count + domain_modified_count,
                    "action": self.action,
                    "lower_bound": lower_bound,
                    "upper_bound": upper_bound,
                }
                columns_modified += 1

                # 3. Apply Action
                if self.action == "clip":
                    df[col] = df[col].clip(lower_bound, upper_bound)
                elif self.action == "replace_median":
                    col_median = s.median()
                    df.loc[outlier_mask, col] = col_median
                elif self.action == "remove":
                    # Mark indices to drop (dropped after loop to avoid size mismatch)
                    indices = df.index[outlier_mask].tolist()
                    rows_to_drop.update(indices)
                elif self.action == "flag":
                    df[f"{col}_outlier"] = outlier_mask

        if self.action == "remove" and rows_to_drop:
            df.drop(index=list(rows_to_drop), inplace=True)
            self.log.success(f"Outlier Detector: Removed {len(rows_to_drop):,} outlier rows")
        elif outliers_total > 0:
            self.log.success(
                f"Outlier Detector: Handled {outliers_total:,} outliers across {columns_modified} columns (action: {self.action})"
            )
        else:
            self.log.info("Outlier Detector: No statistical or domain outliers detected")

        return df

    def _apply_domain_constraints(self, df: pd.DataFrame, col: str) -> tuple:
        """Enforces physical/logical business constraints (e.g. age between 0 and 120)."""
        modified_count = 0
        col_lower = col.lower()
        
        # Check if there is a constraint matching this column name keywords
        matched_rule = None
        for key, rule in self.constraints.items():
            if key in col_lower:
                matched_rule = rule
                break

        if matched_rule:
            min_val = matched_rule.get("min")
            max_val = matched_rule.get("max")
            
            if min_val is not None:
                under_mask = df[col] < min_val
                under_count = under_mask.sum()
                if under_count > 0:
                    modified_count += under_count
                    # Clip or replace
                    df.loc[under_mask, col] = min_val
            
            if max_val is not None:
                over_mask = df[col] > max_val
                over_count = over_mask.sum()
                if over_count > 0:
                    modified_count += over_count
                    # Clip or replace
                    df.loc[over_mask, col] = max_val

        return df, int(modified_count)

    def _calculate_bounds(self, s: pd.Series) -> tuple:
        """Calculates lower and upper bounds using selected statistical method."""
        if self.method == "iqr":
            q1 = s.quantile(0.25)
            q3 = s.quantile(0.75)
            iqr = q3 - q1
            if iqr == 0:
                return -np.inf, np.inf
            lower = q1 - IQR_MULTIPLIER * iqr
            upper = q3 + IQR_MULTIPLIER * iqr
            return lower, upper

        elif self.method == "zscore":
            mean = s.mean()
            std = s.std()
            if std == 0:
                return -np.inf, np.inf
            lower = mean - ZSCORE_THRESHOLD * std
            upper = mean + ZSCORE_THRESHOLD * std
            return lower, upper

        elif self.method == "percentile":
            lower = np.percentile(s, PERCENTILE_LOWER)
            upper = np.percentile(s, PERCENTILE_UPPER)
            return lower, upper

        else:
            raise ValueError(f"Unknown outlier detection method: {self.method}")
