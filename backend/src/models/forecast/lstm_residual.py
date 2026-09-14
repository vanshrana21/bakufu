"""
LSTM that predicts the residuals of Prophet's forecast.

Prophet captures the smooth structure - trend, yearly seasonality, the
rainfall and capex regressors. What it misses is short-term irregularity:
a specific washout, a haulage bottleneck, a restocking push. That signal,
if any, lives in the residual series.

    combined forecast = Prophet + LSTM(residual)

The LSTM is deliberately tiny (~10k params) because the residual series is
only as long as the production history. If it cannot beat "predict zero
residual" on the validation split, that is reported rather than hidden -
a residual model that adds nothing is a real finding about the data.

Run: python -m src.models.forecast.lstm_residual
"""

from __future__ import annotations

import json
import warnings
from pathlib import Path

import joblib
import mlflow
import numpy as np
import pandas as pd
import torch
from torch import nn

from src.config.settings import settings
from src.models.forecast.prophet_baseline import (
    HORIZONS,
    MODEL_PATH as PROPHET_PATH,
    _future_regressors,
    build_frame,
    fit_prophet,
    mape,
)

warnings.filterwarnings("ignore")

MLFLOW_URI: str = (settings.PROJECT_ROOT / "mlruns").as_uri()
EXPERIMENT: str = "phase_3_lstm_residual"

MODEL_PATH: Path = settings.MODELS_DIR / "lstm_residual_v1.pt"
METRICS_PATH: Path = settings.DATA_PROCESSED / "lstm_residual_metrics.json"

LOOKBACK: int = 12
HIDDEN: int = 64
EPOCHS: int = 50
BATCH_SIZE: int = 16
LEARNING_RATE: float = 1e-3
PATIENCE: int = 10
TORCH_THREADS: int = 4

#: Columns fed to the LSTM at each timestep.
FEATURES: tuple[str, ...] = ("y", "rainfall_mm", "prophet_yhat", "residual")


class ResidualLSTM(nn.Module):
    """LSTM(64) -> Dense(32) -> Dense(1) over a 12-month window."""

    def __init__(self, n_features: int = len(FEATURES), hidden: int = HIDDEN) -> None:
        super().__init__()
        self.lstm = nn.LSTM(n_features, hidden, batch_first=True)
        self.head = nn.Sequential(nn.Linear(hidden, 32), nn.ReLU(), nn.Linear(32, 1))

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        output, _ = self.lstm(x)
        return self.head(output[:, -1, :]).squeeze(-1)


def in_sample_prophet(frame: pd.DataFrame) -> pd.DataFrame:
    """Attach Prophet's fitted values and residuals to the frame."""
    model = fit_prophet(frame)
    future = _future_regressors(frame, frame[["ds"]].copy())
    fitted = model.predict(future)
    out = frame.copy()
    out["prophet_yhat"] = fitted.yhat.to_numpy()
    out["residual"] = out.y - out.prophet_yhat
    return out


def make_windows(frame: pd.DataFrame, lookback: int = LOOKBACK) -> tuple[np.ndarray, np.ndarray]:
    """Sliding windows of FEATURES -> next month's residual."""
    values = frame[list(FEATURES)].to_numpy(dtype="float32")
    targets = frame["residual"].to_numpy(dtype="float32")
    xs, ys = [], []
    for end in range(lookback, len(frame)):
        xs.append(values[end - lookback : end])
        ys.append(targets[end])
    if not xs:
        return np.empty((0, lookback, len(FEATURES)), dtype="float32"), np.empty(0, dtype="float32")
    return np.stack(xs), np.asarray(ys, dtype="float32")


