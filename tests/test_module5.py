"""
RefineFlow — Module 5 Comprehensive Test Suite
Tests: VizPrepEngine, FeatureScaler, PowerBIPrep, TableauPrep, and VizRecommender.
Run: python tests/test_module5.py
"""

import sys
if sys.stdout and hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

import os
import shutil
import tempfile
import traceback
import json
import pandas as pd
import numpy as np

# Make sure refineflow is importable from project root
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# Color helpers
try:
    from colorama import Fore, Style, init
    init(autoreset=True)
    GREEN  = Fore.GREEN
    RED    = Fore.RED
    YELLOW = Fore.YELLOW
    CYAN   = Fore.CYAN
    RESET  = Style.RESET_ALL
    _COLORAMA = True
except ImportError:
    GREEN = RED = YELLOW = CYAN = RESET = ""
    Fore = Style = None
    _COLORAMA = False

PASS = f"{GREEN}[PASS]{RESET}"
FAIL = f"{RED}[FAIL]{RESET}"

_results = {"pass": 0, "fail": 0, "skip": 0}


def test(name: str, condition: bool, detail: str = "") -> None:
    if condition:
        print(f"  {PASS} {name}")
        _results["pass"] += 1
    else:
        print(f"  {FAIL} {name}" + (f"  ->  {detail}" if detail else ""))
        _results["fail"] += 1


def section(title: str) -> None:
    bar = "-" * 55
    print(f"\n{CYAN}{bar}\n  {title}\n{bar}{RESET}")


# =============================================================================
# 1. BASE VIZ PREP ENGINE
# =============================================================================

def test_viz_prep_engine():
    section("1. Base Viz Prep Engine")
    from refineflow.viz.prep_engine import VizPrepEngine
    from refineflow.logger import RefineLogger

    log = RefineLogger(verbose=False)

    # Test column name sanitization
    df = pd.DataFrame({
        "Revenue ($)": [100, 200],
        "First Name": ["John", "Jane"],
        "A#B%C_": [1, 2],
        "A"*70: [3, 4]  # will truncate to 64 chars
    })

    prep = VizPrepEngine(df, log=log)
    res = prep._sanitize_column_names()

    test("Sanitizes special characters (removes $, %)", "Revenue" in res.columns)
    test("Replaces spaces with underscore", "First_Name" in res.columns)
    test("Strips trailing underscores and truncates to 64 chars", "A"*64 in res.columns)

    # Test drop useless columns
    df_useless = pd.DataFrame({
        "good": [1, 2, 3],
        "all_null": [np.nan, np.nan, np.nan],
        "zero_var": [4, 4, 4]
    })
    prep_useless = VizPrepEngine(df_useless, log=log)
    res_useless = prep_useless._drop_useless_columns()
    test("Drops >95% null columns", "all_null" not in res_useless.columns)
    test("Drops zero-variance columns", "zero_var" not in res_useless.columns)

    # Test datetime format formatting
    df_dt = pd.DataFrame({
        "date_str": ["2025-05-12 14:00:00", "2025-05-13 15:30:00"],
        "not_date": ["hello", "world"]
    })
    prep_dt = VizPrepEngine(df_dt, log=log)
    res_dt = prep_dt._format_datetimes()
    test("Formats date strings to ISO 8601 YYYY-MM-DD HH:MM:SS", res_dt["date_str"].iloc[0] == "2025-05-12 14:00:00")

    # Test cardinality reduction (requires >500 unique values)
    df_cardinal = pd.DataFrame({
        "cat": ["A"] * 600 + [f"Cat_{i}" for i in range(500)] + ["C"] * 2  # C is < 0.5% (2 / 1102 = 0.18%)
    })
    prep_cardinal = VizPrepEngine(df_cardinal, log=log)
    res_cardinal = prep_cardinal._reduce_category_cardinality()
    unique_cats = set(res_cardinal["cat"].unique())
    test("Groups rare categories (< 0.5%) into 'Other'", "Other" in unique_cats and "C" not in unique_cats)


# =============================================================================
# 2. FEATURE SCALER
# =============================================================================

def test_feature_scaler():
    section("2. Feature Scaler")
    from refineflow.viz.feature_scaler import FeatureScaler
    from refineflow.logger import RefineLogger

    log = RefineLogger(verbose=False)

    df = pd.DataFrame({
        "age": [20, 30, 40],
        "income": [10000, 50000, 90000],
        "id_col": [1, 2, 3]  # should auto-exclude
    })

    # MinMax scaling
    scaler = FeatureScaler(df, method="minmax", log=log)
    res_minmax = scaler.run()

    test("MinMax: scales age correctly into [0.0, 1.0]", res_minmax["age_scaled"].min() == 0.0 and res_minmax["age_scaled"].max() == 1.0)
    test("MinMax: auto-excludes ID column", "id_col_scaled" not in res_minmax.columns)

    # Inverse transform
    unscaled = scaler.inverse_transform(res_minmax)
    test("MinMax: inverse_transform recovers original values", (unscaled["age"] == df["age"]).all())
    test("MinMax: inverse_transform drops scaled columns", "age_scaled" not in unscaled.columns)

    # Standard scaling
    scaler_std = FeatureScaler(df, method="standard", log=log)
    res_std = scaler_std.run()
    test("Standard: centers mean near 0.0", np.isclose(res_std["age_scaled"].mean(), 0.0))

    # Robust scaling
    scaler_rob = FeatureScaler(df, method="robust", log=log)
    res_rob = scaler_rob.run()
    test("Robust: scales correctly using median", res_rob["age_scaled"].iloc[1] == 0.0)


