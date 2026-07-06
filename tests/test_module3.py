"""
RefineFlow - Module 3 Comprehensive Test Suite
Tests: NullHandler, Deduplicator, TypeFixer, TextCleaner, OutlierDetector,
       MemoryOptimizer, UnitNormalizer, PerChunkValidator, CleaningPipeline, and ParallelRunner.
Run: python tests/test_module3.py
"""

import sys
if sys.stdout and hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

import os
import json
import shutil
import tempfile
import traceback
import pandas as pd
import numpy as np

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
    try:
        fn()
    except Exception as e:
        print(f"  {FAIL} {name} raised: {e}")
        traceback.print_exc()
        _results["fail"] += 1


# =============================================================================
# 1. NULL HANDLER
# =============================================================================

def test_null_handler():
    section("1. Null Handler")
    from refineflow.cleaning.null_handler import NullHandler
    from refineflow.logger import RefineLogger

    log = RefineLogger(verbose=False)

    # Test hidden null conversion & imputation
    df = pd.DataFrame({
        "num_col": [10.0, np.nan, 20.0, 30.0, np.nan],
        "cat_col": ["Apple", "Banana", "N/A", "Apple", "nil"],
        "date_col": [pd.Timestamp("2026-01-01"), pd.NaT, pd.Timestamp("2026-01-03"), pd.NaT, pd.Timestamp("2026-01-05")]
    })

    nh = NullHandler(log=log)
    cleaned = nh.run(df)

    test("Numerical nulls filled (default median = 20)", cleaned["num_col"].isnull().sum() == 0)
    test("Numerical filled with 20.0", cleaned["num_col"].iloc[1] == 20.0)
    test("Categorical 'N/A' and 'nil' replaced with NaN, then filled mode = 'Apple'", cleaned["cat_col"].isnull().sum() == 0)
    test("Categorical mode is 'Apple'", cleaned["cat_col"].iloc[2] == "Apple" and cleaned["cat_col"].iloc[4] == "Apple")
    test("Datetime nulls filled (default ffill)", cleaned["date_col"].isnull().sum() == 0)

    # Custom override
    df_over = pd.DataFrame({
        "num_col": [10.0, np.nan, 20.0]
    })
    nh_over = NullHandler(strategy_config={"num_col": "mean"}, log=log)
    cleaned_over = nh_over.run(df_over)
    test("Respects custom Mean strategy (mean = 15)", cleaned_over["num_col"].iloc[1] == 15.0)


# =============================================================================
# 2. DEDUPLICATOR
# =============================================================================

def test_deduplicator():
    section("2. Deduplicator")
    from refineflow.cleaning.deduplicator import Deduplicator
    from refineflow.logger import RefineLogger

    log = RefineLogger(verbose=False)

    df = pd.DataFrame({
        "id": [1, 2, 2, 3, 4],
        "name": ["A", "B", "B", "C", "D"],
        "val": ["X", "Y", "Z", "W", "X"] # row 2 id=2 name=B val=Z is a partial duplicate of row 1 (on id, name)
    })

    # Full deduplication
    df_dup = pd.concat([df, df.iloc[[0]]], ignore_index=True) # add complete duplicate of row 0
    dedup1 = Deduplicator(log=log)
    res1 = dedup1.run(df_dup)
    test("Removes exact duplicate rows", len(res1) == 5)

    # Subset deduplication
    dedup2 = Deduplicator(subset=["id", "name"], keep="first", log=log)
    res2 = dedup2.run(df)
    test("Removes partial duplicates based on subset", len(res2) == 4)
    test("Keeps first duplicate", res2.iloc[1]["val"] == "Y")

    # Hash-based deduplication
    dedup_hash = Deduplicator(hash_based=True, log=log)
    res_hash = dedup_hash.run(df_dup)
    test("Hash-based deduplication matches length", len(res_hash) == 5)


# =============================================================================
# 3. TYPE FIXER
# =============================================================================

