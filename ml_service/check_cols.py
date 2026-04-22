
import os
from main import load_aggregated_series, train_prophet
import numpy as np
import pandas as pd
from prophet import Prophet

def evaluate(history):
    df = history.copy().reset_index(drop=True)
    test_ratio = 0.2
    split_idx = int(len(df) * (1.0 - test_ratio))
    train_df = df.iloc[:split_idx].copy()
    test_df = df.iloc[split_idx:].copy()
    
    model = Prophet(
        yearly_seasonality=False,
        weekly_seasonality=True,
        daily_seasonality=True,
        changepoint_prior_scale=0.001, # back to stable
        seasonality_mode='multiplicative'
    )
    model.fit(train_df)
    preds = model.predict(test_df[['ds']])
    predicted = preds['yhat'].to_numpy()
    actual = test_df['y'].to_numpy()
    errors = actual - predicted
    mape = np.mean(np.abs(errors) / ((np.abs(actual) + np.abs(predicted)) / 2.0)) * 100.0
    return 100.0 - mape

def main():
    os.environ["ADNE_DATASET"] = "institutions"
    for col in ["n_flows", "n_packets", "n_bytes"]:
        history = load_aggregated_series(freq="1_hour", n_files=1000, target_col=col)
        acc = evaluate(history)
        print(f"Col: {col:12} | Accuracy: {acc:.2f}%")

if __name__ == "__main__":
    main()
