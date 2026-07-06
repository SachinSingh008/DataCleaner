# Module 5 — Visualization Preparation & BI Optimization

> **Goal:** Transform the clean dataset into formats optimized for Power BI, Tableau, Streamlit, and AI analytics pipelines. Includes chart recommendations and feature scaling.

---

## File Structure

```
refineflow/
├── viz/
│   ├── __init__.py
│   ├── prep_engine.py        # Base visualization preparation
│   ├── powerbi_prep.py       # Power BI specific optimizations
│   ├── tableau_prep.py       # Tableau specific optimizations
│   ├── recommender.py        # Auto chart recommendation engine
│   └── feature_scaler.py     # Normalization & scaling for ML/BI
```

---

## Task 5.1 — Base Viz Prep Engine (`viz/prep_engine.py`)

### Class: `VizPrepEngine(df)`

General preparation applied before any tool-specific export:

- [ ] **Column name sanitization**:
  - Replace spaces with `_`: `"First Name"` → `"First_Name"`
  - Remove special characters: `$`, `%`, `#`, `(`, `)`
  - Strip leading/trailing underscores
  - Truncate to 64 chars (Power BI limit)
  - Log renamed columns:
    ```
    [✓] Renamed: "Revenue ($)" → "Revenue_USD"
    ```

- [ ] **Datetime formatting**:
  - Convert all datetime columns to ISO 8601: `YYYY-MM-DD HH:MM:SS`
  - Ensure consistent timezone (UTC by default)

- [ ] **Remove useless columns**:
  - Drop columns with >95% null values
  - Drop columns with only 1 unique value (zero variance)
  - Log dropped columns

- [ ] **Category cardinality reduction**:
  - If a category column has >500 unique values: group rare values (< 0.5% frequency) into `"Other"`
  - This improves BI rendering performance

- [ ] **Aggregation helpers**:
  - Auto-detect potential group-by candidates (low-cardinality categoricals)
  - Auto-detect potential measures (numerical columns)
  - Store as metadata: `self.dimensions` and `self.measures`

```python
class VizPrepEngine:
    def run(self) -> pd.DataFrame:
        df = self._sanitize_column_names()
        df = self._format_datetimes()
        df = self._drop_useless_columns()
        df = self._reduce_category_cardinality()
        self._detect_dimensions_and_measures()
        return df
```

---

## Task 5.2 — Feature Scaler (`viz/feature_scaler.py`)

### Class: `FeatureScaler(df, method="minmax", columns=None)`

Applied to numerical columns only (skips ID, date, boolean columns):

| Method | Formula | Use Case |
|--------|---------|----------|
| `minmax` | `(x - min) / (max - min)` | BI dashboards (0–1 range) |
| `standard` | `(x - mean) / std` | ML pipelines, AI analytics |
| `robust` | `(x - median) / IQR` | Outlier-resistant normalization |
| `none` | No scaling | Default if not called |

- [ ] Auto-exclude: ID columns, boolean columns, datetime columns
- [ ] Store scaler parameters for inverse transform:
  ```python
  self.scaler_params = {
      "revenue": {"method": "minmax", "min": 0, "max": 5_000_000},
      "age": {"method": "minmax", "min": 18, "max": 87}
  }
  ```
- [ ] Expose `.inverse_transform(df)` to undo scaling
- [ ] Add `_scaled` suffix to scaled column names (configurable)
- [ ] Log:
  ```
  [✓] Feature Scaler: Scaled 8 numerical columns (MinMax, range 0–1)
  ```

---

## Task 5.3 — Power BI Preparation (`viz/powerbi_prep.py`)

### Class: `PowerBIPrep(df, output_dir="./")`

```python
.prepare_for_powerbi()
```

#### Optimizations

- [ ] **Export to Parquet**:
  - Use `pyarrow` with `snappy` compression
  - Parquet is 10x faster than CSV in Power BI
  - Output: `powerbi_ready_<filename>.parquet`

- [ ] **DateTime decomposition**:
  - For each datetime column, add helper columns:
    ```
    date_col → date_col_Year, date_col_Month, date_col_Day,
                date_col_Quarter, date_col_WeekDay, date_col_Hour
    ```
  - These are standard Power BI date table patterns

- [ ] **Measure vs Dimension detection**:
  - Dimensions: categorical, low-cardinality columns → tag in metadata
  - Measures: numerical, aggregatable columns → tag in metadata
  - Output `powerbi_schema.json`:
    ```json
    {
      "measures": ["revenue", "quantity", "profit"],
      "dimensions": ["city", "product", "category"],
      "date_columns": ["order_date", "ship_date"]
    }
    ```

- [ ] **Relationship-friendly formatting**:
  - Ensure ID/key columns are clean strings (no nulls, no duplicates)
  - Standardize FK columns for easy Power BI relationship mapping

- [ ] **Remove unnecessary columns** for BI:
  - Drop raw text blobs, hash columns, internal system IDs (unless configured to keep)

