# Module 3 — Parallel Cleaning Engine

> **Goal:** Apply all cleaning operations to each partition independently and in parallel using multiprocessing/multithreading.

---

## File Structure

```
refineflow/
├── cleaning/
│   ├── __init__.py
│   ├── pipeline.py           # Orchestrates all cleaning steps per chunk
│   ├── null_handler.py       # Missing value strategies
│   ├── deduplicator.py       # Duplicate removal
│   ├── type_fixer.py         # Datatype detection & conversion
│   ├── text_cleaner.py       # Text normalization & encoding fix
│   ├── outlier_detector.py   # IQR, Z-score, percentile filtering
│   ├── memory_optimizer.py   # Downcast dtypes to save memory
│   └── validator.py          # Per-chunk invalid value checks
├── parallel_runner.py        # Multiprocessing pool manager
```

---

## Task 3.1 — Null Handler (`cleaning/null_handler.py`)

### Class: `NullHandler(df, strategy_config=None)`

- [ ] Auto-detect column type: **numerical / categorical / datetime**
- [ ] Apply strategy per type:

| Column Type | Default Strategy | Alternatives |
|-------------|-----------------|--------------|
| Numerical   | `median`        | `mean`, `interpolation`, `drop` |
| Categorical | `mode`          | `"Unknown"`, `drop` |
| Datetime    | `ffill`         | `bfill`, `interpolation` |

- [ ] Allow per-column override via config dict:
  ```python
  strategy_config = {
      "age": "mean",
      "city": "Unknown",
      "date": "ffill"
  }
  ```
- [ ] Track stats: `{col: {"nulls_before": N, "nulls_after": M, "strategy": "median"}}`
- [ ] Log summary:
  ```
  [✓] Null Handler: Filled 1,203 nulls across 5 columns
  ```

```python
class NullHandler:
    def run(self, df) -> pd.DataFrame:
        for col in df.columns:
            if df[col].isnull().sum() == 0:
                continue
            col_type = self._detect_type(col, df)
            strategy = self.config.get(col, self.defaults[col_type])
            df = self._apply_strategy(df, col, strategy)
        return df
```

---

## Task 3.2 — Deduplicator (`cleaning/deduplicator.py`)

### Class: `Deduplicator(df, subset=None, keep="first")`

- [ ] Hash-based row fingerprinting for fast dedup
- [ ] `df.drop_duplicates(subset=subset, keep=keep)`
- [ ] Support subset of key columns (e.g., deduplicate by `["order_id", "customer_id"]`)
- [ ] Track stats: `{"rows_before": N, "rows_after": M, "removed": K}`
- [ ] Log:
  ```
  [✓] Deduplicator: Removed 441 duplicate rows
  ```

---

## Task 3.3 — Type Fixer (`cleaning/type_fixer.py`)

### Class: `TypeFixer(df)`

Auto-detect and convert column types:

- [ ] **String → Datetime**
  - Try `pd.to_datetime()` with multiple format strings
  - Only convert if >80% of values parse successfully
- [ ] **String → Boolean**
  - Map: `yes/no`, `true/false`, `1/0`, `y/n` → `True/False`
- [ ] **Currency strings → float**
  - Strip `$`, `€`, `£`, `₹`, `,` then cast to float
- [ ] **Percentage strings → float**
  - Strip `%`, divide by 100
- [ ] **Numeric strings → int/float**
  - Try cast, fallback gracefully
- [ ] **Object → Category**
  - If unique values < 50% of total rows → convert to `category`
- [ ] **ID columns → string**
  - Detect by column name (`_id`, `_code`, `_key` suffixes)
  - Preserve leading zeros

- [ ] Track stats: `{col: {"from": "object", "to": "datetime64"}}`
- [ ] Log:
  ```
  [✓] Type Fixer: Converted 4 date columns, 2 currency columns
  ```

---

## Task 3.4 — Text Cleaner (`cleaning/text_cleaner.py`)

### Class: `TextCleaner(df, text_columns=None)`

Applied only to string/object columns:

- [ ] Strip leading/trailing whitespace: `.str.strip()`
- [ ] Normalize multiple spaces → single space: `re.sub(r'\s+', ' ', text)`
- [ ] Unicode normalization: `unicodedata.normalize("NFKD", text)`
- [ ] Replace corrupted characters: remove `\ufffd` (replacement char)
- [ ] Remove invisible characters: zero-width space `\u200b`, `\u00ad`
- [ ] Standardize casing rules:
  - Name columns (detected by `name`, `city`, `country` in col name): `Title Case`
  - Code columns (detected by `code`, `id`, `sku`): `UPPER`
  - Description columns: keep original casing
