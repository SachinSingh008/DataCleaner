"""
RefineFlow - Module 2 Comprehensive Test Suite
Tests: EngineSelector, load_as_pandas, DataPartitioner, and Cleaner load integration.
Run: python tests/test_module2.py
"""

import sys
if sys.stdout and hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

import os
import json
import tempfile
import traceback
import pandas as pd
import polars as pl
import dask.dataframe as dd

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
# 1. ENGINE SELECTOR
# =============================================================================

def test_engine_selector():
    section("1. Engine Selector")
    from refineflow.engine.selector import EngineSelector
    from refineflow.logger import RefineLogger

    log = RefineLogger(verbose=False)

    # 1. Pandas Selection (< SMALL_DATA_THRESHOLD_GB and < MEDIUM_ROW_THRESHOLD)
    report_small = {"size_gb": 0.05, "rows": 50000}
    sel1 = EngineSelector(report_small, backend_override="auto", log=log)
    test("Selects Pandas for small file", sel1.select() == "Pandas")

    # 2. Polars Selection (< SMALL_DATA_THRESHOLD_GB and >= MEDIUM_ROW_THRESHOLD)
    report_med_rows = {"size_gb": 0.5, "rows": 1200000}
    sel2 = EngineSelector(report_med_rows, backend_override="auto", log=log)
    test("Selects Polars for medium rows", sel2.select() == "Polars")

    # 3. Dask Selection (SMALL_DATA_THRESHOLD_GB to BIG_DATA_THRESHOLD_GB)
    report_dask = {"size_gb": 25.0, "rows": 10000000}
    sel3 = EngineSelector(report_dask, backend_override="auto", log=log)
    test("Selects Dask for 25GB", sel3.select() == "Dask")

    # 4. Spark Selection (>= BIG_DATA_THRESHOLD_GB)
    report_spark = {"size_gb": 150.0, "rows": 100000000}
    sel4 = EngineSelector(report_spark, backend_override="auto", log=log)
    test("Selects Spark for 150GB", sel4.select() == "Spark")

    # 5. User override
    sel5 = EngineSelector(report_small, backend_override="Polars", log=log)
    test("Respects override override='Polars'", sel5.select() == "Polars")

    # 6. Invalid override fallback
    sel6 = EngineSelector(report_small, backend_override="mystery_engine", log=log)
    test("Fallback to auto when override is invalid", sel6.select() == "Pandas")


# =============================================================================
# 2. ENGINE LOADERS
# =============================================================================

def test_engine_loaders():
    section("2. Engine Loaders")
    from refineflow.engine.loader import load_as_pandas
    from refineflow.logger import RefineLogger

    log = RefineLogger(verbose=False)
    normal_csv = "tests/data/normal.csv"

    if not os.path.exists(normal_csv):
        print(f"  {SKIP} test data missing - run tests/create_test_data.py first")
        _results["skip"] += 3
        return

    # Scan report simulation
    report = {
        "format": "csv",
        "encoding": "ascii",
        "size_gb": 0.0001,
        "rows": 500
    }

    # Test load via Pandas
    df_pd = load_as_pandas(normal_csv, "pandas", report, log=log)
    test("Pandas load returns pd.DataFrame", isinstance(df_pd, pd.DataFrame))
    test("Pandas load has rows", len(df_pd) > 0)

    # Test chunked Pandas loader (by simulating size_gb >= 1.0)
    report_large = report.copy()
    report_large["size_gb"] = 2.5
    df_pd_chunked = load_as_pandas(normal_csv, "pandas", report_large, log=log)
    test("Pandas chunked load returns pd.DataFrame", isinstance(df_pd_chunked, pd.DataFrame))
    test("Pandas chunked load row count matches", len(df_pd_chunked) == len(df_pd))

    # Test load via Polars
    df_pl = load_as_pandas(normal_csv, "polars", report, log=log)
    test("Polars load converts to pd.DataFrame", isinstance(df_pl, pd.DataFrame))
    test("Polars load row count matches", len(df_pl) == len(df_pd))

    # Test load via Dask
    df_dd = load_as_pandas(normal_csv, "dask", report, log=log)
    test("Dask load converts to pd.DataFrame", isinstance(df_dd, pd.DataFrame))
    test("Dask load row count matches", len(df_dd) == len(df_pd))

    # Test load via Spark (conditional verification)
    from refineflow.engine.spark_engine import _SPARK_AVAILABLE
    if _SPARK_AVAILABLE:
        try:
            df_spark = load_as_pandas(normal_csv, "spark", report, log=log)
            test("Spark load converts to pd.DataFrame", isinstance(df_spark, pd.DataFrame))
            test("Spark load row count matches", len(df_spark) == len(df_pd))
        except Exception as e:
            test("Spark loader execution (if available) failed", False, str(e))
    else:
        # If not installed, it should fallback to Polars or raise gracefully.
        # Let's verify loader fallback logic
        fallback_df = load_as_pandas(normal_csv, "spark", report, log=log)
        test("Spark fallback to Polars when unavailable returns pd.DataFrame", isinstance(fallback_df, pd.DataFrame))
        test("Spark fallback row count matches", len(fallback_df) == len(df_pd))


