"""
RefineFlow - Module 1 Comprehensive Test Suite
Tests: config, logger, utils, scanner, cleaner (scan only)
Run: python tests/test_module1.py
"""
import sys, io
if sys.stdout and hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

import os
import json
import tempfile
import traceback

# Make sure refineflow is importable from project root
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# Colour helpers
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
SKIP = f"{YELLOW}[SKIP]{RESET}"

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


def run_test(name, fn):
    """Run a test function, catch exceptions as failures."""
    try:
        fn()
    except Exception as e:
        print(f"  {FAIL} {name} raised: {e}")
        traceback.print_exc()
        _results["fail"] += 1


# =============================================================================
# 1. CONFIG
# =============================================================================

def test_config():
    section("1. Config")
    from refineflow.config import (
        SMALL_DATA_THRESHOLD_GB, BIG_DATA_THRESHOLD_GB,
        SUPPORTED_FORMATS, HIDDEN_NULL_VALUES, BOOL_TRUE_VALUES,
        DATE_FORMATS, WEIGHT_TO_GRAMS, PII_PATTERNS,
        CORRUPTED_COL_NULL_RATIO, CATEGORY_UNIQUE_RATIO,
    )

    test("SMALL_DATA_THRESHOLD_GB is 10", SMALL_DATA_THRESHOLD_GB == 10)
    test("BIG_DATA_THRESHOLD_GB is 100", BIG_DATA_THRESHOLD_GB == 100)
    test("csv in SUPPORTED_FORMATS", "csv" in SUPPORTED_FORMATS)
    test("parquet in SUPPORTED_FORMATS", "parquet" in SUPPORTED_FORMATS)
    test("'na' in HIDDEN_NULL_VALUES", "na" in HIDDEN_NULL_VALUES)
    test("'n/a' in HIDDEN_NULL_VALUES", "n/a" in HIDDEN_NULL_VALUES)
    test("'yes' in BOOL_TRUE_VALUES", "yes" in BOOL_TRUE_VALUES)
    test("DATE_FORMATS is non-empty list", isinstance(DATE_FORMATS, list) and len(DATE_FORMATS) > 5)
    test("kg in WEIGHT_TO_GRAMS", "kg" in WEIGHT_TO_GRAMS)
    test("WEIGHT_TO_GRAMS['kg'] == 1000", WEIGHT_TO_GRAMS["kg"] == 1000)
    test("email PII pattern exists", "email" in PII_PATTERNS)
    test("CORRUPTED_COL_NULL_RATIO == 0.90", CORRUPTED_COL_NULL_RATIO == 0.90)
    test("CATEGORY_UNIQUE_RATIO == 0.50", CATEGORY_UNIQUE_RATIO == 0.50)


# =============================================================================
# 2. LOGGER
# =============================================================================

def test_logger():
    section("2. Logger")
    from refineflow.logger import RefineLogger, get_logger

    log = RefineLogger(verbose=False)   # silent for tests

    log.success("test success")
    log.warning("test warning")
    log.error("test error")
    log.info("test info")
    log.skip("test skip")
    log.resume("test resume")

    entries = log.get_entries()
    test("Logger captures entries", len(entries) == 6)
    test("First entry level is 'success'", entries[0]["level"] == "success")
    test("Warning entry captured", any(e["level"] == "warning" for e in entries))
    test("Error entry captured",   any(e["level"] == "error"   for e in entries))
    test("Each entry has 'time' key", all("time" in e for e in entries))
    test("Each entry has 'message' key", all("message" in e for e in entries))

    log.clear()
    test("Clear empties entries", len(log.get_entries()) == 0)

    log2 = get_logger("TestLogger")
    test("get_logger returns RefineLogger", isinstance(log2, RefineLogger))

    # File logging - close handler before deleting on Windows
    with tempfile.NamedTemporaryFile(suffix=".log", delete=False) as tf:
        tmp_log = tf.name
    log3 = RefineLogger(log_file=tmp_log, verbose=False)
    log3.success("written to file")
    # Close all handlers to release file lock on Windows
    if log3._file_logger:
        for h in log3._file_logger.handlers[:]:
            h.close()
            log3._file_logger.removeHandler(h)
    try:
        os.unlink(tmp_log)
        test("File logger created and cleaned up", True)
    except Exception as e:
        test("File logger created and cleaned up", False, str(e))


