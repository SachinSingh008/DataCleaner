# Module 1 — Core Infrastructure & Dataset Scanner

> **Goal:** Establish the project skeleton, base `Cleaner` class, and intelligent dataset scanning system.

---

## File Structure

```
DataCleaner/
├── refineflow/
│   ├── __init__.py
│   ├── cleaner.py          # Main Cleaner class (entry point)
│   ├── scanner.py          # Dataset Scanner
│   ├── config.py           # Global thresholds & constants
│   ├── logger.py           # Real-time logging system
│   └── utils.py            # Shared utility functions
├── docs/
├── tests/
│   └── test_module1.py
├── setup.py
└── README.md
```

---

## Task 1.1 — Project Setup

- [ ] Initialize Python package with `pyproject.toml`
- [ ] Define core dependencies:
  ```
  pandas >= 2.0
  polars >= 0.19
  pyarrow >= 13.0
  psutil >= 5.9
  chardet >= 5.0
  tqdm >= 4.65
  ```
- [ ] Create `config.py` with global constants:
  ```python
  SMALL_DATA_THRESHOLD_GB = 10
  PARTITION_ROW_THRESHOLD = 10_000
  DEFAULT_PARTITIONS = 4
  SUPPORTED_FORMATS = ["csv", "xlsx", "parquet", "json"]
  CHECKPOINT_DIR = ".refineflow_cache/"
  ```

---

## Task 1.2 — Logger System (`logger.py`)

- [ ] Create `RefineLogger` class with timestamped output
- [ ] Support log levels: `INFO`, `WARNING`, `ERROR`, `SUCCESS`
- [ ] Output format:
  ```
  [✓] Partitioned dataset into 8 chunks
  [!] Warning: 2 corrupted columns detected
  [✗] Error: Could not read file encoding
  ```
- [ ] Optionally write logs to `refineflow_run.log`
- [ ] Color-coded terminal output using `colorama`

```python
# Usage
from refineflow.logger import RefineLogger
log = RefineLogger()
log.success("Dataset scanned successfully")
log.warning("Duplicate risk is HIGH")
log.error("File not found")
```

---

## Task 1.3 — Dataset Scanner (`scanner.py`)

Core class: `DatasetScanner(filepath)`

### Sub-tasks

- [ ] **Format detection** — infer format from extension (csv, xlsx, parquet, json)
- [ ] **File size** — `os.path.getsize()` converted to GB
- [ ] **Encoding detection** — `chardet.detect()` on raw bytes sample
- [ ] **Row & column count** — fast estimation without full load
  - For CSV: count newlines in file
  - For Parquet: read metadata only
- [ ] **Memory estimate** — load a 1000-row sample, extrapolate
- [ ] **Datatype complexity** — count mixed-type and object columns
- [ ] **Corrupted column detection** — columns with >90% nulls or all-identical values
- [ ] **Duplicate probability** — hash first 10k rows, check collision rate
- [ ] **Missing value map** — per-column null percentage from sample
- [ ] **Schema consistency** — detect columns with inconsistent data patterns
- [ ] **Engine recommendation** — based on size and row count

### Output Format

```python
scan_report = {
    "file": "sales.csv",
    "size_gb": 12.4,
    "rows": 120_000_000,
    "columns": 48,
    "encoding": "utf-8",
    "estimated_memory_gb": 9.6,
    "corrupted_columns": ["col_x", "col_y"],
    "duplicate_risk": "High",          # Low / Medium / High
    "missing_values": {
        "age": 0.12,
        "revenue": 0.03,
        "city": 0.00
    },
    "datatype_complexity": "Mixed",    # Simple / Mixed / Complex
    "recommended_engine": "Dask",
    "recommended_partitions": 8
}
```

### Console Output

```
╔══════════════════════════════════════════════╗
║         RefineFlow — Dataset Scan Report     ║
╠══════════════════════════════════════════════╣
║  File:             sales.csv                 ║
║  Size:             12.4 GB                   ║
║  Rows:             120,000,000               ║
║  Columns:          48                        ║
║  Encoding:         UTF-8                     ║
║  Corrupted Cols:   2 (col_x, col_y)          ║
║  Duplicate Risk:   HIGH                      ║
║  Recommended:      Dask | 8 Partitions       ║
╚══════════════════════════════════════════════╝
```

---

## Task 1.4 — Base Cleaner Class (`cleaner.py`)

- [ ] `__init__(file, partitions=None, backend="auto", export_format="csv")`
- [ ] Validate file exists and format is supported
- [ ] Store config: `self.config`
- [ ] Store scan report: `self.scan_report`
- [ ] Store cleaned df: `self.df`
- [ ] Store running stats: `self.stats = {}`
- [ ] Fluent API — every method returns `self`
- [ ] Expose `.scan()` method which calls `DatasetScanner`

```python
class Cleaner:
    def __init__(self, file, partitions=None, backend="auto", export_format="csv"):
        self.file = file
        self.partitions = partitions
        self.backend = backend
        self.export_format = export_format
        self.scan_report = {}
        self.stats = {}
        self.df = None
        self.chunks = []
        self.log = RefineLogger()

    def scan(self):
        scanner = DatasetScanner(self.file)
        self.scan_report = scanner.run()
        scanner.print_report()
        return self   # enables chaining
```

---

## Task 1.5 — Utility Functions (`utils.py`)

