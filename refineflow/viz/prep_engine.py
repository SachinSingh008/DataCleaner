"""
RefineFlow — Base Visualization Preparation Engine
Sanitizes names, formats datetimes, drops zero-variance/high-null columns,
and groups high-cardinality tails before export.
"""

import re
from typing import List, Optional
import pandas as pd
import numpy as np
from refineflow.logger import RefineLogger


class VizPrepEngine:
    """
    Standard visualization preparation pipeline applied to any dataset
    before exporting to BI or dashboard platforms.
    """

    def __init__(self, df: pd.DataFrame, log: Optional[RefineLogger] = None):
        self.df = df.copy()
        self.log = log or RefineLogger()
        self.dimensions: List[str] = []
        self.measures: List[str] = []

    def run(self) -> pd.DataFrame:
        """
        Executes the visualization prep pipeline.
        Returns:
            pd.DataFrame: The prepared DataFrame.
        """
        self.log.section("Base Visualization Prep")
        self.df = self._sanitize_column_names()
        self.df = self._format_datetimes()
        self.df = self._drop_useless_columns()
        self.df = self._reduce_category_cardinality()
        self._detect_dimensions_and_measures()
        return self.df

    def _sanitize_column_names(self) -> pd.DataFrame:
        """Sanitizes column names for BI tool compatibility."""
        renamed = {}
        new_cols = []
        for col in self.df.columns:
            s = str(col)
            # Replace spaces with underscore
            s = s.replace(" ", "_")
            # Remove special characters $, %, #, (, )
            s = re.sub(r"[\$\%\#\(\)]", "", s)
            # Replace consecutive underscores with single underscore
            s = re.sub(r"_+", "_", s)
            # Strip leading/trailing underscores
            s = s.strip("_")
            # Truncate to 64 characters
            s = s[:64]

            if s != str(col):
                renamed[col] = s
            new_cols.append(s)

        self.df.columns = new_cols

        if renamed:
            self.log.success(f"Viz Prep: Sanitized column names ({len(renamed)} renamed):")
            for old, new in renamed.items():
                self.log.info(f"  - Renamed: \"{old}\" → \"{new}\"")
        else:
            self.log.info("Viz Prep: Column names are already clean")

        return self.df

    def _format_datetimes(self) -> pd.DataFrame:
        """Ensures all datetime columns are formatted to ISO 8601 strings."""
        formatted_count = 0
        for col in self.df.columns:
            # Check if column is datetime-like
            if pd.api.types.is_datetime64_any_dtype(self.df[col]):
                # Convert to string format YYYY-MM-DD HH:MM:SS
                self.df[col] = self.df[col].dt.strftime("%Y-%m-%d %H:%M:%S")
                formatted_count += 1
            elif pd.api.types.is_string_dtype(self.df[col]):
                # Attempt to detect if it looks like datetimes
                try:
                    # Look at non-null first values
                    sample = self.df[col].dropna().head(5)
                    if not sample.empty:
                        # Try to parse to datetime; if successful, format
                        parsed = pd.to_datetime(sample, errors="raise")
                        # Perform conversion on whole column
                        parsed_col = pd.to_datetime(self.df[col], errors="coerce")
                        self.df[col] = parsed_col.dt.strftime("%Y-%m-%d %H:%M:%S")
                        formatted_count += 1
                except Exception:
                    pass

        if formatted_count > 0:
            self.log.success(f"Viz Prep: Formatted {formatted_count} datetime columns to YYYY-MM-DD HH:MM:SS")
        return self.df

    def _drop_useless_columns(self) -> pd.DataFrame:
        """Drops columns with >95% null values or 1 unique value (zero variance)."""
        to_drop = []
        dropped_reasons = {}

        for col in self.df.columns:
            null_ratio = self.df[col].isnull().mean()
            if null_ratio > 0.95:
                to_drop.append(col)
                dropped_reasons[col] = f">95% nulls ({null_ratio:.1%})"
                continue

            # Drop zero variance columns (1 unique value)
            non_null_series = self.df[col].dropna()
            if len(self.df) > 1 and non_null_series.nunique() <= 1:
                to_drop.append(col)
                dropped_reasons[col] = "zero variance (1 or fewer unique values)"

        if to_drop:
            self.df.drop(columns=to_drop, inplace=True)
            self.log.success(f"Viz Prep: Dropped {len(to_drop)} useless columns:")
            for col in to_drop:
                self.log.info(f"  - Dropped: \"{col}\" due to {dropped_reasons[col]}")
        else:
            self.log.info("Viz Prep: No useless columns detected")

        return self.df

    def _reduce_category_cardinality(self) -> pd.DataFrame:
        """Groups rare values (<0.5% frequency) into 'Other' for high-cardinality columns (>500 unique)."""
        reduced_cols = []
        for col in self.df.columns:
            if (pd.api.types.is_string_dtype(self.df[col]) or 
                isinstance(self.df[col].dtype, pd.CategoricalDtype)):
                
                # Check cardinality
                unique_vals = self.df[col].dropna().unique()
                if len(unique_vals) > 500:
                    counts = self.df[col].value_counts(normalize=True)
                    # Identify rare categories (frequency < 0.5% / 0.005)
                    rare_vals = counts[counts < 0.005].index
                    
                    if not rare_vals.empty:
                        # Group into "Other"
                        if isinstance(self.df[col].dtype, pd.CategoricalDtype):
                            if "Other" not in self.df[col].cat.categories:
                                self.df[col] = self.df[col].cat.add_categories("Other")
                        
                        self.df[col] = self.df[col].replace(rare_vals, "Other")
                        reduced_cols.append(col)

        if reduced_cols:
            self.log.success(f"Viz Prep: Reduced cardinality for {len(reduced_cols)} columns (rare values grouped to 'Other')")
        return self.df

    def _detect_dimensions_and_measures(self) -> None:
        """Identifies dimensions and measures based on dtypes and cardinality."""
        self.dimensions = []
        self.measures = []
        
        # ID column patterns (avoid marking as numeric measures)
        id_patterns = re.compile(r"(id|_id|key|code|number|phone|zip|postal|email|phone)", re.IGNORECASE)

        for col in self.df.columns:
            col_name_lower = col.lower()
            
            # Datetimes are dimensions
            # Look for YYYY-MM-DD HH:MM:SS formatted string columns
            is_date_str = False
            if pd.api.types.is_string_dtype(self.df[col]):
                sample = self.df[col].dropna().head(3)
                if not sample.empty:
                    # Regex match ISO datetime
                    is_date_str = all(re.match(r"^\d{4}-\d{2}-\d{2}", str(x)) for x in sample)

            if pd.api.types.is_datetime64_any_dtype(self.df[col]) or is_date_str:
                self.dimensions.append(col)
                continue

            # Check if numeric
            if pd.api.types.is_numeric_dtype(self.df[col]):
                # If it's boolean or matches ID patterns, it's a dimension
                if (pd.api.types.is_bool_dtype(self.df[col]) or 
                    id_patterns.search(col_name_lower) or 
                    self.df[col].nunique() < min(10, len(self.df))):
                    self.dimensions.append(col)
                else:
                    self.measures.append(col)
            else:
                self.dimensions.append(col)

        self.log.info(
            f"Viz Prep: Detected {len(self.dimensions)} dimensions and {len(self.measures)} measures"
        )
