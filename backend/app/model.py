from __future__ import annotations

import hashlib
import math
import os
from pathlib import Path
from typing import Iterable

import numpy as np
from PIL import Image, ImageStat


FALLBACK_EMBEDDING_DIMENSIONS = 48
CLIP_MODEL_ID = os.environ.get("IMAGE_SEARCH_CLIP_MODEL", "openai/clip-vit-base-patch32")


class LocalImageModel:
    """Local image/text embedding model with a deterministic fallback.

    The preferred path uses a local CLIP model through transformers/torch, which
    puts images and text in the same semantic vector space. The fallback keeps
    the app runnable before the heavier AI packages are installed, but it is not
    intended to produce strong natural-language search results.
    """

    fallback_name = "fallback-color-texture"
    fallback_version = "0.1.0"

    def __init__(self) -> None:
        self._clip_loaded = False
        self._clip_failed_reason: str | None = None
        self._processor = None
        self._model = None
        self._torch = None
        if os.environ.get("IMAGE_SEARCH_MODEL", "clip").lower() != "fallback":
            self._try_load_clip()

    @property
    def name(self) -> str:
        return f"clip:{CLIP_MODEL_ID}" if self._clip_loaded else self.fallback_name

    @property
    def version(self) -> str:
        return "1.0.0" if self._clip_loaded else self.fallback_version

    @property
    def dimensions(self) -> int:
        return 512 if self._clip_loaded else FALLBACK_EMBEDDING_DIMENSIONS

    @property
    def descriptor(self) -> dict[str, str | int]:
        descriptor: dict[str, str | int] = {
            "name": self.name,
            "version": self.version,
            "dimensions": self.dimensions,
            "mode": "local",
        }
        if self._clip_failed_reason:
            descriptor["fallback_reason"] = self._clip_failed_reason
        return descriptor

    def embed_image(self, image_path: Path) -> np.ndarray:
        if self._clip_loaded:
            return self._embed_clip_image(image_path)
        return self._embed_fallback_image(image_path)

    def embed_text(self, query: str) -> np.ndarray:
        if self._clip_loaded:
            return self._embed_clip_text(query)
        return self._embed_fallback_text(query)

    def _try_load_clip(self) -> None:
        try:
            import torch
            from transformers import CLIPModel, CLIPProcessor

            self._torch = torch
            self._processor = CLIPProcessor.from_pretrained(CLIP_MODEL_ID)
            self._model = CLIPModel.from_pretrained(CLIP_MODEL_ID)
            self._model.eval()
            self._clip_loaded = True
        except Exception as exc:
            self._clip_failed_reason = f"CLIP unavailable: {exc.__class__.__name__}"
            self._clip_loaded = False

    def _embed_clip_image(self, image_path: Path) -> np.ndarray:
        assert self._processor is not None and self._model is not None and self._torch is not None
        with Image.open(image_path) as image:
            inputs = self._processor(images=image.convert("RGB"), return_tensors="pt")
        with self._torch.no_grad():
            features = self._model.get_image_features(**inputs)
        return normalize(features[0].detach().cpu().numpy().astype(np.float32))

    def _embed_clip_text(self, query: str) -> np.ndarray:
        assert self._processor is not None and self._model is not None and self._torch is not None
        inputs = self._processor(text=[query], return_tensors="pt", padding=True, truncation=True)
        with self._torch.no_grad():
            features = self._model.get_text_features(**inputs)
        return normalize(features[0].detach().cpu().numpy().astype(np.float32))

    def _embed_fallback_image(self, image_path: Path) -> np.ndarray:
        with Image.open(image_path) as image:
            rgb = image.convert("RGB").resize((96, 96))
            array = np.asarray(rgb, dtype=np.float32) / 255.0
            means = array.mean(axis=(0, 1))
            stds = array.std(axis=(0, 1))
            extrema = np.array(ImageStat.Stat(rgb).extrema, dtype=np.float32).flatten() / 255.0
            hist = np.concatenate(
                [
                    np.histogram(array[:, :, channel], bins=8, range=(0.0, 1.0))[0]
                    for channel in range(3)
                ]
            ).astype(np.float32)
            hist = hist / max(float(hist.sum()), 1.0)
            gray = array.mean(axis=2)
            texture = np.array(
                [
                    np.abs(np.diff(gray, axis=0)).mean(),
                    np.abs(np.diff(gray, axis=1)).mean(),
                    gray.mean(),
                    gray.std(),
                ],
                dtype=np.float32,
            )

        vector = np.concatenate([means, stds, extrema, hist, texture])
        return normalize(pad_or_trim(vector, FALLBACK_EMBEDDING_DIMENSIONS))

    def _embed_fallback_text(self, query: str) -> np.ndarray:
        vector = np.zeros(FALLBACK_EMBEDDING_DIMENSIONS, dtype=np.float32)
        for token in tokenize(query):
            digest = hashlib.sha256(token.encode("utf-8")).digest()
            for offset in range(0, 12, 2):
                index = digest[offset] % FALLBACK_EMBEDDING_DIMENSIONS
                sign = 1.0 if digest[offset + 1] % 2 else -1.0
                vector[index] += sign
        color_hints = color_vector(query)
        vector[: len(color_hints)] += color_hints
        return normalize(vector)


def tokenize(value: str) -> Iterable[str]:
    cleaned = "".join(char.lower() if char.isalnum() else " " for char in value)
    return [token for token in cleaned.split() if token]


def color_vector(query: str) -> np.ndarray:
    words = set(tokenize(query))
    colors: dict[str, tuple[float, float, float]] = {
        "red": (1.0, 0.1, 0.1),
        "green": (0.1, 0.8, 0.2),
        "blue": (0.1, 0.25, 1.0),
        "yellow": (1.0, 0.85, 0.1),
        "orange": (1.0, 0.45, 0.05),
        "purple": (0.55, 0.25, 0.9),
        "pink": (1.0, 0.45, 0.7),
        "white": (0.95, 0.95, 0.95),
        "black": (0.02, 0.02, 0.02),
        "gray": (0.45, 0.45, 0.45),
        "grey": (0.45, 0.45, 0.45),
    }
    values = [colors[word] for word in words if word in colors]
    if not values:
        return np.zeros(3, dtype=np.float32)
    return np.array(values, dtype=np.float32).mean(axis=0)


def pad_or_trim(vector: np.ndarray, dimensions: int) -> np.ndarray:
    if vector.size == dimensions:
        return vector.astype(np.float32)
    if vector.size > dimensions:
        return vector[:dimensions].astype(np.float32)
    padded = np.zeros(dimensions, dtype=np.float32)
    padded[: vector.size] = vector
    return padded


def normalize(vector: np.ndarray) -> np.ndarray:
    norm = float(np.linalg.norm(vector))
    if math.isclose(norm, 0.0):
        return vector.astype(np.float32)
    return (vector / norm).astype(np.float32)
