import os
from refineflow.cleaner import Cleaner

if __name__ == "__main__":
    # Ensure output directory exists
    os.makedirs("output", exist_ok=True)

    # Run full pipeline programmatically
    cleaner = (
        Cleaner("files/delivery.csv")
        .scan()
        .auto_clean()
        .optimize_memory()
        .generate_report(format="all", output_dir="output")
        .export(format="all", output_dir="output")
    )

    print(f"Dataset cleaned successfully! Output row count: {len(cleaner.df):,}")
