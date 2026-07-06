"""
RefineFlow — Command-Line Interface (CLI)
Exposes scan, clean, and recommend actions to the command line using click.
"""

import os
import sys
import click
from typing import Optional

# Ensure sys.stdout is configured to use UTF-8 on Windows
if sys.stdout and hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

from refineflow.cleaner import Cleaner
from refineflow.exporter import format_size


@click.group()
def main():
    """RefineFlow: Distributed Intelligent Data Refinement Engine."""
    pass


@main.command()
@click.argument("file", type=click.Path(exists=True, file_okay=True, dir_okay=False))
def scan(file):
    """Run dataset scanner only on the target file."""
    try:
        cleaner = Cleaner(file, verbose=True)
        cleaner.scan()
    except Exception as e:
        click.secho(f"Error scanning file: {e}", fg="red", err=True)
        sys.exit(1)


@main.command()
@click.argument("file", type=click.Path(exists=True, file_okay=True, dir_okay=False))
def recommend(file):
    """Scan the dataset and recommend visualizations."""
    try:
        cleaner = Cleaner(file, verbose=True)
        cleaner.scan().auto_clean().recommend_visualizations()
    except Exception as e:
        click.secho(f"Error during recommendation: {e}", fg="red", err=True)
        sys.exit(1)


@main.command()
@click.argument("file", type=click.Path(exists=True, file_okay=True, dir_okay=False))
@click.option("--partitions", default=None, type=int, help="Number of partitions/chunks")
@click.option("--backend", default="auto", help="pandas / polars / dask / spark")
@click.option("--export", default="csv", help="csv / parquet / excel / json / all")
@click.option("--report", default="html", help="html / json / pdf / all")
@click.option("--output-dir", default="./", help="Output directory")
@click.option("--no-report", is_flag=True, default=False, help="Skip report generation")
def clean(file, partitions, backend, export, report, output_dir, no_report):
    """Run full auto-clean, export products, and write refinement reports."""
    try:
        cleaner = Cleaner(
            file=file,
            partitions=partitions,
            backend=backend,
            verbose=True
        )
        
        # Run clean pipeline
        cleaner.scan().auto_clean().optimize_memory()
        
        # Run reports
        if not no_report:
            cleaner.generate_report(format=report, output_dir=output_dir)
            
        # Run export
        cleaner.export(format=export, output_dir=output_dir)
        
        # Display completion summary card
        _print_summary_card(cleaner)
        
    except Exception as e:
        click.secho(f"Error executing auto_clean: {e}", fg="red", err=True)
        sys.exit(1)


def _print_summary_card(cleaner: Cleaner) -> None:
    """Prints a beautiful, ASCII-safe console card summarizing execution metrics."""
    stats = cleaner.stats
    
    rows_cleaned = stats.get("rows_final", 0)
    dupes_removed = stats.get("duplicates_removed_total", 0)
    nulls_filled = stats.get("nulls_filled_total", 0)
    
    mem_before = format_size(int(stats.get("memory_before_gb", 0.0) * 1024 * 1024 * 1024))
    mem_after = format_size(int(stats.get("memory_after_gb", 0.0) * 1024 * 1024 * 1024))
    
    runtime = stats.get("runtime_seconds", 0.0)
    if runtime >= 60:
        minutes = int(runtime // 60)
        seconds = int(runtime % 60)
        runtime_str = f"{minutes}m {seconds}s"
    else:
        runtime_str = f"{runtime:.2f}s"
        
    exported_files = stats.get("exported_files", [])
    export_str = os.path.basename(exported_files[-1]) if exported_files else "None"
    if len(export_str) > 23:
        export_str = export_str[:20] + "..."

    # Printable ASCII-safe card (CP1252/Windows friendly)
    border = "+--------------------------------------+"
    click.echo("")
    click.echo(border)
    click.echo("|  RefineFlow - Run Complete           |")
    click.echo("+--------------------------------------+")
    click.echo(f"|  Rows Cleaned:    {rows_cleaned:<18,} |")
    click.echo(f"|  Dupes Removed:   {dupes_removed:<18,} |")
    click.echo(f"|  Nulls Filled:    {nulls_filled:<18,} |")
    click.echo(f"|  Memory Saved:    {mem_before} -> {mem_after:<9} |")
    click.echo(f"|  Runtime:         {runtime_str:<18} |")
    click.echo(f"|  Exports:         {export_str:<18} |")
    click.echo(border)
    click.echo("")


if __name__ == "__main__":
    main()
