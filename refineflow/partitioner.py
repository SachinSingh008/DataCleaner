"""
RefineFlow — Data Partitioner
Divides a Pandas DataFrame into manageable, checkpointed partitions.
"""

import os
import glob
from typing import Optional, List
import pandas as pd
from refineflow.config import (
    PARTITION_ROW_THRESHOLD,
    CHECKPOINT_DIR,
)
from refineflow.logger import RefineLogger


class DataPartitioner:
    """
    Splits a Pandas DataFrame into N partitions.
    Supports checkpoint saving and recovery.
    """

    def __init__(
        self,
        df: pd.DataFrame,
        n_partitions: int,
        scan_report: Optional[dict] = None,
        checkpoint: bool = True,
        log: Optional[RefineLogger] = None,
    ):
        self.df = df
        self.n_partitions = n_partitions
        self.scan_report = scan_report or {}
        self.checkpoint = checkpoint
        self.log = log or RefineLogger()

        # Generate a unique key for checkpoints (using fingerprint if available, otherwise shape/columns)
        fp = self.scan_report.get("fingerprint")
        if not fp and df is not None:
            # Fallback fingerprint based on df shape and columns
            import hashlib
            cols_str = "".join(df.columns)
            fp_raw = f"{df.shape[0]}_{df.shape[1]}_{cols_str}"
            fp = hashlib.md5(fp_raw.encode()).hexdigest()
        self.fingerprint = fp or "temp"

    def split(self) -> List[pd.DataFrame]:
        """
        Splits df into self.n_partitions row-slices.
        If rows < PARTITION_ROW_THRESHOLD, returns [df] without splitting.
        """
        # Check if checkpoints already exist and can be loaded (resuming run)
        if self.checkpoint:
            loaded_chunks = self._load_checkpoints()
            if loaded_chunks:
                self.log.resume(
                    f"Resumed partitioning: loaded {len(loaded_chunks)} chunks "
                    f"from checkpoints in '{CHECKPOINT_DIR}'"
                )
                return loaded_chunks

        if self.df is None or len(self.df) == 0:
            self.log.warning("DataFrame is empty. Skipping partitioning.")
            return []

        rows_count = len(self.df)

        if rows_count < PARTITION_ROW_THRESHOLD:
            self.log.info(
                f"Row count ({rows_count}) below threshold ({PARTITION_ROW_THRESHOLD}). "
                "Skipping partitioning (single partition mode)."
            )
            self.df.attrs["metadata"] = {
                "chunk_id": 0,
                "rows": rows_count,
                "start_idx": 0,
                "end_idx": rows_count - 1,
            }
            return [self.df]

        # Calculate chunk size
        chunk_size = rows_count // self.n_partitions
        chunks = []

        self.log.info(
            f"Partitioning {rows_count:,} rows into {self.n_partitions} chunks "
            f"(~{chunk_size:,} rows each)"
        )

        for i in range(self.n_partitions):
            start = i * chunk_size
            end = start + chunk_size if i < self.n_partitions - 1 else rows_count
            chunk = self.df.iloc[start:end].copy()

            # Assign chunk metadata
            chunk.attrs["metadata"] = {
                "chunk_id": i,
                "rows": len(chunk),
                "start_idx": start,
                "end_idx": end - 1,
            }

            chunks.append(chunk)

            if self.checkpoint:
                self._save_checkpoint(chunk, i)

        self.log.success(f"Partitioned dataset into {len(chunks)} chunks successfully")
        return chunks

    def _save_checkpoint(self, chunk: pd.DataFrame, chunk_id: int) -> None:
        """Saves a chunk to parquet format as a checkpoint."""
        os.makedirs(CHECKPOINT_DIR, exist_ok=True)
        filename = f"chunk_{self.fingerprint}_{chunk_id}.parquet"
        filepath = os.path.join(CHECKPOINT_DIR, filename)
        try:
            chunk.to_parquet(filepath, index=False)
            self.log.info(f"Saved checkpoint: {filename}")
        except Exception as e:
            self.log.warning(f"Failed to save checkpoint for chunk {chunk_id}: {e}")

    def _load_checkpoints(self) -> List[pd.DataFrame]:
        """Attempts to load checkpoints from disk if they all exist."""
        chunks = []
        for i in range(self.n_partitions):
            filename = f"chunk_{self.fingerprint}_{i}.parquet"
            filepath = os.path.join(CHECKPOINT_DIR, filename)
            if not os.path.exists(filepath):
                return []  # Return empty list if any partition checkpoint is missing
            try:
                chunk = pd.read_parquet(filepath)
                # Re-assign metadata
                chunk.attrs["metadata"] = {
                    "chunk_id": i,
                    "rows": len(chunk),
                    # approximate indices since start/end of raw df isn't persisted directly in parquet
                    "start_idx": i * (len(chunk)),
                    "end_idx": (i + 1) * (len(chunk)) - 1,
                }
                chunks.append(chunk)
            except Exception as e:
                self.log.warning(f"Error reading checkpoint {filename}: {e}")
                return []
        return chunks
