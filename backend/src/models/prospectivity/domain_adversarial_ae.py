"""
Domain-adversarial autoencoder - learns country-invariant features
so India and foreign positives are represented on the same manifold.

Architecture (extends v1 autoencoder):
  Encoder (initialised from v1) - 64-dim bottleneck as before
  New branch: country classifier head
    Linear(64, 32) -> ReLU -> Linear(32, N_COUNTRIES)
    trained ADVERSARIALLY via a gradient reversal layer (Ganin 2015)

  During training:
    - Reconstruction loss trains encoder + decoder normally
    - Country loss trains the classifier head normally
    - Gradient reversal on the classifier's gradients into the encoder
      forces the encoder to lose country-distinguishing information

Result: 64-dim embeddings that describe "what this pixel looks like"
without leaking "which country it's in".

Reference: Ganin et al. 2015, "Domain-Adversarial Training of Neural
Networks", https://arxiv.org/abs/1505.07818

Run: python -m src.models.prospectivity.domain_adversarial_ae
"""

from __future__ import annotations

import time
from pathlib import Path

import mlflow
import numpy as np
import torch
from torch import nn
from torch.autograd import Function
from torch.utils.data import DataLoader, Dataset
from tqdm import tqdm

from src.config.settings import settings
from src.data.ingest.download_unlabelled_tiles import (
    AUSTRALIA_TILES,
    BRAZIL_TILES,
    INDIA_TILES,
)
from src.models.prospectivity.autoencoder import BOTTLENECK_DIM
from src.models.prospectivity.autoencoder import MODEL_PATH as AE_V1_PATH
from src.models.prospectivity.autoencoder import (
    PATCH_SIZE,
    TILE_DIR,
    MnAutoencoder,
    TileDataset,
)

EPOCHS: int = 15
BATCH_SIZE: int = 128
LEARNING_RATE: float = 5e-4  # lower than v1's 1e-3; this is fine-tuning
LAMBDA_RAMP_EPOCHS: int = 10
PATCHES_PER_TILE: int = 250
TORCH_THREADS: int = 4

OUT_PATH: Path = settings.MODELS_DIR / "autoencoder_v2_adversarial.pt"
MLFLOW_URI: str = (settings.PROJECT_ROOT / "mlruns").as_uri()
EXPERIMENT: str = "phase_2_7_all_levers"

#: Reconstruction ceiling above which Lever 1 is judged to have failed.
MSE_FAILURE_CEILING: float = 0.01


class GradientReversal(Function):
    """Identity forwards; negated, scaled gradient backwards."""

    @staticmethod
    def forward(ctx, x, lambda_):  # noqa: ANN001
        ctx.lambda_ = lambda_
        return x.view_as(x)

    @staticmethod
    def backward(ctx, grad):  # noqa: ANN001
        return grad.neg() * ctx.lambda_, None


def country_of(tile_path: Path) -> str:
    """Country tag for a pretraining tile, derived from its filename."""
    stem = tile_path.stem
    if stem.startswith("foreign_"):
        # foreign_<Country>_c07 -> Country (country itself may contain "_")
        parts = stem.split("_")[1:]
        return "_".join(parts[:-1]) if len(parts) > 1 else parts[0]
    india = {name for name, _, _ in INDIA_TILES}
    australia = {name for name, _, _ in AUSTRALIA_TILES}
    brazil = {name for name, _, _ in BRAZIL_TILES}
    if stem in india:
        return "India"
    if stem in australia:
        return "Australia"
    if stem in brazil:
        return "Brazil"
    return "Unknown"


class CountryTileDataset(Dataset):
    """TileDataset patches paired with the tile's country index."""

    def __init__(
        self, tile_dir: Path = TILE_DIR, patches_per_tile: int = PATCHES_PER_TILE
    ) -> None:
        self.base = TileDataset(tile_dir=tile_dir, patches_per_tile=patches_per_tile)
        countries = [country_of(p) for p in self.base.tile_paths]
        self.classes: list[str] = sorted(set(countries))
        self.class_to_index = {c: i for i, c in enumerate(self.classes)}
        self.tile_country = np.array(
            [self.class_to_index[c] for c in countries], dtype="int64"
        )

    def __len__(self) -> int:
        return len(self.base)

    def __getitem__(self, index: int) -> tuple[torch.Tensor, int]:
        patch = self.base[index]
        tile_index = index // self.base.patches_per_tile
        return patch, int(self.tile_country[tile_index])


