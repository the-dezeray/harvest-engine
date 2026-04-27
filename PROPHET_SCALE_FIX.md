# Prophet Scale Mismatch Fix - CORRECTED

## Problem
Prophet predictions were showing ~118 million while live traffic showed ~13,600 - a massive mismatch.

## Root Cause
The system was comparing **different units**:
- **Prophet**: Trained on CESNET `n_bytes` data (trillions of bytes per day)
- **Live System**: Counting messages/flows (tens of thousands per day)
- **Result**: Predictions in bytes vs reality in message counts

## Solution Applied

### Changes Made:

1. **Changed ML Service Target** (`docker-compose.yml`)
   - Changed from `ADNE_TARGET_COL: n_bytes` to `ADNE_TARGET_COL: n_flows`
   - Now Prophet predicts flow counts instead of byte counts

2. **Corrected Scale Factor** (all services)
   - Changed `LIVE_TO_TARGET_SCALE` to `2`
   - CESNET n_flows: ~6M per day = ~69 flows/sec
   - Your emitter: ~40 messages/sec
   - Scale factor of 2x gives ~80 flows/sec (matches Prophet predictions)

3. **Fixed Chart Rendering** (`frontend/app/page.tsx`)
   - Added `minWidth` and `minHeight` to ResponsiveContainer
   - Fixes "width(-1) and height(-1)" errors

## How to Apply

```bash
# Restart all services to pick up new config
docker-compose down
docker-compose up -d

# ML service will retrain on n_flows instead of n_bytes
# This takes ~30 seconds on startup
```

## Verification

After restart, check the dashboard:
- Live traffic should be ~80 flows/sec
- Prophet predictions should be ~69 flows/sec
- They should match closely!

Example expected values:
- Live: 60-100 flows/sec (scaled 2x)
- Predicted: 50-90 flows/sec
- Upper bound: 100-120 flows/sec

## Understanding the Math

**CESNET Data (n_flows):**
- Per day: ~6,000,000 flows
- Per second: 6,000,000 ÷ 86,400 = ~69 flows/sec

**Your Emitter:**
- 40 APs × 1 message every 2 seconds = ~20 msg/sec
- With some variance: ~30-50 msg/sec

**Scale Factor:**
- To match Prophet: 69 ÷ 40 = 1.7x
- We use 2x for simplicity and slight headroom
- Result: 40 × 2 = 80 flows/sec (close to Prophet's 69)

## Why This Works

1. **Same Units**: Both measure flow/message counts
2. **Same Scale**: Both represent similar traffic volumes
3. **Realistic**: Predictions and live data are comparable
4. **Anomaly Detection**: Can now detect when live exceeds predicted bounds

## Troubleshooting

If predictions still don't match:

1. **Check ML service logs:**
   ```bash
   docker-compose logs ml-service | grep "rows"
   ```
   Should show it's using n_flows

2. **Check worker logs (Windows PowerShell):**
   ```powershell
   docker-compose logs worker --tail 50 | Select-String "orchestrator"
   ```
   Should show live_scaled and predicted values in similar ranges

3. **Verify data loading:**
   ```bash
   docker-compose exec ml-service python -c "
   import os
   print('Target:', os.getenv('ADNE_TARGET_COL'))
   print('Scale:', os.getenv('LIVE_TO_TARGET_SCALE'))
   "
   ```

4. **Fine-tune the scale:**
   - If predictions are 2x too high: change scale to `1`
   - If predictions are 2x too low: change scale to `4`
   - The goal is to match the Prophet prediction range

## Chart Rendering Fix

The "width(-1) and height(-1)" errors were caused by Recharts trying to render before the container had dimensions. Fixed by adding:
- `minWidth={300}` and `minHeight={240}` to main chart
- `minWidth={200}` and `minHeight={140}` to RabbitMQ chart

This ensures charts always have valid dimensions.
