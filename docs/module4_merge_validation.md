# Module 4 — Hierarchical Merge & Global Validation

> **Goal:** Merge all cleaned chunks back into one DataFrame using hierarchical reduction, then run cross-partition validation to catch inconsistencies that per-chunk cleaning couldn't resolve.

---

## File Structure

```
refineflow/
├── merger.py               # Hierarchical merge logic
├── global_validator.py     # Cross-partition validation
```

---

## Why This Module?

Per-chunk cleaning (Module 3) is excellent but has a **fundamental limitation**: each chunk is isolated. This means:

- `chunk_1` may contain `Mumbai`
- `chunk_2` may contain `mumbai`
- `chunk_3` may contain `MUMBAI`

These are **not** caught by per-chunk deduplication. Module 4 resolves this with a global merge and a cross-partition validation pass.

---

## Task 4.1 — Hierarchical Merger (`merger.py`)

### Class: `HierarchicalMerger(chunks)`

#### Why Hierarchical?

Naive approach: concat all 8 chunks at once → memory spike.  
Better approach: merge in pairs, reducing N chunks to 1 in `log2(N)` rounds.

```
Round 1: (chunk0 + chunk1), (chunk2 + chunk3), (chunk4 + chunk5), (chunk6 + chunk7)
Round 2: (01 + 23), (45 + 67)
Round 3: (0123 + 4567)
```

This keeps peak memory usage low.

#### Implementation

- [ ] Accept list of cleaned DataFrames
- [ ] Merge in tree-reduction pattern using `pd.concat()`
- [ ] `ignore_index=True` at each merge step
- [ ] Handle **mismatched columns**:
  - If chunk schemas differ: fill missing columns with `NaN`, log warning
  - Do NOT raise an error — log and continue
- [ ] Log each merge round:
  ```
  [✓] Merge Round 1: 8 chunks → 4 chunks
  [✓] Merge Round 2: 4 chunks → 2 chunks
  [✓] Merge Round 3: 2 chunks → 1 DataFrame (1,200,000 rows)
  ```
- [ ] Track total rows before and after merge
- [ ] Return: single merged `pd.DataFrame`

```python
class HierarchicalMerger:
    def merge(self) -> pd.DataFrame:
        chunks = self.chunks
        round_num = 1
        while len(chunks) > 1:
            merged = []
            for i in range(0, len(chunks), 2):
                if i + 1 < len(chunks):
                    combined = pd.concat([chunks[i], chunks[i+1]], ignore_index=True)
                else:
                    combined = chunks[i]   # odd chunk out — carry forward
                merged.append(combined)
            chunks = merged
            self.log.info(f"Merge Round {round_num}: done ({len(chunks)} remaining)")
            round_num += 1
        return chunks[0]
```

---

## Task 4.2 — Global Validator (`global_validator.py`)

### Class: `GlobalValidator(df, scan_report, config=None)`

Runs after full merge. Catches issues that span chunk boundaries.

---

### 4.2.1 — Global Deduplication

- [ ] Final deduplication pass on the **entire** merged DataFrame
- [ ] Use hash-based row fingerprinting for speed on large DFs
- [ ] Support key-column subset dedup (same as Module 3 Deduplicator)
- [ ] Track: `{"cross_chunk_dupes_removed": N}`
- [ ] Log:
  ```
  [✓] Global Dedup: Removed 1,482 cross-chunk duplicates
  ```

---

### 4.2.2 — Category Standardization

This is the **most important** global step.

- [ ] For each categorical column:
  1. Normalize all values to lowercase
  2. Group identical-after-normalization values
  3. Pick the **most frequent** form as the canonical value
  4. Replace all variants with the canonical form

```python
# Example
variants = {"mumbai": 8420, "Mumbai": 1200, "MUMBAI": 340}
canonical = "mumbai"   # most frequent
# Replace all → "mumbai"  (or use Title Case as final step)
```

- [ ] After canonicalization, apply `Title Case` to city/name columns
- [ ] Optional: **fuzzy matching** with `difflib.get_close_matches()` for typo resolution:
  - `Mumabi` → `Mumbai` (>85% similarity threshold)