- [ ] Log:
  ```
  [✓] Power BI Prep: Exported powerbi_ready_sales.parquet (380 MB)
  [✓] Added 12 datetime helper columns
  [✓] Schema saved: powerbi_schema.json
  ```

---

## Task 5.4 — Tableau Preparation (`viz/tableau_prep.py`)

### Class: `TableauPrep(df, output_dir="./")`

```python
.prepare_for_tableau()
```

#### Optimizations

- [ ] **Export to CSV** (primary):
  - Clean UTF-8 encoding
  - Output: `tableau_ready_<filename>.csv`

- [ ] **Tableau Hyper export** (optional, if `pantab` installed):
  - `.hyper` files load 5x faster in Tableau
  - Detect if `pantab` available, use it; otherwise fallback to CSV

- [ ] **Calculated field suggestions**:
  - Auto-detect pairs of columns that could form useful calculated fields:
    - `profit` + `revenue` → `profit_margin = profit / revenue`
    - `quantity` + `price` → `total_value = quantity * price`
  - Output as `tableau_calculated_fields.json`:
    ```json
    [
      {"name": "Profit Margin", "formula": "[Profit] / [Revenue]"},
      {"name": "Total Value", "formula": "[Quantity] * [Unit_Price]"}
    ]
    ```

- [ ] **Aggregation-ready columns**:
  - Ensure all dimension columns are clean strings (no nulls)
  - Ensure all measure columns are numeric (no mixed types)

- [ ] **Tableau metadata file**:
  - Output `tableau_metadata.json` with field types and roles:
    ```json
    {
      "dimensions": ["Region", "Category", "Sub_Category"],
      "measures": ["Sales", "Profit", "Quantity"],
      "dates": ["Order_Date", "Ship_Date"]
    }
    ```

- [ ] Log:
  ```
  [✓] Tableau Prep: Exported tableau_ready_sales.csv
  [✓] 3 calculated field suggestions generated
  [✓] Metadata saved: tableau_metadata.json
  ```

---

## Task 5.5 — Visualization Recommender (`viz/recommender.py`)

### Class: `VizRecommender(df, scan_report)`

```python
.recommend_visualizations()
```

#### Rule Engine

Analyze column types and apply recommendation rules:

| Pattern | Recommended Chart | Priority |
|---------|-----------------|----------|
| Date + Numerical | Line Chart (Trend) | High |
| Categorical (≤10 unique) + Numerical | Bar Chart | High |
| Categorical (>10 unique) + Numerical | Horizontal Bar / Treemap | Medium |
| Single Categorical (≤6 unique) | Pie / Donut Chart | Medium |
| Two Numerical columns | Scatter Plot | Medium |
| Geo column detected (`city`, `country`, `lat`, `lon`) | Map Chart | High |
| Numerical + Numerical + Categorical | Bubble Chart | Low |
| Single Numerical, time-independent | KPI Card / Gauge | Medium |

- [ ] Score and rank recommendations by data quality and usefulness
- [ ] Suggest specific column mappings for each chart:
  ```python
  {
    "chart": "Line Chart",
    "title": "Revenue Trend Over Time",
    "x_axis": "order_date",
    "y_axis": "revenue",
    "confidence": "High"
  }
  ```
- [ ] Return top 5 recommendations
- [ ] Print formatted output:
  ```
  ╔══════════════════════════════════════════════════════╗
  ║       RefineFlow — Visualization Recommendations     ║
  ╠══════════════════════════════════════════════════════╣
  ║  1. [HIGH]   Revenue Trend         → Line Chart      ║
  ║              x: order_date  |  y: revenue            ║
  ║                                                      ║
  ║  2. [HIGH]   Sales by Region       → Bar Chart       ║
  ║              x: region      |  y: sales              ║
  ║                                                      ║
  ║  3. [MEDIUM] Product Distribution  → Pie Chart       ║
  ║              dimension: product_category             ║
  ╚══════════════════════════════════════════════════════╝
  ```

---

## Task 5.6 — Wire-up into `Cleaner`

- [ ] `.prepare_for_powerbi(output_dir="./")` → calls `VizPrepEngine` + `PowerBIPrep`
- [ ] `.prepare_for_tableau(output_dir="./")` → calls `VizPrepEngine` + `TableauPrep`
- [ ] `.optimize_memory()` → standalone call to `MemoryOptimizer` (from Module 3)
- [ ] `.recommend_visualizations()` → calls `VizRecommender`, prints output

All return `self` for chaining.

---

## Output Files Generated

| File | Format | Size Reduction | Use |
|------|--------|---------------|-----|
| `powerbi_ready_<name>.parquet` | Parquet + Snappy | ~70% vs CSV | Power BI |
| `powerbi_schema.json` | JSON | — | Data model hints |
| `tableau_ready_<name>.csv` | CSV UTF-8 | — | Tableau |
| `tableau_metadata.json` | JSON | — | Field roles |
| `tableau_calculated_fields.json` | JSON | — | Calculated fields |

