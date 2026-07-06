# RefineFlow — Detailed Implementation Plan

> **6-Module Breakdown** | Build order: Module 1 → 6 (each depends on previous)

---

## Module 1 — Core Infrastructure & Dataset Scanner

### Goal
Establish the project skeleton, base `Cleaner` class, and intelligent dataset scanning system.

### File Structure
```
refineflow/
├── __init__.py
├── cleaner.py          # Main Cleaner class (entry point)
├── scanner.py          # Dataset Scanner
├── config.py           # Global thresholds & constants
├── logger.py           # Real-time logging system
└── utils.py            # Shared utility functions
docs/
tests/
setup.py
README.md
```

### Tasks

#### 1.1 — Project Setup
- [ ] Initialize Python package with `setup.py` / `pyproject.toml`
- [ ] Define dependencies: `pandas`, `polars`, `pyarrow`, `psutil`, `chardet`, `tqdm`
- [ ] Create `config.py` with global constants:
  ```python
  SMALL_DATA_THRESHOLD_GB = 10
  PARTITION_ROW_THRESHOLD = 10_000
  DEFAULT_PARTITIONS = 4
  SUPPORTED_FORMATS = ["csv", "xlsx", "parquet", "json"]
  ```

#### 1.2 — Logger System (`logger.py`)
- [ ] Implement `RefineLogger` with timestamped console output
- [ ] Support log levels: `INFO`, `WARNING`, `ERROR`, `SUCCESS`
- [ ] Format: `[✓] Partitioned dataset into 8 chunks`
- [ ] Write logs to `refineflow_run.log` optionally

#### 1.3 — Dataset Scanner (`scanner.py`)
Core class: `DatasetScanner`

- [ ] **File ingestion** — detect format (CSV, Excel, Parquet, JSON), load sample
- [ ] **Size detection** — `os.path.getsize()` → convert to GB
- [ ] **Row/column count** — fast estimation without full load
- [ ] **Memory estimate** — `df.memory_usage(deep=True).sum()`
- [ ] **Encoding detection** — `chardet.detect()` on raw bytes
- [ ] **Datatype complexity** — count mixed-type columns
- [ ] **Corrupted column detection** — columns with >90% nulls or all-identical values
- [ ] **Duplicate probability** — hash-based sampling on first 10k rows
- [ ] **Schema consistency** — detect columns with inconsistent patterns
- [ ] **Missing value map** — per-column null percentage

```python
# Output example
{
  "size_gb": 12.4,
  "rows": 120_000_000,
  "columns": 48,
  "corrupted_columns": ["col_x", "col_y"],
  "duplicate_risk": "High",
  "encoding": "utf-8",
  "missing_values": {"age": 0.12, "revenue": 0.03},
  "recommended_engine": "Spark"
}
```

#### 1.4 — Base Cleaner Class (`cleaner.py`)
- [ ] `__init__(file, partitions=None, backend="auto", export_format="csv")`
- [ ] Fluent API (method chaining): every method returns `self`
- [ ] Expose `.scan()` → calls `DatasetScanner`, prints report
- [ ] Store scan results in `self.scan_report`

### Deliverable
```python
from refineflow import Cleaner
report = Cleaner("sales.csv").scan()
# Prints formatted scan report to console
```

---

## Module 2 — Adaptive Engine Selection & Partitioning

### Goal
Auto-select the right processing backend and divide the dataset into manageable, independently processable partitions.

### New Files
```
refineflow/
├── engine/
│   ├── __init__.py
│   ├── selector.py       # Engine selection logic
│   ├── pandas_engine.py  # Pandas/Polars backend
│   ├── dask_engine.py    # Dask backend
│   └── spark_engine.py   # Spark backend (optional/future)
├── partitioner.py        # Divide & conquer partitioning
```

### Tasks

#### 2.1 — Engine Selector (`engine/selector.py`)
- [ ] `EngineSelector(scan_report)` → returns engine name
- [ ] Decision logic:
  ```python
  if size_gb < 10:
      if rows < 1_000_000:
          return "pandas"
      else:
          return "polars"
  elif size_gb < 100:
      return "dask"
  else:
      return "spark"
  ```
- [ ] Allow manual override: `backend="pandas"` forces selection
- [ ] Log selected engine with reason

