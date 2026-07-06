"""
RefineFlow — Global Configuration & Constants
All thresholds, limits, and shared settings live here.
"""

# ── Engine Selection Thresholds ─────────────────────────────────────────────
SMALL_DATA_THRESHOLD_GB   = 10       # < 10 GB  → Pandas / Polars
MEDIUM_ROW_THRESHOLD      = 1_000_000  # < 1M rows → Pandas; >= 1M → Polars
BIG_DATA_THRESHOLD_GB     = 100      # >= 100 GB → Spark

# ── Partitioning ─────────────────────────────────────────────────────────────
PARTITION_ROW_THRESHOLD   = 10_000   # Skip partitioning if fewer rows
DEFAULT_PARTITIONS        = 4
MAX_CHUNK_SIZE_RATIO      = 2.0      # Re-split chunk if > 2x avg size

# ── File Handling ─────────────────────────────────────────────────────────────
SUPPORTED_FORMATS         = ["csv", "xlsx", "xls", "parquet", "json", "tsv"]
COMPRESSED_EXTENSIONS     = [".gz", ".zip", ".bz2", ".tar.gz"]
CHECKPOINT_DIR            = ".refineflow_cache"
SCHEMA_SNAPSHOT_FILE      = "schema_snapshot.json"
WATERMARK_FILE            = "watermark.json"

# ── Scanner Settings ──────────────────────────────────────────────────────────
ENCODING_SAMPLE_BYTES     = 50_000   # Bytes to read for encoding detection
ENCODING_CONFIDENCE_MIN   = 0.80     # Below this → flag as encoding_risk HIGH
SCAN_SAMPLE_ROWS          = 1_000    # Rows to load for memory estimation
DUPLICATE_PROBE_ROWS      = 10_000   # Rows to hash for duplicate probability
CORRUPTED_COL_NULL_RATIO  = 0.90     # > 90% nulls → column is corrupted
DATE_PARSE_CONFIDENCE     = 0.80     # > 80% values parse → treat as date

# ── Cleaning Thresholds ───────────────────────────────────────────────────────
CATEGORY_UNIQUE_RATIO     = 0.50     # unique/total < 50% → convert to category
HIGH_CARDINALITY_LIMIT    = 500      # > 500 unique values → reduce cardinality
TOP_N_CATEGORIES          = 50       # Keep top-N, rest → "Other"
MIN_ROWS_FOR_OUTLIER      = 30       # Skip outlier detection if fewer rows
NULL_DROP_COLUMN_RATIO    = 0.95     # Drop column if > 95% null
FUZZY_MATCH_THRESHOLD     = 0.85     # Similarity threshold for fuzzy matching

# ── Outlier Detection ─────────────────────────────────────────────────────────
IQR_MULTIPLIER            = 1.5
ZSCORE_THRESHOLD          = 3.0
PERCENTILE_LOWER          = 1        # Clip below 1st percentile
PERCENTILE_UPPER          = 99       # Clip above 99th percentile

# ── Memory Optimization ───────────────────────────────────────────────────────
INT8_MAX   = 127
INT16_MAX  = 32_767
INT32_MAX  = 2_147_483_647

# ── Fault Tolerance ───────────────────────────────────────────────────────────
MAX_CHUNK_RETRIES         = 3        # Retry failed chunks up to 3 times
RETRY_BACKOFF_BASE        = 2        # Exponential: 2^attempt seconds

# ── Confidence Scoring ────────────────────────────────────────────────────────
CONFIDENCE_REVIEW_THRESHOLD = 0.70   # Below this → flag as REVIEW in report

# ── PII Detection ─────────────────────────────────────────────────────────────
PII_PATTERNS = {
    "email":   r"[\w.\-+]+@[\w.\-]+\.\w{2,}",
    "phone":   r"[6-9]\d{9}",
    "aadhaar": r"\d{4}[\s\-]?\d{4}[\s\-]?\d{4}",
    "pan":     r"[A-Z]{5}[0-9]{4}[A-Z]",
    "ssn":     r"\d{3}-\d{2}-\d{4}",
}
PII_MATCH_RATE_THRESHOLD  = 0.70     # > 70% values match pattern → flag as PII

# ── Hidden Null Strings ───────────────────────────────────────────────────────
HIDDEN_NULL_VALUES = {
    "na", "n/a", "n.a.", "n.a", "none", "null", "nil",
    "nan", "-", "--", "---", "?", "unknown", "unk",
    "not available", "not applicable", "missing",
    "undefined", "void", "#n/a", "#null!", ""
}

# ── Boolean Standardization ───────────────────────────────────────────────────
BOOL_TRUE_VALUES  = {"yes", "true", "1", "y", "on", "t", "si", "oui"}
BOOL_FALSE_VALUES = {"no", "false", "0", "n", "off", "f", "non"}

# ── Business Constraint Defaults ──────────────────────────────────────────────
DEFAULT_COLUMN_CONSTRAINTS = {
    "age":        {"min": 0,   "max": 120},
    "salary":     {"min": 0},
    "revenue":    {"min": 0},
    "price":      {"min": 0},
    "rating":     {"min": 0,   "max": 5},
    "percentage": {"min": 0,   "max": 100},
    "quantity":   {"min": 0},
    "discount":   {"min": 0,   "max": 100},
}

# ── Date Formats (tried in order) ─────────────────────────────────────────────
DATE_FORMATS = [
    "%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y",
    "%d-%m-%Y", "%Y/%m/%d", "%d.%m.%Y",
    "%Y%m%d",   "%d%m%Y",   "%m%d%Y",
    "%Y-%m-%d %H:%M:%S", "%d/%m/%Y %H:%M:%S",
    "%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M:%SZ",
]

# ── Unit Conversion Maps ──────────────────────────────────────────────────────
WEIGHT_TO_GRAMS = {"kg": 1000, "g": 1, "lb": 453.592, "oz": 28.3495, "mg": 0.001}
TIME_TO_SECONDS = {"ms": 0.001, "s": 1, "sec": 1, "min": 60, "hr": 3600, "h": 3600}

# ── Report Settings ───────────────────────────────────────────────────────────
REPORT_FILENAME_HTML = "refineflow_report.html"
REPORT_FILENAME_JSON = "refineflow_report.json"
REPORT_FILENAME_PDF  = "refineflow_report.pdf"