def test_type_fixer():
    section("3. Type Fixer")
    from refineflow.cleaning.type_fixer import TypeFixer
    from refineflow.logger import RefineLogger

    log = RefineLogger(verbose=False)

    df = pd.DataFrame({
        "order_id": [101, 102, 103] * 10,        # ID column (int, should convert to string)
        "price": ["$12.50", "₹150.00", "$9.99"] * 10, # Currency mixed with numbers
        "discount": ["10%", "20%", "5%"] * 10,   # Percentage strings
        "active": ["Yes", "no", "TRUE"] * 10,     # Boolean inconsistency
        "date_col": ["2025-05-12", "2025/05/13", "2025-05-14"] * 10, # Date strings
        "city": ["Mumbai", "Delhi", "Mumbai"] * 10 # Low cardinality -> category candidate
    })

    tf = TypeFixer(log=log)
    res = tf.run(df)

    test("ID column converted to string/object", pd.api.types.is_string_dtype(res["order_id"]))
    test("Currency standardizes to float", pd.api.types.is_float_dtype(res["price"]) and res["price"].iloc[1] == 150.0)
    test("Percentage converted to float decimals", pd.api.types.is_float_dtype(res["discount"]) and res["discount"].iloc[0] == 0.10)
    test("Boolean standardized to bool dtype", str(res["active"].dtype) == "boolean")
    test("Boolean values correctly mapped", res["active"].iloc[0] == True and res["active"].iloc[1] == False)
    test("Date column successfully converted to datetime64", pd.api.types.is_datetime64_any_dtype(res["date_col"]))
    test("Low cardinality objects converted to category", isinstance(res["city"].dtype, pd.CategoricalDtype))


# =============================================================================
# 4. TEXT CLEANER
# =============================================================================

def test_text_cleaner():
    section("4. Text Cleaner")
    from refineflow.cleaning.text_cleaner import TextCleaner
    from refineflow.logger import RefineLogger

    log = RefineLogger(verbose=False)

    df = pd.DataFrame({
        "emp_name": ["  john  doe ", "Jane\u200b Doe", "mumbai  city"], # spacing / zero-width space
        "emp_code": ["emp_01", "emp_02", "emp_03"],
        "city": ["Mumbi", "Delhi", "Bangalor"], # Fuzzy city names
        "state": ["mh", "DL", "Pune MH"]      # Abbreviated states
    })

    tc = TextCleaner(log=log)
    res = tc.run(df)

    test("Strips and title-cases name column", res["emp_name"].iloc[0] == "John Doe")
    test("Removes zero-width space", "\u200b" not in res["emp_name"].iloc[1])
    test("Title cases other names", res["emp_name"].iloc[2] == "Mumbai City")
    test("Upper cases code column", res["emp_code"].iloc[0] == "EMP_01")
    test("Fuzzy corrects city 'Mumbi' to 'Mumbai'", res["city"].iloc[0] == "Mumbai")
    test("Fuzzy corrects city 'Bangalor' to 'Bangalore'", res["city"].iloc[2] == "Bangalore")
    test("Expands state abbreviation 'mh' to 'Maharashtra'", res["state"].iloc[0] == "Maharashtra")
    test("Expands state abbreviation inside sentence 'Pune MH' to 'Pune Maharashtra'", res["state"].iloc[2] == "Pune Maharashtra")


# =============================================================================
# 5. OUTLIER DETECTOR
# =============================================================================

def test_outlier_detector():
    section("5. Outlier Detector")
    from refineflow.cleaning.outlier_detector import OutlierDetector
    from refineflow.logger import RefineLogger

    log = RefineLogger(verbose=False)

    # Let's create a numerical series with distinct statistical outliers
    # (Needs enough elements (>=30 rows) to run)
    np.random.seed(42)
    # The ages dataset needs to check domain constraints
    # Since IQR is 0, it skips statistical outlier bounds check, leaving domain constraint values intact
    ages = [25] * 35 + [300, -50] # 37 elements total
    df = pd.DataFrame({"age": ages})

    # Test IQR + Clipping + Domain Constraint checks
    od = OutlierDetector(method="iqr", action="clip", log=log)
    res = od.run(df)

    # -50 should be clipped to 0 (hard domain constraint for age)
    # 300 should be clipped to 120 (hard domain constraint for age)
    test("Domain constraints clip negative age to 0", res["age"].min() == 0)
    test("Domain constraints clip future/excessive age to 120", res["age"].max() == 120)

    # Test Statistical IQR clipping on unconstrained column with normal variance
    salaries = [49000, 50000, 51000] * 12 + [9999999, 100]
    df_sal = pd.DataFrame({"salary": salaries})
    od_sal = OutlierDetector(method="iqr", action="clip", log=log)
    res_sal = od_sal.run(df_sal)

    test("Outliers statistical clipping applied", res_sal["salary"].max() < 9999999)
    test("Low outliers statistical clipping applied", res_sal["salary"].min() > 100)


