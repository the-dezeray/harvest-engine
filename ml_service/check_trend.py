
import os
import pandas as pd
import matplotlib.pyplot as plt
from main import load_aggregated_series

def main():
    os.environ["ADNE_DATASET"] = "institutions"
    history = load_aggregated_series(freq="1_hour", n_files=1000, target_col="n_bytes")
    
    # Just print some stats and trends
    history['ds'] = pd.to_datetime(history['ds'])
    history = history.sort_values('ds')
    
    # Split as in evaluate
    test_ratio = 0.2
    split_idx = int(len(history) * (1.0 - test_ratio))
    train = history.iloc[:split_idx]
    test = history.iloc[split_idx:]
    
    print(f"Train mean: {train['y'].mean():.2e}")
    print(f"Test mean:  {test['y'].mean():.2e}")
    print(f"Ratio:      {test['y'].mean() / train['y'].mean():.2f}")
    
    # Rolling mean to see trend
    history['rolling'] = history['y'].rolling(window=24*7).mean()
    print("\nWeekly rolling mean (start, middle, end):")
    print(f"Start:  {history['rolling'].iloc[24*7+1]:.2e}")
    print(f"Middle: {history['rolling'].iloc[len(history)//2]:.2e}")
    print(f"End:    {history['rolling'].iloc[-1]:.2e}")

if __name__ == "__main__":
    main()
