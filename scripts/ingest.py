"""
Ingest the preprocessed accrual accounts CSV into PostgreSQL.

Usage:
    python -m scripts.ingest [path/to/csv]

If no path is given, defaults to "Data Dump - Accrual Accounts.csv" in the
project root.
"""

import sys
from pathlib import Path

import pandas as pd
from app.db.database import SessionLocal, init_db
from app.db.models import AccrualTransaction
from app.preprocessing.pipeline import preprocess

DEFAULT_CSV = Path(__file__).resolve().parent.parent / "Data Dump - Accrual Accounts.csv"


def ingest(csv_path: Path) -> int:
    """Preprocess CSV and bulk-insert into the database. Returns row count."""
    print(f"Preprocessing {csv_path} ...")
    df = preprocess(csv_path)
    print(f"  {len(df)} rows after preprocessing")

    # Convert pandas NA → None for SQLAlchemy.
    # df.where(..., None) doesn't replace NaN in float-dtype columns; those stay
    # as float('nan') in the dict and cause psycopg2 "smallint out of range" when
    # inserting into integer columns.  Use NaN != NaN (IEEE 754) to catch all floats.
    records = [
        {k: None if pd.isna(v) else v for k, v in row.items()}
        for row in df.to_dict(orient="records")
    ]

    print("Creating tables (if not exist) ...")
    init_db()

    print("Inserting records ...")
    db = SessionLocal()
    try:
        db.execute(AccrualTransaction.__table__.delete())
        db.bulk_insert_mappings(AccrualTransaction, records)
        db.commit()
        count = db.query(AccrualTransaction).count()
        print(f"  {count} rows in accrual_transactions")
        return count
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_CSV
    if not path.exists():
        print(f"Error: {path} not found")
        sys.exit(1)
    ingest(path)
    print("Done.")
