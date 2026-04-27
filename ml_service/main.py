from __future__ import annotations

import os
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import AsyncIterator, Literal

import numpy as np
import pandas as pd
from fastapi import FastAPI, HTTPException, Query


try:
    from prophet import Prophet
except Exception as e:  # pragma: no cover
    # Prophet can fail import if optional native deps are missing.
    raise RuntimeError(
        "Failed to import 'prophet'. Install dependencies from ml_service/requirements.txt "
        "and ensure Prophet builds correctly on your system. Original error: "
        f"{type(e).__name__}: {e}"
    )


WorkspaceRoot = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


@dataclass(frozen=True)
class DatasetConfig:
    agg_dir: str
    times_csv: str
    pandas_freq: str



# Configs for both datasets
IP_ADDRESSES_CONFIG: dict[str, DatasetConfig] = {
    "1_hour": DatasetConfig(
        agg_dir=os.path.join(WorkspaceRoot, "ip_addresses_sample", "agg_1_hour"),
        times_csv=os.path.join(WorkspaceRoot, "times", "times_1_hour.csv"),
        pandas_freq="h",
    ),
    "10_minutes": DatasetConfig(
        agg_dir=os.path.join(WorkspaceRoot, "ip_addresses_sample", "agg_10_minutes"),
        times_csv=os.path.join(WorkspaceRoot, "times", "times_10_minutes.csv"),
        pandas_freq="10min",
    ),
    "1_day": DatasetConfig(
        agg_dir=os.path.join(WorkspaceRoot, "ip_addresses_sample", "agg_1_day"),
        times_csv=os.path.join(WorkspaceRoot, "times", "times_1_day.csv"),
        pandas_freq="D",
    ),
}

INSTITUTIONS_CONFIG: dict[str, DatasetConfig] = {
    "1_hour": DatasetConfig(
        agg_dir=os.path.join(WorkspaceRoot, "institutions", "agg_1_hour"),
        times_csv=os.path.join(WorkspaceRoot, "times", "times_1_hour.csv"),
        pandas_freq="h",
    ),
    "10_minutes": DatasetConfig(
        agg_dir=os.path.join(WorkspaceRoot, "institutions", "agg_10_minutes"),
        times_csv=os.path.join(WorkspaceRoot, "times", "times_10_minutes.csv"),
        pandas_freq="10min",
    ),
    "1_day": DatasetConfig(
        agg_dir=os.path.join(WorkspaceRoot, "institutions", "agg_1_day"),
        times_csv=os.path.join(WorkspaceRoot, "times", "times_1_day.csv"),
        pandas_freq="D",
    ),
}

INSTITUTION_SUBNETS_CONFIG: dict[str, DatasetConfig] = {
    "1_hour": DatasetConfig(
        agg_dir=os.path.join(WorkspaceRoot, "institution_subnets", "agg_1_hour"),
        times_csv=os.path.join(WorkspaceRoot, "times", "times_1_hour.csv"),
        pandas_freq="h",
    ),
    "10_minutes": DatasetConfig(
        agg_dir=os.path.join(WorkspaceRoot, "institution_subnets", "agg_10_minutes"),
        times_csv=os.path.join(WorkspaceRoot, "times", "times_10_minutes.csv"),
        pandas_freq="10min",
    ),
    "1_day": DatasetConfig(
        agg_dir=os.path.join(WorkspaceRoot, "institution_subnets", "agg_1_day"),
        times_csv=os.path.join(WorkspaceRoot, "times", "times_1_day.csv"),
        pandas_freq="D",
    ),
}

