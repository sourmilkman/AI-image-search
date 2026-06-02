from __future__ import annotations

import threading
from pathlib import Path
from typing import Any

from PIL import Image, ImageOps

from .model import LocalImageModel
from .storage import Store


class Indexer:
    def __init__(self, store: Store, model: LocalImageModel) -> None:
        self.store = store
        self.model = model
        self._thread: threading.Thread | None = None
        self._lock = threading.Lock()
        self.status: dict[str, Any] = {
            "running": False,
            "stage": "idle",
            "processed": 0,
            "total": 0,
            "indexed": 0,
            "skipped": 0,
            "errors": 0,
            "message": "Idle",
        }

    def start(self) -> dict[str, Any]:
        with self._lock:
            if self._thread and self._thread.is_alive():
                return self.status
            self._thread = threading.Thread(target=self._run, daemon=True)
            self._thread.start()
            return self.status

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            return dict(self.status)

    def _set(self, **updates: Any) -> None:
        with self._lock:
            self.status.update(updates)

    def _run(self) -> None:
        self._set(
            running=True,
            stage="discovering",
            processed=0,
            total=0,
            indexed=0,
            skipped=0,
            errors=0,
            message="Discovering image files",
        )
        try:
            indexed = 0
            skipped = 0
            errors = 0
            processed = 0
            for processed, (folder_id, path) in enumerate(self.store.iter_folder_image_paths(), start=1):
                try:
                    stat = path.stat()
                    existing = self.store.existing_image(path)
                    model_matches = (
                        existing
                        and existing["model_name"] == self.model.name
                        and existing["model_version"] == self.model.version
                    )
                    file_unchanged = existing and int(existing["size"]) == stat.st_size and float(existing["modified"]) == stat.st_mtime
                    if existing and file_unchanged and model_matches:
                        skipped += 1
                        self._set(stage="skipping", processed=processed, total=processed, skipped=skipped, message=f"Skipped {path.name}")
                        continue
                    self._set(stage="embedding", processed=processed, total=processed, message=f"Indexing {path.name}")
                    embedding = self.model.embed_image(path)
                    width, height = image_dimensions(path)
                    image_id = self.store.upsert_image(
                        folder_id,
                        path,
                        stat.st_size,
                        stat.st_mtime,
                        width,
                        height,
                        embedding,
                        self.model.name,
                        self.model.version,
                    )
                    make_thumbnail(path, self.store.thumbnail_path(image_id))
                    indexed += 1
                    self._set(indexed=indexed)
                except Exception:
                    errors += 1
                    self._set(errors=errors, message=f"Could not index {path.name}")

            self._set(
                running=False,
                stage="complete",
                processed=processed,
                total=processed,
                indexed=indexed,
                skipped=skipped,
                errors=errors,
                message=f"Indexed {indexed}, skipped {skipped}, errors {errors}",
            )
        except Exception as exc:
            self._set(
                running=False,
                stage="error",
                message=f"Indexing failed during discovery: {exc}",
            )


def image_dimensions(path: Path) -> tuple[int, int]:
    with Image.open(path) as image:
        return image.size


def make_thumbnail(source: Path, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    with Image.open(source) as image:
        image = ImageOps.exif_transpose(image).convert("RGB")
        image.thumbnail((520, 520))
        image.save(target, format="JPEG", quality=82, optimize=True)
