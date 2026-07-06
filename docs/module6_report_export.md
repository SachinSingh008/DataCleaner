# Module 6 — Report Generation & Export Engine

> **Goal:** Generate rich cleaning reports (HTML/JSON/PDF), handle multi-format data exports, provide a CLI interface, and complete the full fluent API wiring.

---

## File Structure

```
refineflow/
├── reporter.py              # Report generator
├── exporter.py              # Multi-format export engine
├── cli.py                   # Command-line interface
├── schema_drift.py          # Schema drift detection
└── templates/
    └── report_template.html # Jinja2 HTML report template
```

---

## Task 6.1 — Report Generator (`reporter.py`)

### Class: `ReportGenerator(stats, scan_report, validation_report)`

Collects stats accumulated across all modules and renders them into reports.

---

### 6.1.1 — Stats Aggregation

Combine all module stats into a unified report dict:

```python
full_report = {
    "meta": {
        "file": "sales.csv",
        "runtime_seconds": 272.4,
        "engine_used": "Dask",
        "partitions": 8,
        "timestamp": "2025-01-15T14:32:00Z"
    },
    "dataset": {
        "rows_original": 1_212_452,
        "rows_final": 1_200_000,
        "columns_original": 48,
        "columns_final": 46
    },
    "cleaning": {
        "nulls_filled": 18_341,
        "duplicates_removed": 12_452,     # per-chunk + cross-chunk
        "outliers_handled": 2_891,
        "type_conversions": 6,
        "text_columns_cleaned": 3
    },
    "memory": {
        "before_gb": 7.2,
        "after_gb": 2.1,
        "reduction_percent": 70.8
    },
    "per_column": {
        "age": {"nulls_filled": 1203, "strategy": "median", "outliers": 32},
        "revenue": {"nulls_filled": 302, "strategy": "median", "outliers": 18},
        "city": {"variants_merged": 14, "canonical": 6}
    },
    "validation": {
        "cross_chunk_dupes": 1_482,
        "categories_standardized": 3,
        "integrity_violations_fixed": 23
    },
    "export": {
        "files": ["cleaned_sales.parquet", "powerbi_ready_sales.parquet"],
        "total_size_mb": 430
    }
}
```

---

### 6.1.2 — HTML Report (`templates/report_template.html`)

A styled, self-contained HTML report:

- [ ] **Header section**: RefineFlow logo, file name, run timestamp, runtime
- [ ] **Dataset Summary card**: rows/cols before → after, engine used
- [ ] **Cleaning Summary table**: nulls filled, dupes removed, outliers handled
- [ ] **Memory Reduction bar**: visual before/after bar (inline SVG)
- [ ] **Per-column table**: null %, strategy used, type conversion, outliers
  - Color-coded: green (clean), yellow (warned), red (issues)
- [ ] **Validation section**: cross-chunk dedup result, categories standardized
- [ ] **Cleaning Log timeline**: all `[✓]` log entries in order
- [ ] **Export section**: list of output files generated

Use `Jinja2` for templating:
```python
from jinja2 import Environment, FileSystemLoader
env = Environment(loader=FileSystemLoader("templates/"))
template = env.get_template("report_template.html")
html = template.render(report=full_report)
```

- [ ] Save as: `refineflow_report.html`
- [ ] Ensure it is **fully self-contained** (no external CDN dependencies for offline use)

---

### 6.1.3 — JSON Report

- [ ] Dump `full_report` dict as formatted JSON
- [ ] Save as: `refineflow_report.json`
- [ ] Machine-readable for downstream ETL pipelines or CI/CD checks

```python
import json
with open("refineflow_report.json", "w") as f:
    json.dump(full_report, f, indent=2, default=str)
```

---

### 6.1.4 — PDF Report (optional)

- [ ] Convert HTML report → PDF using `weasyprint`
- [ ] Only if `weasyprint` is installed (graceful skip if not)
- [ ] Save as: `refineflow_report.pdf`

```python
.generate_report(format="all")   # generates html + json + pdf
.generate_report(format="html")  # only html
.generate_report(format="json")  # only json
```

- [ ] Log:
  ```
  [✓] Report Generated:
      → refineflow_report.html  (145 KB)
      → refineflow_report.json  (28 KB)
  ```

---

## Task 6.2 — Export Engine (`exporter.py`)

### Class: `DataExporter(df, output_dir="./", filename_prefix="cleaned")`

```python
.export(format="parquet", output_dir="./output/")
```

#### Supported Formats

| Format | Method | Notes |
|--------|--------|-------|
| `csv` | `df.to_csv()` | UTF-8, no index |
| `parquet` | `df.to_parquet()` | Snappy compression |
| `excel` | `df.to_excel()` | Auto column widths |
| `json` | `df.to_json()` | orient="records" |
| `all` | All of the above | Export all formats |

