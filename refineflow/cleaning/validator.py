"""
RefineFlow — Per-Chunk Semantic Validator
Validates data against patterns and business rules, setting semantic anomalies to NaN.
"""

import re
from typing import Optional, Dict
import pandas as pd
import numpy as np
from refineflow.logger import RefineLogger

COLUMN_RULES = {
    "age": {"type": "numeric", "min": 0, "max": 120},
    "email": {"pattern": r'^[\w.\-+]+@[\w.\-]+\.\w+$'},
    "name": {"no_digits_ratio": 0.8},   # Name must have at least 80% non-digit characters
    "salary": {"type": "numeric", "min": 0},
    "revenue": {"type": "numeric", "min": 0},
    "phone": {"pattern": r'^[+\d\s\-()]+$'}, # Standard phone characters only
}


class PerChunkValidator:
    """
    Validates per-chunk data based on column semantics and patterns.
    Replaces values violating rules with NaN to allow downstream imputation.
    """

    def __init__(self, rules: Optional[Dict[str, dict]] = None, log: Optional[RefineLogger] = None):
        self.rules = COLUMN_RULES.copy()
        if rules:
            self.rules.update(rules)
        self.log = log or RefineLogger()
        self.stats = {}

    def run(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Validates columns according to semantic rules.
        """
        df = df.copy()
        total_anomalies = 0

        for col in df.columns:
            col_lower = col.lower()
            matched_rule = None
            
            # Match rule based on token boundary matching
            for key, rule in self.rules.items():
                pattern = rf"(?:^|_){re.escape(key)}(?:_|$)"
                if re.search(pattern, col_lower):
                    matched_rule = rule
                    break

            if not matched_rule:
                continue

            anomalies_count = 0
            series_len = len(df[col])

            # Apply pattern rules (regex)
            if "pattern" in matched_rule:
                pattern = re.compile(matched_rule["pattern"])
                # Only check non-nulls
                mask = df[col].notnull()
                if mask.any():
                    # Apply pattern check
                    valid_mask = df.loc[mask, col].astype(str).str.match(pattern)
                    # Get invalid indices
                    invalid_mask = ~valid_mask
                    invalid_indices = df.loc[mask].index[invalid_mask]
                    if len(invalid_indices) > 0:
                        df.loc[invalid_indices, col] = np.nan
                        anomalies_count += len(invalid_indices)

            # Apply name/text digit ratio rule
            elif "no_digits_ratio" in matched_rule:
                ratio_threshold = matched_rule["no_digits_ratio"]
                mask = df[col].notnull()
                if mask.any():
                    def check_ratio(val):
                        val_str = str(val)
                        if not val_str:
                            return True
                        digits = sum(c.isdigit() for c in val_str)
                        non_digits = len(val_str) - digits
                        return (non_digits / len(val_str)) >= ratio_threshold

                    valid_mask = df.loc[mask, col].apply(check_ratio)
                    invalid_indices = df.loc[mask].index[~valid_mask]
                    if len(invalid_indices) > 0:
                        df.loc[invalid_indices, col] = np.nan
                        anomalies_count += len(invalid_indices)

            # Apply numeric constraints
            elif matched_rule.get("type") == "numeric":
                # Ensure it's numeric before applying bounds checks
                if pd.api.types.is_numeric_dtype(df[col]):
                    min_val = matched_rule.get("min")
                    max_val = matched_rule.get("max")
                    
                    if min_val is not None:
                        invalid_mask = df[col] < min_val
                        invalid_indices = df.index[invalid_mask]
                        if len(invalid_indices) > 0:
                            df.loc[invalid_indices, col] = np.nan
                            anomalies_count += len(invalid_indices)
                            
                    if max_val is not None:
                        invalid_mask = df[col] > max_val
                        invalid_indices = df.index[invalid_mask]
                        if len(invalid_indices) > 0:
                            df.loc[invalid_indices, col] = np.nan
                            anomalies_count += len(invalid_indices)

            if anomalies_count > 0:
                self.stats[col] = {"anomalies_replaced": anomalies_count}
                total_anomalies += anomalies_count
                self.log.info(f"Validator: Set {anomalies_count} invalid semantic values to NaN in '{col}'")

        if total_anomalies > 0:
            self.log.success(f"Validator: Cleaned {total_anomalies} anomalies across chunk columns")

        return df
