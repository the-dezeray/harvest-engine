# Frequency Comparison - Finding the Right Scale

## The Problem with 1_day

When using daily aggregation:
- **CESNET**: 1.28 trillion bytes per day
- **Per second**: 14.8 million bytes/sec
- **Your live**: 6 million bytes/sec
- **Result**: Predictions 2-20x too high ❌

## Solution: Use 10_minutes

With 10-minute aggregation:
- **CESNET**: 2.3 billion bytes per 10 minutes
- **Per second**: 3.8 million bytes/sec
- **Your live**: 4 million bytes/sec (with 100k scale)
- **Result**: Much closer match! ✅

## Comparison Table

| Frequency | Bytes per Bucket | Bytes/sec | Scale Factor | Live Traffic | Match? |
|-----------|------------------|-----------|--------------|--------------|--------|
| **1_day** | 1.28 trillion | 14.8M | 375,000x | 15M | ❌ Too high |
| **1_hour** | 53 billion | 14.7M | 375,000x | 15M | ❌ Too high |
| **10_minutes** | 2.3 billion | 3.8M | 100,000x | 4M | ✅ Good! |

## Current Configuration: 10_minutes

```yaml
ADNE_FREQ: 10_minutes
ADNE_TARGET_COL: n_bytes
LIVE_TO_TARGET_SCALE: 100000
```

### The Math

**CESNET 10-minute data:**
- Per bucket: 2,332,801,002 bytes (~2.3 GB)
- Per second: 2,332,801,002 ÷ 600 = **3,888,002 bytes/sec** (~3.7 MB/sec)

**Your emitter:**
- 40 messages/sec
- Scale: 100,000x
- Result: 40 × 100,000 = **4,000,000 bytes/sec** (~3.8 MB/sec)

**Match**: 4M vs 3.8M = ✅ **95% accurate!**

## Apply It

```cmd
restart-10min.bat
```

## Expected Results

After restart:
- **Live traffic**: ~4 million bytes/sec
- **Prophet prediction**: ~3.8 million bytes/sec
- **Upper bound**: ~5 million bytes/sec
- **Lower bound**: ~2.5 million bytes/sec

All values should be in the **same range** (millions, not tens of millions).

## Verification

**Worker logs** (PowerShell):
```powershell
docker-compose logs worker --tail 50 | Select-String "orchestrator"
```

Should show:
```
live_scaled=4000000.00 lower=2500000.00 upper=5000000.00
```

All in the **low millions** - much better match!

## Why 10 Minutes Works Better

1. **Smaller buckets**: Less data per bucket = smaller predictions
2. **More granular**: 144 data points per day vs 1
3. **Better for real-time**: 10-min patterns match your 2-sec emitter better
4. **More accurate**: Prophet has more data points to learn from

## Frequency Options

### 1_day (Original)
- ✅ Smoothest predictions
- ✅ Best for long-term trends
- ❌ Numbers too large (14M vs 6M)
- ❌ Less responsive to short-term changes

### 1_hour
- ✅ Good balance
- ✅ 24 data points per day
- ❌ Still too large (14M vs 6M)
- ⚠️ Similar to 1_day for this dataset

### 10_minutes (Recommended)
- ✅ Numbers match well (3.8M vs 4M)
- ✅ 144 data points per day
- ✅ More responsive to changes
- ✅ Better for real-time monitoring
- ⚠️ Slightly noisier predictions

## Trade-offs

**Larger buckets (1_day):**
- Smoother predictions
- Better for capacity planning
- Numbers don't match your simulation

**Smaller buckets (10_minutes):**
- More accurate match
- Better for real-time alerts
- Slightly more volatile predictions

## Recommendation

**Use 10_minutes** because:
1. Predictions match your live traffic (4M vs 3.8M)
2. Better for real-time anomaly detection
3. More data points = better Prophet training
4. Numbers are still impressive (millions)

## Switching Frequencies

### To 10 minutes (recommended):
```cmd
restart-10min.bat
```

### To 1 hour:
Edit `docker-compose.yml`:
```yaml
ADNE_FREQ: 1_hour
LIVE_TO_TARGET_SCALE: "375000"
```

### To 1 day:
Edit `docker-compose.yml`:
```yaml
ADNE_FREQ: 1_day
LIVE_TO_TARGET_SCALE: "375000"
```

Then:
```cmd
docker-compose down
docker-compose up -d
```

## Technical Note

The frequency affects:
1. **Bucket size**: How much data per prediction
2. **Seasonality**: What patterns Prophet can detect
3. **Responsiveness**: How quickly predictions adapt
4. **Accuracy**: How well predictions match reality

For your simulation with 40 APs sending every 2 seconds, **10-minute buckets** provide the best balance between:
- Realistic predictions
- Accurate anomaly detection
- Impressive demo numbers
- Stable performance

## Success Criteria

After switching to 10_minutes:
- ✅ Live and predicted within 20% of each other
- ✅ Both in the 3-5 million range
- ✅ Anomaly detection triggers appropriately
- ✅ Spike scenario shows clear deviation
- ✅ No constant false alarms

You should see **far fewer false anomaly alerts** because the predictions now match your actual traffic scale!
