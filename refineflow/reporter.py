"""
RefineFlow — Report Generator
Aggregates processing metrics and produces HTML, JSON, and PDF reports.
"""

import os
import json
import datetime
from typing import Optional, Dict
from jinja2 import Environment, FileSystemLoader
from refineflow.logger import RefineLogger


class ReportGenerator:
    """
    Assembles logs, scanner details, validator audits, and execution metadata
    into formatted HTML, JSON, and PDF documents.
    """

    def __init__(
        self,
        stats: dict,
        scan_report: Optional[dict] = None,
        validation_report: Optional[dict] = None,
        log: Optional[RefineLogger] = None
    ):
        self.stats = stats or {}
        self.scan_report = scan_report or {}
        self.validation_report = validation_report or {}
        self.log = log or RefineLogger()

    def generate_report(self, format: str = "html", output_dir: str = "./") -> Dict[str, str]:
        """
        Generates reports in HTML, JSON, and PDF formats.
        
        Args:
            format: Output format ('html', 'json', 'pdf', or 'all').
            output_dir: Directory where reports will be saved.
            
        Returns:
            Dict[str, str]: Dict mapping generated formats to their output file paths.
        """
        from refineflow.utils import ensure_dir
        ensure_dir(output_dir)
        full_report = self._aggregate_stats()

        generated = {}
        fmt = format.lower()
        
        formats_to_gen = []
        if fmt == "all":
            formats_to_gen = ["json", "html", "pdf"]
        else:
            formats_to_gen = [fmt]

        self.log.section("Report Generation")

        # 1. JSON Report
        if "json" in formats_to_gen or "all" in formats_to_gen:
            json_path = os.path.join(output_dir, "refineflow_report.json")
            try:
                with open(json_path, "w") as f:
                    json.dump(full_report, f, indent=2, default=str)
                generated["json"] = json_path
            except Exception as e:
                self.log.error(f"Reporter: Failed to write JSON report: {e}")

        # 2. HTML Report
        html_content = ""
        if "html" in formats_to_gen or "pdf" in formats_to_gen or "all" in formats_to_gen:
            html_path = os.path.join(output_dir, "refineflow_report.html")
            try:
                templates_dir = os.path.join(os.path.dirname(__file__), "templates")
                env = Environment(loader=FileSystemLoader(templates_dir))
                template = env.get_template("report_template.html")
                html_content = template.render(report=full_report)
                
                if "html" in formats_to_gen:
                    with open(html_path, "w", encoding="utf-8") as f:
                        f.write(html_content)
                    generated["html"] = html_path
            except Exception as e:
                self.log.error(f"Reporter: Failed to write HTML report: {e}")

        # 3. PDF Report
        if "pdf" in formats_to_gen or "all" in formats_to_gen:
            pdf_path = os.path.join(output_dir, "refineflow_report.pdf")
            try:
                import weasyprint
                # Renders the HTML string directly to a PDF document
                if not html_content:
                    templates_dir = os.path.join(os.path.dirname(__file__), "templates")
                    env = Environment(loader=FileSystemLoader(templates_dir))
                    template = env.get_template("report_template.html")
                    html_content = template.render(report=full_report)
                
                weasyprint.HTML(string=html_content).write_pdf(pdf_path)
                generated["pdf"] = pdf_path
            except ImportError:
                self.log.warning("Reporter: weasyprint is not installed. Skipping PDF generation.")
            except Exception as e:
                self.log.error(f"Reporter: Failed to write PDF report: {e}")

        # Log results
        if generated:
            self.log.success("Report Generated:")
            for mode, path in generated.items():
                size_kb = os.path.getsize(path) / 1024
                self.log.info(f"      → {os.path.basename(path)}  ({size_kb:.1f} KB)")

        return generated

    def _aggregate_stats(self) -> dict:
        """Compiles stats from scanner, cleaner, and validator into a unified schema."""
        # Calculate memory reduction
        before_gb = self.stats.get("memory_before_gb", 0.0)
        after_gb = self.stats.get("memory_after_gb", 0.0)
        pct_reduction = 0.0
        if before_gb > 0:
            pct_reduction = max(0.0, (1.0 - (after_gb / before_gb)) * 100)

        # Collect column statistics
        per_column = {}
        for col, col_stats in self.stats.get("columns", {}).items():
            per_column[col] = {
                "dtype": col_stats.get("dtype", ""),
                "nulls_filled": col_stats.get("nulls_filled", 0),
                "strategy": col_stats.get("strategy", "None"),
                "outliers": col_stats.get("outliers_detected", 0),
                "variants_merged": col_stats.get("variants_merged", 0),
                "canonical": col_stats.get("canonical_count", 0),
                "type_converted": col_stats.get("type_converted", False)
            }

        # Format low-confidence items (for review queue)
        low_confidence_items = self.stats.get("low_confidence_corrections", [])

        # Build aggregated report structure
        full_report = {
            "meta": {
                "file": self.stats.get("source_file", "unknown_dataset"),
                "runtime_seconds": self.stats.get("runtime_seconds", 0.0),
                "engine_used": self.stats.get("engine_used", "Pandas"),
                "partitions": self.stats.get("partitions", 1),
                "timestamp": datetime.datetime.utcnow().isoformat() + "Z"
            },
            "dataset": {
                "rows_original": self.stats.get("rows_original", 0),
                "rows_final": self.stats.get("rows_final", 0),
                "columns_original": self.stats.get("columns_original", 0),
                "columns_final": self.stats.get("columns_final", 0)
            },
            "cleaning": {
                "nulls_filled": self.stats.get("nulls_filled_total", 0),
                "duplicates_removed": self.stats.get("duplicates_removed_total", 0),
                "outliers_handled": self.stats.get("outliers_handled_total", 0),
                "type_conversions": self.stats.get("type_conversions_total", 0),
                "text_columns_cleaned": self.stats.get("text_columns_cleaned_total", 0),
                "low_confidence_corrections": low_confidence_items
            },
            "memory": {
                "before_gb": round(before_gb, 3),
                "after_gb": round(after_gb, 3),
                "reduction_percent": round(pct_reduction, 1)
            },
            "per_column": per_column,
            "validation": {
                "cross_chunk_dupes": self.validation_report.get("cross_chunk_duplicates_removed", 0),
                "categories_standardized": self.validation_report.get("categories_standardized", 0),
                "integrity_violations_fixed": self.validation_report.get("integrity_violations_fixed", 0),
                "schema_drift": self.validation_report.get("schema_drift_report", {})
            },
            "export": {
                "files": [os.path.basename(f) for f in self.stats.get("exported_files", [])],
                "total_size_mb": round(self.stats.get("exported_total_size_bytes", 0) / (1024 * 1024), 2)
            },
            "logs": [f"[{entry['level'].upper()}] {entry['message']}" for entry in self.log.get_entries()] if hasattr(self.log, "get_entries") else []
        }

        return full_report
