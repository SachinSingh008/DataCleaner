"""
RefineFlow — Dataset Scanner
Scans a file BEFORE loading to produce a full scan report.
"""

import os
import json
import hashlib
from pathlib import Path
from typing import Optional
from datetime import datetime

import pandas as pd
import numpy as np

try:
    import chardet
    _CHARDET = True
except ImportError:
    _CHARDET = False

from refineflow.config import (
    ENCODING_SAMPLE_BYTES, ENCODING_CONFIDENCE_MIN,
    SCAN_SAMPLE_ROWS, DUPLICATE_PROBE_ROWS,
    CORRUPTED_COL_NULL_RATIO, SMALL_DATA_THRESHOLD_GB,
    BIG_DATA_THRESHOLD_GB, MEDIUM_ROW_THRESHOLD,
    SCHEMA_SNAPSHOT_FILE,
)
from refineflow.utils import (
    bytes_to_gb, format_size, count_csv_rows,
    memory_usage_gb, file_fingerprint, detect_file_format,
)
from refineflow.logger import RefineLogger


class DatasetScanner:
    """
    Scans a dataset file and returns a detailed scan_report dict.

    Usage:
        scanner = DatasetScanner("sales.csv")
        report  = scanner.run()
        scanner.print_report()
    """

    def __init__(self, filepath: str, log: Optional[RefineLogger] = None):
        self.filepath = filepath
        self.log = log or RefineLogger()
        self._report: dict = {}

    def run(self) -> dict:
        self.log.section("Dataset Scanner")

        if not os.path.exists(self.filepath):
            raise FileNotFoundError(f"File not found: {self.filepath}")

        fmt = detect_file_format(self.filepath)
        if fmt not in ["csv", "tsv", "xlsx", "xls", "parquet", "json"]:
            raise ValueError(f"Unsupported file format: .{fmt}")
        self.log.info(f"Scanning: {self.filepath}")

        r = {}
        r["file"]        = os.path.basename(self.filepath)
        r["path"]        = self.filepath
        r["format"]      = fmt
        r["size_bytes"]  = os.path.getsize(self.filepath)
        r["size_gb"]     = bytes_to_gb(r["size_bytes"])
        # Store raw bytes for accurate > 0 check regardless of rounding
        r["size_bytes_raw"] = r["size_bytes"]
        r["size_human"]  = format_size(r["size_bytes"])
        r["fingerprint"] = file_fingerprint(self.filepath)
        r["scanned_at"]  = datetime.now().isoformat()

        enc, conf = self._detect_encoding()
        r["encoding"]            = enc
        r["encoding_confidence"] = conf
        r["encoding_risk"]       = "HIGH" if conf < ENCODING_CONFIDENCE_MIN else "LOW"

        r["rows"] = self._estimate_row_count(fmt, enc)

        sample = self._load_sample(fmt, enc)

        r["columns"]         = len(sample.columns)
        r["column_names"]    = list(sample.columns)
        r["estimated_mem_gb"] = round(
            memory_usage_gb(sample) / max(len(sample), 1) * r["rows"], 3
        )

        r["missing_values"]      = self._missing_value_map(sample)
        r["corrupted_columns"]   = self._find_corrupted(sample)
        r["duplicate_risk"]      = self._duplicate_risk(sample)
        r["datatype_complexity"] = self._complexity(sample)
        r["column_name_issues"]  = self._col_name_issues(sample)
        r["schema_drift"]        = self._schema_drift(sample)

        r["recommended_engine"]     = self._recommend_engine(r)
        r["recommended_partitions"] = self._recommend_partitions(r)

        self._report = r
        self.log.success(
            f"Scan complete — {r['size_human']}, "
            f"{r['rows']:,} rows, {r['columns']} cols"
        )
        return r

    def print_report(self) -> None:
        r = self._report
        if not r:
            return

        corrupt  = ", ".join(r["corrupted_columns"]) if r["corrupted_columns"] else "None"
        dup_icon = "[!!]" if r["duplicate_risk"] == "High" else "[OK]"
        enc_icon = "[!!]" if r["encoding_risk"]  == "HIGH" else "[OK]"
        bar      = "=" * 52

        print(f"\n{bar}")
        print(f"  RefineFlow - Dataset Scan Report")
        print(f"{bar}")
        print(f"  File:          {r['file']}")
        print(f"  Format:        {r['format'].upper()}")
        print(f"  Size:          {r['size_human']}")
        print(f"  Rows (est.):   {r['rows']:,}")
        print(f"  Columns:       {r['columns']}")
        print(f"  Est. Memory:   {r['estimated_mem_gb']} GB")
        print(f"  Encoding: {enc_icon} {r['encoding']} (conf: {r['encoding_confidence']})")
        print(f"  Corrupt Cols:  {corrupt}")
        print(f"  Dupe Risk: {dup_icon} {r['duplicate_risk']}")
        print(f"  Complexity:    {r['datatype_complexity']}")
        print(f"  Recommended:   {r['recommended_engine']} | {r['recommended_partitions']} partitions")
        print(f"{bar}\n")

        mv = {k: f"{v:.1%}" for k, v in r["missing_values"].items() if v > 0}
        if mv:
            print(f"  Missing Values: {mv}")

        drift = r.get("schema_drift", {})
        if drift.get("detected"):
            print("\n  ⚠ Schema Drift Detected!")
            if drift.get("removed_columns"):
                print(f"    Removed:  {drift['removed_columns']}")
            if drift.get("new_columns"):
                print(f"    New:      {drift['new_columns']}")
            if drift.get("type_changes"):
                print(f"    Types:    {drift['type_changes']}")

    # ── Private ───────────────────────────────────────────────────────────────

    def _detect_encoding(self) -> tuple:
        if not _CHARDET:
            return "utf-8", 1.0
        try:
            with open(self.filepath, "rb") as f:
                raw = f.read(ENCODING_SAMPLE_BYTES)
            result = chardet.detect(raw)
            return result.get("encoding") or "utf-8", round(result.get("confidence") or 0.5, 3)
        except Exception:
            return "utf-8", 0.5

    def _estimate_row_count(self, fmt: str, enc: str) -> int:
        try:
            if fmt in ("csv", "tsv"):
                return count_csv_rows(self.filepath)
            elif fmt == "parquet":
                import pyarrow.parquet as pq
                return pq.read_metadata(self.filepath).num_rows
            elif fmt == "json":
                return len(pd.read_json(self.filepath))
        except Exception:
            pass
        return -1

    def _load_sample(self, fmt: str, enc: str) -> pd.DataFrame:
        try:
            if fmt in ("csv", "tsv"):
                sep = "\t" if fmt == "tsv" else ","
                return pd.read_csv(self.filepath, nrows=SCAN_SAMPLE_ROWS,
                                   encoding=enc, sep=sep,
                                   on_bad_lines="warn", low_memory=False)
            elif fmt == "parquet":
                return pd.read_parquet(self.filepath).head(SCAN_SAMPLE_ROWS)
            elif fmt in ("xlsx", "xls"):
                return pd.read_excel(self.filepath, nrows=SCAN_SAMPLE_ROWS)
            elif fmt == "json":
                return pd.read_json(self.filepath).head(SCAN_SAMPLE_ROWS)
        except UnicodeDecodeError:
            return pd.read_csv(self.filepath, nrows=SCAN_SAMPLE_ROWS,
                               encoding="latin-1", on_bad_lines="warn")
        except Exception as e:
            self.log.warning(f"Sample load failed: {e}")
        return pd.DataFrame()

    def _missing_value_map(self, df: pd.DataFrame) -> dict:
        return {col: round(df[col].isnull().mean(), 4) for col in df.columns}

    def _find_corrupted(self, df: pd.DataFrame) -> list:
        out = []
        for col in df.columns:
            if df[col].isnull().mean() >= CORRUPTED_COL_NULL_RATIO:
                out.append(col)
            elif df[col].nunique(dropna=True) <= 1 and len(df) > 1:
                out.append(col)
        return out

    def _duplicate_risk(self, df: pd.DataFrame) -> str:
        sample = df.head(DUPLICATE_PROBE_ROWS).fillna("").astype(str)
        hashes = sample.apply(
            lambda row: hashlib.md5("".join(row.values).encode()).hexdigest(), axis=1
        )
        total = len(hashes)
        ratio = (total - hashes.nunique()) / total if total else 0
        return "High" if ratio >= 0.10 else "Medium" if ratio >= 0.02 else "Low"

    def _complexity(self, df: pd.DataFrame) -> str:
        if df.empty:
            return "Unknown"
        ratio = df.select_dtypes("object").shape[1] / len(df.columns)
        return "Complex" if ratio >= 0.5 else "Mixed" if ratio > 0 else "Simple"

    def _col_name_issues(self, df: pd.DataFrame) -> dict:
        import re
        issues: dict = {"spaces": [], "symbols": [], "duplicates": []}
        seen_normalized: set = set()
        for col in df.columns:
            s = str(col)
            if " " in s.strip() or s != s.strip():
                issues["spaces"].append(s)
            if re.search(r"[^a-zA-Z0-9_\s]", s):
                issues["symbols"].append(s)
            # Check duplicates on normalized form (catches 'Age' vs 'age' vs 'AGE')
            normalized = s.lower().strip()
            if normalized in seen_normalized:
                issues["duplicates"].append(s)
            seen_normalized.add(normalized)
        return {k: v for k, v in issues.items() if v}

    def _schema_drift(self, df: pd.DataFrame) -> dict:
        current = {col: str(dt) for col, dt in df.dtypes.items()}
        if not os.path.exists(SCHEMA_SNAPSHOT_FILE):
            try:
                with open(SCHEMA_SNAPSHOT_FILE, "w") as f:
                    json.dump({"columns": current,
                               "created_at": datetime.now().isoformat()}, f, indent=2)
            except Exception:
                pass
            return {"detected": False, "first_run": True}

        try:
            saved = json.load(open(SCHEMA_SNAPSHOT_FILE))["columns"]
        except Exception:
            return {"detected": False}

        curr_set  = set(current)
        saved_set = set(saved)
        new_cols     = list(curr_set - saved_set)
        removed_cols = list(saved_set - curr_set)
        type_chg     = {c: {"was": saved[c], "now": current[c]}
                        for c in curr_set & saved_set if saved[c] != current[c]}

        from difflib import SequenceMatcher
        renames = [{"old": r, "new": n,
                    "similarity": round(SequenceMatcher(None, r, n).ratio(), 2)}
                   for r in removed_cols for n in new_cols
                   if SequenceMatcher(None, r, n).ratio() >= 0.85]

        return {
            "detected":        bool(new_cols or removed_cols or type_chg),
            "new_columns":     new_cols,
            "removed_columns": removed_cols,
            "renamed_likely":  renames,
            "type_changes":    type_chg,
        }

    def _recommend_engine(self, r: dict) -> str:
        gb   = r["size_gb"]
        rows = r["rows"]
        if gb >= BIG_DATA_THRESHOLD_GB:
            return "Spark"
        elif gb >= SMALL_DATA_THRESHOLD_GB:
            return "Dask"
        elif rows >= MEDIUM_ROW_THRESHOLD or rows == -1:
            return "Polars"
        return "Pandas"

    def _recommend_partitions(self, r: dict) -> int:
        gb = r["size_gb"]
        if gb < 1:   return 1
        if gb < 5:   return 2
        if gb < 20:  return 4
        if gb < 50:  return 8
        return 16
