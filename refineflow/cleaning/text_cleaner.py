"""
RefineFlow — Text Cleaner
Applies standard Unicode normalization, whitespace stripping, casing standardization, and address/city adjustments to text columns.
"""

import re
import unicodedata
from typing import Optional, List
import pandas as pd
from difflib import get_close_matches
from refineflow.logger import RefineLogger

KNOWN_CITIES = [
    "Mumbai", "Delhi", "Bangalore", "Chennai", "Kolkata", "Hyderabad", 
    "Pune", "Ahmedabad", "Jaipur", "Surat", "Lucknow", "Kanpur"
]

STATE_MAP = {
    "mh": "Maharashtra",
    "dl": "Delhi",
    "ka": "Karnataka",
    "tn": "Tamil Nadu",
    "wb": "West Bengal",
    "gj": "Gujarat",
    "up": "Uttar Pradesh",
    "ts": "Telangana",
    "ap": "Andhra Pradesh",
    "hr": "Haryana",
    "pb": "Punjab",
    "mp": "Madhya Pradesh",
    "rj": "Rajasthan",
}


class TextCleaner:
    """
    Cleans text columns: normalizes spaces, decodes Unicode garbage, corrects casing,
    and performs address/city standardizations.
    """

    def __init__(self, text_columns: Optional[List[str]] = None, log: Optional[RefineLogger] = None):
        self.text_columns = text_columns
        self.log = log or RefineLogger()
        self.stats = {}

    def _fix_mojibake(self, text: str) -> str:
        if not isinstance(text, str):
            return text
        for enc in ["cp1252", "latin-1"]:
            try:
                b = text.encode(enc)
                decoded = b.decode("utf-8")
                if len(decoded) < len(text):
                    return decoded
            except (UnicodeEncodeError, UnicodeDecodeError):
                continue
        return text

    def run(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Cleans string columns in the DataFrame.
        """
        df = df.copy()
        
        # Identify text columns if not specified
        cols_to_clean = self.text_columns
        if cols_to_clean is None:
            cols_to_clean = [
                c for c in df.columns 
                if pd.api.types.is_string_dtype(df[c]) or isinstance(df[c].dtype, pd.CategoricalDtype)
            ]

        cleaned_cols_count = 0
        total_encoding_fixes = 0

        for col in cols_to_clean:
            # Skip if columns not in df
            if col not in df.columns:
                continue

            orig_series = df[col].astype(str)
            cleaned_series = []
            encoding_fixes = 0
            
            col_lower = col.lower()
            is_name = any(kw in col_lower for kw in ["name", "city", "country", "state", "location", "address"])
            is_code = any(kw in col_lower for kw in ["code", "id", "sku", "zip", "postal"])
            is_city = "city" in col_lower
            is_state = "state" in col_lower

            for val in orig_series:
                if val == "nan" or pd.isnull(val):
                    cleaned_series.append(None)
                    continue

                # Repair Mojibake double encoding issues first
                val_fixed = self._fix_mojibake(val)
                if val_fixed != val:
                    encoding_fixes += 1

                # 1. Unicode normalization and cleaning (using NFC to preserve composed chars)
                normalized = unicodedata.normalize("NFC", val_fixed)
                
                # Check for encoding replacement char or zero-width characters
                if "\ufffd" in normalized or "\u200b" in normalized or "\u00ad" in normalized:
                    encoding_fixes += 1
                
                # Strip replacement and invisible chars
                normalized = (
                    normalized.replace("\ufffd", "")
                    .replace("\u200b", "")
                    .replace("\u00ad", "")
                )

                # 2. Normalize whitespace
                normalized = re.sub(r"\s+", " ", normalized).strip()

                # 3. Geo standardizations (city correction and state abbreviation mapping)
                if is_city:
                    # Fuzzy match correction
                    matches = get_close_matches(normalized, KNOWN_CITIES, n=1, cutoff=0.8)
                    if matches:
                        normalized = matches[0]
                elif is_state:
                    # Abbreviation mapping
                    norm_lower = normalized.lower()
                    if norm_lower in STATE_MAP:
                        normalized = STATE_MAP[norm_lower]
                    elif " " in normalized:
                        # Handle trailing abbreviations like "Pune MH" -> "Pune Maharashtra"
                        parts = normalized.split()
                        last_part = parts[-1].lower()
                        if last_part in STATE_MAP:
                            parts[-1] = STATE_MAP[last_part]
                            normalized = " ".join(parts)

                # 4. Standard Casing Rules
                if is_name:
                    normalized = normalized.title()
                elif is_code:
                    normalized = normalized.upper()

                cleaned_series.append(normalized)

            # Assign cleaned series back to DataFrame with proper categories / objects
            df[col] = cleaned_series
            cleaned_cols_count += 1
            total_encoding_fixes += encoding_fixes

            if encoding_fixes > 0 or is_city or is_state:
                self.stats[col] = {
                    "encoding_fixes": encoding_fixes,
                    "casing": "Title" if is_name else ("UPPER" if is_code else "None"),
                }

        if cleaned_cols_count > 0:
            self.log.success(
                f"Text Cleaner: Cleaned {cleaned_cols_count} text columns, "
                f"fixed {total_encoding_fixes} encoding issues"
            )

        return df
