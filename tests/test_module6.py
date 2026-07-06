"""
RefineFlow — Module 6 Comprehensive Test Suite
Tests: SchemaDriftDetector, DataExporter, ReportGenerator, CLI commands, and Fluent Chaining.
Run: python tests/test_module6.py
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
import openpyxl
from click.testing import CliRunner

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
        print(f"  {FAIL} {name}")
        if detail:
            print(f"         Detail: {detail}")
        _results["fail"] += 1


def section(name: str) -> None:
    print(f"\n{CYAN}{'='*55}\n  {name}\n{'='*55}")


# =============================================================================
# SETUP TEMP DIRECTORY
# =============================================================================
tmp_dir = tempfile.mkdtemp()
csv_file_path = os.path.join(tmp_dir, "sample_data.csv")

# Create a sample CSV file
df_init = pd.DataFrame({
    "order_id": [1, 2, 3, 4, 5],
    "user_email": [
        "john.doe@gmail.com", "jane@yahoo.com",
        "invalid_email", "admin@company.org", "test@test.com"
    ],
    "revenue": ["$120.50", "₹1,500.00", "500", "invalid", None],
    "price": [10.0, 20.0, 15.0, 50.0, 100.0],
    "weight": [1.5, 2.5, 3.0, 4.5, 2.0],
    "order_date": ["2023-01-01", "2023-02-01", "2023-03-01", "invalid-date", "2023-05-01"],
    "city": ["New York", "new york", "London", "London", "Paris"]
})
df_init.to_csv(csv_file_path, index=False)


# =============================================================================
# 1. SCHEMA DRIFT DETECTOR
# =============================================================================
section("1. Schema Drift Detector")

try:
    from refineflow.schema_drift import SchemaDriftDetector, SchemaDriftWarning
    
    snapshot_path = os.path.join(tmp_dir, "schema_snapshot_test.json")
    if os.path.exists(snapshot_path):
        os.remove(snapshot_path)
        
    df_snapshot = pd.DataFrame({
        "age": [25, 30, 35],
        "city": ["New York", "Paris", "London"],
        "revenue": [100.0, 200.0, 300.0]
    })
    
    # First run saves snapshot
    detector1 = SchemaDriftDetector(df_snapshot, snapshot_path=snapshot_path)
    rep1 = detector1.detect_drift()
    test("Schema Drift: First run detects no drift", rep1["detected"] is False)
    test("Schema Drift: Snapshot file created", os.path.exists(snapshot_path))
    
    # Load snapshot to verify content
    with open(snapshot_path, "r") as f:
        snap_data = json.load(f)
    test("Schema Drift: Snapshot records all column dtypes", len(snap_data["columns"]) == 3)
    
    # Second run: added column and type change
    df_drift = pd.DataFrame({
        "age": [25, 30, 35],
        "city": ["New York", "Paris", "London"],
        "revenue": ["$100.0", "$200.0", "$300.0"],  # Changed float -> string
        "country": ["USA", "France", "UK"]            # Added column
    })
    
    detector2 = SchemaDriftDetector(df_drift, snapshot_path=snapshot_path)
    import warnings
    
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        rep2 = detector2.detect_drift()
        
        test("Schema Drift: Detects drift on altered df", rep2["detected"] is True)
        test("Schema Drift: Identifies new column", "country" in rep2["new_columns"])
        test("Schema Drift: Identifies type change", "revenue" in rep2["type_changes"])
        test("Schema Drift: Type change marked as HIGH risk (float -> string)", 
             rep2["type_changes"]["revenue"]["risk"] == "HIGH")
        test("Schema Drift: Warning is raised", len(w) > 0 and issubclass(w[-1].category, SchemaDriftWarning))

    # Test renamed likely
    df_rename = pd.DataFrame({
        "ag_e": [25, 30, 35],  # renamed 'age' -> 'ag_e'
        "city": ["New York", "Paris", "London"],
        "revenue": [100.0, 200.0, 300.0]
    })
    detector3 = SchemaDriftDetector(df_rename, snapshot_path=snapshot_path)
    rep3 = detector3.detect_drift()
    test("Schema Drift: Identifies likely renamed columns", 
         len(rep3["renamed_likely"]) > 0 and rep3["renamed_likely"][0]["old"] == "age" and rep3["renamed_likely"][0]["new"] == "ag_e")

except Exception as e:
    test("Schema Drift: Error running tests", False, f"{e}\n{traceback.format_exc()}")


# =============================================================================
# 2. DATA EXPORTER
# =============================================================================
section("2. Data Exporter")

try:
    from refineflow.exporter import DataExporter, format_size
    
    df_export = pd.DataFrame({
        "name": ["Alice", "Bob", "Charlie"],
        "age": [25, 30, 35],
        "salary": [50000, 60000, 70000]
    })
    
    exporter = DataExporter(df_export, source_file=csv_file_path, output_dir=tmp_dir)
    
    # Test format_size helper
    test("Exporter: format_size handles zero bytes", format_size(0) in ["0 B", "0.0 B"])
    test("Exporter: format_size handles KB", "KB" in format_size(1500))
    test("Exporter: format_size handles MB", "MB" in format_size(2 * 1024 * 1024))

    # Test CSV Export
    csv_paths = exporter.export(format="csv")
    test("Exporter: CSV path returned", len(csv_paths) == 1 and csv_paths[0].endswith(".csv"))
    test("Exporter: CSV file created", os.path.exists(csv_paths[0]))
    df_csv_loaded = pd.read_csv(csv_paths[0])
    test("Exporter: CSV file content is correct", len(df_csv_loaded) == 3 and list(df_csv_loaded.columns) == ["name", "age", "salary"])

    # Test Parquet Export
    parquet_paths = exporter.export(format="parquet")
    test("Exporter: Parquet path returned", len(parquet_paths) == 1 and parquet_paths[0].endswith(".parquet"))
    test("Exporter: Parquet file created", os.path.exists(parquet_paths[0]))
    df_pq_loaded = pd.read_parquet(parquet_paths[0])
    test("Exporter: Parquet file content matches", df_pq_loaded.shape == (3, 3))

    # Test Excel Export
    excel_paths = exporter.export(format="excel")
    test("Exporter: Excel path returned", len(excel_paths) == 1 and excel_paths[0].endswith(".xlsx"))
    test("Exporter: Excel file created", os.path.exists(excel_paths[0]))
    
    # Validate Excel styling (Frozen header row & auto-filter)
    wb = openpyxl.load_workbook(excel_paths[0])
    ws = wb.active
    test("Exporter: Excel freezes header row (A2)", ws.freeze_panes == "A2")
    test("Exporter: Excel auto-filter enabled", ws.auto_filter.ref is not None)
    test("Exporter: Excel column dimensions sized dynamically", ws.column_dimensions["A"].width is not None)
    wb.close()

    # Test JSON Export
    json_paths = exporter.export(format="json")
    test("Exporter: JSON path returned", len(json_paths) == 1 and json_paths[0].endswith(".json"))
    test("Exporter: JSON file created", os.path.exists(json_paths[0]))
    with open(json_paths[0], "r") as f:
        loaded_json = json.load(f)
    test("Exporter: JSON contains records", isinstance(loaded_json, list) and len(loaded_json) == 3 and loaded_json[0]["name"] == "Alice")

except Exception as e:
    test("Exporter: Error running tests", False, f"{e}\n{traceback.format_exc()}")


# =============================================================================
# 3. REPORT GENERATOR
# =============================================================================
section("3. Report Generator")

try:
    from refineflow.reporter import ReportGenerator
    
    mock_stats = {
        "source_file": "sample_data.csv",
        "runtime_seconds": 15.45,
        "engine_used": "Pandas",
        "partitions": 2,
        "rows_original": 100,
        "rows_final": 95,
        "columns_original": 5,
        "columns_final": 5,
        "memory_before_gb": 0.05,
        "memory_after_gb": 0.01,
        "nulls_filled_total": 12,
        "duplicates_removed_total": 5,
        "outliers_handled_total": 3,
        "type_conversions_total": 1,
        "text_columns_cleaned_total": 2,
        "exported_files": [
            "cleaned_sample_data.csv",
            "cleaned_sample_data.parquet"
        ],
        "exported_total_size_bytes": 1024 * 15,
        "columns": {
            "order_id": {"dtype": "int64", "nulls_filled": 0, "strategy": "None", "outliers_detected": 0},
            "revenue": {"dtype": "float64", "nulls_filled": 5, "strategy": "median", "outliers_detected": 2}
        },
        "low_confidence_corrections": [
            {
                "column": "revenue",
                "action": "type_converted",
                "from": "invalid",
                "to": 120.50,
                "confidence": 0.65,
                "flag": "REVIEW"
            }
        ]
    }
    
    mock_validation = {
        "cross_chunk_duplicates_removed": 1,
        "categories_standardized": 2,
        "integrity_violations_fixed": 1,
        "schema_drift_report": {
            "detected": True,
            "new_columns": ["country"],
            "removed_columns": [],
            "type_changes": {},
            "renamed_likely": []
        }
    }
    
    reporter = ReportGenerator(mock_stats, validation_report=mock_validation)
    rep_files = reporter.generate_report(format="all", output_dir=tmp_dir)
    
    test("Reporter: JSON report file generated", "json" in rep_files and os.path.exists(rep_files["json"]))
    test("Reporter: HTML report file generated", "html" in rep_files and os.path.exists(rep_files["html"]))
    
    # Read HTML report to verify structure
    with open(rep_files["html"], "r", encoding="utf-8") as f:
        html_str = f.read()
    test("Reporter: HTML report contains title", "RefineFlow Cleaning Report" in html_str)
    test("Reporter: HTML contains Low Confidence corrections", "Human Review Queue" in html_str)
    test("Reporter: HTML contains drift alert", "Schema Drift Warnings Detected" in html_str)
    test("Reporter: HTML contains memory bar percentage", "80.0% RAM Reduction" in html_str)

    # Read JSON report to verify keys
    with open(rep_files["json"], "r") as f:
        json_data = json.load(f)
    test("Reporter: JSON contains dataset summary", "dataset" in json_data)
    test("Reporter: JSON contains cleaning totals", json_data["cleaning"]["nulls_filled"] == 12)
    test("Reporter: JSON contains memory metrics", json_data["memory"]["reduction_percent"] == 80.0)

except Exception as e:
    test("Reporter: Error running tests", False, f"{e}\n{traceback.format_exc()}")


# =============================================================================
# 4. CLI COMMANDS
# =============================================================================
section("4. CLI Command-Line Interface")

try:
    from refineflow.cli import main
    runner = CliRunner()
    
    # 4.1 CLI Scan
    result_scan = runner.invoke(main, ["scan", csv_file_path])
    test("CLI: 'scan' runs successfully", result_scan.exit_code == 0)
    test("CLI: 'scan' outputs Dataset Scan Report", "Dataset Scan Report" in result_scan.output)
    
    # 4.2 CLI Recommend
    result_rec = runner.invoke(main, ["recommend", csv_file_path])
    test("CLI: 'recommend' runs successfully", result_rec.exit_code == 0)
    test("CLI: 'recommend' prints visualization recommendations", "Visualization Recommendations" in result_rec.output)
    
    # 4.3 CLI Clean
    out_clean_dir = os.path.join(tmp_dir, "cli_clean_out")
    os.makedirs(out_clean_dir, exist_ok=True)
    
    result_clean = runner.invoke(main, [
        "clean", csv_file_path,
        "--export", "parquet",
        "--report", "html",
        "--output-dir", out_clean_dir
    ])
    
    test("CLI: 'clean' runs successfully", result_clean.exit_code == 0)
    test("CLI: 'clean' displays summary card", "RefineFlow - Run Complete" in result_clean.output)
    
    # Check exported artifacts
    test("CLI: Clean generated Parquet output", os.path.exists(os.path.join(out_clean_dir, "cleaned_sample_data.parquet")))
    test("CLI: Clean generated HTML report", os.path.exists(os.path.join(out_clean_dir, "refineflow_report.html")))

except Exception as e:
    test("CLI: Error running tests", False, f"{e}\n{traceback.format_exc()}")


# =============================================================================
# 5. FULL FLUENT API CHAIN
# =============================================================================
section("5. End-to-End Fluent Chaining")

try:
    from refineflow.cleaner import Cleaner
    
    fluent_out_dir = os.path.join(tmp_dir, "fluent_out")
    os.makedirs(fluent_out_dir, exist_ok=True)
    
    # Run full chain
    cleaner = (
        Cleaner(csv_file_path, partitions=2, backend="pandas")
        .scan()
        .auto_clean()
        .optimize_memory()
        .prepare_for_powerbi(output_dir=fluent_out_dir)
        .prepare_for_tableau(output_dir=fluent_out_dir)
        .recommend_visualizations()
        .generate_report(format="all", output_dir=fluent_out_dir)
        .export(format="all", output_dir=fluent_out_dir)
    )
    
    test("Fluent API: Chain executed without error", cleaner is not None)
    test("Fluent API: Exports tracked in stats", len(cleaner.stats.get("exported_files", [])) > 0)
    test("Fluent API: Total size tracked", cleaner.stats.get("exported_total_size_bytes", 0) > 0)
    
    # Verify report is exported in the chain
    test("Fluent API: HTML report generated in folder", os.path.exists(os.path.join(fluent_out_dir, "refineflow_report.html")))
    test("Fluent API: JSON report generated in folder", os.path.exists(os.path.join(fluent_out_dir, "refineflow_report.json")))
    
    # Verify export products generated in the chain
    test("Fluent API: Parquet file generated", os.path.exists(os.path.join(fluent_out_dir, "cleaned_sample_data.parquet")))
    test("Fluent API: CSV file generated", os.path.exists(os.path.join(fluent_out_dir, "cleaned_sample_data.csv")))
    test("Fluent API: Excel file generated", os.path.exists(os.path.join(fluent_out_dir, "cleaned_sample_data.xlsx")))
    test("Fluent API: JSON file generated", os.path.exists(os.path.join(fluent_out_dir, "cleaned_sample_data.json")))

except Exception as e:
    test("Fluent API: Error running tests", False, f"{e}\n{traceback.format_exc()}")


# =============================================================================
# CLEAN UP TEMP DIRECTORY
# =============================================================================
try:
    shutil.rmtree(tmp_dir)
except Exception:
    pass


# =============================================================================
# PRINT FINAL RESULTS SUMMARY
# =============================================================================
print("\n" + "=" * 55)
print("  Module 6 Test Results Summary")
print("=" * 55)
print(f"  PASSED : {_results['pass']}")
print(f"  FAILED : {_results['fail']}")
print(f"  TOTAL  : {_results['pass'] + _results['fail']}")
print("=" * 55)

if _results["fail"] > 0:
    sys.exit(1)
else:
    sys.exit(0)