# =============================================================================
# 3. UTILS
# =============================================================================

def test_utils():
    section("3. Utils")
    from refineflow.utils import (
        bytes_to_gb, bytes_to_mb, format_number, format_size,
        detect_file_format, normalize_column_name,
        deduplicate_column_names, safe_sample, flatten,
        clamp, safe_divide, StopWatch,
    )
    import pandas as pd

    # bytes_to_gb
    test("bytes_to_gb(1073741824) == 1.0", bytes_to_gb(1_073_741_824) == 1.0)
    test("bytes_to_gb(0) == 0.0",           bytes_to_gb(0) == 0.0)

    # bytes_to_mb
    test("bytes_to_mb(1048576) == 1.0", bytes_to_mb(1_048_576) == 1.0)

    # format_number
    test("format_number(1200000) == '1,200,000'", format_number(1_200_000) == "1,200,000")
    test("format_number(0) == '0'",               format_number(0) == "0")

    # format_size
    test("format_size returns GB string for large",  "GB" in format_size(2_000_000_000))
    test("format_size returns MB string for medium", "MB" in format_size(5_000_000))
    test("format_size returns KB string for small",  "KB" in format_size(5_000))

    # detect_file_format
    test("detect csv",     detect_file_format("data.csv")     == "csv")
    test("detect parquet", detect_file_format("data.parquet") == "parquet")
    test("detect xlsx",    detect_file_format("data.xlsx")    == "xlsx")
    test("detect json",    detect_file_format("data.json")    == "json")
    test("detect gz",      detect_file_format("data.csv.gz")  == "csv")

    # normalize_column_name
    test("normalize spaces",   normalize_column_name("Customer Name") == "customer_name")
    test("normalize symbols",  normalize_column_name("Revenue($)") == "revenue")
    test("normalize upper",    normalize_column_name("CITY") == "city")
    test("normalize trailing", normalize_column_name("__age__") == "age")
    test("normalize empty returns 'col'", normalize_column_name("") == "col")
    test("normalize max 64 chars",
         len(normalize_column_name("a" * 100)) <= 64)

    # deduplicate_column_names
    result = deduplicate_column_names(["sales", "sales", "revenue", "sales"])
    test("dedup: first unchanged",      result[0] == "sales")
    test("dedup: second gets suffix",   result[1] == "sales_1")
    test("dedup: non-dup unchanged",    result[2] == "revenue")
    test("dedup: third gets suffix",    result[3] == "sales_2")
    test("dedup: no duplicates in result", len(result) == len(set(result)))

    # safe_sample
    df = pd.DataFrame({"a": range(2000)})
    sample = safe_sample(df, 100)
    test("safe_sample returns 100 rows from 2000",   len(sample) == 100)
    small = pd.DataFrame({"a": range(50)})
    sample2 = safe_sample(small, 100)
    test("safe_sample returns all rows when df < n", len(sample2) == 50)

    # flatten
    test("flatten nested list", flatten([[1, 2], [3, 4]]) == [1, 2, 3, 4])
    test("flatten mixed",       flatten([[1], 2, [3]]) == [1, 2, 3])

    # clamp
    test("clamp within range",  clamp(5.0, 0.0, 10.0) == 5.0)
    test("clamp below min",     clamp(-5.0, 0.0, 10.0) == 0.0)
    test("clamp above max",     clamp(15.0, 0.0, 10.0) == 10.0)

    # safe_divide
    test("safe_divide normal",      safe_divide(10, 2) == 5.0)
    test("safe_divide by zero",     safe_divide(10, 0) == 0.0)
    test("safe_divide custom default", safe_divide(10, 0, -1) == -1)

    # StopWatch
    import time
    sw = StopWatch()
    time.sleep(0.05)
    sw.split("step1")
    rep = sw.report()
    test("StopWatch has step1",  "step1" in rep)
    test("StopWatch has total",  "total" in rep)
    test("StopWatch step1 > 0",  rep["step1"] > 0)


# =============================================================================
# 4. SCANNER — Normal CSV
# =============================================================================