def train(frame: pd.DataFrame | None = None, log_mlflow: bool = True) -> dict[str, object]:
    torch.set_num_threads(TORCH_THREADS)
    torch.manual_seed(42)

    frame = build_frame() if frame is None else frame
    enriched = in_sample_prophet(frame)

    X, y = make_windows(enriched)
    if len(X) < 24:
        raise RuntimeError(
            f"only {len(X)} training windows after a {LOOKBACK}-month lookback; "
            "the production history is too short for a residual LSTM"
        )

    split = int(len(X) * 0.8)
    # Standardise on train statistics only, so validation stays honest.
    mean = X[:split].reshape(-1, X.shape[-1]).mean(axis=0)
    std = X[:split].reshape(-1, X.shape[-1]).std(axis=0)
    std[std == 0] = 1.0
    target_scale = float(np.abs(y[:split]).mean()) or 1.0

    Xn = (X - mean) / std
    X_train = torch.from_numpy(Xn[:split])
    y_train = torch.from_numpy(y[:split] / target_scale)
    X_val = torch.from_numpy(Xn[split:])
    y_val = torch.from_numpy(y[split:] / target_scale)

    model = ResidualLSTM()
    n_params = sum(p.numel() for p in model.parameters())
    optimiser = torch.optim.Adam(model.parameters(), lr=LEARNING_RATE)
    criterion = nn.MSELoss()

    print(f"  windows        : {len(X)} (train {split}, val {len(X) - split})")
    print(f"  parameters     : {n_params:,}")

    best_val = float("inf")
    best_state = None
    stale = 0
    history: list[dict[str, float]] = []

    for epoch in range(1, EPOCHS + 1):
        model.train()
        order = torch.randperm(len(X_train))
        losses = []
        for start in range(0, len(X_train), BATCH_SIZE):
            batch = order[start : start + BATCH_SIZE]
            optimiser.zero_grad()
            loss = criterion(model(X_train[batch]), y_train[batch])
            loss.backward()
            optimiser.step()
            losses.append(loss.item())

        model.eval()
        with torch.no_grad():
            val_loss = float(criterion(model(X_val), y_val)) if len(X_val) else float("nan")
        history.append({"epoch": epoch, "train": float(np.mean(losses)), "val": val_loss})

        if val_loss < best_val - 1e-6:
            best_val, best_state, stale = val_loss, {k: v.clone() for k, v in model.state_dict().items()}, 0
        else:
            stale += 1
            if stale >= PATIENCE:
                print(f"  early stop     : epoch {epoch} (no val gain for {PATIENCE})")
                break

    if best_state is not None:
        model.load_state_dict(best_state)

    # Does the LSTM beat "assume zero residual"? That is the only comparison
    # that matters - Prophet alone already implies a zero-residual forecast.
    model.eval()
    with torch.no_grad():
        predicted = model(X_val).numpy() * target_scale
    actual_resid = y[split:] * target_scale
    actual = enriched.y.to_numpy()[LOOKBACK:][split:]
    prophet_only = enriched.prophet_yhat.to_numpy()[LOOKBACK:][split:]
    hybrid = prophet_only + predicted

    summary = {
        "n_params": n_params,
        "epochs_run": len(history),
        "best_val_loss": best_val,
        "prophet_mape": mape(actual, prophet_only),
        "hybrid_mape": mape(actual, hybrid),
        "residual_rmse_zero": float(np.sqrt(np.mean(actual_resid**2))),
        "residual_rmse_lstm": float(np.sqrt(np.mean((actual_resid - predicted) ** 2))),
    }
    summary["mape_improvement_pp"] = summary["prophet_mape"] - summary["hybrid_mape"]
    summary["beats_zero_residual"] = bool(
        summary["residual_rmse_lstm"] < summary["residual_rmse_zero"]
    )

    MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
    torch.save(
        {
            "state_dict": model.state_dict(),
            "mean": mean,
            "std": std,
            "target_scale": target_scale,
            "lookback": LOOKBACK,
            "features": list(FEATURES),
            "summary": summary,
        },
        MODEL_PATH,
    )

    if log_mlflow:
        mlflow.set_tracking_uri(MLFLOW_URI)
        mlflow.set_experiment(EXPERIMENT)
        with mlflow.start_run(run_name="lstm_residual_v1"):
            mlflow.log_params(
                {
                    "lookback": LOOKBACK,
                    "hidden": HIDDEN,
                    "epochs_max": EPOCHS,
                    "batch_size": BATCH_SIZE,
                    "learning_rate": LEARNING_RATE,
                    "n_params": n_params,
                    "features": ",".join(FEATURES),
                }
            )
            mlflow.log_metrics({k: v for k, v in summary.items() if isinstance(v, (int, float))})
            for entry in history:
                mlflow.log_metric("val_loss", entry["val"], step=int(entry["epoch"]))
            mlflow.log_artifact(str(MODEL_PATH))

    print("")
    print("=" * 66)
    print("LSTM RESIDUAL CORRECTION")
    print("=" * 66)
    print(f"  epochs run           : {summary['epochs_run']}")
    print(f"  residual RMSE (zero) : {summary['residual_rmse_zero']:,.0f} t")
    print(f"  residual RMSE (LSTM) : {summary['residual_rmse_lstm']:,.0f} t")
    print(f"  beats zero-residual  : {summary['beats_zero_residual']}")
    print(f"  Prophet MAPE (val)   : {summary['prophet_mape']:.2f}%")
    print(f"  Hybrid MAPE  (val)   : {summary['hybrid_mape']:.2f}%")
    print(f"  improvement          : {summary['mape_improvement_pp']:+.2f} pp")
    print(f"  saved to             : {MODEL_PATH}")

    METRICS_PATH.write_text(json.dumps(summary, indent=2, default=str), encoding="utf-8")
    return summary


def main() -> None:
    train()


if __name__ == "__main__":
    main()