- [ ] Track stats per column: `{col: {"variants_merged": N, "canonical_values": K}}`
- [ ] Log:
  ```
  [✓] Category Standardization: 3 columns standardized
      city: 14 variants → 6 canonical values
      country: 8 variants → 4 canonical values
  ```

---

### 4.2.3 — Schema Reconciliation

- [ ] Verify all columns from original scan report are present in merged DF
- [ ] Detect unexpected extra columns and log as warning
- [ ] Detect missing columns and log as error
- [ ] Ensure column dtypes match expected types from TypeFixer output

```python
# Schema check output
{
  "expected_columns": 48,
  "present_columns": 48,
  "missing": [],
  "extra": ["_unnamed_col"],
  "dtype_mismatches": {"revenue": {"expected": "float32", "actual": "object"}}
}
```

---

### 4.2.4 — Data Integrity Checks

Rule-based consistency checks:

- [ ] **Age columns**: values must be 0–120; flag/remove outside range
- [ ] **Revenue/price columns**: flag unexpected negatives
- [ ] **Date columns**: no future dates for historical datasets (configurable)
- [ ] **Email columns** (if detected): validate format with regex
- [ ] **Phone columns** (if detected): normalize format
- [ ] **Percentage columns**: values must be 0–100
- [ ] Allow users to define custom rules via config:
  ```python
  custom_rules = {
      "salary": {"min": 0, "max": 10_000_000},
      "rating": {"allowed_values": [1, 2, 3, 4, 5]}
  }
  ```

---

### 4.2.5 — Final Null Audit

- [ ] One final scan for remaining nulls after all cleaning
- [ ] Apply fallback strategy for any remaining nulls:
  - Numerical: fill with `0` or `median`
  - Categorical: fill with `"Unknown"`
- [ ] Log summary: `[✓] Final Null Audit: 0 nulls remaining`

---

### Global Validation Report

```python
global_validation_report = {
    "rows_before_merge": 1_202_000,
    "rows_after_merge": 1_200_000,
    "cross_chunk_dupes_removed": 1_482,
    "categories_standardized": {
        "city": {"variants": 14, "canonical": 6},
        "country": {"variants": 8, "canonical": 4}
    },
    "schema": {
        "expected": 48,
        "present": 48,
        "missing": [],
        "extra": []
    },
    "integrity_violations_fixed": 23,
    "final_null_count": 0
}
```

---

## Task 4.3 — Wire-up into `Cleaner`

- [ ] After `ParallelRunner` completes, call `HierarchicalMerger`
- [ ] Store merged DF in `self.df`
- [ ] Call `GlobalValidator` on `self.df`
- [ ] Store validation report in `self.stats["global_validation"]`
- [ ] `auto_clean()` method in Cleaner wires all of Module 2 + 3 + 4 together

```python
def auto_clean(self):
    # Module 2: load + partition
    engine = EngineSelector(self.scan_report, self.backend).select()
    self.df = load_with_engine(engine, self.file)
    self.chunks = DataPartitioner(self.df, self.partitions).split()

    # Module 3: parallel clean
    cleaned_chunks = ParallelRunner(self.chunks).run()

    # Module 4: merge + validate
    self.df = HierarchicalMerger(cleaned_chunks).merge()
    self.df, validation_report = GlobalValidator(self.df, self.scan_report).run()
    self.stats["global_validation"] = validation_report

    return self
```

---

## Deliverable

```python
Cleaner("sales.csv", partitions=8).auto_clean()
```

**Expected Output:**
```
[✓] Parallel cleaning complete (8/8 chunks)

[✓] Merge Round 1: 8 chunks → 4 chunks
[✓] Merge Round 2: 4 chunks → 2 chunks
[✓] Merge Round 3: 2 chunks → 1 DataFrame (1,200,000 rows)

[✓] Global Dedup: Removed 1,482 cross-chunk duplicates
[✓] Category Standardization: city (14→6), country (8→4)
[✓] Schema validated: 48/48 columns present
[✓] Integrity checks: 23 violations fixed
[✓] Final Null Audit: 0 nulls remaining

[✓] auto_clean() complete — Dataset is clean and ready
```

---

## Tests (`tests/test_module4.py`)

