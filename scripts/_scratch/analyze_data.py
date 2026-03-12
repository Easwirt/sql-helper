import pandas as pd

df = pd.read_csv("Data Dump - Accrual Accounts.csv")
print("Shape:", df.shape)
print("\nColumns:")
for c in df.columns:
    print(f"  {c}: dtype={df[c].dtype}, nulls={df[c].isnull().sum()}, unique={df[c].nunique()}")
print("\nSample values per column:")
for c in df.columns:
    print(f"  {c}: {df[c].dropna().unique()[:8]}")
print("\nDescribe numeric:")
print(df.describe())
print("\nValue counts for key categoricals:")
for c in ["Bus. Transac. Type", "Cleared Item", "Debit/Credit ind", "Currency", "Country Key", "Document Is Back-Posted", "Cash Flow-Relevant Doc."]:
    print(f"\n{c}:")
    print(df[c].value_counts())
print("\nFiscal Year.1 distribution:")
print(df["Fiscal Year.1"].value_counts().sort_index())
print("\nFiscal Year.2 distribution:")
print(df["Fiscal Year.2"].value_counts().sort_index())
print("\nPosting period.1 distribution:")
print(df["Posting period.1"].value_counts().sort_index())