---

## Deliverable

```python
Cleaner("sales.csv") \
    .auto_clean() \
    .prepare_for_powerbi() \
    .prepare_for_tableau() \
    .recommend_visualizations()
```

**Expected Output:**
```
[✓] Viz Prep: Column names sanitized (3 renamed)
[✓] Viz Prep: Dropped 2 zero-variance columns
[✓] Power BI: Exported powerbi_ready_sales.parquet (380 MB)
[✓] Power BI: 12 datetime helper columns added
[✓] Tableau: Exported tableau_ready_sales.csv
[✓] Tableau: 3 calculated field suggestions saved

╔══════════════════════════════════════════╗
║  Visualization Recommendations           ║
║  1. [HIGH]   Revenue Trend → Line Chart  ║
║  2. [HIGH]   Sales by Region → Bar Chart ║
║  3. [MED]    Product Dist → Pie Chart    ║
╚══════════════════════════════════════════╝
```

---

## Tests (`tests/test_module5.py`)

- [ ] Test column name sanitizer removes special chars and spaces
- [ ] Test datetime decomposition adds correct helper columns
- [ ] Test Power BI export creates valid `.parquet` file
- [ ] Test Power BI schema JSON has correct measure/dimension keys
- [ ] Test Tableau export creates valid UTF-8 CSV
- [ ] Test calculated field suggestions for `profit/revenue` pair
- [ ] Test viz recommender returns Line Chart for date + numerical pair
- [ ] Test viz recommender returns Map Chart when `city` column present
- [ ] Test feature scaler produces values in [0,1] range for MinMax

---

## Dependencies Installed

```bash
pip install pyarrow pandas
# Optional:
pip install pantab   # for Tableau Hyper export
```

---

## Real-World Problems Handled in This Module

> Module 5 bridges the gap between a clean dataset and one that BI tools can actually use well. These problems appear at the **export and presentation layer**.

### Visualization Prep Problems

| Problem | Real Example | Solution | Technique |
|---------|-------------|----------|-----------|
| Bad categorical labels | `mumbai`, `Mumbai`, `MUMBAI` coexist | Category standardization before export | Label normalizer (leverages Module 4 output) |
| High cardinality categories | 50,000 unique product SKUs | Smart aggregation — group tail into `"Other"` | BI optimization: keep top-N, merge rest |
| Unformatted dates | Raw Unix timestamps in BI tool | Date formatting + decomposition | ISO 8601 + Year/Month/Day helper columns |
| Non-aggregatable metrics | Mixed text+numbers in measure column | Convert to pure numeric, tag as measure | Feature engineering + measure detection |

**High cardinality handling:**
```python
def reduce_cardinality(col, df, top_n=50):
    top_values = df[col].value_counts().nlargest(top_n).index
    df[col] = df[col].where(df[col].isin(top_values), other="Other")
    return df
# Before: 50,000 unique SKUs
# After:  50 top SKUs + "Other" → renders perfectly in Power BI treemap
```

**Unusable metrics fix:**
```python
# Detect columns where >50% values are numeric strings
# "revenue" column has: "5000", "$4200", "N/A", "3100"
# After TypeFixer (Module 3): all clean floats
# In Module 5: tag as MEASURE since it's now purely numeric
self.measures = [c for c in df.columns if pd.api.types.is_numeric_dtype(df[c])
                 and c not in self.id_columns and c not in self.date_columns]
```

---

### AI Cleaning Concepts (Future Feature — Documented Here)

| Problem | Real Example | Solution | Technique |
|---------|-------------|----------|-----------|
| Unknown dataset semantics | Mixed business data with no schema | AI schema inference | LLM prompt: "What type of dataset is this?" |
| Dataset type detection | Ecommerce vs HR vs Finance | Template-based cleaning profiles | Dataset classifier → load domain-specific rules |
| Low-confidence corrections | Ambiguous column values | Human review queue | Confidence scoring — flag uncertain fixes |

**How it will work (`.clean_with_ai()`):**
```python
# Future implementation outline:
# 1. Send column names + sample values to LLM
# 2. LLM returns: dataset_type, column_semantics, suggested_rules
# 3. Load domain-specific cleaning profile (e.g., "ecommerce_profile.json")
# 4. Apply profile rules on top of standard cleaning pipeline

# Example LLM output:
{
  "dataset_type": "ecommerce",
  "columns": {
    "rev":    {"semantic": "revenue",  "type": "currency", "currency": "INR"},
    "qty":    {"semantic": "quantity", "type": "integer",  "min": 0},
    "cust":   {"semantic": "name",     "type": "text"}
  },
  "suggestions": [
    "Strip currency symbols from 'rev' column",
    "Column 'ship_dt' appears to be a date — detected format: DD/MM/YYYY"
  ]
}
```
