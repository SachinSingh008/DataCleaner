"""
RefineFlow — Module 4 Comprehensive Test Suite
Tests: HierarchicalMerger, GlobalValidator (dedup, standardization, fuzzy, schema reconciliation, data integrity, final null audit), and Cleaner integration.
Run: python tests/test_module4.py
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
# 1. HIERARCHICAL MERGER
# =============================================================================

def test_hierarchical_merger():
    section("1. Hierarchical Merger")
    from refineflow.merger import HierarchicalMerger
    from refineflow.logger import RefineLogger

    log = RefineLogger(verbose=False)

    # Test 8 chunks merging
    chunks_8 = [pd.DataFrame({"a": [i], "b": [i*10]}) for i in range(8)]
    merger = HierarchicalMerger(chunks_8, log=log)
    res_8 = merger.merge()
    test("Merges 8 chunks correctly", len(res_8) == 8)
    test("Preserves all columns", list(res_8.columns) == ["a", "b"])

    # Test odd number of chunks (7)
    chunks_7 = [pd.DataFrame({"a": [i], "b": [i*10]}) for i in range(7)]
    merger_7 = HierarchicalMerger(chunks_7, log=log)
    res_7 = merger_7.merge()
    test("Merges odd number of chunks (7)", len(res_7) == 7)

    # Test mismatched schemas
    df1 = pd.DataFrame({"a": [1], "b": [2]})
    df2 = pd.DataFrame({"b": [3], "c": [4]})
    merger_mismatch = HierarchicalMerger([df1, df2], log=log)
    res_mismatch = merger_mismatch.merge()
    test("Mismatched schemas merged", len(res_mismatch) == 2)
    test("Pads missing columns with NaN", pd.isna(res_mismatch["c"].iloc[0]))
    test("Contains all columns from both", set(res_mismatch.columns) == {"a", "b", "c"})


# =============================================================================
# 2. GLOBAL VALIDATOR - DEDUPLICATION
# =============================================================================

def test_global_deduplication():
    section("2. Global Deduplication")
    from refineflow.global_validator import GlobalValidator
    from refineflow.logger import RefineLogger

    log = RefineLogger(verbose=False)

    df = pd.DataFrame({
        "id": [1, 2, 2, 3, 3],
        "name": ["A", "B", "B", "C", "D"]
    })

    validator = GlobalValidator(df, log=log)
    cleaned, stats = validator.run()

    test("Removes cross-chunk duplicates", len(cleaned) == 4)
    test("Tracks removed duplicate count", stats["cross_chunk_dupes_removed"] == 1)


# =============================================================================
# 3. GLOBAL VALIDATOR - CATEGORY STANDARDIZATION
# =============================================================================

def test_category_standardization():
    section("3. Category Standardization")
    from refineflow.global_validator import GlobalValidator
    from refineflow.logger import RefineLogger

    log = RefineLogger(verbose=False)

    df = pd.DataFrame({
        "city": ["mumbai", "Mumbai", "MUMBAI", "delhi", "delhi", "delhi", "Mumabi", "Bangalor", "Bangalore"],
    })

    # Note: 'delhi' is most frequent (3 times) so canonical.
    # 'Mumbai' is most frequent original form within lowercase 'mumbai' (2 times original vs 1 time 'mumbai'/'MUMBAI' each).
    # 'Mumabi' should fuzzy match 'Mumbai'. 'Bangalor' should fuzzy match 'Bangalore'.
    validator = GlobalValidator(df, log=log)
    cleaned, stats = validator.run()

    # Cities should be title cased
    unique_cities = set(cleaned["city"].dropna())
    test("Case variants standardized to canonical representation", "Mumbai" in unique_cities)
    test("Fuzzy typos corrected ('Mumabi' -> 'Mumbai')", "Mumabi" not in unique_cities)
    test("Fuzzy typos corrected ('Bangalor' -> 'Bangalore')", "Bangalor" not in unique_cities)
    test("Standardized values are title cased", all(c[0].isupper() for c in unique_cities))


# =============================================================================
# 4. GLOBAL VALIDATOR - SCHEMA RECONCILIATION
# =============================================================================

def test_schema_reconciliation():
    section("4. Schema Reconciliation")
    from refineflow.global_validator import GlobalValidator
    from refineflow.logger import RefineLogger

    log = RefineLogger(verbose=False)

    df = pd.DataFrame({"a": [1, 2], "b": [3, 4]})
    scan_report = {"column_names": ["a", "b", "c"]} # 'c' is missing

    validator = GlobalValidator(df, scan_report=scan_report, log=log)
    cleaned, stats = validator.run()

    test("Detects missing columns", "c" in stats["schema"]["missing"])
    test("Counts expected and present columns", stats["schema"]["expected"] == 3 and stats["schema"]["present"] == 2)


# =============================================================================
# 5. GLOBAL VALIDATOR - DATA INTEGRITY
# =============================================================================

def test_data_integrity():
    section("5. Data Integrity")
    from refineflow.global_validator import GlobalValidator
    from refineflow.logger import RefineLogger

    log = RefineLogger(verbose=False)

    df = pd.DataFrame({
        "age": [25, 150, -5],
        "email_address": ["a@b.com", "invalid-email", "c@d.com"],
        "phone_number": ["98765 43210", "+1-555-0199", "abc123xyz"],
        "rating": [4.5, 6.0, 3.0]
    })

    custom_rules = {
        "rating": {"min": 0, "max": 5}
    }
    config = {"custom_rules": custom_rules, "skip_null_audit": True}

    validator = GlobalValidator(df, config=config, log=log)
    cleaned, stats = validator.run()

    # Out of bounds age should be replaced with NaN
    test("Age constraints flag/remove invalid age (>120)", pd.isna(cleaned["age"].iloc[1]))
    test("Age constraints flag/remove negative age (<0)", pd.isna(cleaned["age"].iloc[2]))

    # Invalid email replaced with NaN
    test("Email regex replaces invalid email", pd.isna(cleaned["email_address"].iloc[1]))
    test("Email regex keeps valid email", cleaned["email_address"].iloc[0] == "a@b.com")

    # Phone normalization
    test("Phone normalization strips spaces/hyphens", cleaned["phone_number"].iloc[0] == "9876543210")
    test("Phone normalization keeps leading +", cleaned["phone_number"].iloc[1] == "+15550199")

    # Custom rules rating validation
    test("Custom rules enforce bounds (rating <= 5)", pd.isna(cleaned["rating"].iloc[1]))


# =============================================================================
# 6. GLOBAL VALIDATOR - FINAL NULL AUDIT
# =============================================================================

def test_final_null_audit():
    section("6. Final Null Audit")
    from refineflow.global_validator import GlobalValidator
    from refineflow.logger import RefineLogger

    log = RefineLogger(verbose=False)

    df = pd.DataFrame({
        "age": [30.0, np.nan, 40.0],
        "city": ["Mumbai", np.nan, "Delhi"]
    })

    validator = GlobalValidator(df, log=log)
    cleaned, stats = validator.run()

    # Age null filled with median (35.0)
    test("Numerical null filled with column median", cleaned["age"].iloc[1] == 35.0)
    # City null filled with "Unknown"
    test("Categorical null filled with 'Unknown'", cleaned["city"].iloc[1] == "Unknown")
    test("Final null count is 0", stats["final_null_count"] == 0)


# =============================================================================
# 7. CLEANER INTEGRATION (Fluent API Auto Clean)
# =============================================================================

def test_cleaner_integration():
    section("7. Cleaner Auto Clean Integration")
    from refineflow.cleaner import Cleaner

    temp_dir = tempfile.mkdtemp()
    try:
        csv_path = os.path.join(temp_dir, "test_data.csv")
        df = pd.DataFrame({
            "order_id": [101, 102, 102, 103],
            "user_email": ["a@b.com", "xyz.com", "xyz.com", "c@d.com"],
            "price": ["$10.00", "$20.00", "$20.00", "₹30.00"],
            "weight": ["1kg", "2kg", "2kg", "3kg"]
        })
        df.to_csv(csv_path, index=False)

        cleaner = Cleaner(csv_path, partitions=2, verbose=False)
        cleaner.scan()
        cleaner.auto_clean()

        # Check results
        test("auto_clean executes full pipeline successfully", cleaner.df is not None)
        test("Deduplication run globally", len(cleaner.df) == 3)
        test("Global validation stats collected", "global_validation" in cleaner.stats)
    finally:
        shutil.rmtree(temp_dir)


# =============================================================================
# RUN ALL
# =============================================================================

if __name__ == "__main__":
    print(f"\n=======================================================")
    print(f"  RefineFlow — Module 4 Test Suite")
    print(f"=======================================================")

    try:
        test_hierarchical_merger()
        test_global_deduplication()
        test_category_standardization()
        test_schema_reconciliation()
        test_data_integrity()
        test_final_null_audit()
        test_cleaner_integration()
    except Exception as e:
        print(f"\n{RED}Test execution crashed!{RESET}")
        traceback.print_exc()
        sys.exit(1)

    print(f"\n=======================================================")
    print(f"  Module 4 Test Results")
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
        print(f"  {GREEN}All tests passed! Module 4 is solid.{RESET}\n")
        sys.exit(0)
