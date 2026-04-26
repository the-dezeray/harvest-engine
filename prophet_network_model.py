"""
Prophet Network Traffic Prediction Model for COMP 322 Project
Author: [Your Name]
Purpose: AI-driven load prediction for auto-scaling distributed systems
"""

import pandas as pd
import numpy as np
from prophet import Prophet
from sklearn.metrics import mean_absolute_error, mean_squared_error

def smape(actual, predicted):
    """Symmetric Mean Absolute Percentage Error"""
    return 100 * np.mean(2 * np.abs(actual - predicted) / (np.abs(actual) + np.abs(predicted) + 1))

# ============================================
# MODEL SPECIFICATIONS
# ============================================
# Model: Facebook Prophet
# Prediction horizon: 60 seconds
# Seasonality mode: Multiplicative
# Changepoint prior: 0.1
# Threshold: 90th percentile of historical data

# ============================================
# LOAD AND PREPARE DATA
# ============================================
df = pd.read_csv('nf-ton-iot_Subset_Dataset.csv')
df['ds'] = pd.date_range(start='2024-01-01 00:00:00', periods=len(df), freq='s')

# Remove outliers (cap at 99th percentile)
cap = df['IN_BYTES'].quantile(0.99)
df['y'] = df['IN_BYTES'].clip(upper=cap)

# Log transform to handle spikes
df['y'] = np.log1p(df['y'])

df_prophet = df[['ds', 'y']]

# ============================================
# TRAIN/TEST SPLIT (80/20)
# ============================================
train_size = int(len(df_prophet) * 0.8)
train_df = df_prophet[:train_size]
test_df = df_prophet[train_size:]

print(f"Training data: {len(train_df)} rows")
print(f"Testing data: {len(test_df)} rows")

# ============================================
# TRAIN MODEL
# ============================================
model = Prophet(changepoint_prior_scale=0.1, seasonality_mode='multiplicative')
model.fit(train_df)

# ============================================
# TEST ACCURACY
# ============================================
future = model.make_future_dataframe(periods=len(test_df), freq='s')
forecast = model.predict(future)

predictions_log = forecast[-len(test_df):]['yhat'].values
actuals_log = test_df['y'].values

predictions = np.expm1(predictions_log)
actuals = np.expm1(actuals_log)

mae = mean_absolute_error(actuals, predictions)
rmse = np.sqrt(mean_squared_error(actuals, predictions))
smape_score = smape(actuals, predictions)

print("\n" + "="*50)
print("MODEL ACCURACY REPORT")
print("="*50)
print(f"MAE:  {mae:.2f} bytes")
print(f"RMSE: {rmse:.2f} bytes")
print(f"SMAPE: {smape_score:.2f}%")

# ============================================
# AUTO-SCALING DECISION
# ============================================
future_60 = model.make_future_dataframe(periods=60, freq='s')
forecast_60 = model.predict(future_60)

last_prediction_log = forecast_60['yhat'].iloc[-1]
last_prediction = np.expm1(last_prediction_log)

threshold = df['IN_BYTES'].quantile(0.90)

print("\n" + "="*50)
print("AUTO-SCALING DECISION")
print("="*50)
print(f"Predicted load in 60 seconds: {last_prediction:.2f} bytes")
print(f"Threshold: {threshold:.2f} bytes")

if last_prediction > threshold:
    print("DECISION: ADD MORE WORKERS")
else:
    print("DECISION: No scaling needed")