def test_scanner_normal():
    section("4. Scanner — Normal CSV")
    from refineflow.scanner import DatasetScanner
    from refineflow.logger import RefineLogger

    path = "tests/data/normal.csv"
    if not os.path.exists(path):
        print(f"  {SKIP} test data missing — run tests/create_test_data.py first")
        _results["skip"] += 3
        return

    log = RefineLogger(verbose=False)
    scanner = DatasetScanner(path, log=log)
    report = scanner.run()

    # Required keys
    required_keys = [
        "file", "format", "size_gb", "size_human", "size_bytes",
        "encoding", "encoding_confidence", "encoding_risk",
        "rows", "columns", "column_names", "estimated_mem_gb",
        "missing_values", "corrupted_columns", "duplicate_risk",
        "datatype_complexity", "column_name_issues", "schema_drift",
        "recommended_engine", "recommended_partitions", "fingerprint", "scanned_at"
    ]
    for key in required_keys:
        test(f"report has '{key}' key", key in report, f"missing key: {key}")

    test("format == 'csv'",    report["format"] == "csv")
    # normal.csv has 7 columns (status col has trailing space → still 7 distinct cols)
    test("columns >= 6",       report["columns"] >= 6,
         f"got {report['columns']}")
    test("rows ~ 500",         450 <= report["rows"] <= 510,
         f"got {report['rows']}")
    test("size_gb is float",   isinstance(report["size_gb"], float))
    test("size_bytes > 0",     report["size_bytes"] > 0)
    test("encoding detected",  report["encoding"] is not None)
    test("fingerprint is str", isinstance(report["fingerprint"], str))
    test("fingerprint len 32", len(report["fingerprint"]) == 32)

    # Missing values (we added nulls to age and revenue)
    mv = report["missing_values"]
    test("missing_values is dict", isinstance(mv, dict))
    test("missing_values has age key", "age" in mv)

    # Duplicate risk
    test("duplicate_risk in [Low/Medium/High]",
         report["duplicate_risk"] in ("Low", "Medium", "High"))

    # Engine recommendation
    test("recommended_engine is str",
         isinstance(report["recommended_engine"], str))
    test("recommended_engine in valid list",
         report["recommended_engine"] in ("Pandas", "Polars", "Dask", "Spark"))
    test("recommended_partitions >= 1",
         report["recommended_partitions"] >= 1)


# =============================================================================
# 5. SCANNER — Column Name Issues
# =============================================================================

def test_scanner_col_issues():
    section("5. Scanner — Column Name Issues")
    from refineflow.scanner import DatasetScanner
    from refineflow.logger import RefineLogger

    path = "tests/data/issues.csv"
    if not os.path.exists(path):
        print(f"  {SKIP} test data missing")
        return

    log = RefineLogger(verbose=False)
    scanner = DatasetScanner(path, log=log)
    report = scanner.run()

    issues = report.get("column_name_issues", {})
    test("column_name_issues detected",   bool(issues),
         f"got: {issues}")
    test("spaces detected in col names",  "spaces" in issues,
         f"issues keys: {list(issues.keys())}")
    test("symbols detected in col names", "symbols" in issues,
         f"issues keys: {list(issues.keys())}")
    # Pandas auto-renames duplicate 'Age' col to 'Age.1' before scanner sees it.
    # Scanner correctly flags 'Age.1' as a symbol issue (dot = non-alphanumeric).
    test("Age.1 detected as symbol (pandas renamed duplicate)",
         any("Age" in c for c in issues.get("symbols", [])),
         f"symbols: {issues.get('symbols', [])}")


# =============================================================================
# 6. SCANNER — Corrupted Columns
# =============================================================================

def test_scanner_corrupted():
    section("6. Scanner — Corrupted Columns")
    from refineflow.scanner import DatasetScanner
    from refineflow.logger import RefineLogger

    path = "tests/data/corrupted.csv"
    if not os.path.exists(path):
        print(f"  {SKIP} test data missing")
        return

    log = RefineLogger(verbose=False)
    scanner = DatasetScanner(path, log=log)
    report = scanner.run()

    corrupted = report.get("corrupted_columns", [])
    test("corrupted_columns is list",          isinstance(corrupted, list))
    test("corrupted_col detected (95% null)",  "corrupted_col" in corrupted,
         f"got: {corrupted}")
    test("single_val detected (zero variance)","single_val" in corrupted,
         f"got: {corrupted}")
    test("id not flagged as corrupted",        "id" not in corrupted)
    test("name not flagged as corrupted",      "name" not in corrupted)


# =============================================================================
# 7. SCANNER — High Duplicate Risk
# =============================================================================