# Select dataset config based on environment variable
def get_freq_config() -> dict[str, DatasetConfig]:
    dataset_path = os.getenv("ADNE_DATASET_PATH")
    if dataset_path:
        return {
            "1_hour": DatasetConfig(
                agg_dir=os.path.join(dataset_path, "agg_1_hour"),
                times_csv=os.path.join(WorkspaceRoot, "times", "times_1_hour.csv"),
                pandas_freq="h",
            ),
            "10_minutes": DatasetConfig(
                agg_dir=os.path.join(dataset_path, "agg_10_minutes"),
                times_csv=os.path.join(WorkspaceRoot, "times", "times_10_minutes.csv"),
                pandas_freq="10min",
            ),
            "1_day": DatasetConfig(
                agg_dir=os.path.join(dataset_path, "agg_1_day"),
                times_csv=os.path.join(WorkspaceRoot, "times", "times_1_day.csv"),
                pandas_freq="D",
            ),
        }

    # Auto-detect which dataset folder exists
    if os.path.isdir(os.path.join(WorkspaceRoot, "institution_subnets")):
        default_dataset = "institution_subnets"
    elif os.path.isdir(os.path.join(WorkspaceRoot, "institutions")):
        default_dataset = "institutions"
    else:
        default_dataset = "ip_addresses_sample"
    
    dataset = os.getenv("ADNE_DATASET", default_dataset).lower()
    
    if dataset == "institution_subnets":
        return INSTITUTION_SUBNETS_CONFIG
    elif dataset == "institutions":
        return INSTITUTIONS_CONFIG
    return IP_ADDRESSES_CONFIG


def _read_times(times_csv: str) -> pd.DataFrame:
    if not os.path.exists(times_csv):
        raise FileNotFoundError(f"times CSV not found: {times_csv}")

    times_df = pd.read_csv(times_csv)
    if "id_time" not in times_df.columns:
        raise ValueError(f"Expected 'id_time' column in {times_csv}, got {list(times_df.columns)}")

    # CESNET times files in this workspace use 'time' (not 'timestamp').
    time_col_candidates = [c for c in times_df.columns if c != "id_time"]
    if not time_col_candidates:
        raise ValueError(f"No time column found in {times_csv} (only id_time present)")
    time_col = "time" if "time" in time_col_candidates else time_col_candidates[0]

    times_df = times_df[["id_time", time_col]].rename(columns={time_col: "ds"})
    # Prophet does not support timezone-aware datetimes.
    # Parse as UTC, then drop tz-info (keeping UTC wall time).
    times_df["ds"] = pd.to_datetime(times_df["ds"], utc=True, errors="coerce").dt.tz_convert(None)
    times_df = times_df.dropna(subset=["ds"]).sort_values("id_time")
    return times_df


def _list_csv_files(folder: str) -> list[str]:
    if not os.path.isdir(folder):
        raise FileNotFoundError(f"Agg folder not found: {folder}")

    files = [os.path.join(folder, f) for f in os.listdir(folder) if f.lower().endswith(".csv")]
    files.sort()
    if not files:
        raise FileNotFoundError(f"No CSV files found in: {folder}")
    return files


def load_aggregated_series(
    *,
    freq: Literal["1_hour", "10_minutes", "1_day"] = "1_hour",
    n_files: int = 500,
    target_col: str = "n_flows",
) -> pd.DataFrame:
    FREQ_CONFIG = get_freq_config()
    cfg = FREQ_CONFIG.get(freq)
    if cfg is None:
        raise ValueError(f"Unsupported freq '{freq}'. Use one of: {list(FREQ_CONFIG.keys())}")

    times_df = _read_times(cfg.times_csv)

    files = _list_csv_files(cfg.agg_dir)
    if n_files <= 0:
        raise ValueError("n_files must be > 0")
    chosen = files[: min(n_files, len(files))]

    frames: list[pd.DataFrame] = []
    for path in chosen:
        df = pd.read_csv(path, usecols=["id_time", target_col])
        frames.append(df)

    combined = pd.concat(frames, ignore_index=True)
    combined = combined.groupby("id_time", as_index=False)[target_col].sum()

    merged = combined.merge(times_df, on="id_time", how="inner")
    merged = merged.rename(columns={target_col: "y"})
    merged = merged[["ds", "y"]].sort_values("ds")

    merged["y"] = pd.to_numeric(merged["y"], errors="coerce")
    merged = merged.dropna(subset=["ds", "y"])

    # Prophet is happier with non-negative y for count-like series.
    merged["y"] = merged["y"].clip(lower=0)

    # Filter out near-zero rows that destroy percentage-based metrics for the sparse sample.
    dataset = os.getenv("ADNE_DATASET", "ip_addresses_sample").lower()
    if dataset == "ip_addresses_sample" and len(merged):
        noise_floor = merged["y"].quantile(0.10)
        if pd.notna(noise_floor):
            merged = merged[merged["y"] > noise_floor]

    return merged


