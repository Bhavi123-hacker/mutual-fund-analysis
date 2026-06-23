import pandas as pd

file = "data/raw/01_fund_master.xlsx"

df = pd.read_excel(file)

print("Shape:", df.shape)
print("\nColumns:")
print(df.columns.tolist())

print("\nFirst 5 rows:")
print(df.head())