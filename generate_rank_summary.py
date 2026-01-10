import pandas as pd

# Data from our previous analysis run (Hardcoded for immediate generation)
data = [
    {"Bucket": "Top 1", "Cumulative_Pct": 3.48},
    {"Bucket": "Top 3", "Cumulative_Pct": 12.38},
    {"Bucket": "Top 5", "Cumulative_Pct": 25.52},
    {"Bucket": "Top 10", "Cumulative_Pct": 39.76},
    {"Bucket": "Top 30", "Cumulative_Pct": 40.93}
]

df = pd.DataFrame(data)

# Calculate Marginal (How much did this bucket ADD?)
df['Marginal_Pct'] = df['Cumulative_Pct'] - df['Cumulative_Pct'].shift(1).fillna(0)

print(df)
df.to_csv("rank_distribution_summary.csv", index=False)

