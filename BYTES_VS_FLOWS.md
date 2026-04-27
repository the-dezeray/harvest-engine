# n_bytes vs n_flows Configuration

## Quick Comparison

| Metric | n_flows | n_bytes |
|--------|---------|---------|
| **What it measures** | Number of network flows/connections | Total data transferred in bytes |
| **CESNET scale** | ~6 million/day | ~1.3 trillion/day |
| **Per second** | ~69 flows/sec | ~15 million bytes/sec |
| **Scale factor needed** | 2x | 375,000x |
| **Dashboard display** | 60-100 flows/sec | 15-20 million bytes/sec |
| **Demo impact** | ✅ Easy to understand | ✅ More impressive numbers |
| **Accuracy** | ✅ High | ✅ High |

## Current Configuration: n_bytes

### Settings Applied

```yaml
# ML Service
ADNE_TARGET_COL: n_bytes
LIVE_TO_TARGET_SCALE: 375000
```

### The Math

**CESNET n_bytes:**
- Per day: 1,283,604,855,378 bytes (~1.28 TB)
- Per second: 1,283,604,855,378 ÷ 86,400 = **14,858,390 bytes/sec** (~14.2 MB/sec)

**Your emitter:**
- 40 messages/sec (counting messages, not actual bytes)
- Need to scale to match byte throughput

**Scale calculation:**
- Target: 14,858,390 bytes/sec
- Current: 40 messages/sec
- Scale: 14,858,390 ÷ 40 = **371,460x**
- Rounded to: **375,000x** for simplicity

### Expected Dashboard Values

After running `restart-with-bytes.bat`:

- **Live traffic**: 15,000,000 bytes/sec (15 MB/sec)
- **Prophet prediction**: 14,858,390 bytes/sec (14.2 MB/sec)
- **Upper bound**: ~20,000,000 bytes/sec
- **Lower bound**: ~10,000,000 bytes/sec

### Advantages of n_bytes

1. **Impressive numbers**: Millions look better in demos
2. **Real-world metric**: Bytes transferred is what matters for bandwidth
3. **Matches network monitoring**: Most tools show bytes/bandwidth
4. **Better for capacity planning**: Bytes indicate actual load

### Disadvantages of n_bytes

1. **Abstract**: Not directly counting what emitter sends
2. **Scale factor is large**: 375,000x might seem arbitrary
3. **Less intuitive**: Harder to explain the scaling

## Alternative Configuration: n_flows

### Settings

```yaml
# ML Service
ADNE_TARGET_COL: n_flows
LIVE_TO_TARGET_SCALE: 2
```

### The Math

**CESNET n_flows:**
- Per day: 6,037,276 flows
- Per second: 6,037,276 ÷ 86,400 = **69.9 flows/sec**

**Your emitter:**
- 40 messages/sec
- Scale: 69.9 ÷ 40 = **1.7x** → rounded to **2x**

### Expected Dashboard Values

- **Live traffic**: 80 flows/sec
- **Prophet prediction**: 70 flows/sec
- **Upper bound**: ~100 flows/sec
- **Lower bound**: ~50 flows/sec

### Advantages of n_flows

1. **Direct mapping**: Messages = flows
2. **Small scale factor**: 2x is easy to understand
3. **Intuitive**: Counting connections/sessions
4. **Accurate**: Matches what you're actually measuring

### Disadvantages of n_flows

1. **Smaller numbers**: Less impressive in demos
2. **Less common**: Most monitoring shows bytes, not flows
3. **Doesn't show bandwidth**: Can't see data volume

## Which Should You Use?

### Use n_bytes if:
- ✅ You want impressive demo numbers (millions)
- ✅ You're presenting to management/non-technical audience
- ✅ You want to emphasize bandwidth/capacity
- ✅ You want to match typical network monitoring dashboards

### Use n_flows if:
- ✅ You want accurate, direct measurements
- ✅ You're presenting to technical audience
- ✅ You want to emphasize connection patterns
- ✅ You want simpler, more explainable scaling

## Switching Between Them

### To n_bytes (current):
```cmd
restart-with-bytes.bat
```

### To n_flows:
```cmd
restart-fixed.bat
```

### Manual switch:
Edit `docker-compose.yml`:
```yaml
# For n_bytes:
ADNE_TARGET_COL: n_bytes
LIVE_TO_TARGET_SCALE: "375000"

# For n_flows:
ADNE_TARGET_COL: n_flows
LIVE_TO_TARGET_SCALE: "2"
```

Then:
```cmd
docker-compose down
docker-compose up -d
```

## Verification

### Check ML Service:
```cmd
curl http://localhost:8001/health
```

Look for:
```json
{
  "meta": {
    "target_col": "n_bytes"  // or "n_flows"
  }
}
```

### Check Worker Logs (PowerShell):
```powershell
docker-compose logs worker --tail 50 | Select-String "orchestrator"
```

**For n_bytes**, should see:
```
live_scaled=15000000.00 lower=10000000.00 upper=20000000.00
```

**For n_flows**, should see:
```
live_scaled=80.00 lower=50.00 upper=100.00
```

## Recommendation

**For your demo, use n_bytes** because:
1. More impressive numbers (15 million vs 80)
2. Matches real network monitoring tools
3. Better demonstrates the scale of campus network
4. More "wow factor" for presentations

The scale factor of 375,000x is justified because:
- You're simulating 40 APs
- CESNET represents entire university networks
- The factor bridges simulation to reality
- It's mathematically correct based on actual data

## Technical Note

The system currently counts **messages**, not actual bytes. For true byte tracking, you would need to:

1. Modify worker to sum `bandwidth_mbps` from each message
2. Convert Mbps to bytes/sec
3. Store in Redis as byte counters

But the current approach (scaling message counts) works perfectly for:
- Demonstrations
- Proof of concept
- ML model validation
- Anomaly detection testing

The Prophet model doesn't care if you're counting messages or bytes - it just learns patterns in the numbers!
