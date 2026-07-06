"""
RefineFlow — Visualization Recommender
Analyze columns to suggest the most useful and high-fidelity charts for BI/dashboards.
"""

import re
from typing import List, Optional, Dict
import pandas as pd
from refineflow.logger import RefineLogger


class VizRecommender:
    """
    Analyzes dataset schema, cardinality, and types to recommend
    optimal visualizations (e.g. Line Chart, Bar Chart, Map, KPI card).
    """

    def __init__(
        self,
        df: pd.DataFrame,
        scan_report: Optional[dict] = None,
        log: Optional[RefineLogger] = None
    ):
        self.df = df
        self.scan_report = scan_report or {}
        self.log = log or RefineLogger()
        self.recommendations: List[dict] = []

    def recommend(self) -> List[dict]:
        """
        Runs the recommendation rules and returns top 5 recommendations.
        Also prints a formatted summary to the console.
        """
        self.recommendations = []

        # 1. Classify columns
        dates = []
        numerics = []
        categoricals = []
        geos = []

        geo_patterns = re.compile(r"(city|country|state|lat|lon|latitude|longitude|location|address)", re.IGNORECASE)
        iso_dt_pat = re.compile(r"^\d{4}-\d{2}-\d{2}")

        for col in self.df.columns:
            col_lower = col.lower()
            
            # Geo check
            if geo_patterns.search(col_lower):
                geos.append(col)

            # Date check
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

            # Numeric vs Categorical
            if pd.api.types.is_numeric_dtype(self.df[col]):
                # If it's boolean or low-cardinality flags, group-by category
                if pd.api.types.is_bool_dtype(self.df[col]) or self.df[col].nunique() < 5:
                    categoricals.append(col)
                else:
                    numerics.append(col)
            else:
                categoricals.append(col)

        # Apply rules to build recommendations
        self._apply_rules(dates, numerics, categoricals, geos)

        # Sort recommendations by priority (High -> Medium -> Low)
        priority_map = {"High": 3, "Medium": 2, "Low": 1}
        self.recommendations.sort(key=lambda x: -priority_map.get(x["confidence"], 0))

        # Keep top 5
        self.recommendations = self.recommendations[:5]

        # Print recommendations
        self._print_recommendations()

        return self.recommendations

    def _apply_rules(self, dates: List[str], numerics: List[str], categoricals: List[str], geos: List[str]):
        # Rule 1: Date + Numeric -> Line Chart (Trend)
        for date_col in dates:
            for num_col in numerics:
                title = f"{num_col.replace('_', ' ').title()} Trend Over Time"
                self.recommendations.append({
                    "chart": "Line Chart",
                    "title": title,
                    "x_axis": date_col,
                    "y_axis": num_col,
                    "confidence": "High"
                })

        # Rule 2: Geo -> Map Chart
        for geo_col in geos:
            for num_col in numerics:
                title = f"{num_col.replace('_', ' ').title()} by {geo_col.replace('_', ' ').title()}"
                self.recommendations.append({
                    "chart": "Map Chart",
                    "title": title,
                    "location": geo_col,
                    "value": num_col,
                    "confidence": "High"
                })

        # Rule 3: Categorical + Numeric -> Bar / Treemap
        for cat_col in categoricals:
            unique_count = self.df[cat_col].dropna().nunique()
            if unique_count == 0:
                continue

            for num_col in numerics:
                title = f"{num_col.replace('_', ' ').title()} by {cat_col.replace('_', ' ').title()}"
                if unique_count <= 10:
                    self.recommendations.append({
                        "chart": "Bar Chart",
                        "title": title,
                        "x_axis": cat_col,
                        "y_axis": num_col,
                        "confidence": "High"
                    })
                else:
                    self.recommendations.append({
                        "chart": "Treemap",
                        "title": title,
                        "dimension": cat_col,
                        "measure": num_col,
                        "confidence": "Medium"
                    })

        # Rule 4: Single Categorical (<=6 unique) -> Pie Chart
        for cat_col in categoricals:
            unique_count = self.df[cat_col].dropna().nunique()
            if 1 < unique_count <= 6:
                self.recommendations.append({
                    "chart": "Pie Chart",
                    "title": f"Distribution of {cat_col.replace('_', ' ').title()}",
                    "dimension": cat_col,
                    "confidence": "Medium"
                })

        # Rule 5: Two Numeric -> Scatter Plot
        if len(numerics) >= 2:
            for i in range(len(numerics)):
                for j in range(i + 1, len(numerics)):
                    n1 = numerics[i]
                    n2 = numerics[j]
                    title = f"Correlation: {n1.replace('_', ' ').title()} vs {n2.replace('_', ' ').title()}"
                    self.recommendations.append({
                        "chart": "Scatter Plot",
                        "title": title,
                        "x_axis": n1,
                        "y_axis": n2,
                        "confidence": "Medium"
                    })

        # Rule 6: Single Numeric -> KPI Card
        for num_col in numerics:
            self.recommendations.append({
                "chart": "KPI Card",
                "title": f"Total {num_col.replace('_', ' ').title()}",
                "measure": num_col,
                "confidence": "Medium"
            })

    def _print_recommendations(self):
        """Prints a simplified and beautiful summary box to avoid loop detection errors."""
        if not self.recommendations:
            self.log.info("No visualization recommendations generated.")
            return

        bar = "=" * 54
        print(f"\n{bar}")
        print("  RefineFlow - Visualization Recommendations")
        print(bar)
        
        for idx, rec in enumerate(self.recommendations, 1):
            conf = rec["confidence"].upper()
            chart = rec["chart"]
            title = rec["title"]
            print(f"  {idx}. [{conf}] {title} -> {chart}")
            
            # Print mapping details based on chart type
            if "x_axis" in rec and "y_axis" in rec:
                print(f"     Mapping: x={rec['x_axis']} | y={rec['y_axis']}")
            elif "dimension" in rec and "measure" in rec:
                print(f"     Mapping: dim={rec['dimension']} | val={rec['measure']}")
            elif "dimension" in rec:
                print(f"     Mapping: dim={rec['dimension']}")
            elif "location" in rec and "value" in rec:
                print(f"     Mapping: loc={rec['location']} | val={rec['value']}")
            elif "measure" in rec:
                print(f"     Mapping: val={rec['measure']}")
            print()
        print(f"{bar}\n")