class CountryHead(nn.Module):
    """Adversarial country classifier sitting on the bottleneck."""

    def __init__(self, bottleneck: int = BOTTLENECK_DIM, n_countries: int = 15) -> None:
        super().__init__()
        self.net = nn.Sequential(
            nn.Linear(bottleneck, 32),
            nn.ReLU(),
            nn.Linear(32, n_countries),
        )

    def forward(self, z: torch.Tensor, lambda_: float) -> torch.Tensor:
        return self.net(GradientReversal.apply(z, lambda_))


def lambda_at(epoch: int, ramp: int = LAMBDA_RAMP_EPOCHS) -> float:
    """Ganin's schedule, ramped linearly 0 -> 1 over the first `ramp` epochs."""
    return float(min(1.0, epoch / max(ramp, 1)))


def train(
    epochs: int = EPOCHS,
    batch_size: int = BATCH_SIZE,
    learning_rate: float = LEARNING_RATE,
    save_path: Path = OUT_PATH,
    log_mlflow: bool = True,
) -> dict[str, object]:
    """Fine-tune the v1 encoder adversarially against country identity."""
    torch.set_num_threads(TORCH_THREADS)
    torch.manual_seed(42)

    dataset = CountryTileDataset()
    loader = DataLoader(dataset, batch_size=batch_size, shuffle=True, num_workers=0)
    n_countries = len(dataset.classes)

    # Class balance sets the honest baseline: an encoder that leaks nothing
    # leaves the head no better than always guessing the commonest country.
    counts = np.bincount(dataset.tile_country, minlength=n_countries).astype("float64")
    majority_baseline = float(counts.max() / counts.sum())
    random_baseline = 1.0 / n_countries

    model = MnAutoencoder()
    checkpoint = torch.load(AE_V1_PATH, map_location="cpu", weights_only=False)
    model.load_state_dict(checkpoint["state_dict"])
    head = CountryHead(n_countries=n_countries)

    optimiser = torch.optim.Adam(
        list(model.parameters()) + list(head.parameters()), lr=learning_rate
    )
    recon_loss_fn = nn.MSELoss()
    country_loss_fn = nn.CrossEntropyLoss()

    print(f"tiles           : {len(dataset.base.tile_paths)}")
    print(f"countries       : {n_countries} -> {dataset.classes}")
    print(f"patches/epoch   : {len(dataset)}")
    print(f"random baseline : {random_baseline:.4f}")
    print(f"majority basline: {majority_baseline:.4f}")
    print(f"epochs {epochs}, lr {learning_rate}, batch {batch_size}, ramp {LAMBDA_RAMP_EPOCHS}")

    if log_mlflow:
        mlflow.set_tracking_uri(MLFLOW_URI)
        mlflow.set_experiment(EXPERIMENT)

    history: list[dict[str, float]] = []
    started = time.perf_counter()
    run = mlflow.start_run(run_name="autoencoder_v2_adversarial") if log_mlflow else None

    try:
        if log_mlflow:
            mlflow.log_params(
                {
                    "model": "MnAutoencoder+CountryHead",
                    "init_from": "autoencoder_v1",
                    "epochs": epochs,
                    "batch_size": batch_size,
                    "learning_rate": learning_rate,
                    "lambda_ramp_epochs": LAMBDA_RAMP_EPOCHS,
                    "n_countries": n_countries,
                    "patches_per_tile": PATCHES_PER_TILE,
                    "n_tiles": len(dataset.base.tile_paths),
                    "random_baseline": random_baseline,
                    "majority_baseline": majority_baseline,
                }
            )

        for epoch in range(1, epochs + 1):
            lambda_ = lambda_at(epoch - 1)
            model.train()
            head.train()
            recon_losses: list[float] = []
            country_losses: list[float] = []
            correct = 0
            seen = 0

            progress = tqdm(loader, desc=f"epoch {epoch}/{epochs}", unit="batch", leave=False)
            for patches, countries in progress:
                optimiser.zero_grad()
                z = model.encode(patches)
                reconstruction = model.decode(z)
                recon = recon_loss_fn(reconstruction, patches)

                logits = head(z, lambda_)
                country = country_loss_fn(logits, countries)

                (recon + country).backward()
                optimiser.step()

                recon_losses.append(recon.item())
                country_losses.append(country.item())
                correct += int((logits.argmax(dim=1) == countries).sum())
                seen += len(countries)
                progress.set_postfix(recon=f"{recon.item():.6f}", ctry=f"{country.item():.3f}")

            entry = {
                "epoch": float(epoch),
                "lambda": lambda_,
                "recon_mse": float(np.mean(recon_losses)),
                "country_loss": float(np.mean(country_losses)),
                "country_acc": correct / max(seen, 1),
            }
            history.append(entry)
            print(
                f"  epoch {epoch:2d}/{epochs}  lambda={lambda_:.2f}  "
                f"recon MSE {entry['recon_mse']:.6f}  "
                f"country loss {entry['country_loss']:.4f}  "
                f"country acc {entry['country_acc']:.4f}"
            )
            if log_mlflow:
                mlflow.log_metrics(
                    {
                        "recon_mse": entry["recon_mse"],
                        "country_loss": entry["country_loss"],
                        "country_acc": entry["country_acc"],
                        "lambda": lambda_,
                    },
                    step=epoch,
                )

        elapsed = time.perf_counter() - started
        final = history[-1]

        save_path.parent.mkdir(parents=True, exist_ok=True)
        torch.save(
            {
                "state_dict": model.state_dict(),
                "n_bands": checkpoint.get("n_bands", 6),
                "bottleneck": BOTTLENECK_DIM,
                "patch_size": PATCH_SIZE,
                "final_loss": final["recon_mse"],
                "country_acc": final["country_acc"],
                "countries": dataset.classes,
                "epochs": epochs,
                "adversarial": True,
            },
            save_path,
        )

        if log_mlflow:
            mlflow.log_metrics(
                {
                    "final_recon_mse": final["recon_mse"],
                    "final_country_acc": final["country_acc"],
                    "train_seconds": elapsed,
                }
            )
            mlflow.log_artifact(str(save_path))
    finally:
        if run is not None:
            mlflow.end_run()

    v1_mse = float(checkpoint.get("final_loss", float("nan")))
    ok = final["recon_mse"] <= MSE_FAILURE_CEILING
    beat = final["country_acc"] < majority_baseline

    print("")
    print("=" * 64)
    print("DOMAIN-ADVERSARIAL FINE-TUNING COMPLETE")
    print("=" * 64)
    print(f"  epochs run          : {epochs}")
    print(f"  v1 recon MSE        : {v1_mse:.6f}")
    print(f"  v2 recon MSE        : {final['recon_mse']:.6f}")
    print(f"  reconstruction ok   : {ok} (ceiling {MSE_FAILURE_CEILING})")
    print(f"  country accuracy    : {final['country_acc']:.4f}")
    print(f"  random baseline     : {random_baseline:.4f}")
    print(f"  majority baseline   : {majority_baseline:.4f}")
    print(f"  below majority base : {beat}  <- adversarial worked if True")
    print(f"  elapsed             : {elapsed / 60:.1f} min")
    print(f"  saved to            : {save_path}")

    return {
        "history": history,
        "final_recon_mse": final["recon_mse"],
        "final_country_acc": final["country_acc"],
        "random_baseline": random_baseline,
        "majority_baseline": majority_baseline,
        "v1_recon_mse": v1_mse,
        "reconstruction_ok": ok,
        "elapsed_s": elapsed,
        "path": str(save_path),
        "countries": dataset.classes,
    }


def main() -> None:
    train()


if __name__ == "__main__":
    main()
