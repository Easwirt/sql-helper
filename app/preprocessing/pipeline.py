"""
Simple preprocessing for the SAP Accrual Accounts CSV.

Minimal cleanup to get the data into the database for the PoC.
"""

from pathlib import Path
import pandas as pd

# Column rename mapping: raw CSV → clean DB column names
COLUMN_MAP = {
    "Authorization Group": "authorization_group",
    "Bus. Transac. Type": "business_transaction_type",
    "Calculate Tax": "calculate_tax",
    "Cash Flow-Relevant Doc.": "cash_flow_relevant",
    "Cleared Item": "is_cleared",
    "Clearing Date": "clearing_date",
    "Clearing Entry Date": "clearing_entry_date",
    "Clearing Fiscal Year": "clearing_fiscal_year",
    "Country Key": "country_key",
    "Currency": "currency",
    "Debit/Credit ind": "debit_credit_indicator",
    "Transaction Value": "transaction_value",
    "Document Is Back-Posted": "document_is_back_posted",
    "Exchange rate": "exchange_rate",
    "Fiscal Year.1": "original_fiscal_year",
    "Fiscal Year.2": "fiscal_year",
    "Posting period.1": "posting_period",
    "Ref. Doc. Line Item": "ref_doc_line_item",
}

TRUE_SET = {"x", "true", "1", "yes", "selected"}
FALSE_SET = {"", "false", "0", "no", "not selected"}

def _to_bool(value) -> bool:
    if pd.isna(value):
        return False
    s = str(value).strip().lower()
    if s in TRUE_SET:
        return True
    if s in FALSE_SET:
        return False
    return False

def preprocess(csv_path: str | Path) -> pd.DataFrame:
    """Load CSV and apply minimal transformations for DB ingestion."""
    df = pd.read_csv(csv_path)

    if "Unnamed: 0" in df.columns:
        df = df.drop(columns=["Unnamed: 0"])

    df["Calculate Tax"] = df["Calculate Tax"].map(_to_bool)
    df["Cash Flow-Relevant Doc."] = df["Cash Flow-Relevant Doc."].map(_to_bool)
    df["Document Is Back-Posted"] = df["Document Is Back-Posted"].map(_to_bool)
    df["Cleared Item"] = df["Cleared Item"].map(_to_bool)

    for col in ["Clearing Date", "Clearing Entry Date"]:
        df[col] = pd.to_datetime(df[col], errors="coerce").dt.date

    numeric_cols = [
        "Clearing Fiscal Year",
        "Fiscal Year.1",
        "Fiscal Year.2",
        "Posting period.1",
        "Ref. Doc. Line Item",
    ]
    for col in numeric_cols:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    df["Transaction Value"] = pd.to_numeric(df["Transaction Value"], errors="coerce")
    df["Exchange rate"] = pd.to_numeric(df["Exchange rate"], errors="coerce")

    df = df.rename(columns=COLUMN_MAP)
    df = df[list(COLUMN_MAP.values())]

    # Enforce nullable ints cleanly
    int_cols = [
        "authorization_group",
        "clearing_fiscal_year",
        "original_fiscal_year",
        "fiscal_year",
        "posting_period",
        "ref_doc_line_item",
    ]
    for col in int_cols:
        df[col] = df[col].astype("Int64")

    # Optional quality features
    df["abs_transaction_value"] = df["transaction_value"].abs()
    df["is_credit"] = df["debit_credit_indicator"].eq("H")
    df["is_debit"] = df["debit_credit_indicator"].eq("S")
    df["fiscal_period_key"] = (df["fiscal_year"].astype("Int64") * 100 + df["posting_period"].astype("Int64"))

    return df
