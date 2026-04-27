# Quick Start - n_bytes Configuration

## What You're Getting

Switching to `n_bytes` gives you **bigger, more impressive numbers**:

| Metric | Value |
|--------|-------|
| Live traffic | ~15 million bytes/sec |
| Prophet prediction | ~14-16 million bytes/sec |
| Scale factor | 375,000x |

Compare to `n_flows`:
- Live: ~80 flows/sec
- Much smaller numbers

## Apply It Now

**Run this:**
```cmd
restart-with-bytes.bat
```

**Or manually:**
```cmd
docker-compose down
docker-compose up -d
```

## What Changed

```yaml
ADNE_TARGET_COL: n_bytes      # Was: n_flows
LIVE_TO_TARGET_SCALE: 375000  # Was: 2
```

## Why 375,000x?

**CESNET data:**
- 1.28 trillion bytes per day
- = 14.8 million bytes per second

**Your emitter:**
- 40 messages per second

**Scale needed:**
- 14,800,000 ÷ 40 = 375,000x

## Verify It Works

1. **Dashboard**: http://localhost:3000
   - Should show ~15 million bytes/sec

2. **Worker logs** (PowerShell):
   ```powershell
   docker-compose logs worker --tail 50 | Select-String "orchestrator"
   ```
   
   Should show:
   ```
   live_scaled=15000000.00 lower=10000000.00 upper=20000000.00
   ```

3. **ML Service**:
   ```cmd
   curl http://localhost:8001/health
   ```
   Should show: `"target_col": "n_bytes"`

## Test Scenarios

### Spike Mode
```cmd
curl -X POST http://localhost:8000/scenario?mode=spike
```
- Live jumps to 40-50 million bytes/sec
- Alert triggers!

### Normal Mode
```cmd
curl -X POST http://localhost:8000/scenario?mode=normal
```
- Returns to 15 million bytes/sec

## Why Use n_bytes?

✅ **More impressive**: 15 million vs 80
✅ **Real-world metric**: Bytes = bandwidth
✅ **Better for demos**: Bigger numbers = more impact
✅ **Matches monitoring tools**: Most show bytes/bandwidth

## Switch Back to n_flows?

If you want smaller, simpler numbers:
```cmd
restart-fixed.bat
```

## Files Reference

- `BYTES_VS_FLOWS.md` - Detailed comparison
- `restart-with-bytes.bat` - Apply n_bytes config
- `restart-fixed.bat` - Apply n_flows config

---

**Bottom line**: n_bytes gives you millions, n_flows gives you tens. Both work perfectly - pick based on your audience!
