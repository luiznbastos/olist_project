#!/usr/bin/env python3
"""
Unzip olist.zip and convert each CSV to Parquet in data_lake/raw/.

Run from the olist_dbt/ directory:
    python scripts/init_data_lake.py

The zip file is expected at ../olist.zip (sibling of olist_dbt/).
Output directory: data_lake/raw/ (relative to olist_dbt/).
"""
import os
import sys
import zipfile
import tempfile
from pathlib import Path

import pandas as pd

SCRIPT_DIR = Path(__file__).parent
REPO_DIR = SCRIPT_DIR.parent
ZIP_PATH = REPO_DIR.parent / "data_lake" / "olist.zip"
OUTPUT_DIR = REPO_DIR.parent / "data_lake" / "raw"


def main():
    if not ZIP_PATH.exists():
        print(f"ERROR: zip not found at {ZIP_PATH}", file=sys.stderr)
        sys.exit(1)

    for layer in ("raw", "bronze", "silver", "gold"):
        (OUTPUT_DIR.parent / layer).mkdir(parents=True, exist_ok=True)
    print(f"Writing Parquet files to {OUTPUT_DIR}")

    with tempfile.TemporaryDirectory() as tmp:
        print(f"Extracting {ZIP_PATH} ...")
        with zipfile.ZipFile(ZIP_PATH) as zf:
            zf.extractall(tmp)

        csv_files = list(Path(tmp).glob("**/*.csv"))
        if not csv_files:
            print("ERROR: no CSV files found inside the zip", file=sys.stderr)
            sys.exit(1)

        for csv_path in sorted(csv_files):
            parquet_name = csv_path.stem + ".parquet"
            out_path = OUTPUT_DIR / parquet_name
            print(f"  {csv_path.name} -> {parquet_name}")
            df = pd.read_csv(csv_path, low_memory=False)
            df.to_parquet(out_path, index=False, engine="pyarrow")

    written = sorted(OUTPUT_DIR.glob("*.parquet"))
    print(f"\nDone. {len(written)} Parquet files in {OUTPUT_DIR}:")
    for p in written:
        size_mb = p.stat().st_size / 1_048_576
        print(f"  {p.name}  ({size_mb:.1f} MB)")


if __name__ == "__main__":
    main()
