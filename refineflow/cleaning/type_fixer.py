"""
RefineFlow — Type Fixer
Auto-detects and standardizes data types (dates, currencies, percentages, booleans, IDs, categories).
"""

import re
from typing import Optional, Dict
import pandas as pd
import numpy as np
from refineflow.config import (
    DATE_FORMATS,
    DATE_PARSE_CONFIDENCE,
    CATEGORY_UNIQUE_RATIO,
    BOOL_TRUE_VALUES,
    BOOL_FALSE_VALUES,
)
from refineflow.logger import RefineLogger


class TypeFixer:
    """
    Standardizes types across columns: fixes currencies, percentages, dates,
    booleans, categorical compression, and preserves ID column types.
    """

    def __init__(self, log: Optional[RefineLogger] = None):
        self.log = log or RefineLogger()
        self.stats = {}

    def _safe_convert(self, col: str, orig_series: pd.Series, converted_series: pd.Series, conversion_type: str) -> Optional[pd.Series]:
        """
        Validates the converted series against the original series.
        Calculates conversion success rate. If below 90% (for non-nulls),
        aborts the conversion, returns None, and logs a warning.
        If >= 90%, returns the converted series and logs warnings for any coerced rows.
        """
        orig_non_null = orig_series.dropna()
        if len(orig_non_null) == 0:
            return converted_series

        orig_indices = orig_non_null.index
        converted_non_null_mask = converted_series.loc[orig_indices].notna()
        failed_indices = orig_indices[~converted_non_null_mask]
        failed_count = len(failed_indices)
        
        success_rate = 1.0 - (failed_count / len(orig_non_null))

        if success_rate < 0.90:
            self.log.warning(
                f"Aborted converting column '{col}' to {conversion_type}. "
                f"Conversion success rate ({success_rate:.1%}) is below 90% threshold. "
                f"Preserving original values."
            )
            return None

        if failed_count > 0:
            for idx in failed_indices[:5]:
                self.log.warning(
                    f"Column '{col}' row {idx}: failed to convert '{orig_non_null.loc[idx]}' to {conversion_type} (coerced to NaN/NaT)."
                )
            if failed_count > 5:
                self.log.warning(f"Column '{col}': ... and {failed_count - 5} more failed conversions coerced to NaN/NaT.")
        
        return converted_series

    def run(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Scans all columns in the DataFrame, detects and fixes their data types.
        """
        df = df.copy()
        conversions = []

        for col in df.columns:
            orig_dtype = str(df[col].dtype)
            
            # 1. ID column check (preserve leading zeros, format to string/object)
            if self._is_id_column(col):
                if not pd.api.types.is_string_dtype(df[col]):
                    # Fill nulls with empty string or keep nan, but cast non-nulls to string
                    df[col] = df[col].astype(str).replace("nan", np.nan)
                    self._record_conversion(col, orig_dtype, "string (ID preservation)")
                    conversions.append(f"{col} (ID)")
                continue

            # Check if column is object/string type for complex cleaning
            if pd.api.types.is_string_dtype(df[col]):
                # Remove leading/trailing space for clean detection
                # Drop nulls from check series to avoid issues
                check_series = df[col].dropna().astype(str).str.strip()
                if len(check_series) == 0:
                    continue

                # 2. Boolean detection
                if self._check_boolean(check_series):
                    converted = self._convert_boolean(df[col])
                    validated = self._safe_convert(col, df[col], converted, "bool")
                    if validated is not None:
                        df[col] = validated
                        self._record_conversion(col, orig_dtype, "bool")
                        conversions.append(f"{col} (bool)")
                        continue

                # 3. Currency / Percentage detection
                is_currency = self._check_currency(check_series)
                is_percentage = self._check_percentage(check_series)

                if is_currency:
                    converted = self._convert_currency(df[col])
                    validated = self._safe_convert(col, df[col], converted, "currency")
                    if validated is not None:
                        df[col] = validated
                        self._record_conversion(col, orig_dtype, "float (currency)")
                        conversions.append(f"{col} (currency)")
                        continue

                if is_percentage:
                    converted = self._convert_percentage(df[col])
                    validated = self._safe_convert(col, df[col], converted, "percentage")
                    if validated is not None:
                        df[col] = validated
                        self._record_conversion(col, orig_dtype, "float (percentage)")
                        conversions.append(f"{col} (percentage)")
                        continue

                # 4. Date/Datetime detection
                parsed_date = self._parse_date_column(df[col])
                if parsed_date is not None:
                    validated = self._safe_convert(col, df[col], parsed_date, "datetime")
                    if validated is not None:
                        df[col] = validated
                        self._record_conversion(col, orig_dtype, "datetime64")
                        conversions.append(f"{col} (datetime)")
                        continue

                # 5. General Numeric detection
                parsed_numeric = self._parse_general_numeric(df[col])
                if parsed_numeric is not None:
                    validated = self._safe_convert(col, df[col], parsed_numeric, "numeric")
                    if validated is not None:
                        df[col] = validated
                        self._record_conversion(col, orig_dtype, str(validated.dtype))
                        conversions.append(f"{col} (numeric)")
                        continue

                # 6. Low cardinality Object -> Category conversion
                if self._should_convert_to_category(df[col]):
                    df[col] = df[col].astype("category")
                    self._record_conversion(col, orig_dtype, "category")
                    conversions.append(f"{col} (category)")

            # Check Unix timestamps mixed in numeric columns
            elif pd.api.types.is_numeric_dtype(df[col]):
                # If values are unix timestamps (average value > 1e9)
                non_null_s = df[col].dropna()
                if len(non_null_s) > 0 and non_null_s.mean() > 1e9:
                    df[col] = pd.to_datetime(df[col], unit="s", errors="coerce")
                    self._record_conversion(col, orig_dtype, "datetime64 (Unix Timestamp)")
                    conversions.append(f"{col} (unix_timestamp)")

        if conversions:
            self.log.success(f"Type Fixer: Converted {len(conversions)} columns: {', '.join(conversions)}")
        else:
            self.log.info("Type Fixer: No type conversions needed")

        return df

    def _record_conversion(self, col: str, from_type: str, to_type: str) -> None:
        self.stats[col] = {"from": from_type, "to": to_type}

    def _is_id_column(self, col_name: str) -> bool:
        """Determines if a column is an identifier column by its name."""
        name = col_name.lower().strip()
        suffixes = ("_id", "_code", "_key", "id", "code", "key")
        prefixes = ("id_", "code_", "key_")
        return name.endswith(suffixes) or name.startswith(prefixes) or name == "id"

    def _check_boolean(self, s: pd.Series) -> bool:
        """Checks if a sample of values are predominantly boolean strings."""
        s_lower = s.str.lower()
        union_bools = BOOL_TRUE_VALUES | BOOL_FALSE_VALUES
        match_rate = s_lower.isin(union_bools).mean()
        return match_rate > 0.85

    def _convert_boolean(self, s: pd.Series) -> pd.Series:
        """Standardizes boolean string representations into true boolean type."""
        s_clean = s.astype(str).str.strip().str.lower()
        true_mask = s_clean.isin(BOOL_TRUE_VALUES)
        false_mask = s_clean.isin(BOOL_FALSE_VALUES)
        
        result = pd.Series(np.nan, index=s.index, dtype="boolean")
        result[true_mask] = True
        result[false_mask] = False
        return result

    def _check_currency(self, s: pd.Series) -> bool:
        """Checks if string values look like currency values."""
        # Starts or ends with currency symbols
        pattern = r"^\s*[₹$€£]\s*\d|^\s*\d+.*\s*[₹$€£]\s*$"
        return s.str.match(pattern).mean() > 0.60

    def _convert_currency(self, s: pd.Series) -> pd.Series:
        """Strips currency markers and converts to float."""
        # Strip currency symbols and commas
        cleaned = s.astype(str).str.replace(r"[₹$€£,\s]", "", regex=True)
        return pd.to_numeric(cleaned, errors="coerce")

    def _check_percentage(self, s: pd.Series) -> bool:
        """Checks if string values represent percentages."""
        pattern = r"^\s*[\d.]+\s*%\s*$"
        return s.str.match(pattern).mean() > 0.60

    def _convert_percentage(self, s: pd.Series) -> pd.Series:
        """Strips percentage symbol and normalizes values to scale of 0.0-1.0."""
        cleaned = s.astype(str).str.replace(r"[%\s]", "", regex=True)
        numeric = pd.to_numeric(cleaned, errors="coerce")
        return numeric / 100.0

    def _parse_date_column(self, s: pd.Series) -> Optional[pd.Series]:
        """
        Attempts to parse date strings. Samples first for performance.
        Returns parsed datetime Series if successful, else None.
        """
        non_null = s.dropna()
        if len(non_null) == 0:
            return None

        # Sample for performance if series is large
        sample_size = min(1000, len(non_null))
        sample = non_null.sample(sample_size, random_state=42).astype(str).str.strip()

        # Try pandas to_datetime default with format="mixed" first
        try:
            parsed_sample = pd.to_datetime(sample, format="mixed", errors="coerce")
            if parsed_sample.notna().mean() >= DATE_PARSE_CONFIDENCE:
                # Default parse succeeded on sample, run on whole series
                return pd.to_datetime(s, format="mixed", errors="coerce")
        except Exception:
            pass

        # Try specific formats sequentially
        for fmt in DATE_FORMATS:
            try:
                parsed_sample = pd.to_datetime(sample, format=fmt, errors="coerce")
                if parsed_sample.notna().mean() >= DATE_PARSE_CONFIDENCE:
                    # Apply format to whole series
                    return pd.to_datetime(s, format=fmt, errors="coerce")
            except Exception:
                continue

        return None

    def _parse_general_numeric(self, s: pd.Series) -> Optional[pd.Series]:
        """
        Attempts to convert object column to numeric if > 85% of values can be cast.
        """
        non_null = s.dropna()
        if len(non_null) == 0:
            return None

        sample_size = min(1000, len(non_null))
        sample = non_null.sample(sample_size, random_state=42)

        parsed_sample = pd.to_numeric(sample, errors="coerce")
        if parsed_sample.notna().mean() >= 0.85:
            return pd.to_numeric(s, errors="coerce")

        return None

    def _should_convert_to_category(self, s: pd.Series) -> bool:
        """Determines if column meets cardinality constraints to convert to category."""
        total = len(s)
        if total == 0:
            return False
        unique_cnt = s.nunique()
        ratio = unique_cnt / total
        return ratio < CATEGORY_UNIQUE_RATIO and unique_cnt < 1000
