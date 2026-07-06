"""
RefineFlow — Cleaning Pipeline Orchestrator
Executes all cleaning tasks on a chunk and aggregates run metrics.
"""

from typing import Optional, Tuple, Dict
import pandas as pd
from refineflow.logger import RefineLogger
from refineflow.cleaning.type_fixer import TypeFixer
from refineflow.cleaning.null_handler import NullHandler
from refineflow.cleaning.text_cleaner import TextCleaner
from refineflow.cleaning.unit_normalizer import UnitNormalizer
from refineflow.cleaning.deduplicator import Deduplicator
from refineflow.cleaning.outlier_detector import OutlierDetector
from refineflow.cleaning.memory_optimizer import MemoryOptimizer
from refineflow.cleaning.validator import PerChunkValidator


class CleaningPipeline:
    """
    Sequentially runs TypeFixer, NullHandler, TextCleaner, UnitNormalizer, Deduplicator,
    OutlierDetector, MemoryOptimizer, and PerChunkValidator.
    Tracks statistics and provides error isolation per step.
    """

    def __init__(self, config: Optional[dict] = None, log: Optional[RefineLogger] = None):
        self.config = config or {}
        self.log = log or RefineLogger()
        self.stats = {}

    def run(self, df: pd.DataFrame) -> Tuple[pd.DataFrame, Dict]:
        """
        Executes the cleaning pipeline on df. Returns (cleaned_df, stats_dict).
        """
        # Ensure df is a copy to prevent settings-with-copy issues
        df = df.copy()

        # Step 1: TypeFixer
        try:
            tf = TypeFixer(log=self.log)
            df = tf.run(df)
            self.stats["type_fixer"] = tf.stats
        except Exception as e:
            self.log.warning(f"Pipeline step 'TypeFixer' failed: {e}")

        # Step 2: UnitNormalizer (standardizes physical weight/time suffixes to numbers)
        try:
            un = UnitNormalizer(log=self.log)
            df = un.run(df)
            self.stats["unit_normalizer"] = un.stats
        except Exception as e:
            self.log.warning(f"Pipeline step 'UnitNormalizer' failed: {e}")

        # Step 3: TextCleaner
        try:
            tc = TextCleaner(log=self.log)
            df = tc.run(df)
            self.stats["text_cleaner"] = tc.stats
        except Exception as e:
            self.log.warning(f"Pipeline step 'TextCleaner' failed: {e}")

        # Step 4: Deduplicator
        try:
            dedup_config = self.config.get("deduplicator", {})
            dedup = Deduplicator(
                subset=dedup_config.get("subset"),
                keep=dedup_config.get("keep", "first"),
                hash_based=dedup_config.get("hash_based", False),
                log=self.log,
            )
            df = dedup.run(df)
            self.stats["deduplicator"] = dedup.stats
        except Exception as e:
            self.log.warning(f"Pipeline step 'Deduplicator' failed: {e}")

        # Step 5: OutlierDetector
        try:
            outlier_config = self.config.get("outlier", {})
            od = OutlierDetector(
                method=outlier_config.get("method", "iqr"),
                action=outlier_config.get("action", "clip"),
                custom_constraints=outlier_config.get("custom_constraints"),
                log=self.log,
            )
            df = od.run(df)
            self.stats["outlier_detector"] = od.stats
        except Exception as e:
            self.log.warning(f"Pipeline step 'OutlierDetector' failed: {e}")

        # Step 6: PerChunkValidator
        try:
            validator_config = self.config.get("validator", {})
            v = PerChunkValidator(rules=validator_config.get("rules"), log=self.log)
            df = v.run(df)
            self.stats["validator"] = v.stats
        except Exception as e:
            self.log.warning(f"Pipeline step 'PerChunkValidator' failed: {e}")

        # Step 7: NullHandler (run after other steps so anomalous values set to NaN can be filled)
        try:
            null_config = self.config.get("null_strategy")
            nh = NullHandler(strategy_config=null_config, log=self.log)
            df = nh.run(df)
            self.stats["null_handler"] = nh.stats
        except Exception as e:
            self.log.warning(f"Pipeline step 'NullHandler' failed: {e}")

        # Step 8: MemoryOptimizer
        try:
            mo = MemoryOptimizer(log=self.log)
            df, mo_stats = mo.run(df)
            self.stats["memory_optimizer"] = mo_stats
        except Exception as e:
            self.log.warning(f"Pipeline step 'MemoryOptimizer' failed: {e}")

        return df, self.stats
