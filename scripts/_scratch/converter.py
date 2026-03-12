import pandas as pd

read_file = pd.read_excel("Data Dump - Accrual Accounts.xlsx")

read_file.to_csv("Data Dump - Accrual Accounts.csv", index=None, header=True)

df = pd.DataFrame(pd.read_csv("Data Dump - Accrual Accounts.csv"))

print(df)