# =============================================================================
# 6. MEMORY OPTIMIZER
# =============================================================================

def test_memory_optimizer():
    section("6. Memory Optimizer")
    from refineflow.cleaning.memory_optimizer import MemoryOptimizer
    from refineflow.logger import RefineLogger

    log = RefineLogger(verbose=False)

    df = pd.DataFrame({
        "int_col": [1, 2, 3, 4, 5] * 100,       # fits in int8
        "float_col": [1.5, 2.5, 3.5, 4.5] * 125, # float64 can become float32
        "cat_col": ["a", "b", "c", "d"] * 125    # repetition -> category candidate
    })

    mo = MemoryOptimizer(log=log)
    res, stats = mo.run(df)

    test("Downcasts integer col to int8", str(res["int_col"].dtype) in ["int8", "Int8"])
    test("Downcasts float col to float32", str(res["float_col"].dtype) == "float32")
    test("Compresses objects to category", isinstance(res["cat_col"].dtype, pd.CategoricalDtype))
    test("Saves memory by at least 30%", stats["reduction_percentage"] > 30.0)


# =============================================================================
# 7. UNIT NORMALIZER
# =============================================================================

def test_unit_normalizer():
    section("7. Unit Normalizer")
    from refineflow.cleaning.unit_normalizer import UnitNormalizer
    from refineflow.logger import RefineLogger

    log = RefineLogger(verbose=False)

    df = pd.DataFrame({
        "weight_col": ["1.5kg", "500g", "2.0 lb", "10 oz"],
        "time_col": ["10sec", "5min", "1.5hr", "100ms"]
    })

    un = UnitNormalizer(log=log)
    res = un.run(df)

    test("Normalizes kg to grams (1.5 * 1000 = 1500)", res["weight_col"].iloc[0] == 1500.0)
    test("Normalizes lb to grams (2.0 * 453.592 = 907.184)", round(res["weight_col"].iloc[2], 2) == 907.18)
    test("Normalizes min to seconds (5 * 60 = 300)", res["time_col"].iloc[1] == 300.0)
    test("Normalizes hr to seconds (1.5 * 3600 = 5400)", res["time_col"].iloc[2] == 5400.0)


# =============================================================================
# 8. PER CHUNK VALIDATOR
# =============================================================================

def test_validator():
    section("8. Per Chunk Validator")
    from refineflow.cleaning.validator import PerChunkValidator
    from refineflow.logger import RefineLogger

    log = RefineLogger(verbose=False)

    df = pd.DataFrame({
        "user_email": ["john@example.com", "invalid_email.com", "test.user@domain.org"],
        "user_age": [25, 150, 45], # 150 exceeds max age
        "user_name": ["John Doe", "Alice123", "Bob"] # Alice123 has too many digits
    })

    v = PerChunkValidator(log=log)
    res = v.run(df)

    test("Invalid email set to NaN", pd.isna(res["user_email"].iloc[1]))
    test("Valid emails remain unchanged", res["user_email"].iloc[0] == "john@example.com")
    test("Invalid age (150) set to NaN", pd.isna(res["user_age"].iloc[1]))
    test("Valid age remains unchanged", res["user_age"].iloc[0] == 25)
    test("Name with too many digits set to NaN", pd.isna(res["user_name"].iloc[1]))


# =============================================================================
# 9. CLEANING PIPELINE
# =============================================================================