- [ ] Log:
  ```
  [✓] Text Cleaner: Cleaned 3 text columns, fixed 228 encoding issues
  ```

---

## Task 3.5 — Outlier Detector (`cleaning/outlier_detector.py`)

### Class: `OutlierDetector(df, method="iqr", action="clip")`

Applied only to numerical columns:

#### Methods

| Method | Logic |
|--------|-------|
| `iqr` | Flag values below Q1 − 1.5×IQR or above Q3 + 1.5×IQR |
| `zscore` | Flag values where \|z\| > 3 |
| `percentile` | Clip values at [1st, 99th] percentile |

#### Actions

| Action | Behavior |
|--------|----------|
| `clip` | Cap at boundary value (default) |
| `remove` | Drop outlier rows |
| `flag` | Add `_outlier` boolean column |
| `replace_median` | Replace with column median |

- [ ] Skip columns with <30 rows (too few to detect outliers)
- [ ] Skip ID, boolean, and datetime columns
- [ ] Track stats: `{col: {"outliers_found": N, "action": "clip"}}`
- [ ] Log:
  ```
  [✓] Outlier Detector: Clipped 32 outliers across 3 columns
      age: max was 300 → clipped to 87
      revenue: min was -50000 → clipped to 0
  ```

---

## Task 3.6 — Memory Optimizer (`cleaning/memory_optimizer.py`)

### Class: `MemoryOptimizer(df)`

- [ ] Calculate memory before: `df.memory_usage(deep=True).sum()`
- [ ] Downcast integers:
  ```python
  int64 → int32 (if max < 2^31)
  int64 → int16 (if max < 2^15)
  int64 → int8  (if max < 127)
  ```
- [ ] Downcast floats:
  ```python
  float64 → float32
  ```
- [ ] Convert low-cardinality object columns → `category`:
  - Threshold: unique count < 50% of total rows
- [ ] Calculate memory after and % reduction
- [ ] Log:
  ```
  [✓] Memory Optimizer: 1.8 GB → 620 MB (65.6% reduction)
  ```

---

## Task 3.7 — Cleaning Pipeline (`cleaning/pipeline.py`)

### Class: `CleaningPipeline(chunk_df, config=None)`

Ordered execution of all cleaning steps:

```
Step 1 → TypeFixer
Step 2 → NullHandler
Step 3 → TextCleaner
Step 4 → Deduplicator
Step 5 → OutlierDetector
Step 6 → MemoryOptimizer
Step 7 → Validator (per-chunk sanity check)
```

- [ ] Each step logs its own output
- [ ] Each step updates `self.stats` dict
- [ ] Wrap each step in try/except — log error, skip step, continue
- [ ] Return: `(cleaned_df, stats_dict)`

```python
class CleaningPipeline:
    def run(self) -> tuple:
        df = self.df
        df = TypeFixer(df).run()
        df = NullHandler(df, self.config.get("null_strategy")).run()
        df = TextCleaner(df).run()
        df = Deduplicator(df).run()
        df = OutlierDetector(df).run()
        df = MemoryOptimizer(df).run()
        return df, self.stats
```

---

## Task 3.8 — Parallel Runner (`parallel_runner.py`)

### Class: `ParallelRunner(chunks, pipeline_config, max_workers=None)`

- [ ] Auto-detect worker count: `os.cpu_count() - 1`
- [ ] Use `concurrent.futures.ProcessPoolExecutor` for CPU-bound cleaning
- [ ] Map `CleaningPipeline.run` over all chunks in parallel
- [ ] Show `tqdm` progress bar:
  ```
  Cleaning chunks: 100%|████████████| 8/8 [01:23<00:00, 10.4s/chunk]
  ```
- [ ] **Fault Tolerance**:
  - Wrap each chunk in try/except
  - On failure: retry up to 3× with exponential backoff
  - On 3rd failure: save failed chunk to `CHECKPOINT_DIR/failed/` and skip
  - Log: `[!] Chunk 3 failed after 3 retries — skipped`
- [ ] After all chunks complete: aggregate all stats dicts
- [ ] Return: `[cleaned_chunk_0, ..., cleaned_chunk_N]`

```python
class ParallelRunner:
    def run(self) -> list:
        cleaned = []
        with ProcessPoolExecutor(max_workers=self.workers) as executor:
            futures = {executor.submit(self._clean_chunk, i, c): i
                       for i, c in enumerate(self.chunks)}
            for future in tqdm(as_completed(futures), total=len(futures)):
                result = future.result()
                cleaned.append(result)
        return cleaned
```

