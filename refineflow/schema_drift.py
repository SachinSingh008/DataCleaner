"""
RefineFlow — Schema Drift Detector
Monitors and logs alterations in schema structure across pipeline runs.
"""

import os
import json
import warnings
import datetime
import difflib
from typing import Dict, List, Optional
import pandas as pd


class SchemaDriftWarning(UserWarning):
    """Warning raised when schema drift is detected."""
    pass


class SchemaDriftDetector:
    """
    Detects changes between the schema of the current DataFrame and a saved
    historical schema snapshot. Raises warnings on drift and outputs JSON metadata reports.
    """

    def __init__(self, current_df: pd.DataFrame, snapshot_path: str = "schema_snapshot.json"):
        self.df = current_df
        self.snapshot_path = snapshot_path

    def detect_drift(self) -> dict:
        """
        Compares the current DataFrame schema with the saved snapshot.
        If no snapshot exists, saves the current schema as the snapshot.
        
        Returns:
            dict: Schema drift report containing detected flag, new/removed columns,
                  type changes, and likely renamed columns.
        """
        report = {
            "detected": False,
            "new_columns": [],
            "removed_columns": [],
            "type_changes": {},
            "renamed_likely": []
        }

        current_schema = {
            col: str(self.df[col].dtype) for col in self.df.columns
        }

        # First run: snapshot doesn't exist, create it
        if not os.path.exists(self.snapshot_path):
            snapshot_data = {
                "columns": current_schema,
                "row_count": len(self.df),
                "created_at": datetime.datetime.utcnow().isoformat() + "Z"
            }
            try:
                with open(self.snapshot_path, "w") as f:
                    json.dump(snapshot_data, f, indent=2)
            except Exception:
                pass
            return report

        # Load snapshot
        try:
            with open(self.snapshot_path, "r") as f:
                snapshot = json.load(f)
        except Exception:
            # Fallback if corrupt
            return report

        snapshot_schema = snapshot.get("columns", {})

        # Added & Removed columns
        new_cols = [c for c in current_schema if c not in snapshot_schema]
        removed_cols = [c for c in snapshot_schema if c not in current_schema]

        report["new_columns"] = new_cols
        report["removed_columns"] = removed_cols

        # Type changes
        type_changes = {}
        for col in current_schema:
            if col in snapshot_schema:
                old_type = snapshot_schema[col]
                new_type = current_schema[col]
                if old_type != new_type:
                    # Risk evaluation: high risk if converting numeric <-> non-numeric
                    old_num = any(x in old_type for x in ["int", "float", "double"])
                    new_num = any(x in new_type for x in ["int", "float", "double"])
                    risk = "HIGH" if (old_num != new_num) else "LOW"
                    type_changes[col] = {
                        "was": old_type,
                        "now": new_type,
                        "risk": risk
                    }
        report["type_changes"] = type_changes

        # Likely renames using string similarity (difflib)
        renamed_likely = []
        # Copy to avoid mutation during iteration
        temp_removed = list(removed_cols)
        for new_col in list(new_cols):
            best_match = None
            best_ratio = 0.0
            for r_col in temp_removed:
                ratio = difflib.SequenceMatcher(None, new_col.lower(), r_col.lower()).ratio()
                if ratio > best_ratio:
                    best_ratio = ratio
                    best_match = r_col

            if best_match and best_ratio >= 0.8:
                renamed_likely.append({
                    "old": best_match,
                    "new": new_col,
                    "similarity": round(best_ratio, 2)
                })
                # Remove from temp to prevent double mapping
                temp_removed.remove(best_match)

        report["renamed_likely"] = renamed_likely

        # Determine if drift detected
        if new_cols or removed_cols or type_changes or renamed_likely:
            report["detected"] = True

        # Raise warnings
        if report["detected"]:
            warn_msg = "Schema drift detected in RefineFlow run:\n"
            if new_cols:
                warn_msg += f"  - New columns: {new_cols}\n"
            if removed_cols:
                warn_msg += f"  - Removed columns: {removed_cols}\n"
            if type_changes:
                warn_msg += "  - Type changes:\n"
                for c, info in type_changes.items():
                    warn_msg += f"    * {c}: {info['was']} -> {info['now']} (Risk: {info['risk']})\n"
            if renamed_likely:
                warn_msg += "  - Likely Renamed Columns:\n"
                for entry in renamed_likely:
                    warn_msg += f"    * {entry['old']} -> {entry['new']} (similarity: {entry['similarity']})\n"

            warnings.warn(warn_msg, category=SchemaDriftWarning, stacklevel=2)

        return report