# =============================================================================
# 3. POWER BI PREPARATION
# =============================================================================

def test_powerbi_prep():
    section("3. Power BI Prep")
    from refineflow.viz.powerbi_prep import PowerBIPrep
    from refineflow.logger import RefineLogger

    log = RefineLogger(verbose=False)

    temp_dir = tempfile.mkdtemp()
    try:
        df = pd.DataFrame({
            "order_date": pd.to_datetime(["2025-01-15 08:30:00", "2025-04-20 12:45:00"]),
            "revenue": [5000.0, 7500.0],
            "customer_id": [101, 102],
            "huge_text": ["a" * 300, "b" * 300], # should be dropped
            "hash_md5": ["e10adc3949ba59abbe56e057f20f883e", "c33367701511b4f6020ec61ded352059"] # should be dropped
        })

        pbi = PowerBIPrep(df, output_dir=temp_dir, source_file="sales.csv", log=log)
        res = pbi.run()

        # Date helper checks
        test("Power BI: Adds Date Year helper column", "order_date_Year" in res.columns)
        test("Power BI: Adds Date Month helper column", "order_date_Month" in res.columns)
        test("Power BI: Adds Date Quarter helper column", "order_date_Quarter" in res.columns)
        test("Power BI: Adds Date WeekDay helper column", "order_date_WeekDay" in res.columns)

        # Drop text/hash check
        test("Power BI: Drops huge text columns", "huge_text" not in res.columns)
        test("Power BI: Drops hex hash columns", "hash_md5" not in res.columns)

        # Files check
        parquet_exists = os.path.exists(os.path.join(temp_dir, "powerbi_ready_sales.parquet"))
        csv_exists = os.path.exists(os.path.join(temp_dir, "powerbi_ready_sales.csv"))
        test("Power BI: Exports Parquet file (or fallback CSV)", parquet_exists or csv_exists)

        schema_json_path = os.path.join(temp_dir, "powerbi_schema.json")
        test("Power BI: Saves schema metadata JSON file", os.path.exists(schema_json_path))
        if os.path.exists(schema_json_path):
            with open(schema_json_path) as f:
                schema = json.load(f)
            test("Power BI: Schema classifies measures correctly", "revenue" in schema["measures"])
            test("Power BI: Schema classifies date columns correctly", "order_date" in schema["date_columns"])
    finally:
        shutil.rmtree(temp_dir)


# =============================================================================
# 4. TABLEAU PREPARATION
# =============================================================================

def test_tableau_prep():
    section("4. Tableau Prep")
    from refineflow.viz.tableau_prep import TableauPrep
    from refineflow.logger import RefineLogger

    log = RefineLogger(verbose=False)

    temp_dir = tempfile.mkdtemp()
    try:
        df = pd.DataFrame({
            "profit": [100.0, 200.0],
            "revenue": [500.0, 800.0],
            "qty": [10, 20],
            "price": [50.0, 40.0],
            "city": ["Mumbai", np.nan] # NaN should be filled with "Unknown"
        })

        tab = TableauPrep(df, output_dir=temp_dir, source_file="orders.csv", log=log)
        res = tab.run()

        # Null cleaning check
        test("Tableau: Fills string column NaNs with 'Unknown'", res["city"].iloc[1] == "Unknown")

        # Files check
        csv_exists = os.path.exists(os.path.join(temp_dir, "tableau_ready_orders.csv"))
        hyper_exists = os.path.exists(os.path.join(temp_dir, "tableau_ready_orders.hyper"))
        test("Tableau: Exports Hyper file (if pantab installed) or CSV file", csv_exists or hyper_exists)

        # Calculated fields suggestions check
        suggestions_path = os.path.join(temp_dir, "tableau_calculated_fields.json")
        test("Tableau: Saves calculated field suggestions JSON file", os.path.exists(suggestions_path))
        if os.path.exists(suggestions_path):
            with open(suggestions_path) as f:
                calc_fields = json.load(f)
            test("Tableau: Correctly suggests Profit Margin", any(cf["name"] == "Profit Margin" for cf in calc_fields))
            test("Tableau: Correctly suggests Total Value", any(cf["name"] == "Total Value" for cf in calc_fields))

        # Metadata check
        metadata_path = os.path.join(temp_dir, "tableau_metadata.json")
        test("Tableau: Saves metadata JSON file", os.path.exists(metadata_path))
        if os.path.exists(metadata_path):
            with open(metadata_path) as f:
                meta = json.load(f)
            test("Tableau: Metadata classifies measures", "profit" in meta["measures"])
            test("Tableau: Metadata classifies dimensions", "city" in meta["dimensions"])
    finally:
        shutil.rmtree(temp_dir)


