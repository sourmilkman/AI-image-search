from __future__ import annotations

import asyncio
import json
import os
import subprocess
from pathlib import Path
from typing import Any

import numpy as np
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel

from .indexer import Indexer
from .model import LocalImageModel
from .storage import Store


APP_VERSION = "0.1.0"
DATA_DIR = Path(os.environ.get("IMAGE_SEARCH_DATA_DIR", Path.home() / ".local-ai-image-search"))

store = Store(DATA_DIR)
model = LocalImageModel()
indexer = Indexer(store, model)

app = FastAPI(title="Local AI Image Search", version=APP_VERSION)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


class FolderRequest(BaseModel):
    path: str


class SearchRequest(BaseModel):
    query: str
    limit: int = 40


@app.get("/api/health")
def health() -> dict[str, Any]:
    return {
        "ok": True,
        "app_version": APP_VERSION,
        "backend": "FastAPI",
        "model": model.descriptor,
        "index": store.index_summary(),
    }


@app.get("/api/folders")
def list_folders() -> dict[str, Any]:
    return {"folders": store.list_folders()}


@app.post("/api/folders")
def add_folder(request: FolderRequest) -> dict[str, Any]:
    path = Path(request.path).expanduser()
    if not path.exists() or not path.is_dir():
        raise HTTPException(status_code=400, detail="Folder does not exist or is not a directory")
    return {"folder": store.add_folder(path)}


@app.post("/api/index")
def start_indexing() -> dict[str, Any]:
    return {"status": indexer.start()}


@app.get("/api/index/status")
def index_status() -> dict[str, Any]:
    return {"status": indexer.snapshot(), "summary": store.index_summary()}


@app.post("/api/search")
async def search(request: SearchRequest) -> StreamingResponse:
    async def events():
        yield event("query_embedding", 15, "Understanding search text")
        query_vector = model.embed_text(request.query)
        await asyncio.sleep(0)

        yield event("vector_search", 45, "Comparing against local image index")
        images = store.all_images()
        scored: list[dict[str, Any]] = []
        for row in images:
            image_vector = np.frombuffer(row["embedding"], dtype=np.float32)
            if image_vector.size != query_vector.size:
                continue
            score = float(np.dot(query_vector, image_vector))
            scored.append({**without_embedding(row), "score": score})

        yield event("ranking", 75, "Ranking strongest matches")
        scored.sort(key=lambda item: item["score"], reverse=True)
        results = scored[: max(1, min(request.limit, 100))]

        yield event("thumbnails", 90, "Preparing thumbnails")
        for item in results:
            item["thumbnail_url"] = f"/api/images/{item['id']}/thumbnail"

        yield event("complete", 100, "Search complete", {"results": results})

    return StreamingResponse(events(), media_type="text/event-stream")


@app.get("/api/images/{image_id}/thumbnail")
def thumbnail(image_id: int) -> FileResponse:
    image = store.get_image(image_id)
    if not image:
        raise HTTPException(status_code=404, detail="Image not found")
    path = store.thumbnail_path(image_id)
    if not path.exists():
        raise HTTPException(status_code=404, detail="Thumbnail not found")
    return FileResponse(path)


@app.get("/api/images/{image_id}/open")
def open_image(image_id: int) -> dict[str, Any]:
    image = store.get_image(image_id)
    if not image:
        raise HTTPException(status_code=404, detail="Image not found")
    path = Path(image["path"])
    if not path.exists():
        raise HTTPException(status_code=404, detail="File no longer exists")
    if os.name == "nt":
        os.startfile(path)  # type: ignore[attr-defined]
    elif sys_platform() == "darwin":
        subprocess.Popen(["open", str(path)])
    else:
        subprocess.Popen(["xdg-open", str(path)])
    return {"opened": True}


@app.get("/api/images/{image_id}/reveal")
def reveal_image(image_id: int) -> dict[str, Any]:
    image = store.get_image(image_id)
    if not image:
        raise HTTPException(status_code=404, detail="Image not found")
    path = Path(image["path"])
    if not path.exists():
        raise HTTPException(status_code=404, detail="File no longer exists")
    if os.name == "nt":
        subprocess.Popen(["explorer", f"/select,{path}"])
    elif sys_platform() == "darwin":
        subprocess.Popen(["open", "-R", str(path)])
    else:
        subprocess.Popen(["xdg-open", str(path.parent)])
    return {"revealed": True}


def event(stage: str, progress: int, message: str, payload: dict[str, Any] | None = None) -> str:
    body = {"stage": stage, "progress": progress, "message": message}
    if payload:
        body.update(payload)
    return f"data: {json.dumps(body)}\n\n"


def without_embedding(row: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in row.items() if key != "embedding"}


def sys_platform() -> str:
    import sys

    return sys.platform
