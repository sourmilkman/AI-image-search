from __future__ import annotations

import json
import os
import sqlite3
import threading
from pathlib import Path
from collections.abc import Iterator
from typing import Any

import numpy as np


IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".gif", ".tif", ".tiff"}


class Store:
    def __init__(self, data_dir: Path) -> None:
        self.data_dir = data_dir
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.thumbnail_dir = self.data_dir / "thumbnails"
        self.thumbnail_dir.mkdir(exist_ok=True)
        self.db_path = self.data_dir / "image-search.sqlite"
        self._lock = threading.Lock()
        self._init()

    def connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.db_path, check_same_thread=False)
        connection.row_factory = sqlite3.Row
        return connection

    def _init(self) -> None:
        with self.connect() as db:
            db.executescript(
                """
                CREATE TABLE IF NOT EXISTS folders (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    path TEXT NOT NULL UNIQUE,
                    added_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );
                CREATE TABLE IF NOT EXISTS images (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    folder_id INTEGER NOT NULL,
                    path TEXT NOT NULL UNIQUE,
                    filename TEXT NOT NULL,
                    size INTEGER NOT NULL,
                    modified REAL NOT NULL,
                    width INTEGER,
                    height INTEGER,
                    embedding BLOB NOT NULL,
                    model_name TEXT NOT NULL,
                    model_version TEXT NOT NULL,
                    indexed_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    error TEXT,
                    FOREIGN KEY(folder_id) REFERENCES folders(id)
                );
                CREATE INDEX IF NOT EXISTS idx_images_folder ON images(folder_id);
                """
            )

    def list_folders(self) -> list[dict[str, Any]]:
        with self.connect() as db:
            return [dict(row) for row in db.execute("SELECT * FROM folders ORDER BY id DESC")]

    def add_folder(self, path: Path) -> dict[str, Any]:
        resolved = str(path.resolve())
        with self._lock, self.connect() as db:
            db.execute("INSERT OR IGNORE INTO folders(path) VALUES (?)", (resolved,))
            row = db.execute("SELECT * FROM folders WHERE path = ?", (resolved,)).fetchone()
            return dict(row)

    def delete_folder(self, folder_id: int) -> dict[str, Any] | None:
        with self._lock, self.connect() as db:
            folder = db.execute("SELECT * FROM folders WHERE id = ?", (folder_id,)).fetchone()
            if not folder:
                return None
            images = db.execute("SELECT id FROM images WHERE folder_id = ?", (folder_id,)).fetchall()
            for image in images:
                thumbnail = self.thumbnail_path(int(image["id"]))
                if thumbnail.exists():
                    thumbnail.unlink()
            db.execute("DELETE FROM images WHERE folder_id = ?", (folder_id,))
            db.execute("DELETE FROM folders WHERE id = ?", (folder_id,))
            return {"folder": dict(folder), "removed_images": len(images)}

    def image_count(self) -> int:
        with self.connect() as db:
            row = db.execute("SELECT COUNT(*) AS count FROM images").fetchone()
            return int(row["count"])

    def folder_image_paths(self) -> list[tuple[int, Path]]:
        return list(self.iter_folder_image_paths())

    def iter_folder_image_paths(self) -> Iterator[tuple[int, Path]]:
        folders = self.list_folders()
        for folder in folders:
            root = Path(folder["path"])
            if not root.exists():
                continue
            for current_root, _dirs, files in os.walk(root, onerror=lambda _error: None):
                for filename in files:
                    path = Path(current_root) / filename
                    if path.suffix.lower() in IMAGE_EXTENSIONS:
                        yield (int(folder["id"]), path)

    def existing_image(self, path: Path) -> sqlite3.Row | None:
        with self.connect() as db:
            return db.execute(
                "SELECT id, size, modified, model_name, model_version FROM images WHERE path = ?",
                (str(path),),
            ).fetchone()

    def upsert_image(
        self,
        folder_id: int,
        path: Path,
        size: int,
        modified: float,
        width: int,
        height: int,
        embedding: np.ndarray,
        model_name: str,
        model_version: str,
    ) -> int:
        with self._lock, self.connect() as db:
            db.execute(
                """
                INSERT INTO images(folder_id, path, filename, size, modified, width, height, embedding, model_name, model_version)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(path) DO UPDATE SET
                  folder_id=excluded.folder_id,
                  filename=excluded.filename,
                  size=excluded.size,
                  modified=excluded.modified,
                  width=excluded.width,
                  height=excluded.height,
                  embedding=excluded.embedding,
                  model_name=excluded.model_name,
                  model_version=excluded.model_version,
                  indexed_at=CURRENT_TIMESTAMP,
                  error=NULL
                """,
                (
                    folder_id,
                    str(path),
                    path.name,
                    size,
                    modified,
                    width,
                    height,
                    embedding.astype(np.float32).tobytes(),
                    model_name,
                    model_version,
                ),
            )
            row = db.execute("SELECT id FROM images WHERE path = ?", (str(path),)).fetchone()
            return int(row["id"])

    def all_images(self) -> list[dict[str, Any]]:
        with self.connect() as db:
            rows = db.execute(
                """
                SELECT id, path, filename, size, modified, width, height, embedding, model_name, model_version
                FROM images
                WHERE error IS NULL
                """
            ).fetchall()
            return [dict(row) for row in rows]

    def get_image(self, image_id: int) -> dict[str, Any] | None:
        with self.connect() as db:
            row = db.execute("SELECT * FROM images WHERE id = ?", (image_id,)).fetchone()
            return dict(row) if row else None

    def remove_missing(self, present_paths: set[str]) -> int:
        if not present_paths:
            return 0
        with self._lock, self.connect() as db:
            rows = db.execute("SELECT id, path FROM images").fetchall()
            stale = [row["id"] for row in rows if row["path"] not in present_paths]
            if stale:
                db.executemany("DELETE FROM images WHERE id = ?", [(image_id,) for image_id in stale])
            return len(stale)

    def thumbnail_path(self, image_id: int) -> Path:
        return self.thumbnail_dir / f"{image_id}.jpg"

    def index_summary(self) -> dict[str, Any]:
        with self.connect() as db:
            folder_count = db.execute("SELECT COUNT(*) AS count FROM folders").fetchone()["count"]
            image_count = db.execute("SELECT COUNT(*) AS count FROM images").fetchone()["count"]
            last_index = db.execute("SELECT MAX(indexed_at) AS value FROM images").fetchone()["value"]
            models = [
                json.loads(row["model"])
                for row in db.execute(
                    "SELECT json_object('name', model_name, 'version', model_version) AS model FROM images GROUP BY model_name, model_version"
                )
            ]
            return {
                "folders": folder_count,
                "images": image_count,
                "last_indexed_at": last_index,
                "models": models,
            }