def test_cleaning_pipeline():
    section("9. Cleaning Pipeline")
    from refineflow.cleaning.pipeline import CleaningPipeline
    from refineflow.logger import RefineLogger

    log = RefineLogger(verbose=False)

    df = pd.DataFrame({
        "order_id": [101, 102, 102, 103],
        "user_email": ["a@b.com", "xyz.com", "xyz.com", "c@d.com"],
        "price": ["$10.00", "$20.00", "$20.00", "₹30.00"],
        "weight": ["1kg", "2kg", "2kg", "3kg"]
    })

    pipeline = CleaningPipeline(log=log)
    cleaned, stats = pipeline.run(df)

    # Output assertions
    test("Pipeline: Deduplicated duplicates", len(cleaned) == 3)
    test("Pipeline: Converted currencies to float (or downcasted)", pd.api.types.is_numeric_dtype(cleaned["price"]))
    test("Pipeline: Normalized weights to grams", cleaned["weight"].iloc[0] == 1000.0)
    test("Pipeline: Invalid email cleaned and imputed (mode/ffill/etc.)", cleaned["user_email"].isnull().sum() == 0)
    test("Pipeline: Statistics collected", len(stats) > 0)


# =============================================================================
# 10. PARALLEL RUNNER
# =============================================================================

def test_parallel_runner():
    section("10. Parallel Runner")
    from refineflow.parallel_runner import ParallelRunner
    from refineflow.logger import RefineLogger
    from refineflow.config import CHECKPOINT_DIR

    log = RefineLogger(verbose=False)

    df1 = pd.DataFrame({"id": [1, 2], "val": ["A", "B"]})
    df2 = pd.DataFrame({"id": [3, 4], "val": ["C", "D"]})
    chunks = [df1, df2]

    # Test standard execution
    runner = ParallelRunner(chunks, log=log)
    cleaned, stats = runner.run()

    test("Parallel runner returned all chunks", len(cleaned) == 2)
    test("Aggregated stats for chunk 0 exists", "chunk_0" in stats)

    # Test fault tolerance / retry / skip
    # Add a chunk that triggers a crash
    df_crash = pd.DataFrame({"id": [5], "val": ["E"], "trigger_crash": [True]})
    chunks_with_crash = [df1, df_crash, df2]

    # Clean failed checkpoints first
    failed_dir = os.path.join(CHECKPOINT_DIR, "failed")
    if os.path.exists(failed_dir):
        shutil.rmtree(failed_dir)

    runner_ft = ParallelRunner(chunks_with_crash, log=log)
    cleaned_ft, stats_ft = runner_ft.run()

    # Should skip the crashed chunk, return remaining chunks
    test("Fault tolerance: skips crashed chunk and returns remaining 2", len(cleaned_ft) == 2)
    test("Fault tolerance: saved failed chunk parquet to cache directory", len(os.listdir(failed_dir)) == 1)

    # Cleanup failed checkpoints
    if os.path.exists(failed_dir):
        shutil.rmtree(failed_dir)


# =============================================================================
# SUMMARY
# =============================================================================

def print_summary():
    total = sum(_results.values())
    p, f, s = _results["pass"], _results["fail"], _results["skip"]
    print(f"\n{'=' * 55}")
    print(f"  Module 3 Test Results")
    print(f"{'=' * 55}")
    print(f"  {GREEN}PASSED : {p}{RESET}")
    print(f"  {RED}FAILED : {f}{RESET}")
    print(f"  {YELLOW}SKIPPED: {s}{RESET}")
    print(f"  TOTAL  : {total}")
    print(f"{'=' * 55}\n")
    if f == 0:
        print(f"{GREEN}  All tests passed! Module 3 is solid.{RESET}\n")
    else:
        print(f"{RED}  {f} test(s) failed — see details above.{RESET}\n")


if __name__ == "__main__":
    print(f"\n{CYAN}{'=' * 55}")
    print(f"  RefineFlow — Module 3 Test Suite")
    print(f"{'=' * 55}{RESET}\n")

    run_test("Null Handler",        test_null_handler)
    run_test("Deduplicator",        test_deduplicator)
    run_test("Type Fixer",          test_type_fixer)
    run_test("Text Cleaner",        test_text_cleaner)
    run_test("Outlier Detector",    test_outlier_detector)
    run_test("Memory Optimizer",    test_memory_optimizer)
    run_test("Unit Normalizer",     test_unit_normalizer)
    run_test("Per Chunk Validator", test_validator)
    run_test("Cleaning Pipeline",   test_cleaning_pipeline)
    run_test("Parallel Runner",     test_parallel_runner)

    print_summary()