# =============================================================================
# 5. VISUALIZATION RECOMMENDER
# =============================================================================

def test_viz_recommender():
    section("5. Viz Recommender")
    from refineflow.viz.recommender import VizRecommender
    from refineflow.logger import RefineLogger

    log = RefineLogger(verbose=False)

    df = pd.DataFrame({
        "order_date": pd.to_datetime(["2025-01-01", "2025-01-02", "2025-01-03", "2025-01-04", "2025-01-05", "2025-01-06"]),
        "sales": [1000.0, 1500.0, 1200.0, 1300.0, 1400.0, 1100.0],
        "profit": [200.0, 400.0, 300.0, 350.0, 380.0, 250.0],
        "category": ["A", "B", "A", "B", "A", "B"],
        "city": ["Mumbai", "Delhi", "Mumbai", "Delhi", "Mumbai", "Delhi"]
    })

    recommender = VizRecommender(df, log=log)
    recs = recommender.recommend()

    test("Recommender: Returns list of recommendations", isinstance(recs, list) and len(recs) > 0)
    
    charts = [r["chart"] for r in recs]
    test("Recommender: Recommends Line Chart for trend (Date + Numeric)", "Line Chart" in charts)
    test("Recommender: Recommends Map Chart (Geo present)", "Map Chart" in charts)
    test("Recommender: Recommends Bar Chart for small categories", "Bar Chart" in charts)

    # For scatter plot, test on a numeric-only df so High confidence trend/map/bar don't crowd it out in top 5
    df_scatter = pd.DataFrame({
        "sales": [1000.0, 1500.0, 1200.0, 1300.0, 1400.0, 1100.0],
        "profit": [200.0, 400.0, 300.0, 350.0, 380.0, 250.0]
    })
    recommender_s = VizRecommender(df_scatter, log=log)
    recs_s = recommender_s.recommend()
    charts_s = [r["chart"] for r in recs_s]
    test("Recommender: Recommends Scatter Plot for two numeric correlations", "Scatter Plot" in charts_s)


# =============================================================================
# 6. CLEANER INTEGRATION (End-to-End viz optimization chaining)
# =============================================================================

def test_cleaner_viz_integration():
    section("6. Cleaner Fluent API Chaining")
    from refineflow.cleaner import Cleaner

    temp_dir = tempfile.mkdtemp()
    try:
        csv_path = os.path.join(temp_dir, "dataset.csv")
        df = pd.DataFrame({
            "order_date": ["2025-01-01 10:00:00", "2025-01-02 12:00:00"],
            "profit": [50.0, 75.0],
            "revenue": [100.0, 150.0],
            "country": ["India", "USA"]
        })
        df.to_csv(csv_path, index=False)

        cleaner = Cleaner(csv_path, partitions=1, verbose=False)
        cleaner.scan()
        cleaner.auto_clean()

        # Fluent viz prep API execution
        cleaner.prepare_for_powerbi(output_dir=temp_dir)
        cleaner.prepare_for_tableau(output_dir=temp_dir)
        cleaner.recommend_visualizations()

        # Verify output files
        pbi_json = os.path.exists(os.path.join(temp_dir, "powerbi_schema.json"))
        tab_json = os.path.exists(os.path.join(temp_dir, "tableau_calculated_fields.json"))
        test("Cleaner chaining completes successfully", cleaner.df is not None)
        test("Power BI files exported in chain", pbi_json)
        test("Tableau files exported in chain", tab_json)
    finally:
        shutil.rmtree(temp_dir)


# =============================================================================
# RUN ALL
# =============================================================================

if __name__ == "__main__":
    print(f"\n=======================================================")
    print(f"  RefineFlow — Module 5 Test Suite")
    print(f"=======================================================")

    try:
        test_viz_prep_engine()
        test_feature_scaler()
        test_powerbi_prep()
        test_tableau_prep()
        test_viz_recommender()
        test_cleaner_viz_integration()
    except Exception as e:
        print(f"\n{RED}Test execution crashed!{RESET}")
        traceback.print_exc()
        sys.exit(1)

    print(f"\n=======================================================")
    print(f"  Module 5 Test Results")
    print(f"=======================================================")
    print(f"  PASSED : {_results['pass']}")
    print(f"  FAILED : {_results['fail']}")
    print(f"  SKIPPED: {_results['skip']}")
    print(f"  TOTAL  : {_results['pass'] + _results['fail'] + _results['skip']}")
    print(f"=======================================================\n")

    if _results["fail"] > 0:
        print(f"  {RED}{_results['fail']} test(s) failed — see details above.{RESET}\n")
        sys.exit(1)
    else:
        print(f"  {GREEN}All tests passed! Module 5 is solid.{RESET}\n")
        sys.exit(0)
