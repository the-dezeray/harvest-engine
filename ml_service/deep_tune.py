import os
import pandas as pd
import numpy as np
from prophet import Prophet
from main import load_aggregated_series, load_holidays

def evaluate_refined(history, mode, cps, sps, cpr, holidays):
    df = history.copy().reset_index(drop=True)
    test_ratio = 0.2
    split_idx = int(len(df) * (1.0 - test_ratio))
    train_df = df.iloc[:split_idx].copy()
    test_df = df.iloc[split_idx:].copy()

    model = Prophet(
        yearly_seasonality=False,
        weekly_seasonality=True,
        daily_seasonality=False,
        holidays=holidays,
        changepoint_prior_scale=cps,
        seasonality_prior_scale=sps,
        changepoint_range=cpr,
        seasonality_mode=mode,
    )
    model.fit(train_df)
    
    preds = model.predict(test_df[['ds']])
    predicted = preds['yhat'].to_numpy()
    actual = test_df['y'].to_numpy()
    
    errors = actual - predicted
    mape = np.mean(np.abs(errors) / (((np.abs(actual) + np.abs(predicted)) / 2.0) + 1e-9)) * 100.0
    return 100.0 - mape

def main():
    holidays = load_holidays()
    dataset = "institution_subnets"
    freq = "1_day"
    target_col = "n_bytes"
    
    os.environ["ADNE_DATASET"] = dataset
    os.environ.pop("ADNE_DATASET_PATH", None) # Use default local path
    
    print(f"\n--- Deep Tuning Winning Config: {dataset} | {target_col} | {freq} ---")
    history = load_aggregated_series(freq=freq, n_files=1000, target_col=target_col)
    
    best_acc = 0
    best_params = {}
    
    # Testing both modes since multiplicative was the 79.5% winner previously
    for mode in ['multiplicative', 'additive']:
        for cps in [0.001, 0.005]:
            for sps in [5.0, 10.0, 15.0, 20.0]:
                for cpr in [0.85, 0.90, 0.95]:
                    acc = evaluate_refined(history, mode, cps, sps, cpr, holidays)
                    print(f"Mode: {mode:14} | CPS: {cps:5} | SPS: {sps:4} | CPR: {cpr:4} | Acc: {acc:.2f}%")
                    if acc > best_acc:
                        best_acc = acc
                        best_params = {'mode': mode, 'cps': cps, 'sps': sps, 'cpr': cpr}
    
    print(f"\nFinal Best Accuracy: {best_acc:.2f}%")
    print(f"Final Best Parameters: {best_params}")

if __name__ == "__main__":
    main()