- [ ] `bytes_to_gb(size_bytes)` — convert bytes to GB string
- [ ] `format_number(n)` — `1200000` → `"1,200,000"`
- [ ] `detect_file_format(filepath)` — return format string
- [ ] `timer_decorator` — wraps any function and logs runtime
- [ ] `safe_sample(df, n=1000)` — safe sampling without errors

---

## Deliverable

```python
from refineflow import Cleaner

Cleaner("sales.csv").scan()
```

**Expected Output:**
```
[✓] File detected: sales.csv (CSV, UTF-8)
[✓] Scan complete

╔══════════════════════════════════╗
║   RefineFlow — Dataset Report    ║
║  Size:          12.4 GB          ║
║  Rows:          120,000,000      ║
║  Columns:       48               ║
║  Corrupt Cols:  2                ║
║  Duplicate Risk: HIGH            ║
║  Recommended:   Dask | 8 Parts   ║
╚══════════════════════════════════╝
```

---

## Tests (`tests/test_module1.py`)

- [ ] Test scanner on small CSV (< 1MB)
- [ ] Test encoding detection on UTF-8 and Latin-1 files
- [ ] Test corrupted column detection (all-null column)
- [ ] Test scan output has all required keys
- [ ] Test Cleaner instantiation with valid/invalid file paths
- [ ] Test fluent API returns `self` from `.scan()`

---

## Dependencies Installed

```bash
pip install pandas polars pyarrow psutil chardet tqdm colorama
```

---

## Real-World Problems Handled in This Module

> These are detected during **scanning** — before any cleaning begins. Early detection allows the engine to choose the right strategy for every downstream step.

### Encoding Problems

| Problem | Real Example | Solution | Internal Technique |
|---------|-------------|----------|--------------------|
| Broken unicode | `Mumba▯` | Detect encoding before load, repair on read | `chardet.detect()` on raw bytes sample |
| Mixed encodings | UTF-8 + Latin-1 in same file | Detect encoding per-chunk, standardize to UTF-8 | Charset detector with confidence scoring |
| Corrupted currency symbols | `â‚¹` instead of `₹` | Character repair mapping table | Encoding repair engine (mojibake detection) |

**How we solve it in the Scanner:**
- Read first 50KB of raw bytes → run `chardet` → store detected encoding in `scan_report["encoding"]`
- Build a `mojibake_map` dict: `{"â‚¹": "₹", "â€™": "'"}` — applied during text cleaning (Module 3)
- Flag files with confidence < 80% as `encoding_risk: HIGH` in scan report

---

### CSV Structure Problems

| Problem | Real Example | Solution | Internal Technique |
|---------|-------------|----------|--------------------|
| Broken delimiters | Extra commas in row | Stateful CSV parser with quote-awareness | `csv.reader` with `quotechar` + error recovery |
| Multi-line cells | Cell contains newline breaking rows | Row reconstruction using quote-balance detection | Parsing engine with state machine |
| Uneven columns | Some rows have 47 cols, others 48 | Schema reconstruction, pad missing with NaN | Structural validator |
| Quote escaping issues | `"John "Doe""` | Sanitize malformed quotes before parse | Escape handler with regex pre-processing |

**How we solve it in the Scanner:**
- Before loading, scan first 500 lines to detect: delimiter, quoting style, average columns per row
- If column count variance > 0: flag `csv_structure_risk: True` in scan report
- Pass `error_bad_lines=False` + custom `on_bad_lines="warn"` to pandas reader
- Reconstruct broken rows by joining consecutive lines until column count matches expected

---

### Column Name Problems

| Problem | Real Example | Solution | Internal Technique |
|---------|-------------|----------|--------------------|
| Spaces in column names | `Customer Name` | Snake_case conversion | Column normalizer |
| Duplicate column names | `sales`, `sales` | Auto-suffix with `_1`, `_2` | Column resolver |
| Random symbols in names | `revenue($)` | Regex strip of non-alphanumeric chars | Regex sanitizer |
| Inconsistent casing | `CITY`, `city`, `City` | Lowercase normalization on all col names | Standardizer |

**How we solve it in the Scanner:**
- Detect all above patterns on load, store `column_issues` in scan report
- Column normalization applied immediately after load (before partitioning):
  ```python
  df.columns = (df.columns
      .str.strip()
      .str.lower()
      .str.replace(r'[^a-z0-9_]', '_', regex=True)
      .str.replace(r'_+', '_', regex=True))
  ```
- Duplicate columns: append `_1`, `_2` suffix and log warning

---

### Schema Drift Detection (Scanning Phase)

| Problem | Real Example | Solution | Internal Technique |
|---------|-------------|----------|--------------------|
| Column renamed between runs | `cust_name` → `customer_name` | Compare vs saved snapshot | Schema diff engine |
| Datatype changed | int → string between pipeline runs | Adaptive schema inference | Dynamic type analyzer |
| Missing expected columns | Field removed from upstream | Schema reconciliation + alert | Validation layer |

**How we solve it in the Scanner:**
- On first scan: save `schema_snapshot.json` with column names + dtypes
- On every subsequent scan: diff current schema vs snapshot
- Output `schema_drift_report` in scan results:
  ```python
  {
    "new_columns": ["discount_code"],
    "removed_columns": ["cust_name"],
    "renamed_likely": [{"old": "cust_name", "new": "customer_name", "similarity": 0.91}],
    "type_changes": {"revenue": {"was": "int64", "now": "object"}}
  }
  ```
- Use `difflib.SequenceMatcher` to suggest likely renames (similarity > 0.85)
- Raise `SchemaDriftWarning` — not an error, pipeline continues