#### 2.2 — Pandas Engine (`engine/pandas_engine.py`)
- [ ] Wrap pandas `read_csv`, `read_excel`, `read_parquet`
- [ ] Chunked reading via `chunksize` for medium files
- [ ] Expose uniform `.load()`, `.save()` interface

#### 2.3 — Polars Engine (`engine/polars_engine.py`)
- [ ] Use `polars.scan_csv()` (lazy evaluation)
- [ ] Expose same `.load()`, `.save()` interface
- [ ] Leverage Polars' native multi-threading

#### 2.4 — Dask Engine (`engine/dask_engine.py`)
- [ ] `dask.dataframe.read_csv()` with auto-partitioning
- [ ] Set `npartitions` from scan row count
- [ ] Delayed computation graph

#### 2.5 — Partitioner (`partitioner.py`)
- [ ] `DataPartitioner(df, n_partitions)` 
- [ ] Split DataFrame into N equal row chunks
- [ ] Store as list of DataFrames or file-backed chunks
- [ ] If rows < `PARTITION_ROW_THRESHOLD`: skip partitioning, process directly
- [ ] Assign chunk IDs for tracking: `chunk_0`, `chunk_1`, ...
- [ ] Support checkpoint saving per chunk to disk (`/tmp/refineflow/`)

```python
# Partitioning flow
partitioner = DataPartitioner(df, n_partitions=8)
chunks = partitioner.split()
# [chunk_0_df, chunk_1_df, ..., chunk_7_df]
```

#### 2.6 — Wire into Cleaner
- [ ] After `.scan()`, auto-call `EngineSelector`
- [ ] Load data using selected engine
- [ ] Run partitioner if row count > threshold
- [ ] Store chunks in `self.chunks`

### Deliverable
```python
Cleaner("sales.csv", partitions=8).scan()
# [✓] Engine selected: Polars (size: 4.2 GB)
# [✓] Partitioned dataset into 8 chunks
```

---

## Module 3 — Parallel Cleaning Engine

### Goal
Apply all cleaning operations to each partition independently and in parallel using multiprocessing/multithreading.

### New Files
```
refineflow/
├── cleaning/
│   ├── __init__.py
│   ├── pipeline.py         # Orchestrates cleaning steps per chunk
│   ├── null_handler.py     # Missing value strategies
│   ├── deduplicator.py     # Duplicate removal
│   ├── type_fixer.py       # Datatype detection & fixing
│   ├── text_cleaner.py     # Text normalization
│   ├── outlier_detector.py # IQR, Z-score, percentile
│   ├── memory_optimizer.py # Downcast dtypes
│   └── validator.py        # Per-chunk invalid value checks
├── parallel_runner.py      # Multiprocessing pool manager
```

### Tasks

#### 3.1 — Null Handler (`null_handler.py`)
- [ ] Detect column type: numerical / categorical / datetime
- [ ] Numerical strategies: `mean`, `median`, `interpolation`
- [ ] Categorical strategies: `mode`, fill with `"Unknown"`
- [ ] Datetime: `ffill`, `bfill`, `interpolation`
- [ ] Per-column strategy override via config dict
- [ ] Track: count of nulls filled per column

#### 3.2 — Deduplicator (`deduplicator.py`)
- [ ] Hash-based row fingerprinting
- [ ] `df.drop_duplicates()` for pandas
- [ ] Support subset of key columns for dedup
- [ ] Track: rows removed count

#### 3.3 — Type Fixer (`type_fixer.py`)
Auto-detect and convert:
- [ ] String → datetime (via `pd.to_datetime` with error handling)
- [ ] String → boolean (`yes/no`, `true/false`, `1/0`)
- [ ] String with `$`, `%`, `€` → float (strip symbols first)
- [ ] High-cardinality object → `category` if unique% < 50%
- [ ] Numeric strings → int/float
- [ ] ID columns → string (preserve leading zeros)

#### 3.4 — Text Cleaner (`text_cleaner.py`)
- [ ] Strip leading/trailing whitespace
- [ ] Normalize multiple spaces → single space
- [ ] Unicode normalization: `unicodedata.normalize("NFKD", ...)`
- [ ] Fix corrupted characters (replace `\ufffd`)
- [ ] Standardize casing: `Title Case` for names, `UPPER` for codes
- [ ] Remove invisible characters (zero-width spaces etc.)

