import pandas as pd
df = pd.read_csv("data/processed/incidents_clean.csv", sep=';')
print(df.head())
print(df.info())