- [ ] Auto-name files: `cleaned_<original_name>.<ext>`
- [ ] Create `output_dir` if it does not exist
- [ ] Log file size before and after export:
  ```
  [✓] Exported: output/cleaned_sales.parquet
      Size: 380 MB (original: 12.4 GB → 97% reduction via Parquet)
  ```
- [ ] **Parquet optimizations**:
  - `compression="snappy"` (fast + small)
  - `engine="pyarrow"`
- [ ] **Excel optimizations**:
  - Auto-fit column widths using `openpyxl`
  - Freeze top row (header)
  - Add auto-filter to header row
- [ ] Track all exported files in `self.stats["export"]`

---

## Task 6.3 — Schema Drift Detector (`schema_drift.py`)

### Class: `SchemaDriftDetector(current_df, snapshot_path="schema_snapshot.json")`

- [ ] **First run**: save schema snapshot:
  ```json
  {
    "columns": {"age": "int32", "city": "category", "revenue": "float32"},
    "row_count": 1_200_000,
    "created_at": "2025-01-15T14:32:00Z"
  }
  ```
- [ ] **Subsequent runs**: compare current schema vs snapshot:
  - New columns detected → `SchemaDriftWarning: 2 new columns`
  - Removed columns → `SchemaDriftWarning: 1 column removed`
  - Type changes → `SchemaDriftWarning: revenue changed float32 → object`
- [ ] Raise `SchemaDriftWarning` (not an error — allow continuation)
- [ ] Include drift report in final report JSON

---

## Task 6.4 — Full Fluent API (Complete `cleaner.py`)

Wire all modules into the complete fluent API:

```python
class Cleaner:
    def scan(self): ...                             # Module 1
    def auto_clean(self): ...                       # Module 2 + 3 + 4
    def optimize_memory(self): ...                  # Module 3 (standalone)
    def prepare_for_powerbi(self, output_dir): ...  # Module 5
    def prepare_for_tableau(self, output_dir): ...  # Module 5
    def recommend_visualizations(self): ...         # Module 5
    def generate_report(self, format="html"): ...   # Module 6
    def export(self, format="parquet", ...): ...    # Module 6
```

Every method:
- Returns `self`
- Logs its action via `RefineLogger`
- Updates `self.stats`

**Full Chain Example:**
```python
Cleaner("enterprise_data.csv", partitions=8, backend="auto") \
    .scan() \
    .auto_clean() \
    .optimize_memory() \
    .prepare_for_powerbi(output_dir="./bi_output/") \
    .prepare_for_tableau(output_dir="./bi_output/") \
    .recommend_visualizations() \
    .generate_report(format="html") \
    .export(format="parquet", output_dir="./output/")
```

---

## Task 6.5 — CLI Interface (`cli.py`)

```bash
# Basic usage
refineflow clean sales.csv

# With options
refineflow clean sales.csv --partitions 8 --backend dask --export parquet --report html

# Scan only
refineflow scan sales.csv

# Recommend visualizations
refineflow recommend sales.csv
```

#### CLI Commands

| Command | Description |
|---------|-------------|
| `refineflow scan <file>` | Run dataset scanner only |
| `refineflow clean <file>` | Full auto_clean pipeline |
| `refineflow recommend <file>` | Scan + recommend visualizations |

#### CLI Options

| Flag | Default | Description |
|------|---------|-------------|
| `--partitions N` | auto | Number of partitions |
| `--backend NAME` | auto | pandas / polars / dask / spark |
| `--export FORMAT` | csv | csv / parquet / excel / json / all |
| `--report FORMAT` | html | html / json / pdf / all |
| `--output-dir DIR` | `./` | Output directory |
| `--no-report` | False | Skip report generation |

- [ ] Implement using `click` library
- [ ] Show `tqdm` progress bar in terminal
- [ ] Final summary on completion:
  ```
  ┌──────────────────────────────────────┐
  │  RefineFlow — Run Complete           │
  ├──────────────────────────────────────┤
  │  Rows Cleaned:    1,200,000          │
  │  Dupes Removed:   12,452             │
  │  Nulls Filled:    18,341             │
  │  Memory Saved:    7.2 GB → 2.1 GB   │
  │  Runtime:         4m 32s            │
  │  Exports:         cleaned_sales.parquet │
  └──────────────────────────────────────┘
  ```

---

## Deliverable

### Full Pipeline Run

```bash
$ refineflow clean enterprise_data.csv --partitions 8 --export parquet --report html
```