- [ ] Test hierarchical merger handles 8 chunks correctly
- [ ] Test merger handles odd number of chunks (e.g., 7)
- [ ] Test merger handles mismatched columns gracefully
- [ ] Test global dedup removes cross-chunk duplicates
- [ ] Test category standardization: `mumbai`, `MUMBAI`, `Mumbai` → `Mumbai`
- [ ] Test fuzzy matching: `Mumabi` → `Mumbai`
- [ ] Test schema reconciliation detects missing column
- [ ] Test integrity check flags age > 120
- [ ] Test final null audit shows 0 nulls after validation

---

## Dependencies Installed

```bash
pip install pandas difflib recordlinkage   # difflib is built-in Python
```

---

## Real-World Problems Handled in This Module

> Module 4 operates on the **globally merged DataFrame** — the only phase where cross-partition and cross-dataset problems can be detected. These issues are impossible to fix in isolated per-chunk processing.

### Duplicate Problems

| Problem | Real Example | Solution | Technique |
|---------|-------------|----------|-----------|
| Exact duplicate rows | Same order in 2 chunks | Global hash dedup after merge | Row hashing on full merged DF |
| Near duplicates | `Sachin Singh` vs `Sachin S.` | Fuzzy dedup with similarity clustering | `recordlinkage` on key columns |
| Cross-partition duplicates | Duplicate split across chunk boundary | Global dedup phase after hierarchical merge | Distributed merge validator |

**Near-duplicate strategy:**
```python
import recordlinkage
indexer = recordlinkage.Index()
indexer.block("city")   # compare only within same city (blocking)
candidate_pairs = indexer.index(df)
compare = recordlinkage.Compare()
compare.string("name", "name", method="jarowinkler", threshold=0.90)
features = compare.compute(candidate_pairs, df)
near_dupes = features[features.sum(axis=1) >= 1]
# Keep the row with more non-null values; drop the other
```

---

### Time Series Problems

| Problem | Real Example | Solution | Technique |
|---------|-------------|----------|-----------|
| Missing timestamps | Daily sales missing some days | Interpolation on resampled index | `df.resample('D').interpolate()` |
| Duplicate timestamps | Same datetime row repeated | Timestamp deduplication on datetime index | Deduplicate on datetime index |
| Timezone mismatch | UTC + IST timestamps mixed | Normalize all to UTC | `df['ts'].dt.tz_convert('UTC')` |
| Irregular intervals | Random sampling gaps | Resample to regular frequency | Frequency engine: detect dominant interval |

**Timezone normalization:**
```python
if df[col].dt.tz is None:
    df[col] = df[col].dt.tz_localize("UTC")   # naive → UTC
else:
    df[col] = df[col].dt.tz_convert("UTC")    # aware → convert to UTC
```

---

### Business Logic Violations

| Problem | Real Example | Solution | Technique |
|---------|-------------|----------|-----------|
| Order date after delivery | `order=2025-06-01`, `delivery=2025-05-30` | Cross-column date ordering check | Business-rule engine |
| Negative quantity | `quantity = -5` | Constraint validation | Domain validator: quantity >= 0 |
| Revenue mismatch | `price × qty ≠ total_revenue` | Derived-field validation | Formula validator: recalculate + compare |

**Cross-column rule engine:**
```python
BUSINESS_RULES = [
    {"type": "column_order", "col_a": "order_date", "col_b": "delivery_date",
     "rule": "col_a <= col_b", "action": "flag"},
    {"type": "formula_check", "formula": "unit_price * quantity",
     "expected_col": "total_revenue", "tolerance": 0.01, "action": "recalculate"},
    {"type": "range", "col": "quantity", "min": 0, "action": "clip"}
]
```

---

### Address Granularity Problems

| Problem | Real Example | Solution | Technique |
|---------|-------------|----------|-----------|
| Different granularity | `Mumbai` vs `Andheri West, Mumbai` | Extract city from full address | Address tokenizer |

```python
def extract_city(address: str) -> str:
    parts = [p.strip() for p in address.split(",")]
    return parts[-1] if len(parts) >= 2 else address
# "Andheri West, Mumbai" → "Mumbai"
```
