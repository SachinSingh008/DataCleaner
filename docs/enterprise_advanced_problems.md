# RefineFlow — Enterprise & Advanced Problems Registry

> This document maps 70+ enterprise-grade, edge-case, and advanced data engineering problems to the correct RefineFlow module. Each entry includes the problem, real example, best solution, and implementation approach.

---

## Module 1 Additions — Scanner & Infrastructure

### File-Level Problems

| Problem | Example | Solution | Technique |
|---------|---------|----------|-----------|
| Duplicate files | Same CSV uploaded twice | File fingerprinting before processing | MD5/SHA256 hash of file → reject if already seen |
| Compression handling | `.gz`, `.zip`, `.tar.gz` files | Streaming decompression | `gzip.open()` / `zipfile.ZipFile` — never decompress fully to disk |
| File corruption | Partial upload, broken CSV | Corruption recovery | Read in chunks, detect truncation, attempt repair |
| Auto sampling | 500GB dataset preview | Smart sampling for profiling | Reservoir sampling — read every Nth row without full load |
| Metadata loss | Unknown datatypes, no schema | Metadata persistence | Save inferred schema to `metadata.json` on first scan |
| Auto documentation | No dataset explanation | Dataset documentation generator | Auto-generate markdown summary: col names, types, stats, sample values |

**File fingerprinting implementation:**
```python
import hashlib
def file_fingerprint(path: str) -> str:
    h = hashlib.md5()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()

# On every run: check fingerprint registry
# If fingerprint already in registry → warn user, skip or deduplicate
```

**Streaming decompression:**
```python
import gzip, zipfile
def open_compressed(path: str):
    if path.endswith(".gz"):
        return gzip.open(path, "rt", encoding="utf-8")
    elif path.endswith(".zip"):
        zf = zipfile.ZipFile(path)
        return zf.open(zf.namelist()[0])
    return open(path, "r", encoding="utf-8")
```

---

## Module 2 Additions — Engine & Partitioning

### Scale & Infrastructure Problems

| Problem | Example | Solution | Technique |
|---------|---------|----------|-----------|
| Skewed partitions | One chunk has 80% of rows | Adaptive repartitioning | Measure chunk sizes after split, re-split oversized chunks |
| Extremely wide tables | 50,000+ columns (genomics) | Columnar partitioning | Split by column groups, process column-batches |
| Streaming data | Kafka/real-time ingestion | Stream processing | `kafka-python` consumer + micro-batch cleaning |
| Incremental updates | Daily append-only data | Delta cleaning | Track `last_processed_row`, only clean new rows |
| Cloud storage | S3/GCS/Azure Blob | Cloud connector | `s3fs`, `gcsfs`, `adlfs` — transparent file access |
| Database ingestion | PostgreSQL/MongoDB | Connector framework | `SQLAlchemy` for SQL, `pymongo` for NoSQL |
| Distributed shuffle bottleneck | Heavy Spark shuffle | Shuffle optimization | Pre-sort + partition pruning before shuffle |
| Resource scheduling | Too many workers, cluster overload | Dynamic scheduler | Cap workers based on available RAM: `psutil.virtual_memory()` |
| Edge device cleaning | IoT gateway with 512MB RAM | Lightweight engine | Pandas chunked mode + aggressive memory optimization only |

**Adaptive repartitioning:**
```python
def adaptive_repartition(chunks: list, max_ratio: float = 2.0) -> list:
    avg = sum(len(c) for c in chunks) / len(chunks)
    result = []
    for chunk in chunks:
        if len(chunk) > avg * max_ratio:
            # Split this oversized chunk into 2
            mid = len(chunk) // 2
            result.extend([chunk.iloc[:mid], chunk.iloc[mid:]])
        else:
            result.append(chunk)
    return result
```

**Incremental delta cleaning:**
```python
# Save watermark (last processed index or timestamp)
def load_watermark(path="watermark.json"):
    if os.path.exists(path):
        return json.load(open(path))
    return {"last_row": 0, "last_ts": None}

def save_watermark(last_row, last_ts, path="watermark.json"):
    json.dump({"last_row": last_row, "last_ts": str(last_ts)}, open(path, "w"))

# Only clean rows after watermark
df_new = df.iloc[watermark["last_row"]:]
```