#### 3.5 — Outlier Detector (`outlier_detector.py`)
Strategies (configurable per column):
- [ ] **IQR method**: flag values below Q1-1.5×IQR or above Q3+1.5×IQR
- [ ] **Z-score**: flag |z| > 3
- [ ] **Percentile**: clip values at [1%, 99%] by default
- [ ] Actions: `flag`, `remove`, `clip`, `replace_with_median`
- [ ] Track: outlier count per column

#### 3.6 — Memory Optimizer (`memory_optimizer.py`)
- [ ] `int64` → `int32` or `int16` based on value range
- [ ] `float64` → `float32`
- [ ] `object` with low cardinality → `category`
- [ ] Report memory before/after per chunk
- [ ] Target: 40–80% reduction

#### 3.7 — Cleaning Pipeline (`pipeline.py`)
- [ ] `CleaningPipeline(chunk_df, config)` 
- [ ] Ordered step execution:
  1. Type fixing
  2. Null handling
  3. Text cleaning
  4. Deduplication
  5. Outlier detection
  6. Memory optimization
  7. Validation
- [ ] Each step logs its action + stats
- [ ] Returns cleaned chunk + stats dict

#### 3.8 — Parallel Runner (`parallel_runner.py`)
- [ ] `ParallelRunner(chunks, pipeline_config)`
- [ ] Use `concurrent.futures.ProcessPoolExecutor` for CPU-bound cleaning
- [ ] Fallback to `ThreadPoolExecutor` for IO-bound (Dask)
- [ ] Progress bar via `tqdm`
- [ ] **Fault tolerance**: wrap each chunk in try/except, retry up to 3×
- [ ] Checkpoint completed chunks to disk after each success
- [ ] Return: `[cleaned_chunk_0, cleaned_chunk_1, ...]`

### Deliverable
```python
Cleaner("sales.csv").auto_clean()
# [✓] Running parallel cleaning on 8 chunks...
# [✓] Chunk 1/8 — Nulls filled: 1,203 | Duplicates: 441 | Outliers: 32
# [✓] Chunk 2/8 — ...
```

---

## Module 4 — Hierarchical Merge & Global Validation

### Goal
Merge all cleaned chunks back into one DataFrame using hierarchical reduction, then run cross-partition validation to catch inconsistencies that per-chunk cleaning couldn't resolve.

### New Files
```
refineflow/
├── merger.py               # Hierarchical merge logic
├── global_validator.py     # Cross-partition validation
```

### Tasks

#### 4.1 — Hierarchical Merger (`merger.py`)
- [ ] `HierarchicalMerger(chunks)`
- [ ] Merge in tree-reduction pattern:
  ```
  Round 1: (0+1), (2+3), (4+5), (6+7)
  Round 2: (01+23), (45+67)
  Round 3: (0123+4567)
  ```
- [ ] Use `pd.concat()` with `ignore_index=True`
- [ ] Reset index after each merge level
- [ ] Handle mismatched columns (fill with NaN, log warning)
- [ ] Log total rows before/after merge

#### 4.2 — Global Validator (`global_validator.py`)
`GlobalValidator(merged_df)` — runs after full merge:

- [ ] **Global deduplication** — dedup across all chunks (catches cross-boundary duplicates)
- [ ] **Category standardization**:
  - Detect similar values using case normalization: `mumbai` / `MUMBAI` / `Mumbai` → `Mumbai`
  - Optional fuzzy matching with `difflib` for typo normalization
- [ ] **Schema reconciliation** — verify all expected columns present, warn on extras
- [ ] **Consistency checks**:
  - Date ranges (no future birthdates, no negative ages)
  - Referential checks (if `city` column exists, standardize against known list)
  - Revenue/metric columns: no negative values unless expected
- [ ] **Null audit** — final pass for any remaining nulls, apply fallback strategy
- [ ] Return: validated DataFrame + global validation report dict

### Deliverable
```python
# After merge + validation:
# [✓] Merged 8 chunks → 1,200,000 rows
# [✓] Global dedup removed 1,482 cross-chunk duplicates
# [✓] Standardized 3 categorical columns
# [✓] Schema validated — all 48 columns present
```

---

## Module 5 — Visualization Preparation & BI Optimization

### Goal
Transform the clean dataset into formats optimized for Power BI, Tableau, Streamlit, and AI analytics pipelines.

