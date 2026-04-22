import os
import pandas as pd
import numpy as np
from prophet import Prophet
from main import load_aggregated_series, load_holidays

def evaluate(history, mode, cps, sps, holidays, freq):
    df = history.copy().reset_index(drop=True)
    if len(df) < 10: return 0.0
    
    test_ratio = 0.2
    split_idx = int(len(df) * (1.0 - test_ratio))
    train_df = df.iloc[:split_idx].copy()
    test_df = df.iloc[split_idx:].copy()

    model = Prophet(
        yearly_seasonality=False,
        weekly_seasonality=True,
        daily_seasonality=(freq in ["1_hour", "10_minutes"]),
        holidays=holidays,
        changepoint_prior_scale=cps,
        seasonality_prior_scale=sps,
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
    datasets = [
        ("Institutions", None),
        ("IP Samples", None),
        ("Subnets", r"C:\Users\gasen\Videos\ssss\institution_subnets")
    ]
    
    configs = [
        ("Baseline", "additive", 0.05, 10.0),
        ("Optimized", "multiplicative", 0.001, 20.0)
    ]
    
    results = []
    
    for d_name, d_path in datasets:
        os.environ["ADNE_DATASET"] = d_name.lower().replace(" ", "_")
        if d_path:
            os.environ["ADNE_DATASET_PATH"] = d_path
        else:
            os.environ.pop("ADNE_DATASET_PATH", None)

        for freq in ["1_day", "1_hour", "10_minutes"]:
            for col in ["n_flows", "n_bytes"]:
                print(f"Benchmarking: {d_name} | {freq} | {col}...")
                try:
                    history = load_aggregated_series(freq=freq, n_files=1000, target_col=col)
                    for c_name, mode, cps, sps in configs:
                        acc = evaluate(history, mode, cps, sps, holidays, freq)
                        results.append({
                            "Dataset": d_name,
                            "Freq": freq,
                            "Metric": col,
                            "Config": c_name,
                            "Accuracy": f"{acc:.2f}%"
                        })
                except Exception as e:
                    print(f"  Skipped {d_name}/{freq}/{col}: {e}")

    print("\n" + "="*80)
    print(f"{'DATASET':15} | {'FREQ':12} | {'METRIC':10} | {'CONFIG':10} | {'ACCURACY'}")
    print("-" * 80)
    for r in results:
        print(f"{r['Dataset']:15} | {r['Freq']:12} | {r['Metric']:10} | {r['Config']:10} | {r['Accuracy']}")
    print("="*80)

if __name__ == "__main__":
    main()
