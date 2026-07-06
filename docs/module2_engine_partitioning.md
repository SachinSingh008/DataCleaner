# Module 2 — Adaptive Engine Selection & Partitioning

> **Goal:** Auto-select the right processing backend and divide the dataset into manageable, independently processable partitions.

---

## File Structure

```
refineflow/
├── engine/
│   ├── __init__.py
│   ├── selector.py           # Engine selection logic
│   ├── pandas_engine.py      # Pandas backend
│   ├── polars_engine.py      # Polars backend
│   ├── dask_engine.py        # Dask backend
│   └── spark_engine.py       # Spark backend (future)
├── partitioner.py            # Divide & conquer partitioning
```

---

## Task 2.1 — Engine Selector (`engine/selector.py`)

### Decision Logic

```
File Size < 10 GB AND Rows < 1M   →  Pandas
File Size < 10 GB AND Rows >= 1M  →  Polars
File Size 10–100 GB               →  Dask
File Size > 100 GB                →  Spark
```

- [ ] Create `EngineSelector(scan_report, backend_override=None)`
- [ ] If `backend_override` is set, skip auto-detection
- [ ] Return: engine name string + reason string
- [ ] Log selected engine with clear reason:
  ```
  [✓] Engine selected: Polars
      Reason: File size 4.2 GB, row count 8M (medium dataset)
  ```
- [ ] Validate that selected engine is installed; fallback gracefully:
  ```
  Spark not installed → fallback to Dask
  Dask not installed  → fallback to Polars
  ```

```python
class EngineSelector:
    def __init__(self, scan_report, backend_override=None):
        self.scan_report = scan_report
        self.override = backend_override

    def select(self) -> str:
        if self.override and self.override != "auto":
            return self._validate(self.override)
        size = self.scan_report["size_gb"]
        rows = self.scan_report["rows"]
        if size < 10:
            return "polars" if rows >= 1_000_000 else "pandas"
        elif size < 100:
            return "dask"
        else:
            return "spark"
```

---

## Task 2.2 — Pandas Engine (`engine/pandas_engine.py`)

- [ ] Wrap `pd.read_csv()`, `pd.read_excel()`, `pd.read_parquet()`, `pd.read_json()`
- [ ] Detect and apply correct encoding from scan report
- [ ] Chunked reading via `chunksize` for files 1–10 GB
- [ ] Uniform interface:
  - `.load() → pd.DataFrame`
  - `.save(df, path, format) → None`
- [ ] Handle `low_memory=False` for mixed-type CSVs
- [ ] Log load time and row count after loading

---

## Task 2.3 — Polars Engine (`engine/polars_engine.py`)

- [ ] Use `polars.scan_csv()` (lazy, no full load)
- [ ] Collect only when needed: `.collect()`
- [ ] Use `polars.read_parquet()` for parquet files
- [ ] Uniform interface:
  - `.load() → polars.DataFrame`
  - `.save(df, path, format) → None`
- [ ] Auto-convert Polars DataFrame → Pandas when needed downstream
- [ ] Leverage native multi-threading (no extra config needed)

---

## Task 2.4 — Dask Engine (`engine/dask_engine.py`)

- [ ] `dask.dataframe.read_csv()` with computed `npartitions`
- [ ] `npartitions` = max(4, ceil(size_gb / 2))
- [ ] Delayed computation graph — do NOT call `.compute()` prematurely
- [ ] Uniform interface:
  - `.load() → dask.DataFrame`
  - `.save(df, path, format) → None`
- [ ] Expose `.to_pandas_chunks()` to iterate partitions as pandas DFs

---

## Task 2.5 — Partitioner (`partitioner.py`)

### Core Class: `DataPartitioner(df, n_partitions, checkpoint=True)`

- [ ] If rows < `PARTITION_ROW_THRESHOLD` (10,000): skip, return `[df]`
- [ ] Calculate chunk size: `chunk_size = len(df) // n_partitions`
- [ ] Split into N equal row-slices
- [ ] Assign chunk metadata:
  ```python
  {
    "chunk_id": 0,
    "rows": 150_000,
    "start_idx": 0,
    "end_idx": 149_999
  }
  ```
- [ ] Checkpoint: save each chunk as `.parquet` to `CHECKPOINT_DIR` after split
- [ ] Support re-loading from checkpoint if run is resumed after failure
- [ ] Log partitioning result:
  ```
  [✓] Partitioned 1,200,000 rows into 8 chunks
      Chunk size: ~150,000 rows each
  ```

```python
class DataPartitioner:
    def split(self) -> list:
        chunk_size = len(self.df) // self.n_partitions
        chunks = []
        for i in range(self.n_partitions):
            start = i * chunk_size
            end = start + chunk_size if i < self.n_partitions - 1 else len(self.df)
            chunk = self.df.iloc[start:end].copy()
            chunks.append(chunk)
            if self.checkpoint:
                self._save_checkpoint(chunk, i)
        return chunks
```

---

## Task 2.6 — Wire-up into `Cleaner`

- [ ] After `.scan()`, call `EngineSelector` automatically
- [ ] Load data using selected engine
- [ ] Run `DataPartitioner` if rows > threshold
- [ ] Store results:
  - `self.engine_name`
  - `self.df` (full loaded df)
  - `self.chunks` (list of chunk DataFrames)

---

## Partitioning Flow Diagram