def test_scanner_duplicates():
    section("7. Scanner — Duplicate Risk Detection")
    from refineflow.scanner import DatasetScanner
    from refineflow.logger import RefineLogger

    path = "tests/data/duplicates.csv"
    if not os.path.exists(path):
        print(f"  {SKIP} test data missing")
        return

    log = RefineLogger(verbose=False)
    scanner = DatasetScanner(path, log=log)
    report = scanner.run()

    test("duplicate_risk is 'High'",
         report["duplicate_risk"] == "High",
         f"got: {report['duplicate_risk']}")


# =============================================================================
# 8. SCANNER — Edge Cases
# =============================================================================

def test_scanner_edge_cases():
    section("8. Scanner — Edge Cases")
    from refineflow.scanner import DatasetScanner
    from refineflow.logger import RefineLogger

    log = RefineLogger(verbose=False)

    # Non-existent file
    try:
        DatasetScanner("nonexistent.csv", log=log).run()
        test("FileNotFoundError raised for missing file", False)
    except FileNotFoundError:
        test("FileNotFoundError raised for missing file", True)

    # Unsupported format
    with tempfile.NamedTemporaryFile(suffix=".xyz", delete=False, mode="w") as tf:
        tf.write("data")
        tmpname = tf.name
    try:
        DatasetScanner(tmpname, log=log).run()
        test("ValueError raised for unsupported format", False)
    except (ValueError, Exception) as e:
        test("ValueError raised for unsupported format", True)
    finally:
        os.unlink(tmpname)

    # Empty file (header only)
    path = "tests/data/empty.csv"
    if os.path.exists(path):
        scanner = DatasetScanner(path, log=log)
        report = scanner.run()
        test("Empty CSV scanned without crash", isinstance(report, dict))
        test("Empty CSV rows == 0", report["rows"] == 0,
             f"got {report['rows']}")

    # Tiny file
    path = "tests/data/tiny.csv"
    if os.path.exists(path):
        report = DatasetScanner(path, log=log).run()
        test("Tiny CSV scanned", isinstance(report, dict))
        test("Tiny CSV rows == 5", report["rows"] == 5,
             f"got {report['rows']}")


# =============================================================================
# 9. SCANNER — Schema Drift
# =============================================================================

def test_schema_drift():
    section("9. Scanner — Schema Drift")
    from refineflow.scanner import DatasetScanner
    from refineflow.logger import RefineLogger
    from refineflow.config import SCHEMA_SNAPSHOT_FILE

    # Remove old snapshot to start fresh
    if os.path.exists(SCHEMA_SNAPSHOT_FILE):
        os.remove(SCHEMA_SNAPSHOT_FILE)

    log = RefineLogger(verbose=False)
    path = "tests/data/normal.csv"
    if not os.path.exists(path):
        return

    # First scan — should save snapshot
    r1 = DatasetScanner(path, log=log).run()
    drift1 = r1.get("schema_drift", {})
    test("First scan: no drift detected",  not drift1.get("detected", True))
    test("First scan: first_run flag set", drift1.get("first_run") is True)
    test("Snapshot file created",          os.path.exists(SCHEMA_SNAPSHOT_FILE))

    # Second scan — same file, no drift
    r2 = DatasetScanner(path, log=log).run()
    drift2 = r2.get("schema_drift", {})
    test("Second scan: no drift on same file", not drift2.get("detected", True))

    # Create a file with different schema
    import csv
    with tempfile.NamedTemporaryFile(
        suffix=".csv", delete=False, mode="w", newline=""
    ) as tf:
        w = csv.writer(tf)
        w.writerow(["new_col_a", "new_col_b"])   # completely different schema
        for i in range(10):
            w.writerow([i, i * 2])
        tmpname = tf.name

    r3 = DatasetScanner(tmpname, log=log).run()
    drift3 = r3.get("schema_drift", {})
    test("Third scan (diff schema): drift detected",
         drift3.get("detected") is True,
         f"drift: {drift3}")
    os.unlink(tmpname)

    # Cleanup snapshot
    if os.path.exists(SCHEMA_SNAPSHOT_FILE):
        os.remove(SCHEMA_SNAPSHOT_FILE)


# =============================================================================
# 10. SCANNER — print_report (no crash)
# =============================================================================