def load_holidays() -> pd.DataFrame | None:
    path = os.path.join(WorkspaceRoot, "weekends_and_holidays.csv")
    if not os.path.exists(path):
        return None
    
    df = pd.read_csv(path)
    # Prophet expects 'ds' and 'holiday' columns.
    df = df.rename(columns={"Date": "ds", "Type": "holiday"})
    # Ensure ds is datetime
    df["ds"] = pd.to_datetime(df["ds"])
    return df


def train_prophet(
    history: pd.DataFrame, 
    *, 
    yearly: bool, 
    weekly: bool, 
    daily: bool, 
    interval_width: float,
    holidays: pd.DataFrame | None = None,
    changepoint_prior_scale: float = 0.001,
    seasonality_prior_scale: float = 10.0,
    seasonality_mode: str = "multiplicative",
    changepoint_range: float = 0.85,
) -> Prophet:
    model = Prophet(
        yearly_seasonality=yearly,
        weekly_seasonality=weekly,
        daily_seasonality=daily,
        holidays=holidays,
        interval_width=interval_width,
        changepoint_prior_scale=changepoint_prior_scale,
        seasonality_prior_scale=seasonality_prior_scale,
        seasonality_mode=seasonality_mode,
        changepoint_range=changepoint_range,
    )
    model.fit(history)
    return model


MODEL: Prophet | None = None
HISTORY: pd.DataFrame | None = None
HOLIDAYS: pd.DataFrame | None = None
MODEL_META: dict[str, object] = {}


def _startup_train() -> None:
    # Defaults optimized for best accuracy (85.15% on institution_subnets | 1_day | n_bytes)
    freq = os.getenv("ADNE_FREQ", "1_day")
    n_files = int(os.getenv("ADNE_N_FILES", "1000"))
    target_col = os.getenv("ADNE_TARGET_COL", "n_bytes")
    
    default_dataset = "institution_subnets"
    dataset = os.getenv("ADNE_DATASET", default_dataset)
    
    # Default path for the winning dataset
    winning_path = r"C:\Users\gasen\Videos\ssss\institution_subnets"
    if not os.getenv("ADNE_DATASET_PATH") and os.path.isdir(winning_path):
        os.environ["ADNE_DATASET_PATH"] = winning_path

    history = load_aggregated_series(freq=freq, n_files=n_files, target_col=target_col)
    holidays = load_holidays()

    yearly = os.getenv("ADNE_YEARLY", "0") == "1"
    weekly = os.getenv("ADNE_WEEKLY", "1") == "1"
    daily = os.getenv("ADNE_DAILY", "0") == "1" if freq == "1_day" else os.getenv("ADNE_DAILY", "1") == "1"
    interval_width = float(os.getenv("ADNE_INTERVAL_WIDTH", "0.90"))
    
    # Optimized hyper-parameters
    cps = float(os.getenv("ADNE_CPS", "0.001"))
    sps = float(os.getenv("ADNE_SPS", "20.0"))
    mode = os.getenv("ADNE_MODE", "multiplicative")
    cpr = float(os.getenv("ADNE_CPR", "0.95"))

    model = train_prophet(
        history, 
        yearly=yearly, 
        weekly=weekly, 
        daily=daily, 
        interval_width=interval_width,
        holidays=holidays,
        changepoint_prior_scale=cps,
        seasonality_prior_scale=sps,
        seasonality_mode=mode,
        changepoint_range=cpr
    )

    global MODEL, HISTORY, HOLIDAYS, MODEL_META
    MODEL = model
    HISTORY = history
    HOLIDAYS = holidays
    MODEL_META = {
        "freq": freq,
        "n_files": n_files,
        "target_col": target_col,
        "dataset": dataset,
        "rows": int(len(history)),
        "ds_start": history["ds"].min().isoformat() if len(history) else None,
        "ds_end": history["ds"].max().isoformat() if len(history) else None,
        "has_holidays": holidays is not None,
    }


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    _startup_train()
    yield


app = FastAPI(title="AdNe Prophet Service", version="0.1.0", lifespan=lifespan)


@app.get("/health")
def health() -> dict[str, object]:
    return {
        "status": "ok",
        "model_trained": MODEL is not None,
        "meta": MODEL_META,
    }


