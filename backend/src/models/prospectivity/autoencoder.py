"""Convolutional autoencoder for self-supervised Sentinel-2 patch pretraining.

Small by design: the whole point is that it trains on CPU in under an hour.
The 64-dim bottleneck is what downstream models consume as learned spectral
texture features.
"""

from __future__ import annotations

import random
from pathlib import Path

import numpy as np
import rasterio
import torch
from torch import nn
from torch.utils.data import Dataset

from src.config.settings import settings
from src.models.artifact_security import fingerprint, load_torch_checkpoint

#: Sentinel-2 L2A reflectance scale factor (DN -> [0, 1] reflectance).
S2_SCALE: float = 10000.0

PATCH_SIZE: int = 16
N_BANDS: int = 6
BOTTLENECK_DIM: int = 64

TILE_DIR: Path = settings.DATA_RAW / "satellite" / "unlabelled"
MODEL_PATH: Path = settings.MODELS_DIR / "autoencoder_v1.pt"


class MnAutoencoder(nn.Module):
    """6-band 16x16 patch autoencoder with a 64-dim bottleneck."""

    def __init__(self, n_bands: int = N_BANDS, bottleneck: int = BOTTLENECK_DIM) -> None:
        super().__init__()
        self.n_bands = n_bands
        self.bottleneck = bottleneck

        self.encoder_conv = nn.Sequential(
            nn.Conv2d(n_bands, 16, 3, padding=1),
            nn.ReLU(),
            nn.MaxPool2d(2),  # 16x16 -> 8x8
            nn.Conv2d(16, 32, 3, padding=1),
            nn.ReLU(),
            nn.MaxPool2d(2),  # 8x8 -> 4x4
            nn.Conv2d(32, 64, 3, padding=1),
            nn.ReLU(),  # 4x4
        )
        self.encoder_fc = nn.Linear(64 * 4 * 4, bottleneck)

        self.decoder_fc = nn.Linear(bottleneck, 64 * 4 * 4)
        self.decoder_conv = nn.Sequential(
            nn.Upsample(scale_factor=2, mode="nearest"),  # 4x4 -> 8x8
            nn.Conv2d(64, 32, 3, padding=1),
            nn.ReLU(),
            nn.Upsample(scale_factor=2, mode="nearest"),  # 8x8 -> 16x16
            nn.Conv2d(32, 16, 3, padding=1),
            nn.ReLU(),
            nn.Conv2d(16, n_bands, 3, padding=1),
        )

    def encode(self, x: torch.Tensor) -> torch.Tensor:
        """Patch batch (B, 6, 16, 16) -> embedding (B, 64)."""
        h = self.encoder_conv(x)
        return self.encoder_fc(h.flatten(1))

    def decode(self, z: torch.Tensor) -> torch.Tensor:
        h = self.decoder_fc(z).view(-1, 64, 4, 4)
        return self.decoder_conv(h)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.decode(self.encode(x))


class TileDataset(Dataset):
    """Random 16x16 patches sampled from the unlabelled GeoTIFF tiles.

    Tiles are held open lazily per worker and patches are drawn on demand, so
    memory stays flat regardless of how many tiles are on disk. `patches_per_tile`
    defines one epoch's nominal length.
    """

    def __init__(
        self,
        tile_dir: Path = TILE_DIR,
        patch_size: int = PATCH_SIZE,
        patches_per_tile: int = 400,
        seed: int = 42,
        max_nodata_frac: float = 0.1,
    ) -> None:
        self.tile_paths: list[Path] = sorted(Path(tile_dir).glob("*.tif"))
        if not self.tile_paths:
            raise FileNotFoundError(f"no .tif tiles found in {tile_dir}")
        self.patch_size = patch_size
        self.patches_per_tile = patches_per_tile
        self.max_nodata_frac = max_nodata_frac
        self.rng = random.Random(seed)
        self._cache: dict[int, np.ndarray] = {}

    def __len__(self) -> int:
        return len(self.tile_paths) * self.patches_per_tile

    def _tile(self, tile_index: int) -> np.ndarray:
        """Load and cache one tile as a float32 array scaled to [0, 1]."""
        if tile_index not in self._cache:
            with rasterio.open(self.tile_paths[tile_index]) as src:
                arr = src.read().astype("float32") / S2_SCALE
            self._cache[tile_index] = np.clip(arr, 0.0, 1.0)
        return self._cache[tile_index]

    def __getitem__(self, index: int) -> torch.Tensor:
        tile_index = index // self.patches_per_tile
        arr = self._tile(tile_index)
        _, height, width = arr.shape
        size = self.patch_size

        # Retry a few times to avoid patches that are mostly nodata (zeros).
        for _ in range(8):
            row = self.rng.randint(0, max(height - size, 0))
            col = self.rng.randint(0, max(width - size, 0))
            patch = arr[:, row : row + size, col : col + size]
            if patch.shape[1:] != (size, size):
                continue
            if (patch == 0).mean() <= self.max_nodata_frac:
                return torch.from_numpy(np.ascontiguousarray(patch))

        patch = arr[:, :size, :size]
        if patch.shape[1:] != (size, size):
            patch = np.zeros((arr.shape[0], size, size), dtype="float32")
        return torch.from_numpy(np.ascontiguousarray(patch))


def extract_features(patch: np.ndarray | torch.Tensor, model: MnAutoencoder) -> np.ndarray:
    """Encode one patch (6, 16, 16) or a batch (B, 6, 16, 16) into embeddings.

    Input is expected already scaled to [0, 1]. Returns (64,) for a single
    patch, or (B, 64) for a batch.
    """
    model.eval()
    if isinstance(patch, np.ndarray):
        tensor = torch.from_numpy(patch.astype("float32"))
    else:
        tensor = patch.float()

    single = tensor.ndim == 3
    if single:
        tensor = tensor.unsqueeze(0)

    with torch.no_grad():
        embedding = model.encode(tensor).cpu().numpy()

    return embedding[0] if single else embedding


def encoder_fingerprint(model_path: Path = MODEL_PATH) -> str:
    """Short digest of the encoder in use, for cache keys and health output.

    The bundle is versioned by the registry; the encoder defines the feature
    space that bundle was trained against. Anything that caches scores has to
    key on both, or a swapped encoder silently changes what a cached score means.
    """
    try:
        return fingerprint(model_path)
    except OSError:
        return "missing"


def load_autoencoder(model_path: Path = MODEL_PATH) -> MnAutoencoder:
    """Load a trained autoencoder in eval mode."""
    if not model_path.exists():
        raise FileNotFoundError(
            f"no trained autoencoder at {model_path} - "
            "run python -m src.models.prospectivity.train_autoencoder"
        )
    # Verified against the pinned digest and loaded weights-only: this file is
    # deserialised inside the API process, so a replaced checkpoint must not be
    # able to run code here.
    checkpoint = load_torch_checkpoint(model_path)
    model = MnAutoencoder(
        n_bands=checkpoint.get("n_bands", N_BANDS),
        bottleneck=checkpoint.get("bottleneck", BOTTLENECK_DIM),
    )
    model.load_state_dict(checkpoint["state_dict"])
    model.eval()
    return model
