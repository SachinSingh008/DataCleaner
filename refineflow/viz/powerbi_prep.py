"""
RefineFlow — Power BI Preparation Module
Decomposes dates, detects dimensions/measures, drops text/hash blobs,
and exports snappy-compressed Parquet with schema mapping JSON.
"""

import os
import re
import json
from typing import List, Optional
import pandas as pd
import numpy as np
from refineflow.logger import RefineLogger
from refineflow.utils import ensure_dir


class PowerBIPrep:
    """
    Optimizes and prepares a DataFrame specifically for Power BI,
    generating calendar hierarchies and compressed Parquet files.
    """

    def __init__(
        self,
        df: pd.DataFrame,
        output_dir: str = "./",
        source_file: str = "dataset.csv",
        log: Optional[RefineLogger] = None
    ):
        self.df = df.copy()
        self.output_dir = output_dir
        self.source_file = source_file
        self.log = log or RefineLogger()

        ensure_dir(self.output_dir)

    def run(self) -> pd.DataFrame:
        """
        Runs the Power BI preparation pipeline.
        Returns:
            pd.DataFrame: The optimized DataFrame.
        """
        self.log.section("Power BI Preparation")
        
        # 1. Relationship formatting (ID cleanups)
        self._format_relationship_keys()

        # 2. DateTime Decomposition
        date_cols = self._decompose_datetimes()

        # 3. Clean large text blobs & hashes
        self._drop_unusable_bi_columns()

        # 4. Measure vs Dimension Classification
        measures, dimensions = self._classify_fields(date_cols)

        # 5. Export Schema JSON
        self._export_schema_json(measures, dimensions, date_cols)

        # 6. Export to Parquet
        self._export_parquet()

        return self.df

    def _format_relationship_keys(self):
        """Standardizes primary and foreign key columns as clean string types."""
        id_patterns = re.compile(r"(id|_id|key|code)", re.IGNORECASE)
        for col in self.df.columns:
            if id_patterns.search(col):
                # Replace nulls in ID/Key columns with a blank string
                self.df[col] = self.df[col].fillna("").astype(str).str.strip()

    def _decompose_datetimes(self) -> List[str]:
        """Decomposes datetimes into year, month, day, quarter, weekday, and hour columns."""
        date_cols = []
        added_count = 0

        # Pattern for ISO 8601 string dates YYYY-MM-DD HH:MM:SS
        iso_dt_pat = re.compile(r"^\d{4}-\d{2}-\d{2}")

        for col in self.df.columns:
            series = self.df[col]
            is_date = False

            if pd.api.types.is_datetime64_any_dtype(series):
                is_date = True
                dt_series = series
            elif pd.api.types.is_string_dtype(series):
                # Sample to check if it's ISO datetime
                sample = series.dropna().head(3)
                if not sample.empty and all(isinstance(x, str) and iso_dt_pat.match(x) for x in sample):
                    is_date = True
                    dt_series = pd.to_datetime(series, errors="coerce")

            if is_date:
                date_cols.append(col)
                # Decompose
                self.df[f"{col}_Year"] = dt_series.dt.year.fillna(0).astype(int)
                self.df[f"{col}_Month"] = dt_series.dt.month.fillna(0).astype(int)
                self.df[f"{col}_Day"] = dt_series.dt.day.fillna(0).astype(int)
                self.df[f"{col}_Quarter"] = dt_series.dt.quarter.fillna(0).astype(int)
                
                # WeekDay (Day Name)
                self.df[f"{col}_WeekDay"] = dt_series.dt.day_name().fillna("Unknown").astype(str)
                self.df[f"{col}_Hour"] = dt_series.dt.hour.fillna(0).astype(int)
                
                added_count += 6

        if added_count > 0:
            self.log.success(f"Power BI: Added {added_count} datetime helper columns")
        return date_cols

    def _drop_unusable_bi_columns(self):
        """Drops columns representing huge text blobs or hex hashes that slow down BI rendering."""
        to_drop = []
        for col in self.df.columns:
            if pd.api.types.is_string_dtype(self.df[col]):
                sample = self.df[col].dropna().head(10)
                if sample.empty:
                    continue
                
                # Check for large text blobs (average length > 250 characters)
                avg_len = sample.str.len().mean()
                if avg_len > 250:
                    to_drop.append(col)
                    continue

                # Check for hashes (MD5, SHA1, SHA256)
                is_hash = all(
                    isinstance(x, str) and re.match(r"^[0-9a-fA-F]{32,64}$", x) 
                    for x in sample
                )
                if is_hash:
                    to_drop.append(col)

        if to_drop:
            self.df.drop(columns=to_drop, inplace=True)
            self.log.success(f"Power BI: Dropped {len(to_drop)} text/hash columns for optimization: {to_drop}")

    def _classify_fields(self, date_cols: List[str]) -> tuple:
        """Classifies columns as measures or dimensions for Power BI schema definition."""
        measures = []
        dimensions = []
        id_patterns = re.compile(r"(id|_id|key|code|number|phone|zip|postal|email|phone)", re.IGNORECASE)

        # Decomposed date helpers shouldn't be counted as date_columns or measures
        decomposed_suffix = ["_Year", "_Month", "_Day", "_Quarter", "_WeekDay", "_Hour"]

        for col in self.df.columns:
            if col in date_cols:
                continue
            if any(col.endswith(suf) for suf in decomposed_suffix):
                dimensions.append(col)
                continue

            col_name_lower = col.lower()
            if pd.api.types.is_numeric_dtype(self.df[col]):
                if (pd.api.types.is_bool_dtype(self.df[col]) or 
                    id_patterns.search(col_name_lower) or 
                    self.df[col].nunique() < min(10, len(self.df))):
                    dimensions.append(col)
                else:
                    measures.append(col)
            else:
                dimensions.append(col)

        return measures, dimensions

    def _export_schema_json(self, measures: List[str], dimensions: List[str], date_cols: List[str]):
        """Writes the Power BI data model hints schema JSON file."""
        schema_data = {
            "measures": measures,
            "dimensions": dimensions,
            "date_columns": date_cols
        }
        schema_path = os.path.join(self.output_dir, "powerbi_schema.json")
        try:
            with open(schema_path, "w") as f:
                json.dump(schema_data, f, indent=2)
            self.log.success(f"Power BI: Schema saved to {schema_path}")
        except Exception as e:
            self.log.error(f"Power BI: Failed to save schema JSON: {e}")

    def _export_parquet(self):
        """Exports the optimized DataFrame to snappy-compressed Parquet."""
        base_name = os.path.splitext(os.path.basename(self.source_file))[0]
        out_name = f"powerbi_ready_{base_name}.parquet"
        out_path = os.path.join(self.output_dir, out_name)

        try:
            # We enforce snappy compression on parquet export
            self.df.to_parquet(out_path, compression="snappy", index=False)
            self.log.success(f"Power BI: Exported parquet to {out_path}")
        except Exception as e:
            self.log.error(f"Power BI: Failed to export Parquet: {e}")
            # Fallback to standard CSV if parquet engine is missing
            csv_path = os.path.splitext(out_path)[0] + ".csv"
            self.df.to_csv(csv_path, index=False, encoding="utf-8-sig")
            self.log.warning(f"Power BI: Fallback export to CSV: {csv_path}")
