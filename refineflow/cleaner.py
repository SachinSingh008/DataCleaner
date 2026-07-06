"""
RefineFlow — Main Cleaner Class
Entry point. Fluent API — every method returns self for chaining.
"""

from __future__ import annotations

import os
from typing import Optional, Union
from pathlib import Path

import pandas as pd

from refineflow.config import (
    DEFAULT_PARTITIONS, SUPPORTED_FORMATS,
    CHECKPOINT_DIR, REPORT_FILENAME_HTML,
)
from refineflow.logger import RefineLogger
from refineflow.scanner import DatasetScanner
from refineflow.utils import (
    detect_file_format, ensure_dir, StopWatch,
    normalize_column_name, deduplicate_column_names,
)


class Cleaner:
    """
    RefineFlow main entry point.

    Basic usage:
        Cleaner("sales.csv").scan().auto_clean().export()

    Advanced usage:
        Cleaner("sales.csv", partitions=8, backend="dask") \\
            .scan() \\
            .auto_clean() \\
            .optimize_memory() \\
            .prepare_for_powerbi() \\
            .generate_report() \\
            .export(format="parquet")
    """

    def __init__(
        self,
        file: str,
        partitions: Optional[int] = None,
        backend: str = "auto",
        export_format: str = "csv",
        log_file: Optional[str] = None,
        verbose: bool = True,
    ):
        # Validate file
        if not os.path.exists(file):
            raise FileNotFoundError(f"File not found: {file}")

        fmt = detect_file_format(file)
        if fmt not in SUPPORTED_FORMATS:
            raise ValueError(
                f"Unsupported format '.{fmt}'. "
                f"Supported: {SUPPORTED_FORMATS}"
            )

        self.file          = file
        self.partitions    = partitions or DEFAULT_PARTITIONS
        self.backend       = backend
        self.export_format = export_format

        # Internal state
        self.df: Optional[pd.DataFrame] = None
        self.chunks: list[pd.DataFrame] = []
        self.scan_report: dict = {}
        self.validation_report: dict = {}
        self.stats: dict = {}
        self._engine_name: str = ""
        self._watch = StopWatch()

        # Logger
        self.log = RefineLogger(log_file=log_file, verbose=verbose)

        # Ensure cache dir
        ensure_dir(CHECKPOINT_DIR)

    # ── Module 1: Scan ────────────────────────────────────────────────────────

    def scan(self) -> Cleaner:
        """
        Scan the dataset — detect size, encoding, schema, duplicates, etc.
        Populates self.scan_report.
        """
        scanner = DatasetScanner(self.file, log=self.log)
        self.scan_report = scanner.run()
        scanner.print_report()

        # Auto-set partitions from recommendation if not explicitly set
        if self.partitions == DEFAULT_PARTITIONS:
            rec = self.scan_report.get("recommended_partitions", DEFAULT_PARTITIONS)
            if rec > DEFAULT_PARTITIONS:
                self.partitions = rec
                self.log.info(f"Auto-set partitions → {self.partitions}")

        return self

    # ── Module 2: Load + Engine + Partition ───────────────────────────────────

    def _load_data(self) -> None:
        """Load data using the selected engine and normalize column names."""
        from refineflow.engine.selector import EngineSelector
        from refineflow.engine.loader import load_as_pandas

        # Select engine
        selector = EngineSelector(self.scan_report, backend_override=self.backend)
        self._engine_name = selector.select()
        self.log.success(f"Engine selected: {self._engine_name}")

        # Load
        self.log.info(f"Loading data...")
        self.df = load_as_pandas(self.file, self._engine_name, self.scan_report)

        # Normalize column names immediately after load
        self.df.columns = [
            normalize_column_name(c) for c in self.df.columns
        ]
        self.df.columns = deduplicate_column_names(list(self.df.columns))
        self.log.success(f"Loaded {len(self.df):,} rows × {len(self.df.columns)} cols")

    def _partition_data(self) -> None:
        """Split DataFrame into chunks for parallel processing."""
        from refineflow.partitioner import DataPartitioner
        partitioner = DataPartitioner(
            self.df, n_partitions=self.partitions, log=self.log
        )
        self.chunks = partitioner.split()

    # ── Module 3+4: Auto Clean (full pipeline) ────────────────────────────────

    def auto_clean(self) -> Cleaner:
        """
        Run the full cleaning pipeline:
          Load → Partition → Parallel Clean → Merge → Global Validate
        """
        self.log.section("Auto Clean Pipeline")

        # Load if not already done
        if self.df is None:
            if not self.scan_report:
                self.scan()
            self._load_data()

        # Partition
        self._partition_data()

        # Parallel cleaning (Module 3)
        from refineflow.parallel_runner import ParallelRunner
        runner = ParallelRunner(self.chunks, log=self.log)
        cleaned_chunks, chunk_stats = runner.run()
        self.stats["chunks"] = chunk_stats

        # Hierarchical merge (Module 4)
        from refineflow.merger import HierarchicalMerger
        merger = HierarchicalMerger(cleaned_chunks, log=self.log)
        self.df = merger.merge()

        # Global validation (Module 4)
        from refineflow.global_validator import GlobalValidator
        validator = GlobalValidator(self.df, self.scan_report, log=self.log)
        self.df, val_report = validator.run()
        self.validation_report = val_report
        self.stats["global_validation"] = val_report

        # Schema drift detection (Module 6)
        from refineflow.schema_drift import SchemaDriftDetector
        detector = SchemaDriftDetector(self.df, snapshot_path="schema_snapshot.json")
        drift_report = detector.detect_drift()
        self.validation_report["schema_drift_report"] = drift_report

        elapsed = self._watch.split("auto_clean")
        self.log.success(f"auto_clean() complete in {elapsed}s — "
                         f"{len(self.df):,} rows ready")
        return self

    # ── Module 3: Standalone Memory Optimize ─────────────────────────────────

    def optimize_memory(self) -> Cleaner:
        """Standalone memory optimization pass (can be called after auto_clean)."""
        if self.df is None:
            self.log.warning("No data loaded. Run auto_clean() first.")
            return self
        from refineflow.cleaning.memory_optimizer import MemoryOptimizer
        optimizer = MemoryOptimizer(log=self.log)
        self.df, mem_stats = optimizer.run(self.df)
        self.stats["memory"] = mem_stats
        return self

    # ── Module 5: Visualization Preparation ──────────────────────────────────

    def prepare_for_powerbi(self, output_dir: str = "./") -> Cleaner:
        """Export Power BI optimized Parquet + schema JSON."""
        if self.df is None:
            self.log.warning("No data. Run auto_clean() first.")
            return self
        
        from refineflow.viz.prep_engine import VizPrepEngine
        self.df = VizPrepEngine(self.df, log=self.log).run()

        from refineflow.viz.powerbi_prep import PowerBIPrep
        prep = PowerBIPrep(self.df, output_dir=output_dir,
                           source_file=self.file, log=self.log)
        prep.run()
        return self

    def prepare_for_tableau(self, output_dir: str = "./") -> Cleaner:
        """Export Tableau optimized CSV + metadata JSON."""
        if self.df is None:
            self.log.warning("No data. Run auto_clean() first.")
            return self

        from refineflow.viz.prep_engine import VizPrepEngine
        self.df = VizPrepEngine(self.df, log=self.log).run()

        from refineflow.viz.tableau_prep import TableauPrep
        prep = TableauPrep(self.df, output_dir=output_dir,
                           source_file=self.file, log=self.log)
        prep.run()
        return self

    def recommend_visualizations(self) -> Cleaner:
        """Print recommended chart types based on column analysis."""
        if self.df is None:
            self.log.warning("No data. Run auto_clean() first.")
            return self
        from refineflow.viz.recommender import VizRecommender
        rec = VizRecommender(self.df, self.scan_report, log=self.log)
        rec.recommend()
        return self

    # ── Module 6: Report & Export ─────────────────────────────────────────────

    def _compile_stats(self) -> None:
        """Gathers processing stats across all runs and modules into self.stats."""
        # Baseline meta
        self.stats["source_file"] = os.path.basename(self.file)
        self.stats["runtime_seconds"] = self._watch.total()
        self.stats["engine_used"] = self._engine_name or "Pandas"
        self.stats["partitions"] = self.partitions
        
        # Row / column counts
        self.stats["rows_original"] = self.scan_report.get("estimated_rows", 0)
        self.stats["rows_final"] = len(self.df) if self.df is not None else 0
        self.stats["columns_original"] = self.scan_report.get("column_count", 0)
        self.stats["columns_final"] = len(self.df.columns) if self.df is not None else 0
        
        # Memory metrics
        self.stats["memory_before_gb"] = self.scan_report.get("size_bytes", 0.0) / (1024 * 1024 * 1024)
        if self.df is not None:
            self.stats["memory_after_gb"] = self.df.memory_usage(deep=True).sum() / (1024 * 1024 * 1024)
        else:
            self.stats["memory_after_gb"] = 0.0

        # Sum per-partition stats
        nulls_filled_total = 0
        duplicates_removed_total = 0
        outliers_handled_total = 0
        type_conversions_total = 0
        text_columns_cleaned_total = 0
        columns_stats = {}
        low_confidence_corrections = []

        chunk_stats_raw = self.stats.get("chunks", {})
        if isinstance(chunk_stats_raw, dict):
            chunk_stats_list = list(chunk_stats_raw.values())
        elif isinstance(chunk_stats_raw, list):
            chunk_stats_list = chunk_stats_raw
        else:
            chunk_stats_list = []

        for ch_stat in chunk_stats_list:
            if not isinstance(ch_stat, dict):
                continue
            nulls_filled_total += ch_stat.get("nulls_filled", 0)
            duplicates_removed_total += ch_stat.get("duplicates_removed", 0)
            outliers_handled_total += ch_stat.get("outliers_handled", 0)
            type_conversions_total += ch_stat.get("type_conversions", 0)
            text_columns_cleaned_total += ch_stat.get("text_cleaned", 0)
            
            # Aggregate column stats
            for col, col_info in ch_stat.get("columns", {}).items():
                if col not in columns_stats:
                    columns_stats[col] = {
                        "dtype": col_info.get("dtype", ""),
                        "nulls_filled": 0,
                        "strategy": col_info.get("strategy", "None"),
                        "outliers_detected": 0,
                        "type_converted": col_info.get("type_converted", False)
                    }
                columns_stats[col]["nulls_filled"] += col_info.get("nulls_filled", 0)
                columns_stats[col]["outliers_detected"] += col_info.get("outliers_detected", 0)

        # Include cross-chunk duplicates
        cross_dupes = self.validation_report.get("cross_chunk_duplicates_removed", 0)
        duplicates_removed_total += cross_dupes

        # Populate column casing/variants details from validation report
        for col, col_info in self.validation_report.get("columns_standardized", {}).items():
            if col not in columns_stats:
                columns_stats[col] = {}
            columns_stats[col]["variants_merged"] = col_info.get("variants_merged", 0)
            columns_stats[col]["canonical_count"] = col_info.get("canonical_count", 0)

        self.stats["nulls_filled_total"] = nulls_filled_total
        self.stats["duplicates_removed_total"] = duplicates_removed_total
        self.stats["outliers_handled_total"] = outliers_handled_total
        self.stats["type_conversions_total"] = type_conversions_total
        self.stats["text_columns_cleaned_total"] = text_columns_cleaned_total
        self.stats["columns"] = columns_stats

        # Populate low confidence corrections
        for ch_stat in chunk_stats_list:
            if isinstance(ch_stat, dict):
                low_confidence_corrections.extend(ch_stat.get("low_confidence_corrections", []))
        self.stats["low_confidence_corrections"] = low_confidence_corrections

    def generate_report(self, format: str = "html",
                        output_dir: str = "./") -> Cleaner:
        """Generate cleaning report (html / json / pdf / all)."""
        self._compile_stats()
        from refineflow.reporter import ReportGenerator
        gen = ReportGenerator(
            stats=self.stats,
            scan_report=self.scan_report,
            validation_report=self.validation_report,
            log=self.log
        )
        generated = gen.generate_report(format=format, output_dir=output_dir)
        
        # Track report files
        if "exported_files" not in self.stats:
            self.stats["exported_files"] = []
        self.stats["exported_files"].extend(generated.values())
        
        total_bytes = sum(os.path.getsize(f) for f in generated.values() if os.path.exists(f))
        self.stats["exported_total_size_bytes"] = self.stats.get("exported_total_size_bytes", 0) + total_bytes
        
        return self

    def export(self, format: str = "csv", output_dir: str = "./") -> Cleaner:
        """Export cleaned DataFrame (csv / parquet / excel / json / all)."""
        if self.df is None:
            self.log.warning("No data to export.")
            return self
        
        self._compile_stats()
        
        from refineflow.exporter import DataExporter
        exp = DataExporter(
            df=self.df,
            source_file=self.file,
            output_dir=output_dir,
            log=self.log
        )
        exported = exp.export(format=format)
        
        # Track exported files
        if "exported_files" not in self.stats:
            self.stats["exported_files"] = []
        self.stats["exported_files"].extend(exported)
        
        total_bytes = sum(os.path.getsize(f) for f in exported if os.path.exists(f))
        self.stats["exported_total_size_bytes"] = self.stats.get("exported_total_size_bytes", 0) + total_bytes
        
        self._watch.split("export")
        return self

    # ── Introspection ─────────────────────────────────────────────────────────

    def shape(self) -> tuple:
        return self.df.shape if self.df is not None else (0, 0)

    def head(self, n: int = 5) -> pd.DataFrame:
        return self.df.head(n) if self.df is not None else pd.DataFrame()

    def summary(self) -> None:
        """Print a quick runtime summary."""
        total = self._watch.total()
        rows  = len(self.df) if self.df is not None else 0
        cols  = len(self.df.columns) if self.df is not None else 0
        bar   = "=" * 40
        print(f"\n{bar}")
        print(f"  RefineFlow - Run Summary")
        print(f"{bar}")
        print(f"  File:    {os.path.basename(self.file)}")
        print(f"  Engine:  {self._engine_name}")
        print(f"  Rows:    {rows:,}")
        print(f"  Columns: {cols}")
        print(f"  Runtime: {total}s")
        print(f"{bar}\n")

    def __repr__(self) -> str:
        rows = len(self.df) if self.df is not None else "not loaded"
        return f"<Cleaner file='{self.file}' rows={rows} engine='{self._engine_name}'>"
