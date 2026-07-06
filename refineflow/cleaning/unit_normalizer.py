"""
RefineFlow — Unit Normalizer
Normalizes physical units (weight, time) mixed within text columns to numeric base units.
"""

import re
from typing import Optional, List
import pandas as pd
from refineflow.config import WEIGHT_TO_GRAMS, TIME_TO_SECONDS
from refineflow.logger import RefineLogger


class UnitNormalizer:
    """
    Standardizes and converts text representations of physical quantities (like weights, times)
    into standard numeric base units (grams, seconds).
    """

    def __init__(self, log: Optional[RefineLogger] = None):
        self.log = log or RefineLogger()
        self.stats = {}

    def run(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Scans object/string columns for unit-like structures and normalizes them.
        """
        df = df.copy()
        conversions = 0

        # Compile regexes
        # Matches numbers followed optionally by spaces and a weight/time unit label
        weight_units = "|".join(re.escape(k) for k in WEIGHT_TO_GRAMS.keys())
        time_units = "|".join(re.escape(k) for k in TIME_TO_SECONDS.keys())

        # Regex patterns: e.g. "12.5 kg", "250g", "2.5 lbs"
        # Handles optional "s" suffix (e.g. lbs, secs, hrs)
        weight_pat = re.compile(rf"^\s*([\d.]+)\s*({weight_units})s?\s*$", re.IGNORECASE)
        time_pat = re.compile(rf"^\s*([\d.]+)\s*({time_units})s?\s*$", re.IGNORECASE)

        for col in df.columns:
            if df[col].dtype != object and not pd.api.types.is_string_dtype(df[col]):
                continue

            # Drop NaNs for scanning
            non_null = df[col].dropna().astype(str).str.strip()
            if len(non_null) == 0:
                continue

            # Check if majority of values match either weight pattern or time pattern
            weight_match_rate = non_null.str.match(weight_pat).mean()
            time_match_rate = non_null.str.match(time_pat).mean()

            if weight_match_rate > 0.60:
                self.log.info(f"Unit Normalizer: Normalizing weight column '{col}' to grams")
                df[col] = self._normalize_column(df[col], weight_pat, WEIGHT_TO_GRAMS)
                self.stats[col] = {"type": "weight", "unit": "grams"}
                conversions += 1

            elif time_match_rate > 0.60:
                self.log.info(f"Unit Normalizer: Normalizing time column '{col}' to seconds")
                df[col] = self._normalize_column(df[col], time_pat, TIME_TO_SECONDS)
                self.stats[col] = {"type": "time", "unit": "seconds"}
                conversions += 1

        if conversions > 0:
            self.log.success(f"Unit Normalizer: Normalized units in {conversions} columns")

        return df

    def _normalize_column(self, s: pd.Series, pattern: re.Pattern, conversion_map: dict) -> pd.Series:
        """Converts strings matching the unit pattern to standard floats."""
        def convert_val(val):
            if pd.isnull(val) or str(val).strip().lower() == "nan":
                return None
            val_str = str(val).strip()
            match = pattern.match(val_str)
            if not match:
                # Fallback to try and cast directly to numeric if it's already a number
                try:
                    return float(val_str)
                except ValueError:
                    return None
            
            num = float(match.group(1))
            unit = match.group(2).lower()
            factor = conversion_map.get(unit, 1.0)
            return num * factor

        return s.apply(convert_val).astype(float)
