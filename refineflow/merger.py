"""
RefineFlow — Hierarchical Merger
Merges partition chunks in a tree reduction structure to minimize memory overhead.
"""

from typing import List, Optional
import pandas as pd
from refineflow.logger import RefineLogger


class HierarchicalMerger:
    """
    Combines a list of DataFrame chunks into a single DataFrame
    using a tree-reduction pattern (merging in pairs per round).
    """

    def __init__(self, chunks: List[pd.DataFrame], log: Optional[RefineLogger] = None):
        self.chunks = chunks
        self.log = log or RefineLogger()

    def merge(self) -> pd.DataFrame:
        """
        Performs the hierarchical merge.
        Returns a single merged DataFrame.
        """
        if not self.chunks:
            self.log.warning("HierarchicalMerger: Chunks list is empty. Returning empty DataFrame.")
            return pd.DataFrame()

        if len(self.chunks) == 1:
            return self.chunks[0].copy()

        # Track total rows before merge
        total_rows_before = sum(len(chunk) for chunk in self.chunks)
        chunks = [chunk.copy() for chunk in self.chunks]
        round_num = 1

        self.log.info(f"HierarchicalMerger: Starting merge of {len(chunks)} chunks (Total rows: {total_rows_before:,})")

        while len(chunks) > 1:
            merged = []
            for i in range(0, len(chunks), 2):
                if i + 1 < len(chunks):
                    c1 = chunks[i]
                    c2 = chunks[i + 1]
                    
                    # Schema reconciliation / mismatched column handling
                    diff_cols_1 = set(c2.columns) - set(c1.columns)
                    diff_cols_2 = set(c1.columns) - set(c2.columns)
                    
                    if diff_cols_1 or diff_cols_2:
                        mismatched = diff_cols_1.union(diff_cols_2)
                        self.log.warning(
                            f"HierarchicalMerger: Schema mismatch detected. "
                            f"Mismatched columns: {mismatched}. Filling with NaN."
                        )

                    combined = pd.concat([c1, c2], ignore_index=True)
                else:
                    # Odd chunk out — carry forward to next round
                    combined = chunks[i]
                merged.append(combined)

            chunks = merged
            self.log.info(f"Merge Round {round_num}: done ({len(chunks)} chunks remaining)")
            round_num += 1

        final_df = chunks[0]
        total_rows_after = len(final_df)
        self.log.success(
            f"HierarchicalMerger: Completed merge. "
            f"Rows before: {total_rows_before:,} | Rows after: {total_rows_after:,}"
        )

        return final_df