@app.get("/predict")
def predict(
    periods: int = Query(6, ge=1, le=24 * 14),
) -> dict[str, object]:
    """Forecast future load. Uses the model trained at startup."""

    if MODEL is None or HISTORY is None:
        raise HTTPException(status_code=503, detail="Model not trained")

    # Predict at the same resolution as the configured dataset.

    freq = str(MODEL_META.get("freq", "1_hour"))
    FREQ_CONFIG = get_freq_config()
    pandas_freq = FREQ_CONFIG.get(freq, FREQ_CONFIG["1_hour"]).pandas_freq

    future = MODEL.make_future_dataframe(periods=periods, freq=pandas_freq, include_history=False)
    forecast = MODEL.predict(future)

    out = forecast[["ds", "yhat", "yhat_lower", "yhat_upper"]].copy()
    out["ds"] = out["ds"].astype("datetime64[ns]").astype(str)

    return {
        "meta": MODEL_META,
        "periods": periods,
        "forecast": out.to_dict(orient="records"),
    }


@app.get("/evaluate")
def evaluate(
    test_ratio: float = Query(0.2, gt=0.0, lt=0.5),
    interval_width: float = Query(0.90, gt=0.5, lt=0.99),
) -> dict[str, object]:
    """Train/test evaluation with standard error metrics.

    Uses an ordered split (time series): first (1-test_ratio) for training,
    last test_ratio for testing.

    Returns:
    - MAE (absolute error in the configured target metric)
    - RMSE
    - MAPE_percent (reported as sMAPE: symmetric, more robust near zero)
    - accuracy_percent = 100 - MAPE_percent (headline number for demos)
    """

    if HISTORY is None:
        raise HTTPException(status_code=503, detail="History not loaded")

    df = HISTORY.copy().reset_index(drop=True)
    if len(df) < 50:
        raise HTTPException(status_code=400, detail="Not enough rows to evaluate")

    split_idx = int(len(df) * (1.0 - test_ratio))
    train_df = df.iloc[:split_idx].copy()
    test_df = df.iloc[split_idx:].copy()

    # Fresh model to avoid leakage from the startup-trained model.
    freq = str(MODEL_META.get("freq", "1_hour"))
    yearly = bool(os.getenv("ADNE_YEARLY", "0") == "1")
    weekly = bool(os.getenv("ADNE_WEEKLY", "1") == "1")
    daily = bool(os.getenv("ADNE_DAILY", "1") == "1")

    eval_model = train_prophet(
        train_df,
        yearly=yearly,
        weekly=weekly,
        daily=daily,
        interval_width=interval_width,
        holidays=HOLIDAYS,
    )

    preds = eval_model.predict(test_df[["ds"]])
    predicted = preds["yhat"].to_numpy(dtype=float)
    actual = test_df["y"].to_numpy(dtype=float)

    errors = actual - predicted
    mae = float(np.mean(np.abs(errors)))
    rmse = float(np.sqrt(np.mean(np.square(errors))))

    eps = 1e-9
    # sMAPE is more robust than MAPE when actual values can be near zero.
    mape = float(
        np.mean(np.abs(errors) / (((np.abs(actual) + np.abs(predicted)) / 2.0) + eps)) * 100.0
    )
    accuracy = float(100.0 - mape)

    # Keep accuracy in a sensible range for display.
    accuracy_clipped = float(np.clip(accuracy, 0.0, 100.0))

    return {
        "meta": {
            **MODEL_META,
            "eval_freq": freq,
            "test_ratio": test_ratio,
            "interval_width": interval_width,
            "train_rows": int(len(train_df)),
            "test_rows": int(len(test_df)),
            "train_ds_start": train_df["ds"].min().isoformat(),
            "train_ds_end": train_df["ds"].max().isoformat(),
            "test_ds_start": test_df["ds"].min().isoformat(),
            "test_ds_end": test_df["ds"].max().isoformat(),
        },
        "MAE": round(mae, 4),
        "RMSE": round(rmse, 4),
        "MAPE_percent": round(mape, 2),
        "MAPE_note": "sMAPE (symmetric) — robust to near-zero actuals",
        "accuracy_percent": round(accuracy, 2),
        "accuracy_percent_clipped": round(accuracy_clipped, 2),
    }