---

## Module 3 Additions — Parallel Cleaning Engine

### Text & Content Problems

| Problem | Example | Solution | Technique |
|---------|---------|----------|-----------|
| Multi-language data | `मुंबई`, `Mumbai` mixed | Unicode + multilingual normalization | `unicodedata.normalize` + transliteration |
| Emoji/special characters | `Great Product🔥` | Unicode sanitization | Strip non-BMP characters or convert to text |
| HTML/markup noise | `<div>Hello</div>` | HTML stripping | `BeautifulSoup.get_text()` |
| SQL injection strings | `'; DROP TABLE users; --` | Input sanitization | Regex strip SQL keywords in text fields |
| Floating point precision | `0.30000000004` | Precision normalization | `round(value, 10)` or `Decimal` for finance |
| Nested JSON in CSV | `{"city":"Pune"}` in a cell | Nested schema extraction | `json.loads()` + `pd.json_normalize()` |
| XML embedded data | `<user><id>1</id></user>` | XML parser | `xml.etree.ElementTree` → flatten to columns |
| Binary/base64 data | Base64 image in CSV cell | Binary extraction | Detect base64, extract to file, replace cell with filepath |
| Log data parsing | Apache/Nginx raw logs | Log parser engine | Regex pattern per log format → structured columns |
| Sensor noise / IoT spikes | Random spike in temperature | Signal smoothing | Rolling median filter: `df.rolling(5).median()` |
| Sparse data | Mostly-empty recommendation matrix | Sparse optimization | Convert to `scipy.sparse` or `pd.SparseDtype` |
| Duplicate semantics | `M`, `Male`, `male`, `1` | Semantic mapping | Standardization dict per domain |
| Extremely long text | 1MB text in single cell | Text chunking | Truncate or split to `text_1`, `text_2`, etc. |

**HTML stripping:**
```python
from bs4 import BeautifulSoup
def strip_html(text: str) -> str:
    if "<" in str(text) and ">" in str(text):
        return BeautifulSoup(text, "html.parser").get_text(separator=" ").strip()
    return text
```

**Emoji sanitization:**
```python
import re
def remove_emoji(text: str) -> str:
    # Remove characters outside Basic Multilingual Plane (emojis, etc.)
    return re.sub(r'[^\u0000-\uFFFF]', '', str(text))
```

**Nested JSON extraction:**
```python
import json, pandas as pd
def expand_json_column(df, col):
    parsed = df[col].apply(lambda x: json.loads(x) if isinstance(x, str) else {})
    expanded = pd.json_normalize(parsed)
    expanded.columns = [f"{col}_{c}" for c in expanded.columns]
    return pd.concat([df.drop(columns=[col]), expanded], axis=1)
```

**Duplicate semantic mapping:**
```python
GENDER_MAP = {"m": "Male", "f": "Female", "male": "Male", "female": "Female",
              "1": "Male", "0": "Female", "man": "Male", "woman": "Female"}
df["gender"] = df["gender"].str.lower().str.strip().map(GENDER_MAP)
```

**Floating point precision:**
```python
from decimal import Decimal, ROUND_HALF_UP
def normalize_decimal(value, places=2):
    return float(Decimal(str(value)).quantize(
        Decimal("0." + "0" * places), rounding=ROUND_HALF_UP))
```

---

## Module 4 Additions — Merge & Global Validation

### Entity & Relationship Problems

| Problem | Example | Solution | Technique |
|---------|---------|----------|-----------|
| Same entity, different IDs | Customer has ID `C001` and `CUS-001` | Entity resolution engine | Block on name+email, match by similarity |
| Missing foreign keys | Order row with no matching customer | Referential integrity validation | Cross-table FK check: warn + flag orphan rows |
| Data freshness | 2018 records in live dashboard | Timestamp freshness checks | Flag rows older than configured threshold |
| Time drift | Server logs out of chronological order | Clock synchronization | Sort by timestamp after merge, detect skew |
| Join key mismatch | `001` vs `1` vs `CU001` | Key normalization | Strip prefixes/leading zeros, normalize format |
| Multi-table relationships | Customer CSV + Orders CSV linked | Relationship graph engine | Detect shared key columns, build join map |
| Geospatial problems | Latitude `> 90` or longitude `> 180` | Geo validator | Constraint check: lat ∈ [-90, 90], lon ∈ [-180, 180] |
| Duplicate time windows | IoT event replayed multiple times | Temporal deduplication | Dedup on (device_id, timestamp) compound key |
| Session reconstruction | User activity split across chunks | Sessionization engine | Sort by (user_id, timestamp), group by session gap |
| Concurrent modifications | Two processes updating same row | Locking/version control | Optimistic locking: version column check |
| Fraudulent data | Fake/suspicious transactions | Fraud detection | Statistical anomaly: `z-score > 4` on transaction amounts |
| Data poisoning | Fake entries in ML training data | Anomaly detection | Isolation Forest on feature distributions |

