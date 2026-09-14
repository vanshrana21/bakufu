"""Train the Sentinel-2 patch autoencoder on the unlabelled tiles.

CPU-only. Run: python -m src.models.prospectivity.train_autoencoder
"""

from __future__ import annotations

import time
from pathlib import Path

import mlflow
import numpy as np
import torch
from torch import nn
from torch.utils.data import DataLoader
from tqdm import tqdm

from src.config.settings import settings
from src.models.prospectivity.autoencoder import (
    BOTTLENECK_DIM,
    MODEL_PATH,
    N_BANDS,
    PATCH_SIZE,
    TILE_DIR,
    MnAutoencoder,
    TileDataset,
)

EPOCHS: int = 20
BATCH_SIZE: int = 128
LEARNING_RATE: float = 1e-3
PATCHES_PER_TILE: int = 400
TORCH_THREADS: int = 4

MLFLOW_URI: str = (settings.PROJECT_ROOT / "mlruns").as_uri()
EXPERIMENT: str = "manganese-prospectivity"


def train_autoencoder(
    tile_dir: Path = TILE_DIR,
    save_path: Path = MODEL_PATH,
    epochs: int = EPOCHS,
    batch_size: int = BATCH_SIZE,
    learning_rate: float = LEARNING_RATE,
    patches_per_tile: int = PATCHES_PER_TILE,
    log_mlflow: bool = True,
) -> dict[str, object]:
    """Train the autoencoder and save it. Returns a run summary."""
    torch.set_num_threads(TORCH_THREADS)
    torch.manual_seed(42)

    dataset = TileDataset(tile_dir=tile_dir, patches_per_tile=patches_per_tile)
    # num_workers=0: Windows spawn-based workers would re-open every tile per
    # worker and the in-process tile cache would be lost.
    loader = DataLoader(dataset, batch_size=batch_size, shuffle=True, num_workers=0)

    model = MnAutoencoder()
    n_params = sum(p.numel() for p in model.parameters())
    optimiser = torch.optim.Adam(model.parameters(), lr=learning_rate)
    criterion = nn.MSELoss()

    print(f"tiles           : {len(dataset.tile_paths)}")
    print(f"patches/epoch   : {len(dataset)}")
    print(f"parameters      : {n_params:,}")
    print(f"epochs          : {epochs}   batch: {batch_size}   lr: {learning_rate}")

    if log_mlflow:
        mlflow.set_tracking_uri(MLFLOW_URI)
        mlflow.set_experiment(EXPERIMENT)

    context = (
        mlflow.start_run(run_name="autoencoder_v1")
        if log_mlflow
        else _NullRun()
    )

    losses: list[float] = []
    started = time.perf_counter()

    with context:
        if log_mlflow:
            mlflow.log_params(
                {
                    "model": "MnAutoencoder",
                    "epochs": epochs,
                    "batch_size": batch_size,
                    "learning_rate": learning_rate,
                    "patch_size": PATCH_SIZE,
                    "n_bands": N_BANDS,
                    "bottleneck": BOTTLENECK_DIM,
                    "patches_per_tile": patches_per_tile,
                    "n_tiles": len(dataset.tile_paths),
                    "n_parameters": n_params,
                    "optimiser": "Adam",
                    "loss": "MSE",
                    "device": "cpu",
                }
            )

        model.train()
        for epoch in range(1, epochs + 1):
            epoch_losses: list[float] = []
            progress = tqdm(loader, desc=f"epoch {epoch}/{epochs}", unit="batch", leave=False)
            for batch in progress:
                optimiser.zero_grad()
                reconstruction = model(batch)
                loss = criterion(reconstruction, batch)
                loss.backward()
                optimiser.step()
                epoch_losses.append(loss.item())
                progress.set_postfix(loss=f"{loss.item():.6f}")

            mean_loss = float(np.mean(epoch_losses))
            losses.append(mean_loss)
            print(f"  epoch {epoch:2d}/{epochs}  mean MSE {mean_loss:.6f}")
            if log_mlflow:
                mlflow.log_metric("train_mse", mean_loss, step=epoch)

        elapsed = time.perf_counter() - started

        save_path.parent.mkdir(parents=True, exist_ok=True)
        torch.save(
            {
                "state_dict": model.state_dict(),
                "n_bands": N_BANDS,
                "bottleneck": BOTTLENECK_DIM,
                "patch_size": PATCH_SIZE,
                "final_loss": losses[-1],
                "epochs": epochs,
            },
            save_path,
        )
        size_mb = save_path.stat().st_size / 1e6

        if log_mlflow:
            mlflow.log_metrics(
                {
                    "final_train_mse": losses[-1],
                    "first_epoch_mse": losses[0],
                    "train_seconds": elapsed,
                    "model_size_mb": size_mb,
                }
            )
            mlflow.log_artifact(str(save_path))

    print("\n" + "=" * 60)
    print("AUTOENCODER TRAINING COMPLETE")
    print("=" * 60)
    print(f"  epochs run  : {epochs}")
    print(f"  first loss  : {losses[0]:.6f}")
    print(f"  final loss  : {losses[-1]:.6f}")
    print(f"  improvement : {(1 - losses[-1] / losses[0]) * 100:.1f}%")
    print(f"  elapsed     : {elapsed / 60:.1f} min")
    print(f"  saved to    : {save_path}  ({size_mb:.2f} MB)")

    return {
        "losses": losses,
        "final_loss": losses[-1],
        "epochs": epochs,
        "elapsed_s": elapsed,
        "size_mb": size_mb,
        "path": str(save_path),
    }


class _NullRun:
    """No-op context manager for when MLflow logging is disabled."""

    def __enter__(self) -> None:
        return None

    def __exit__(self, *args: object) -> bool:
        return False


def main() -> None:
    train_autoencoder()


if __name__ == "__main__":
    main()