```
            Full Dataset (1.2M rows)
                    │
                    ▼
         ┌──────────────────────┐
         │  DataPartitioner     │
         │  n_partitions = 8    │
         └──────────┬───────────┘
                    │
      ┌─────────────┼─────────────┐
      ▼             ▼             ▼
  chunk_0        chunk_1  ...  chunk_7
 (150k rows)   (150k rows)   (150k rows)
      │             │             │
  checkpoint    checkpoint    checkpoint
  saved ✓       saved ✓       saved ✓
```

---

## Deliverable

```python
Cleaner("sales.csv", partitions=8, backend="auto").scan()
```

**Expected Output:**
```
[✓] Engine selected: Polars (size: 4.2 GB, rows: 8M)
[✓] Data loaded in 3.2s
[✓] Partitioned 8,000,000 rows into 8 chunks (~1M rows each)
[✓] Checkpoints saved to .refineflow_cache/
```

---

## Tests (`tests/test_module2.py`)

- [ ] Test engine selection for all 4 size ranges
- [ ] Test manual backend override (`backend="pandas"`)
- [ ] Test fallback when dask is not installed
- [ ] Test partitioner splits correct number of chunks
- [ ] Test small dataset skips partitioning (rows < 10,000)
- [ ] Test checkpoint files are created on disk
- [ ] Test re-loading from checkpoint after simulated failure

---

## Dependencies Installed

```bash
pip install polars dask[dataframe] pyarrow
# Optional:
pip install pyspark   # only for Spark engine
```

---

## Real-World Problems Handled in This Module

> Engine selection and partitioning are the **first line of defense** against memory crashes and performance bottlenecks. Getting this right means the rest of the pipeline runs smoothly.

### Memory Problems

| Problem | Real Example | Solution | Internal Technique |
|---------|-------------|----------|--------------------|
| RAM overflow | 20 GB CSV on 8 GB RAM machine | Lazy loading — never load full file into RAM | Chunked/streaming read via Dask or Polars lazy scan |
| Slow single-threaded execution | 120M rows cleaned in 45 min | Parallel partitioning across CPU cores | Multiprocessing via ProcessPoolExecutor |
| Huge object columns | Repeated city strings in 100M rows | Convert to `category` dtype before partitioning | Memory optimizer pre-pass |
| CSV inefficiency | 12 GB CSV vs 380 MB Parquet | Convert to Parquet immediately after first load | Columnar Parquet with Snappy compression |

**How we solve it:**
- Polars `scan_csv()` is **lazy** — builds a query plan, reads only needed columns
- Dask reads in `npartitions` chunks, processing each without loading the full file
- After engine loads the data, immediately run `MemoryOptimizer.quick_pass()` before partitioning:
  - Convert obvious object columns to `category`
  - Downcast `int64` → `int32` where safe
  - This reduces per-chunk memory before splitting → smaller, faster chunks

---

### Big Data Problems

| Problem | Real Example | Solution | Internal Technique |
|---------|-------------|----------|--------------------|
| File larger than RAM | 50 GB CSV on 16 GB machine | Distributed processing via Spark/Dask | Apache Spark with HDFS or local disk spill |
| Huge partition imbalance | One chunk has 80% of rows | Adaptive repartitioning based on actual sizes | Distributed scheduler with size-aware splitting |
| Slow distributed joins | Large cross-partition merge | Partition-aware joins using sort-merge | Spark optimizer with broadcast hints |
| Cross-node duplicate detection | Duplicates split across Spark workers | Global reduction phase after local dedup | Distributed hash engine with global dedup pass |

**How we solve it:**
- **Partition imbalance fix**: after initial split, check chunk sizes. If any chunk > 2× average size → re-split that chunk further
  ```python
  for i, chunk in enumerate(chunks):
      if len(chunk) > 2 * avg_chunk_size:
          chunks[i] = DataPartitioner(chunk, n_partitions=2).split()
  chunks = flatten(chunks)
  ```
- **Spark mode**: use `df.repartition(n)` after load to ensure even distribution
- **Cross-node dedup**: local dedup per partition (Module 3) + global dedup at merge (Module 4)

---

### Distributed Systems Problems

| Problem | Real Example | Solution | Internal Technique |
|---------|-------------|----------|--------------------|
| Worker failure | Spark node crashes mid-processing | Fault recovery via checkpointing | Save each completed chunk to disk immediately |
| Partial cleaning failure | Chunk 5 of 8 fails, run stops | Retry mechanism with exponential backoff | Fault-tolerant scheduler (3× retry) |
| Dependency conflicts | Merge attempted before validation completes | DAG orchestration ensures correct order | Pipeline graph engine — no step skipped |

**How we solve it:**
- **Checkpointing strategy**:
  - After each chunk is successfully cleaned → immediately save to `CHECKPOINT_DIR/chunk_{i}.parquet`
  - On restart: detect existing checkpoints → skip already-cleaned chunks → resume from failure point
  ```python
  if checkpoint_exists(chunk_id):
      chunk = load_checkpoint(chunk_id)
      log.info(f"[↺] Resumed chunk {chunk_id} from checkpoint")
  else:
      chunk = pipeline.run(raw_chunk)
      save_checkpoint(chunk, chunk_id)
  ```
- **Retry with backoff**: `time.sleep(2 ** attempt)` between retries (2s, 4s, 8s)
- **DAG enforcement**: `auto_clean()` steps are ordered and non-skippable — merge only runs when ALL chunks complete
