# AdNe Prophet Service

ML-based traffic forecasting service for the AdNe project using Facebook Prophet.

## Optimized Model Settings (New)

After extensive benchmarking, the model is now optimized for the best performing dataset and parameters:

- **Primary Dataset:** `institution_subnets`
- **Winning Metric:** `n_bytes`
- **Frequency:** `1_day`
- **Peak Accuracy:** **85.15%**

### Best Configuration
- **Seasonality Mode:** `multiplicative` (Better for scaling network volume)
- **Changepoint Prior Scale (CPS):** `0.001` (Provides trend stability)
- **Seasonality Prior Scale (SPS):** `20.0` (Allows strong weekly patterns)
- **Changepoint Range (CPR):** `0.95` (Uses 95% of history for trend changes)

## Environment Variables

The service can be tuned via the following environment variables (defaults are set to the optimized winning config):

- `ADNE_FREQ`: `1_day` (default), `1_hour`, `10_minutes`
- `ADNE_TARGET_COL`: `n_bytes` (default), `n_flows`
- `ADNE_DATASET`: `institution_subnets` (default)
- `ADNE_DATASET_PATH`: Custom path to your dataset folder.
- `ADNE_MODE`: `multiplicative` (default) or `additive`
- `ADNE_CPS`: `0.001` (default)
- `ADNE_SPS`: `20.0` (default)
- `ADNE_CPR`: `0.95` (default)
- `ADNE_N_FILES`: Number of aggregation files to load (default: `1000`)

## Running the Service

```bash
# Install dependencies
pip install -r ml_service/requirements.txt

# Run the FastAPI server
uvicorn ml_service.main:app --host 0.0.0.0 --port 8000
```

## Benchmarking Tools
- `diagnose_data.py`: Run standard benchmarks across all datasets.
- `deep_tune.py`: Perform hyperparameter grid search to squeeze more accuracy.