**Entity resolution:**
```python
# Block candidates by first letter of name (reduces comparisons)
# Then compare within each block using fuzzy matching
from recordlinkage import Index, Compare

def resolve_entities(df):
    indexer = Index()
    indexer.block("name_initial")   # pre-computed first letter
    candidates = indexer.index(df)
    cmp = Compare()
    cmp.string("name", "name", method="jaro_winkler", threshold=0.88)
    cmp.string("email", "email", method="exact")
    features = cmp.compute(candidates, df)
    # Pairs where sum > 1.5 are likely the same entity
    duplicates = features[features.sum(axis=1) > 1.5]
    return duplicates
```

**Referential integrity:**
```python
def check_referential_integrity(orders_df, customers_df, key="customer_id"):
    valid_ids = set(customers_df[key])
    orphans = orders_df[~orders_df[key].isin(valid_ids)]
    if len(orphans) > 0:
        log.warning(f"[!] {len(orphans)} orphan rows: {key} not found in parent table")
    return orphans
```

**Geospatial validation:**
```python
def validate_coordinates(df):
    if "latitude" in df.columns:
        invalid = df[(df["latitude"] < -90) | (df["latitude"] > 90)]
        df.loc[invalid.index, "latitude"] = np.nan
    if "longitude" in df.columns:
        invalid = df[(df["longitude"] < -180) | (df["longitude"] > 180)]
        df.loc[invalid.index, "longitude"] = np.nan
    return df
```

---

## Module 5 Additions — Visualization & BI

### BI Architecture Problems

| Problem | Example | Solution | Technique |
|---------|---------|----------|-----------|
| BI semantic modeling | No star schema | Fact/dimension detection | Auto-classify: fact table (many rows, numeric measures) vs dim |
| Semantic column detection | Column named `amt`, `qty` | NLP-based column understanding | Fuzzy match against semantic dictionary |
| Auto indexing | Slow filtering on 100M rows | Index optimizer | Detect high-filter columns, suggest/create index |
| Query pushdown | Full scan for filtered data | Predicate pushdown | Pass `filters=` to `pd.read_parquet()` for column pruning |
| Data compression optimization | 1TB CSV → 50GB Parquet | Compression engine | Columnar Parquet + Zstd compression (better than Snappy for text) |
| Graph data cleaning | Social network nodes/edges | Graph validator | Check: all edge endpoints exist in nodes table |
| Industry-specific rules | Invalid ICD-10 code in healthcare | Domain template engine | Load domain rule pack: `healthcare_rules.json` |
| Data leakage detection | Future sales in ML training set | Leakage detection | Check: training features contain no target-correlated future cols |
| Currency exchange drift | USD converted with stale FX rate | Time-aware FX conversion | Lookup FX rate at `transaction_date`, not today's rate |

**Semantic column detection:**
```python
SEMANTIC_MAP = {
    "revenue": ["rev", "revenue", "income", "amt", "amount", "total"],
    "quantity": ["qty", "quantity", "count", "num", "units"],
    "customer": ["cust", "customer", "client", "user", "buyer"],
    "date":     ["dt", "date", "ts", "timestamp", "created", "updated"]
}

def detect_semantic(col_name: str) -> str:
    col_lower = col_name.lower()
    for semantic, aliases in SEMANTIC_MAP.items():
        if any(alias in col_lower for alias in aliases):
            return semantic
    return "unknown"
```

**Parquet predicate pushdown:**
```python
# Only reads rows where region == "North" — never loads full file
df = pd.read_parquet("sales.parquet",
    filters=[("region", "==", "North"), ("year", ">=", 2023)])
```