**Expected Output:**
```
[✓] Dataset scanned: 120M rows, 48 cols, 12.4 GB
[✓] Engine selected: Dask
[✓] Partitioned into 8 chunks
[✓] Parallel cleaning complete (8/8 chunks)
[✓] Merged: 8 chunks → 1,200,000 rows
[✓] Global validation complete
[✓] Power BI export: powerbi_ready_enterprise_data.parquet
[✓] Report generated: refineflow_report.html

┌──────────────────────────────────────┐
│  RefineFlow — Run Complete           │
│  Memory: 12.4 GB → 2.8 GB (77%)     │
│  Runtime: 4m 32s                    │
└──────────────────────────────────────┘
```

---

## Tests (`tests/test_module6.py`)

- [ ] Test HTML report generates valid HTML file
- [ ] Test JSON report has all required keys
- [ ] Test CSV export creates readable file with correct row count
- [ ] Test Parquet export creates valid file readable by pandas
- [ ] Test Excel export has frozen header row and auto-filter
- [ ] Test CLI `scan` command runs without error
- [ ] Test CLI `clean` command with `--export parquet` creates output
- [ ] Test schema drift detector detects added column
- [ ] Test schema drift detector detects type change
- [ ] Test full fluent chain runs end-to-end on sample CSV

---

## Dependencies Installed

```bash
pip install jinja2 click openpyxl pyarrow
# Optional:
pip install weasyprint   # for PDF export
```

---

## Final Package Dependencies Summary

```toml
[project]
name = "refineflow"
version = "0.1.0"
dependencies = [
    "pandas>=2.0",
    "polars>=0.19",
    "pyarrow>=13.0",
    "psutil>=5.9",
    "chardet>=5.0",
    "tqdm>=4.65",
    "colorama>=0.4",
    "scipy>=1.11",
    "jinja2>=3.1",
    "click>=8.1",
    "openpyxl>=3.1",
    "dask[dataframe]>=2023.1",
    "regex>=2023.1",
    "difflib",       # built-in
]

[project.optional-dependencies]
pdf = ["weasyprint"]
tableau = ["pantab"]
spark = ["pyspark>=3.4"]
```

---

## Real-World Problems Handled in This Module

> Module 6 is the **accountability layer**. Every fix, warning, and transformation made across all modules is captured here. It also handles problems that only become visible at reporting time.

### AI Cleaning & Confidence Scoring (Report Layer)

| Problem | Real Example | Solution | Technique |
|---------|-------------|----------|-----------|
| Low-confidence corrections | Ambiguous value `01/02/2025` (Jan 2 or Feb 1?) | Flag in report with confidence score | Confidence scoring on every auto-correction |
| Unknown dataset semantics | Columns with unclear names like `col_x` | Reported as "unresolved" in per-column table | Human review queue in HTML report |
| High-risk changes logged | Auto-dropped column with 96% nulls | Full audit trail of every deletion | Cleaning log timeline in report |

**Confidence scoring in report:**
```python
# Every auto-correction carries a confidence score
# Low confidence (<70%) → flagged in HTML report as REVIEW NEEDED
correction_log = [
    {
        "column": "order_date",
        "action": "format_converted",
        "from": "01/02/2025",
        "to": "2025-02-01",
        "confidence": 0.62,    # ambiguous: DD/MM or MM/DD?
        "flag": "REVIEW"
    },
    {
        "column": "revenue",
        "action": "symbol_stripped",
        "from": "₹5000",
        "to": 5000.0,
        "confidence": 0.99,
        "flag": "OK"
    }
]
# HTML report shows REVIEW items highlighted in yellow
# User can override decisions via config on next run
```

**Human review queue section in HTML report:**
```html
<!-- Generated by Jinja2 template -->
<section class="review-queue">
  <h2>⚠ Items Requiring Human Review (3)</h2>
  <table>
    <tr class="low-confidence">
      <td>order_date</td>
      <td>Format ambiguous: DD/MM vs MM/DD</td>
      <td>Confidence: 62%</td>
      <td><button>Accept</button> <button>Override</button></td>
    </tr>
  </table>
</section>
```

---

### Schema Drift in Reports

| Problem | Real Example | Solution | Technique |
|---------|-------------|----------|-----------|
| Column renamed | `cust_name` → `customer_name` | Drift report section in HTML/JSON output | Schema diff engine result embedded in report |
| Datatype changed | `revenue` changed int → object | Type change highlighted in red in report | Per-column dtype change log |
| Missing expected column | `discount` column removed | Error section with likely cause | Validation layer alert → surfaced in report |

**Schema drift section in JSON report:**
```json
{
  "schema_drift": {
    "detected": true,
    "new_columns": ["discount_code"],
    "removed_columns": ["cust_name"],
    "renamed_likely": [
      {"old": "cust_name", "new": "customer_name", "similarity": 0.91}
    ],
    "type_changes": {
      "revenue": {"was": "int64", "now": "object", "risk": "HIGH"}
    }
  }
}
```
