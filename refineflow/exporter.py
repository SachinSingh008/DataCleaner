"""
RefineFlow — Multi-Format Export Engine
Optimized data serialization for CSV, Parquet, Excel, and JSON.
"""

import os
import re
from typing import List, Optional
import pandas as pd
from refineflow.logger import RefineLogger
from refineflow.utils import ensure_dir


def format_size(size_bytes: int) -> str:
    """Formats bytes to a human-readable size string."""
    if size_bytes <= 0:
        return "0 B"
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if size_bytes < 1024:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024
    return f"{size_bytes:.1f} PB"


class DataExporter:
    """
    Serializes cleaned DataFrames to various formats with platform-specific optimizations,
    such as snappy compression for Parquet and layout styling for Excel.
    """

    def __init__(
        self,
        df: pd.DataFrame,
        output_dir: str = "./",
        source_file: Optional[str] = None,
        log: Optional[RefineLogger] = None
    ):
        self.df = df
        self.output_dir = output_dir
        self.source_file = source_file
        self.log = log or RefineLogger()

        self.exported_files: List[str] = []
        self.exported_sizes: List[int] = []

    def export(self, format: str = "parquet", output_dir: Optional[str] = None) -> List[str]:
        """
        Exports the DataFrame to the specified format.
        
        Args:
            format: Output format ('csv', 'parquet', 'excel', 'json', or 'all').
            output_dir: Custom output directory (overrides default).
            
        Returns:
            List[str]: Paths to the exported files.
        """
        out_dir = output_dir or self.output_dir
        ensure_dir(out_dir)

        # Get base name from source file
        if self.source_file:
            base_name = os.path.splitext(os.path.basename(self.source_file))[0]
        else:
            base_name = "dataset"

        fmt = format.lower()
        formats_to_run = []
        if fmt == "all":
            formats_to_run = ["parquet", "csv", "excel", "json"]
        else:
            formats_to_run = [fmt]

        self.log.section("Data Export")

        local_exported = []
        for f_type in formats_to_run:
            file_path = ""
            if f_type == "csv":
                file_path = os.path.join(out_dir, f"cleaned_{base_name}.csv")
                self.df.to_csv(file_path, index=False, encoding="utf-8-sig")
            elif f_type == "parquet":
                file_path = os.path.join(out_dir, f"cleaned_{base_name}.parquet")
                self.df.to_parquet(file_path, engine="pyarrow", compression="snappy", index=False)
            elif f_type == "excel":
                file_path = os.path.join(out_dir, f"cleaned_{base_name}.xlsx")
                self._export_excel(file_path)
            elif f_type == "json":
                file_path = os.path.join(out_dir, f"cleaned_{base_name}.json")
                self.df.to_json(file_path, orient="records", indent=2)
            else:
                self.log.error(f"Exporter: Unsupported format '{f_type}'")
                continue

            if file_path and os.path.exists(file_path):
                self.exported_files.append(file_path)
                local_exported.append(file_path)
                file_size = os.path.getsize(file_path)
                self.exported_sizes.append(file_size)

                # Format human readable size message
                size_str = format_size(file_size)
                orig_size_str = ""
                reduction_str = ""
                if self.source_file and os.path.exists(self.source_file):
                    orig_size = os.path.getsize(self.source_file)
                    orig_size_str = f" (original: {format_size(orig_size)}"
                    if orig_size > 0:
                        pct = (1.0 - (file_size / orig_size)) * 100
                        if pct > 0:
                            reduction_str = f" → {pct:.1f}% reduction via {f_type.title()})"
                        else:
                            reduction_str = ")"
                    else:
                        reduction_str = ")"

                msg = f"Exported: {file_path}\n      Size: {size_str}{orig_size_str}{reduction_str}"
                self.log.success(msg)

        return local_exported

    def _export_excel(self, file_path: str):
        """Exports DataFrame to Excel with frozen headers, autofilter, and auto column widths."""
        self.df.to_excel(file_path, index=False, engine="openpyxl")
        try:
            import openpyxl
            wb = openpyxl.load_workbook(file_path)
            ws = wb.active

            # Freeze top row
            ws.freeze_panes = "A2"

            # Auto-fit columns
            for col in ws.columns:
                # Find length of values in this column
                max_len = 0
                for cell in col:
                    val_str = str(cell.value) if cell.value is not None else ""
                    if len(val_str) > max_len:
                        max_len = len(val_str)
                col_letter = openpyxl.utils.get_column_letter(col[0].column)
                ws.column_dimensions[col_letter].width = max(max_len + 3, 10)

            # Auto-filter
            ws.auto_filter.ref = ws.dimensions

            wb.save(file_path)
        except Exception as e:
            self.log.warning(f"Exporter: Failed to apply styling to Excel workbook: {e}")
