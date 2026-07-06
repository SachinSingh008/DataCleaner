"""
RefineFlow — Deduplicator
Handles duplicate identification and removal.
"""

from typing import Optional, List
import pandas as pd
import hashlib
from refineflow.logger import RefineLogger


class Deduplicator:
    """
    Identifies and removes duplicate rows using either native pandas deduplication
    or custom hash-based fingerprinting.
    """

    def __init__(
        self,
        subset: Optional[List[str]] = None,
        keep: str = "first",
        hash_based: bool = False,
        log: Optional[RefineLogger] = None,
    ):
        self.subset = subset
        self.keep = keep
        self.hash_based = hash_based
        self.log = log or RefineLogger()
        self.stats = {}

    def run(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Removes duplicates from the DataFrame and tracks statistics.
        """
        rows_before = len(df)
        self.log.info(f"Deduplicator: Checking for duplicates in {rows_before:,} rows")

        if self.hash_based and not self.subset:
            # Custom hash-based row deduplication
            # Useful for mixed dtypes or complex objects where pandas drop_duplicates might be slower
            row_hashes = df.fillna("").astype(str).apply(
                lambda row: hashlib.md5("".join(row.values).encode()).hexdigest(), axis=1
            )
            # Find the duplicate mask based on keep strategy
            if self.keep == "first":
                dup_mask = row_hashes.duplicated(keep="first")
            elif self.keep == "last":
                dup_mask = row_hashes.duplicated(keep="last")
            else:
                dup_mask = row_hashes.duplicated(keep=False)
            
            df_cleaned = df[~dup_mask].copy()
        else:
            # Native pandas drop_duplicates (highly optimized C-level implementation)
            df_cleaned = df.drop_duplicates(subset=self.subset, keep=self.keep)

        rows_after = len(df_cleaned)
        removed = rows_before - rows_after

        self.stats = {
            "rows_before": rows_before,
            "rows_after": rows_after,
            "removed": removed,
        }

        if removed > 0:
            self.log.success(f"Deduplicator: Removed {removed:,} duplicate rows")
        else:
            self.log.info("Deduplicator: No duplicate rows found")

        return df_cleaned