# =============================================================================
# 3. DATA PARTITIONER
# =============================================================================

def test_data_partitioner():
    section("3. Data Partitioner")
    from refineflow.partitioner import DataPartitioner
    from refineflow.logger import RefineLogger
    from refineflow.config import CHECKPOINT_DIR

    log = RefineLogger(verbose=False)

    # Prepare high-row test dataframe
    data = pd.DataFrame({"col_a": range(15000), "col_b": ["val"] * 15000})

    # Test threshold (PARTITION_ROW_THRESHOLD is 10,000)
    # 1. Below threshold should skip partitioning (return 1 partition)
    small_df = data.iloc[:5000].copy()
    part_small = DataPartitioner(small_df, n_partitions=4, checkpoint=False, log=log)
    chunks_small = part_small.split()
    test("Under 10k rows skips partition (1 chunk returned)", len(chunks_small) == 1)
    test("Metadata assigned to skipped partition", chunks_small[0].attrs.get("metadata") is not None)
    test("Metadata chunk_id is 0", chunks_small[0].attrs["metadata"]["chunk_id"] == 0)

    # 2. Above threshold should partition
    part_large = DataPartitioner(data, n_partitions=4, checkpoint=False, log=log)
    chunks_large = part_large.split()
    test("Splits into 4 chunks", len(chunks_large) == 4)
    test("Chunk 0 row count correct", len(chunks_large[0]) == 3750)
    test("Chunk 3 row count correct", len(chunks_large[3]) == 3750)
    test("Chunk metadata exists", all(c.attrs.get("metadata") is not None for c in chunks_large))
    test("Chunk metadata IDs range from 0 to 3", [c.attrs["metadata"]["chunk_id"] for c in chunks_large] == [0, 1, 2, 3])

    # 3. Checkpointing and Recovery
    import shutil
    if os.path.exists(CHECKPOINT_DIR):
        shutil.rmtree(CHECKPOINT_DIR)

    report = {"fingerprint": "test_fingerprint_abc123"}
    part_cp = DataPartitioner(data, n_partitions=3, scan_report=report, checkpoint=True, log=log)
    chunks_cp = part_cp.split()
    test("Saved parquet checkpoints exist", len(os.listdir(CHECKPOINT_DIR)) == 3)

    # Re-instantiate partitioner to trigger load from checkpoints
    part_resume = DataPartitioner(None, n_partitions=3, scan_report=report, checkpoint=True, log=log)
    chunks_resumed = part_resume.split()
    test("Resumed partitioning loads 3 chunks", len(chunks_resumed) == 3)
    test("Resumed chunks metadata IDs range 0-2", [c.attrs["metadata"]["chunk_id"] for c in chunks_resumed] == [0, 1, 2])
    test("Resumed chunk size matches", len(chunks_resumed[0]) == 5000)

    # Cleanup checkpoints
    if os.path.exists(CHECKPOINT_DIR):
        shutil.rmtree(CHECKPOINT_DIR)


# =============================================================================
# SUMMARY
# =============================================================================

def print_summary():
    total = sum(_results.values())
    p, f, s = _results["pass"], _results["fail"], _results["skip"]
    print(f"\n{'=' * 55}")
    print(f"  Module 2 Test Results")
    print(f"{'=' * 55}")
    print(f"  {GREEN}PASSED : {p}{RESET}")
    print(f"  {RED}FAILED : {f}{RESET}")
    print(f"  {YELLOW}SKIPPED: {s}{RESET}")
    print(f"  TOTAL  : {total}")
    print(f"{'=' * 55}\n")
    if f == 0:
        print(f"{GREEN}  All tests passed! Module 2 is solid.{RESET}\n")
    else:
        print(f"{RED}  {f} test(s) failed — see details above.{RESET}\n")


if __name__ == "__main__":
    print(f"\n{CYAN}{'=' * 55}")
    print(f"  RefineFlow — Module 2 Test Suite")
    print(f"{'=' * 55}{RESET}\n")

    run_test("Engine Selector",     test_engine_selector)
    run_test("Engine Loaders",      test_engine_loaders)
    run_test("Data Partitioner",    test_data_partitioner)

    print_summary()
