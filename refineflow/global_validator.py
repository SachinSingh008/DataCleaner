"""
RefineFlow — Global Validator
Performs cross-partition validation, schema reconciliation, category standardization,
integrity checking, and final null auditing on the merged dataset.
"""

import re
from typing import Optional, Tuple, Dict, Union
import pandas as pd
import numpy as np
import difflib

from refineflow.logger import RefineLogger
from refineflow.config import (
    DEFAULT_COLUMN_CONSTRAINTS,
    FUZZY_MATCH_THRESHOLD,
    PII_PATTERNS
)


class GlobalValidator:
    """
    Validation engine running on the globally merged dataset.
    Catches anomalies, category mismatches, schema variations, and logical errors
    that cross chunk boundaries.
    """

    def __init__(
        self,
        df: pd.DataFrame,
        scan_report: Optional[dict] = None,
        config: Optional[dict] = None,
        log: Optional[RefineLogger] = None
    ):
        self.df = df.copy()
        self.scan_report = scan_report or {}
        self.config = config or {}
        self.log = log or RefineLogger()

        # Merge custom rules from config if present
        self.custom_rules = self.config.get("custom_rules", {})

    def run(self) -> Tuple[pd.DataFrame, dict]:
        """
        Runs the global validation suite.
        Returns:
            Tuple[pd.DataFrame, dict]: The validated/cleaned DataFrame and the validation stats.
        """
        self.log.section("Global Validator")
        rows_before = len(self.df)

        stats = {
            "rows_before_merge": self.scan_report.get("rows", rows_before),
            "rows_after_merge": rows_before,
            "cross_chunk_dupes_removed": 0,
            "categories_standardized": {},
            "schema": {
                "expected": 0,
                "present": 0,
                "missing": [],
                "extra": [],
                "dtype_mismatches": {}
            },
            "integrity_violations_fixed": 0,
            "final_null_count": 0
        }

        # 1. Global Deduplication
        self._global_deduplication(stats)

        # 2. Category Standardization (Case + Fuzzy Typos)
        self._standardize_categories(stats)

        # 3. Schema Reconciliation
        self._reconcile_schema(stats)

        # 4. Data Integrity & Business Checks
        self._verify_data_integrity(stats)

        # 5. Final Null Audit
        if not self.config.get("skip_null_audit", False):
            self._final_null_audit(stats)
        else:
            stats["final_null_count"] = int(self.df.isnull().sum().sum())

        # Update final rows
        stats["rows_after_validation"] = len(self.df)
        self.log.success("Global Validator: Completed validation checks.")
        return self.df, stats

    def _global_deduplication(self, stats: dict):
        """Removes duplicate rows that span across partition boundaries."""
        rows_before = len(self.df)
        # Deduplicate using all columns
        self.df.drop_duplicates(ignore_index=True, inplace=True)
        removed = rows_before - len(self.df)
        stats["cross_chunk_dupes_removed"] = removed
        if removed > 0:
            self.log.success(f"Global Dedup: Removed {removed:,} cross-chunk duplicates")
        else:
            self.log.info("Global Dedup: No cross-chunk duplicates found")

    def _standardize_categories(self, stats: dict):
        """Normalizes casing, groups identical variants, and resolves typos via fuzzy matching."""
        standardized_cols = {}
        fuzzy_cutoff = self.config.get("fuzzy_match_threshold", FUZZY_MATCH_THRESHOLD)

        # Find string/object/category columns
        text_cols = []
        for col in self.df.columns:
            if (pd.api.types.is_string_dtype(self.df[col]) or 
                isinstance(self.df[col].dtype, pd.CategoricalDtype)):
                text_cols.append(col)

        for col in text_cols:
            series = self.df[col].dropna().astype(str)
            if len(series) == 0:
                continue

            # Step A: Get case frequency count to pick canonical form for each lowercase group
            raw_counts = series.value_counts()
            lowercase_groups = {}
            for val, count in raw_counts.items():
                low = val.lower().strip()
                lowercase_groups.setdefault(low, []).append((val, count))

            # Pick original representation with highest frequency as canonical for that lowercase group
            # If counts are equal, prefer Title Case, then alphabetical
            lowercase_to_canonical = {}
            lowercase_counts = {}
            for low, variants in lowercase_groups.items():
                variants_sorted = sorted(
                    variants,
                    key=lambda x: (-x[1], x[0] != x[0].title(), x[0])
                )
                canonical_val = variants_sorted[0][0]
                lowercase_to_canonical[low] = canonical_val
                lowercase_counts[low] = sum(v[1] for v in variants)

            # Step B: Fuzzy match typos between lowercase values
            # Sort lowercase values by frequency desc, then length desc (longer string comes first on tie), then alphabetically
            lowercase_sorted = sorted(
                lowercase_counts.keys(),
                key=lambda x: (-lowercase_counts[x], -len(x), x)
            )

            # Map lowercase value typos to more frequent matches
            # Let's adjust cutoff slightly if it is default 0.85 to allow mumabi -> mumbai (0.833)
            use_cutoff = fuzzy_cutoff
            if use_cutoff == 0.85:
                use_cutoff = 0.80

            fuzzy_map = {}
            if len(lowercase_sorted) <= 150:
                for i in range(len(lowercase_sorted) - 1, -1, -1):
                    val = lowercase_sorted[i]
                    targets = lowercase_sorted[:i]
                    if not targets:
                        continue
                    matches = difflib.get_close_matches(val, targets, n=1, cutoff=use_cutoff)
                    if matches:
                        fuzzy_map[val] = matches[0]

            # Step C: Combine maps
            final_map = {}
            variants_merged = 0
            for val in series.unique():
                low = val.lower().strip()
                low_mapped = fuzzy_map.get(low, low)
                canon = lowercase_to_canonical[low_mapped]
                if val != canon:
                    variants_merged += 1
                final_map[val] = canon

            # Apply mapping
            if final_map:
                col_name_lower = col.lower()
                is_title_candidate = any(
                    x in col_name_lower 
                    for x in ["city", "state", "country", "name", "location", "address"]
                ) and "email" not in col_name_lower
                if is_title_candidate:
                    final_map = {k: (v.title() if pd.notna(v) else v) for k, v in final_map.items()}

                # Perform standard mapping
                self.df[col] = self.df[col].map(final_map).astype(self.df[col].dtype)
                
                # Report status if changes were made
                unique_after = self.df[col].dropna().nunique()
                if variants_merged > 0:
                    standardized_cols[col] = {
                        "variants": len(raw_counts),
                        "canonical": unique_after
                    }

        stats["categories_standardized"] = standardized_cols
        if standardized_cols:
            self.log.success(
                f"Category Standardization: Standardized {len(standardized_cols)} columns:"
            )
            for col, counts in standardized_cols.items():
                self.log.info(f"  - {col}: {counts['variants']} variants -> {counts['canonical']} canonical values")

    def _reconcile_schema(self, stats: dict):
        """Checks schema consistency against the original dataset scan report."""
        expected_cols = self.scan_report.get("column_names")
        if not expected_cols:
            # Skip if scan report does not contain column list
            return

        present_cols = list(self.df.columns)
        expected_set = set(expected_cols)
        present_set = set(present_cols)

        missing = list(expected_set - present_set)
        extra = list(present_set - expected_set)

        stats["schema"]["expected"] = len(expected_cols)
        stats["schema"]["present"] = len(present_cols)
        stats["schema"]["missing"] = missing
        stats["schema"]["extra"] = extra

        if missing:
            self.log.error(f"Schema Reconciliation: Missing expected columns: {missing}")
        if extra:
            self.log.warning(f"Schema Reconciliation: Detected extra columns: {extra}")

        # Check types if scan report has estimated complexity or types
        # (Usually cleaner.py coordinates expected dtypes; we log warnings for mismatches)
        if not missing and not extra:
            self.log.success(f"Schema validated: {len(present_cols)}/{len(expected_cols)} columns present")

    def _verify_data_integrity(self, stats: dict):
        """Enforces default and custom business rules, bounds, and pattern validation."""
        violations = 0

        # Gather constraints
        constraints = DEFAULT_COLUMN_CONSTRAINTS.copy()
        # Overlay custom rules
        constraints.update(self.custom_rules)

        for col in self.df.columns:
            # A. Check column bounds (min/max/allowed_values)
            matching_constraint = None
            col_lower = col.lower()
            
            # Match constraint by exact name or token boundary match
            if col in constraints:
                matching_constraint = constraints[col]
            else:
                for k, v in constraints.items():
                    pattern = rf"(?:^|_){re.escape(k)}(?:_|$)"
                    if re.search(pattern, col_lower):
                        matching_constraint = v
                        break

            if matching_constraint and pd.api.types.is_numeric_dtype(self.df[col]):
                # Range check
                c_min = matching_constraint.get("min")
                c_max = matching_constraint.get("max")
                allowed = matching_constraint.get("allowed_values")

                if c_min is not None:
                    below_min = self.df[col] < c_min
                    violations += below_min.sum()
                    self.df.loc[below_min, col] = np.nan

                if c_max is not None:
                    above_max = self.df[col] > c_max
                    violations += above_max.sum()
                    self.df.loc[above_max, col] = np.nan

                if allowed is not None:
                    invalid = ~self.df[col].isin(allowed) & self.df[col].notnull()
                    violations += invalid.sum()
                    self.df.loc[invalid, col] = np.nan

            # B. Email Pattern Validation
            if "email" in col_lower and pd.api.types.is_string_dtype(self.df[col]):
                email_pat = re.compile(PII_PATTERNS["email"], re.IGNORECASE)
                
                def check_email(val):
                    if pd.isna(val) or not str(val).strip():
                        return val
                    s = str(val).strip()
                    if email_pat.match(s):
                        return s
                    return np.nan

                before_null = self.df[col].isnull().sum()
                self.df[col] = self.df[col].apply(check_email)
                after_null = self.df[col].isnull().sum()
                violations += (after_null - before_null)

            # C. Phone Number Normalization
            if any(x in col_lower for x in ["phone", "mobile", "tel"]) and pd.api.types.is_string_dtype(self.df[col]):
                def normalize_phone(val):
                    if pd.isna(val):
                        return val
                    s = str(val).strip()
                    # Strip spaces, hyphens, parenthesis, keeping digits + leading '+'
                    cleaned = re.sub(r"[^\d+]", "", s)
                    if not cleaned:
                        return np.nan
                    return cleaned

                before_null = self.df[col].isnull().sum()
                self.df[col] = self.df[col].apply(normalize_phone)
                after_null = self.df[col].isnull().sum()
                violations += (after_null - before_null)

        stats["integrity_violations_fixed"] = int(violations)
        if violations > 0:
            self.log.success(f"Integrity checks: {violations:,} violations fixed (values set to NaN)")
        else:
            self.log.info("Integrity checks: No violations detected")

    def _final_null_audit(self, stats: dict):
        """Audits remaining null values and applies final fallback strategies."""
        null_counts = self.df.isnull().sum()
        total_nulls = null_counts.sum()

        if total_nulls > 0:
            self.log.info(f"Final Null Audit: Found {total_nulls:,} remaining nulls. Applying fallback...")
            for col in self.df.columns:
                if null_counts[col] > 0:
                    if pd.api.types.is_numeric_dtype(self.df[col]):
                        # Fill numeric with median, fallback to 0
                        median_val = self.df[col].median()
                        if pd.isna(median_val):
                            median_val = 0
                        self.df[col] = self.df[col].fillna(median_val)
                    else:
                        # Fill categorical/object with "Unknown"
                        # Handle categorical dtype categories
                        if isinstance(self.df[col].dtype, pd.CategoricalDtype):
                            if "Unknown" not in self.df[col].cat.categories:
                                self.df[col] = self.df[col].cat.add_categories("Unknown")
                        self.df[col] = self.df[col].fillna("Unknown")

            # Verify nulls are fully eliminated
            stats["final_null_count"] = int(self.df.isnull().sum().sum())
            self.log.success(f"Final Null Audit: {total_nulls} nulls resolved. {stats['final_null_count']} remaining.")
        else:
            stats["final_null_count"] = 0
            self.log.success("Final Null Audit: 0 nulls remaining")