---

## Deliverable

```python
Cleaner("sales.csv", partitions=8).auto_clean()
```

**Expected Output:**
```
[✓] Running parallel cleaning on 8 chunks (6 workers)...

Cleaning chunks: 100%|████████| 8/8 [01:23<00:00]

[✓] Chunk 1/8 — Nulls: 1,203 | Dupes: 441 | Outliers: 32 | Memory: -62%
[✓] Chunk 2/8 — Nulls:   891 | Dupes: 318 | Outliers: 18 | Memory: -58%
...
[✓] All 8 chunks cleaned successfully
```

---

## Tests (`tests/test_module3.py`)

- [ ] Test null handler fills all nulls with correct strategy
- [ ] Test type fixer converts currency strings to float
- [ ] Test type fixer converts date strings to datetime
- [ ] Test text cleaner removes extra whitespace and unicode issues
- [ ] Test outlier detector clips IQR outliers correctly
- [ ] Test memory optimizer reduces memory by at least 30%
- [ ] Test parallel runner processes all chunks without error
- [ ] Test fault tolerance: inject failure in one chunk, verify retry + skip

---

## Dependencies Installed

```bash
pip install pandas scipy tqdm colorama regex
```

---

## Real-World Problems Handled in This Module

> Module 3 is the **core cleaning brain**. Every problem below is handled per-chunk in parallel. This is where raw, messy data becomes structured and reliable.

### Date Format Problems → `TypeFixer` + new `DateParser`

| Problem | Real Example | Solution | Internal Technique |
|---------|-------------|----------|--------------------|
| Mixed date formats | `12/05/2025`, `2025-05-12`, `120525` | Multi-format parsing with confidence scoring | Try 15+ format patterns, pick the one with >80% match |
| Ambiguous dates | `01/02/2025` — Jan 2 or Feb 1? | Region-aware interpretation | Locale inference: check other values in col for clues |
| Invalid dates | `32/15/2025` | Validation + null replacement | Rule-based validator — flag impossible day/month |
| Unix timestamps mixed with dates | `1715234234` alongside `2025-05-12` | Timestamp detection + conversion | If value > 1e9 and int → treat as Unix epoch, convert |

**Implementation detail:**
```python
# DateParser tries formats in priority order
DATE_FORMATS = [
    "%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y",
    "%d-%m-%Y", "%Y%m%d", "%d%m%Y"
]
for fmt in DATE_FORMATS:
    parsed = pd.to_datetime(col, format=fmt, errors="coerce")
    if parsed.notna().mean() > 0.80:   # >80% parsed → use this format
        return parsed
# Fallback: detect Unix timestamp
if col.dtype in [int, float] and col.mean() > 1e9:
    return pd.to_datetime(col, unit="s", errors="coerce")
```

---

### Datatype Problems → `TypeFixer`

| Problem | Real Example | Solution | Internal Technique |
|---------|-------------|----------|--------------------|
| Numbers stored as strings | `"5000"` | Safe numeric conversion with fallback | Try `pd.to_numeric(errors="coerce")` |
| Currency mixed with numbers | `₹5000`, `$400` | Currency symbol stripping | Regex: `re.sub(r'[₹$€£,\s]', '', value)` |
| Percentage stored as text | `45%` | Strip `%`, divide by 100 | Numeric normalization |
| Boolean inconsistency | `Yes`, `TRUE`, `1`, `y` | Boolean mapping dictionary | Standardization dict → `True/False` |

**Standardization dictionary for booleans:**
```python
BOOL_MAP = {
    "yes": True, "no": False,
    "true": True, "false": False,
    "1": True, "0": False,
    "y": True, "n": False,
    "on": True, "off": False
}
```

---

### Wrong Column Data → `validator.py` (per-chunk)

| Problem | Real Example | Solution | Internal Technique |
|---------|-------------|----------|--------------------|
| City in age column | `Mumbai` in `age` column | Semantic anomaly detection | Column name + value type mismatch → flag |
| Text in salary column | `"Engineer"` in `salary` | Outlier value detection | Non-numeric in numeric column → null + log |
| Phone number in email column | `9876543210` | Regex validation | Email pattern check: must contain `@` |
| Numbers in name column | `John123` | Entity validation | Name columns: flag values with >2 digits |