### New Files
```
refineflow/
├── viz/
│   ├── __init__.py
│   ├── prep_engine.py       # Base viz preparation
│   ├── powerbi_prep.py      # Power BI specific
│   ├── tableau_prep.py      # Tableau specific
│   ├── recommender.py       # Auto chart recommendation
│   └── feature_scaler.py    # Normalization & scaling
```

### Tasks

#### 5.1 — Base Viz Prep (`prep_engine.py`)
`VizPrepEngine(df)`:
- [ ] **Date formatting** — convert all datetime to ISO 8601
- [ ] **Column name sanitization** — remove spaces, special chars (BI tools hate them)
- [ ] **Aggregation helpers** — auto-detect group-by candidates
- [ ] **Category optimization** — reduce cardinality where safe
- [ ] **Label encoding** — encode categoricals for ML-ready output

#### 5.2 — Feature Scaler (`feature_scaler.py`)
- [ ] `StandardScaler` (Z-score normalization)
- [ ] `MinMaxScaler` (0–1 range)
- [ ] `RobustScaler` (outlier-resistant)
- [ ] Apply only to numerical columns, skip ID/date columns
- [ ] Store scaler state for inverse transform later

#### 5.3 — Power BI Prep (`powerbi_prep.py`)
`PowerBIPrep(df)`:
- [ ] Export to `.parquet` (Power BI's fastest format)
- [ ] Datetime columns → split into `Year`, `Month`, `Day`, `Quarter` columns
- [ ] Auto-detect **measures** (numerical aggregatable) vs **dimensions** (categorical)
- [ ] Generate `schema_hint.json` for Power BI data model suggestions
- [ ] Rename columns: replace spaces with `_`, remove special chars
- [ ] Remove columns with >95% nulls (useless in BI)

#### 5.4 — Tableau Prep (`tableau_prep.py`)
`TableauPrep(df)`:
- [ ] Export to `.csv` or `.hyper` (Tableau Hyper format via `pantab` if available)
- [ ] Prepare calculated field suggestions as metadata
- [ ] Aggregation-ready: ensure all dimension columns are clean strings
- [ ] Generate `tableau_metadata.json` with field types

#### 5.5 — Visualization Recommender (`recommender.py`)
`VizRecommender(df, scan_report)`:
- [ ] Analyze column types and distributions
- [ ] Rule-based recommendations:
  - Date + Numerical → **Line chart (Trend)**
  - Categorical + Numerical → **Bar chart (Comparison)**  
  - Single Categorical → **Pie/Donut chart (Distribution)**
  - Two Numerical → **Scatter plot (Correlation)**
  - Geo column detected → **Map chart**
- [ ] Output: ranked list of recommended charts with column mappings

```python
.recommend_visualizations()
# Output:
# 1. Revenue Trend → Line Chart (date_col × revenue_col)
# 2. Sales by Region → Bar Chart (region × sales)
# 3. Product Distribution → Pie Chart (product_category)
```

### Deliverable
```python
Cleaner("sales.csv") \
    .auto_clean() \
    .prepare_for_powerbi()   # exports powerbi_ready.parquet
    .prepare_for_tableau()   # exports tableau_ready.csv
    .recommend_visualizations()
```

---

## Module 6 — Report Generation & Export Engine

### Goal
Generate rich cleaning reports (HTML/PDF/JSON), handle multi-format exports, and provide a polished CLI interface and full fluent API.

### New Files
```
refineflow/
├── reporter.py          # Report generation
├── exporter.py          # Multi-format export
├── cli.py               # Command-line interface
└── templates/
    └── report.html      # HTML report template
```

### Tasks

#### 6.1 — Report Generator (`reporter.py`)
`ReportGenerator(cleaning_stats, scan_report, global_validation_report)`:

Collects all stats accumulated across modules:
- [ ] Rows before / after
- [ ] Duplicates removed (per-chunk + global)
- [ ] Nulls filled (per column)
- [ ] Outliers handled (per column)
- [ ] Memory before / after (GB)
- [ ] Dtypes converted
- [ ] Engine used, partitions, runtime

**HTML Report**:
- [ ] Jinja2 template with styled sections
- [ ] Per-column null heatmap (HTML table with color coding)
- [ ] Memory reduction bar chart (inline SVG or Chart.js CDN)
- [ ] Cleaning log timeline
- [ ] Export as `refineflow_report.html`

**JSON Report**:
- [ ] Full stats as structured JSON
- [ ] Machine-readable for downstream pipelines
- [ ] Export as `refineflow_report.json`

**PDF Report** *(optional)*:
- [ ] Use `weasyprint` to convert HTML → PDF
- [ ] Export as `refineflow_report.pdf`

```python
.generate_report(format="html")  # or "json", "pdf", "all"
```

#### 6.2 — Export Engine (`exporter.py`)
`DataExporter(df, output_dir, filename_prefix)`:
- [ ] **CSV** — `df.to_csv()` with optimized encoding
- [ ] **Excel** — `df.to_excel()` with auto column widths
- [ ] **Parquet** — `df.to_parquet()` with snappy compression
- [ ] **JSON** — `df.to_json()` with orient="records"
- [ ] Auto-name output files: `cleaned_sales.csv`, `cleaned_sales.parquet`
- [ ] Support `output_dir` parameter for destination folder
- [ ] Log file size before/after export

```python
.export(format="parquet", output_dir="./output/")
# [✓] Exported: output/cleaned_sales.parquet (1.2 GB → 380 MB)
```

#### 6.3 — Full Fluent API (wire-up in `cleaner.py`)
Complete method chain:
```python
Cleaner("enterprise_data.csv", partitions=8, backend="auto") \
    .scan()                          # Module 1
    .auto_clean()                    # Module 2 + 3 + 4
    .optimize_memory()               # Module 3 (standalone)
    .prepare_for_powerbi()           # Module 5
    .prepare_for_tableau()           # Module 5
    .recommend_visualizations()      # Module 5
    .generate_report(format="html")  # Module 6
    .export(format="parquet")        # Module 6
```

Each method:
- Returns `self` for chaining
- Logs its actions via `RefineLogger`
- Updates `self.stats` dict for final report

#### 6.4 — CLI Interface (`cli.py`)
```bash
refineflow clean sales.csv --partitions 8 --export parquet --report html
refineflow scan sales.csv
refineflow recommend sales.csv
```
- [ ] Use `argparse` or `click`
- [ ] Support all major Cleaner options as flags
- [ ] Progress bar in terminal

#### 6.5 — Schema Drift Detection
- [ ] Save schema snapshot on first run: `schema_snapshot.json`
- [ ] On subsequent runs, compare current schema vs snapshot
- [ ] Report: new columns, removed columns, type changes
- [ ] Raise `SchemaDriftWarning` if mismatch detected

### Deliverable
Full end-to-end working pipeline:
```bash
$ refineflow clean enterprise_data.csv --partitions 8 --export parquet --report html

[✓] Dataset scanned: 120M rows, 48 cols, 12.4 GB
[✓] Engine selected: Dask
[✓] Partitioned into 8 chunks
[✓] Parallel cleaning complete (8/8 chunks)
[✓] Merged & globally validated
[✓] Power BI export ready
[✓] Report generated: refineflow_report.html
[✓] Exported: cleaned_enterprise_data.parquet
    Memory: 12.4 GB → 2.8 GB (77% reduction)
    Runtime: 4m 32s
```

---

## Build Order & Dependencies

```
Module 1 ──► Module 2 ──► Module 3
                               │
                               ▼
                          Module 4
                               │
                               ▼
                          Module 5
                               │
                               ▼
                          Module 6
```

## Module Summary Table

| Module | Name                          | Key Output                        | Dependencies      |
|--------|-------------------------------|-----------------------------------|-------------------|
| 1      | Core Infrastructure & Scanner | `Cleaner` class, scan report      | None              |
| 2      | Engine Selection & Partitioner| Engine + chunked data             | Module 1          |
| 3      | Parallel Cleaning Engine      | Cleaned chunks + stats            | Module 2          |
| 4      | Merge & Global Validation     | Single validated DataFrame        | Module 3          |
| 5      | Viz Prep & BI Optimization    | BI-ready exports + chart hints    | Module 4          |
| 6      | Report & Export Engine        | Reports, final files, CLI         | All modules       |

## Tech Stack Per Module

| Module | Core Libraries                                 |
|--------|------------------------------------------------|
| 1      | `pandas`, `polars`, `psutil`, `chardet`        |
| 2      | `dask`, `polars`, `pyarrow`                    |
| 3      | `concurrent.futures`, `tqdm`, `scipy`, `regex` |
| 4      | `difflib`, `pandas`                            |
| 5      | `pyarrow`, `jinja2`, `pantab` (optional)       |
| 6      | `jinja2`, `click`, `weasyprint` (optional)     |
