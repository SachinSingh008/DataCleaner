"""
RefineFlow — Tableau Preparation Module
Suggests calculated fields, determines field roles, and exports clean CSV
or optional Tableau .hyper files.
"""

import os
import re
import json
from typing import List, Optional, Tuple
import pandas as pd
import numpy as np
from refineflow.logger import RefineLogger
from refineflow.utils import ensure_dir

try:
    import pantab
    _PANTAB = True
except ImportError:
    _PANTAB = False


class TableauPrep:
    """
    Prepares DataFrames for Tableau dashboards.
    Auto-detects roles (Dimensions, Measures, Dates), suggests calculated fields,
    and handles Hyper file or CSV exports.
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
        Runs the Tableau preparation pipeline.
        Returns:
            pd.DataFrame: The Tableau-optimized DataFrame.
        """
        self.log.section("Tableau Preparation")

        # 1. Clean categoricals and measures for aggregation readiness
        self._ensure_aggregation_ready()

        # 2. Field Role Classification
        dimensions, measures, dates = self._classify_roles()

        # 3. Suggest Calculated Fields
        suggestions = self._suggest_calculated_fields()
        self._export_calculated_fields(suggestions)

        # 4. Save Tableau metadata
        self._export_metadata(dimensions, measures, dates)

        # 5. Export Data (Hyper if pantab is available, fallback to CSV)
        self._export_data()

        return self.df

    def _ensure_aggregation_ready(self):
        """Ensures dimensions contain no null strings and measures are strictly numeric."""
        for col in self.df.columns:
            if pd.api.types.is_numeric_dtype(self.df[col]):
                # Fill null values in measures with 0.0 to prevent sum/avg errors in Tableau
                self.df[col] = self.df[col].fillna(0.0)
            elif pd.api.types.is_string_dtype(self.df[col]):
                # Fill null values in dimensions with "Unknown"
                self.df[col] = self.df[col].fillna("Unknown").astype(str).str.strip()

    def _classify_roles(self) -> Tuple[List[str], List[str], List[str]]:
        """Identifies dimensions, measures, and dates for Tableau metadata classification."""
        dimensions = []
        measures = []
        dates = []
        
        id_patterns = re.compile(r"(id|_id|key|code|number|phone|zip|postal|email|phone)", re.IGNORECASE)
        iso_dt_pat = re.compile(r"^\d{4}-\d{2}-\d{2}")

        for col in self.df.columns:
            col_lower = col.lower()
            
            # Check for Datetime
            is_date = False
            if pd.api.types.is_datetime64_any_dtype(self.df[col]):
                is_date = True
            elif pd.api.types.is_string_dtype(self.df[col]):
                sample = self.df[col].dropna().head(3)
                if not sample.empty and all(isinstance(x, str) and iso_dt_pat.match(x) for x in sample):
                    is_date = True

            if is_date:
                dates.append(col)
                continue

            if pd.api.types.is_numeric_dtype(self.df[col]):
                if (pd.api.types.is_bool_dtype(self.df[col]) or 
                    id_patterns.search(col_lower) or 
                    self.df[col].nunique() < min(10, len(self.df))):
                    dimensions.append(col)
                else:
                    measures.append(col)
            else:
                dimensions.append(col)

        return dimensions, measures, dates

    def _suggest_calculated_fields(self) -> List[dict]:
        """Detects column pairs that could form calculated fields (e.g. Profit Margin)."""
        suggestions = []
        cols = self.df.columns
        cols_lower = [c.lower() for c in cols]

        # 1. Profit Margin = Profit / Revenue (or Sales)
        profit_col = None
        revenue_col = None
        for i, c in enumerate(cols_lower):
            if "profit" in c:
                profit_col = cols[i]
            elif "revenue" in c or "sales" in c:
                revenue_col = cols[i]

        if profit_col and revenue_col:
            suggestions.append({
                "name": "Profit Margin",
                "formula": f"[{profit_col}] / [{revenue_col}]"
            })

        # 2. Total Value = Quantity * Unit Price
        qty_col = None
        price_col = None
        for i, c in enumerate(cols_lower):
            if "qty" in c or "quantity" in c:
                qty_col = cols[i]
            elif "price" in c or "cost" in c or "rate" in c:
                price_col = cols[i]

        if qty_col and price_col:
            suggestions.append({
                "name": "Total Value",
                "formula": f"[{qty_col}] * [{price_col}]"
            })

        return suggestions

    def _export_calculated_fields(self, suggestions: List[dict]):
        """Saves calculated field suggestions to JSON."""
        suggestions_path = os.path.join(self.output_dir, "tableau_calculated_fields.json")
        try:
            with open(suggestions_path, "w") as f:
                json.dump(suggestions, f, indent=2)
            self.log.success(
                f"Tableau: Suggested {len(suggestions)} calculated fields saved to {suggestions_path}"
            )
        except Exception as e:
            self.log.error(f"Tableau: Failed to save calculated field suggestions: {e}")

    def _export_metadata(self, dimensions: List[str], measures: List[str], dates: List[str]):
        """Writes the Tableau metadata file showing column classification roles."""
        metadata = {
            "dimensions": dimensions,
            "measures": measures,
            "dates": dates
        }
        metadata_path = os.path.join(self.output_dir, "tableau_metadata.json")
        try:
            with open(metadata_path, "w") as f:
                json.dump(metadata, f, indent=2)
            self.log.success(f"Tableau: Metadata saved to {metadata_path}")
        except Exception as e:
            self.log.error(f"Tableau: Failed to save Tableau metadata: {e}")

    def _export_data(self):
        """Exports the optimized data to Tableau Hyper format or falls back to clean CSV."""
        base_name = os.path.splitext(os.path.basename(self.source_file))[0]
        
        if _PANTAB:
            out_name = f"tableau_ready_{base_name}.hyper"
            out_path = os.path.join(self.output_dir, out_name)
            try:
                # pantab saves to hyper format natively
                pantab.frame_to_hyper(self.df, out_path, table="Extract")
                self.log.success(f"Tableau: Exported Hyper file to {out_path}")
                return
            except Exception as e:
                self.log.error(f"Tableau: Hyper export failed: {e}. Falling back to CSV.")

        # Fallback to CSV
        csv_name = f"tableau_ready_{base_name}.csv"
        csv_path = os.path.join(self.output_dir, csv_name)
        try:
            self.df.to_csv(csv_path, index=False, encoding="utf-8-sig")
            self.log.success(f"Tableau: Exported CSV file to {csv_path}")
        except Exception as e:
            self.log.error(f"Tableau: CSV export failed: {e}")