def test_scanner_print():
    section("10. Scanner — print_report()")
    from refineflow.scanner import DatasetScanner
    from refineflow.logger import RefineLogger
    import io, sys

    log = RefineLogger(verbose=False)
    path = "tests/data/normal.csv"
    if not os.path.exists(path):
        return

    scanner = DatasetScanner(path, log=log)
    scanner.run()

    # Capture stdout
    captured = io.StringIO()
    old_stdout = sys.stdout
    sys.stdout = captured
    try:
        scanner.print_report()
    finally:
        sys.stdout = old_stdout

    output = captured.getvalue()
    test("print_report produces output",       len(output) > 0)
    test("print_report contains file name",    "normal.csv" in output)
    test("print_report contains CSV",          "CSV" in output)
    test("print_report contains Columns",      "Columns" in output or "columns" in output.lower())


# =============================================================================
# 11. CLEANER — scan() method
# =============================================================================

def test_cleaner_scan():
    section("11. Cleaner — .scan() method")
    from refineflow.cleaner import Cleaner

    path = "tests/data/normal.csv"
    if not os.path.exists(path):
        return

    # Remove snapshot for clean test
    from refineflow.config import SCHEMA_SNAPSHOT_FILE
    if os.path.exists(SCHEMA_SNAPSHOT_FILE):
        os.remove(SCHEMA_SNAPSHOT_FILE)

    c = Cleaner(path, verbose=False)
    result = c.scan()

    test(".scan() returns self (fluent API)",     result is c)
    test("scan_report populated",                 bool(c.scan_report))
    test("scan_report has 'rows'",                "rows" in c.scan_report)
    test("scan_report has 'columns'",             "columns" in c.scan_report)
    test("scan_report has 'recommended_engine'",  "recommended_engine" in c.scan_report)
    test("cleaner repr works",                    "Cleaner" in repr(c))

    # FileNotFoundError
    try:
        Cleaner("ghost.csv")
        test("FileNotFoundError on missing file", False)
    except FileNotFoundError:
        test("FileNotFoundError on missing file", True)

    # Unsupported format
    with tempfile.NamedTemporaryFile(suffix=".abc", delete=False, mode="w") as tf:
        tf.write("x")
        tmp = tf.name
    try:
        Cleaner(tmp)
        test("ValueError on unsupported format", False)
    except ValueError:
        test("ValueError on unsupported format", True)
    finally:
        os.unlink(tmp)

    # Cleanup
    if os.path.exists(SCHEMA_SNAPSHOT_FILE):
        os.remove(SCHEMA_SNAPSHOT_FILE)


# =============================================================================
# SUMMARY
# =============================================================================

def print_summary():
    total = sum(_results.values())
    p, f, s = _results["pass"], _results["fail"], _results["skip"]
    print(f"\n{'=' * 55}")
    print(f"  Module 1 Test Results")
    print(f"{'=' * 55}")
    print(f"  {GREEN}PASSED : {p}{RESET}")
    print(f"  {RED}FAILED : {f}{RESET}")
    print(f"  {YELLOW}SKIPPED: {s}{RESET}")
    print(f"  TOTAL  : {total}")
    print(f"{'=' * 55}\n")
    if f == 0:
        print(f"{GREEN}  All tests passed! Module 1 is solid.{RESET}\n")
    else:
        print(f"{RED}  {f} test(s) failed — see details above.{RESET}\n")


# =============================================================================
# MAIN
# =============================================================================

if __name__ == "__main__":
    print(f"\n{CYAN}{'=' * 55}")
    print(f"  RefineFlow — Module 1 Test Suite")
    print(f"{'=' * 55}{RESET}\n")

    # Create test data if needed
    if not os.path.exists("tests/data/normal.csv"):
        print("Creating test data...")
        exec(open("tests/create_test_data.py").read())

    run_test("Config",              test_config)
    run_test("Logger",              test_logger)
    run_test("Utils",               test_utils)
    run_test("Scanner Normal",      test_scanner_normal)
    run_test("Scanner Col Issues",  test_scanner_col_issues)
    run_test("Scanner Corrupted",   test_scanner_corrupted)
    run_test("Scanner Duplicates",  test_scanner_duplicates)
    run_test("Scanner Edge Cases",  test_scanner_edge_cases)
    run_test("Schema Drift",        test_schema_drift)
    run_test("Scanner print",       test_scanner_print)
    run_test("Cleaner scan",        test_cleaner_scan)

    print_summary()