**Star schema detection:**
```python
def classify_table(df):
    row_count = len(df)
    num_numeric = df.select_dtypes("number").shape[1]
    num_category = df.select_dtypes("category").shape[1]
    # Fact: many rows, more numeric than categorical
    if row_count > 100_000 and num_numeric > num_category:
        return "fact_table"
    # Dimension: fewer rows, mostly categorical
    return "dimension_table"
```

---

## Module 6 Additions — Report, Export & Governance

### Compliance, Security & Governance

| Problem | Example | Solution | Technique |
|---------|---------|----------|-----------|
| PII masking / GDPR | Aadhaar, phone, email exposed | PII detection + redaction | Regex detect → mask/hash/redact before export |
| Data leakage in ML | Future info in training features | Leakage detection flag | Report columns with suspiciously high target correlation |
| Audit tracking | Who changed what, when | Lineage tracking | Append-only audit log per transformation |
| Reproducibility | Different outputs on re-run | Pipeline versioning | Hash pipeline config + random seeds + library versions |
| Pipeline rollback | Bad cleaning corrupted data | Snapshot rollback | Auto-snapshot before each destructive operation |
| Explainability | Why was value changed? | Explainable cleaning logs | Log every decision: `{col, old_val, new_val, rule, confidence}` |
| Confidence scoring | Uncertain correction | Confidence engine | Score 0-1 per correction, flag < 0.7 as REVIEW |
| Auto benchmarking | Unknown cleaning speed | Benchmark framework | Time each pipeline step, compare across runs |
| Data bias analysis | Gender imbalance in dataset | Bias analysis | Distribution report per protected attribute |
| Real-time validation | Invalid data in live Kafka stream | Streaming validators | Apply cleaning rules inline to each micro-batch |
| Versioned datasets | Schema v1 → v2 migration | Version-aware schema manager | Maintain migration scripts per schema version |

**PII detection and masking:**
```python
import re, hashlib

PII_PATTERNS = {
    "email":   r'[\w.-]+@[\w.-]+\.\w+',
    "phone":   r'[6-9]\d{9}',              # Indian mobile
    "aadhaar": r'\d{4}\s\d{4}\s\d{4}',
    "pan":     r'[A-Z]{5}[0-9]{4}[A-Z]',
}

def mask_pii(value: str, mask_type="hash") -> str:
    if mask_type == "hash":
        return hashlib.sha256(str(value).encode()).hexdigest()[:16]
    elif mask_type == "redact":
        return "***REDACTED***"
    elif mask_type == "partial":
        s = str(value)
        return s[:2] + "*" * (len(s) - 4) + s[-2:]

def detect_and_mask_pii(df, mask_type="hash"):
    for col in df.select_dtypes("object").columns:
        for pii_type, pattern in PII_PATTERNS.items():
            sample = df[col].dropna().astype(str).head(100)
            match_rate = sample.str.match(pattern).mean()
            if match_rate > 0.7:
                df[col] = df[col].apply(lambda x: mask_pii(x, mask_type))
                log.warning(f"[!] PII detected in '{col}' ({pii_type}) — masked")
                break
    return df
```

**Explainable cleaning log:**
```python
@dataclass
class CleaningDecision:
    column: str
    row_index: int
    old_value: any
    new_value: any
    rule: str
    confidence: float   # 0.0 – 1.0
    flag: str           # "OK" | "REVIEW" | "WARNING"

# Every fix appends a CleaningDecision to self.audit_log
# Report renders audit_log as a sortable, filterable HTML table
```

**Pipeline versioning for reproducibility:**
```python
import hashlib, json
def pipeline_fingerprint(config: dict) -> str:
    # Hash: config params + library versions + timestamp of run
    import pandas, numpy
    fingerprint_data = {
        "config": config,
        "pandas_version": pandas.__version__,
        "numpy_version": numpy.__version__,
    }
    return hashlib.md5(json.dumps(fingerprint_data, sort_keys=True).encode()).hexdigest()
```

---

## The 12 Missing High-Level Systems

These are cross-cutting systems that span all modules. Each should be designed as a standalone service/class.