**Implementation detail:**
```python
class PerChunkValidator:
    COLUMN_RULES = {
        "age": {"type": "numeric", "min": 0, "max": 120},
        "email": {"pattern": r'^[\w.-]+@[\w.-]+\.\w+$'},
        "name": {"no_digits_ratio": 0.8},   # max 20% digits
        "salary": {"type": "numeric", "min": 0}
    }
    # Auto-detect column semantic type from name keywords
    # Then validate values against expected rules
```

---

### Missing Value Problems → `NullHandler`

| Problem | Real Example | Solution | Internal Technique |
|---------|-------------|----------|--------------------|
| Random nulls | Missing salary values | Median/mode filling by column type | Smart imputation (already in Task 3.1) |
| Hidden nulls | `N/A`, `--`, `null`, `none`, `?`, `-` | Null normalization before filling | Null dictionary engine |
| Entire missing columns | 95% null values | Auto column dropping | Threshold analysis (already in scanner) |
| Missing time-series data | Missing daily sales entries | Interpolation | Time-series filler via `df.interpolate()` |

**Hidden null dictionary (applied before NullHandler):**
```python
HIDDEN_NULLS = {
    "na", "n/a", "n.a.", "none", "null", "nil",
    "nan", "-", "--", "---", "?", "unknown",
    "not available", "not applicable", "missing", ""
}
# Replace all → np.nan before null handling
df.replace(HIDDEN_NULLS, np.nan, inplace=True)
```

---

### Outlier Problems → `OutlierDetector`

| Problem | Real Example | Solution | Internal Technique |
|---------|-------------|----------|--------------------|
| Impossible ages | `age = 300` | Range validation — clip/remove | IQR + hard business rule: max 120 |
| Negative revenue | `revenue = -50000` | Business-rule filtering | Domain rule: revenue >= 0 |
| Future birth dates | `birth_year = 2090` | Temporal validation | Date constraint: birthdate <= today |
| Extreme statistical values | `999999999` in salary | IQR/Z-score filtering | Z-score > 4 → clip to 99th percentile |

**Business rules applied per column type:**
```python
COLUMN_CONSTRAINTS = {
    "age":         {"min": 0,   "max": 120},
    "salary":      {"min": 0                },
    "revenue":     {"min": 0                },
    "rating":      {"min": 0,   "max": 5   },
    "percentage":  {"min": 0,   "max": 100 },
    "quantity":    {"min": 0               },
}
# Hard constraint violations are fixed BEFORE statistical outlier methods
```

---

### Unit Problems → `UnitNormalizer` (new file: `cleaning/unit_normalizer.py`)

| Problem | Real Example | Solution | Internal Technique |
|---------|-------------|----------|--------------------|
| Mixed weight units | `1kg`, `500g`, `2.5 lbs` | Convert all to base unit (grams) | Unit extraction regex + conversion table |
| Currency mismatch | USD + INR in same column | Convert to single currency | Currency engine (requires FX rate config) |
| Mixed time units | `30sec`, `2min`, `1hr` | Normalize to seconds | Time unit converter |

**Implementation:**
```python
class UnitNormalizer:
    WEIGHT_MAP = {"kg": 1000, "g": 1, "lb": 453.6, "oz": 28.35}
    TIME_MAP   = {"s": 1, "sec": 1, "min": 60, "hr": 3600, "ms": 0.001}

    def normalize_weight(self, value: str) -> float:
        # Extract number + unit using regex
        match = re.match(r'([\d.]+)\s*(kg|g|lb|oz)', value, re.IGNORECASE)
        number, unit = float(match[1]), match[2].lower()
        return number * self.WEIGHT_MAP[unit]   # → always grams
```

---

### Address Problems → `TextCleaner` + `AddressNormalizer` (new)

| Problem | Real Example | Solution | Internal Technique |
|---------|-------------|----------|--------------------|
| Misspelled city names | `Mumbi`, `Bangalor` | Fuzzy matching correction | `difflib.get_close_matches()` vs known city list |
| Abbreviated states | `Pune MH`, `MH` | Dictionary mapping | Geo normalization: `MH → Maharashtra` |
| Mixed separators | `Mumbai-MH`, `Mumbai, MH` | Token standardization | Regex split + rejoin with standard separator |

**City correction approach:**
```python
from difflib import get_close_matches
KNOWN_CITIES = ["Mumbai", "Delhi", "Bangalore", "Chennai", ...]

def correct_city(value: str) -> str:
    matches = get_close_matches(value, KNOWN_CITIES, n=1, cutoff=0.8)
    return matches[0] if matches else value
# "Mumbi" → similarity 0.83 → "Mumbai"
```