| # | System | Purpose | Where Used | Implementation |
|---|--------|---------|-----------|----------------|
| 1 | **Confidence Engine** | Score certainty of every auto-correction | All modules | `ConfidenceScorer` — returns 0.0–1.0 per decision |
| 2 | **Human Review System** | Queue low-confidence decisions for user approval | Module 6 Report | Interactive HTML table with Accept/Override buttons |
| 3 | **Explainability Layer** | Log why every value was changed | All modules | `AuditLog` appended per `CleaningDecision` |
| 4 | **Pipeline DAG Engine** | Define step dependencies, prevent out-of-order execution | Module 2 | Directed Acyclic Graph: each step is a node |
| 5 | **Metadata Registry** | Track schemas, versions, and dataset lineage | Modules 1, 6 | JSON registry: `metadata_registry.json` |
| 6 | **Rule Engine** | Custom user-defined business validations | Modules 3, 4 | Config-driven: `custom_rules.yaml` |
| 7 | **AI Semantic Layer** | Understand column context and dataset type | Module 5 | LLM-powered column inference (future) |
| 8 | **Distributed Scheduler** | Efficient cluster task assignment | Module 2 | Priority queue + worker heartbeat |
| 9 | **Observability System** | Monitor cleaning pipelines in production | Module 6 | Emit metrics to Prometheus/Grafana |
| 10 | **Benchmark Engine** | Measure and compare cleaning performance | Module 6 | Time each step, compare across dataset versions |
| 11 | **Lineage Tracking** | Full audit trail of every transformation | Module 6 | DAG of: raw → cleaned → exported |
| 12 | **Security Layer** | Protect sensitive data, prevent PII leaks | Module 6 | PII masking + encryption + role-based access |

---

## Additional Advanced Problems Quick Reference

### Data Lifecycle

| Problem | Module | Solution |
|---------|--------|---------|
| Stale/old records | M4 | Timestamp freshness: flag rows older than N days |
| Versioned datasets | M6 | Schema migration scripts per version |
| Audit tracking | M6 | Append-only transformation log |
| Reproducibility | M6 | Pipeline fingerprinting (hash of config + versions) |
| Pipeline rollback | M6 | Auto-snapshot before destructive steps |

### AI & ML Data Quality

| Problem | Module | Solution |
|---------|--------|---------|
| Data leakage | M5 | Flag future-correlated columns before ML export |
| Data bias | M6 | Distribution report on protected attributes |
| Data poisoning | M4 | Isolation Forest anomaly detection |
| Model drift detection | M6 | Monitor feature distributions over time |
| AI embedding validation | M5 | Check embedding dimensionality + NaN values |
| Synthetic data detection | M4 | Statistical tests: too-uniform distributions = synthetic |
| Active learning | M6 | Store user corrections → retrain rule confidence weights |

### Advanced Text & Encoding

| Problem | Module | Solution |
|---------|--------|---------|
| Multi-language (Hindi+English) | M3 | `langdetect` + transliteration (`indic-transliteration`) |
| Emoji in text fields | M3 | `re.sub(r'[^\u0000-\uFFFF]', '', text)` |
| HTML tags in data | M3 | `BeautifulSoup.get_text()` |
| SQL injection strings | M3 | Strip SQL keywords from text fields |
| PII (Aadhaar, phone) | M6 | Regex detect → hash/redact before export |

### Enterprise Integration

| Problem | Module | Solution |
|---------|--------|---------|
| Cloud storage (S3/GCS) | M2 | `s3fs`, `gcsfs` — transparent path handling |
| Database ingestion | M2 | `SQLAlchemy` + `pymongo` connectors |
| Streaming (Kafka) | M2 | `kafka-python` micro-batch consumer |
| Workflow automation | M6 | `schedule` / Airflow DAG trigger |
| Federated cleaning | M6 | Clean locally, share only stats (privacy-preserving) |

### Performance & Scale

| Problem | Module | Solution |
|---------|--------|---------|
| Extremely wide tables | M2 | Column-batch processing |
| Extremely long text | M3 | Truncate or split into chunks |
| Sparse matrices | M3 | `scipy.sparse` or `pd.SparseDtype` |
| Shuffle bottlenecks | M2 | Pre-sort before shuffle |
| Query pushdown | M5 | `pd.read_parquet(filters=[...])` |
| Auto indexing | M5 | Detect filter columns, suggest index |
