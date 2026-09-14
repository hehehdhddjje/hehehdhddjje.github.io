from __future__ import annotations

import asyncio
import os
import threading
import uuid
import webbrowser
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

import yt_dlp
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, HttpUrl

BASE_DIR = Path(__file__).resolve().parent
DOWNLOAD_DIR = BASE_DIR / "downloads"
TEMPLATES_DIR = BASE_DIR / "templates"
DOWNLOAD_DIR.mkdir(exist_ok=True)

# État en mémoire : adapté à une application locale monoposte.
jobs: dict[str, dict[str, Any]] = {}


class DownloadRequest(BaseModel):
    url: HttpUrl
    quality: str = "best"


QUALITY_FORMATS = {
    "best": "bestvideo*+bestaudio/best",
    "1080p": "bestvideo[height<=1080]+bestaudio/best[height<=1080]",
    "720p": "bestvideo[height<=720]+bestaudio/best[height<=720]",
}


def public_download_name(path: Path) -> str:
    return path.relative_to(DOWNLOAD_DIR).as_posix()


def list_downloads() -> list[dict[str, Any]]:
    supported = {".mp4", ".webm", ".mkv", ".mov", ".avi", ".mp3", ".m4a", ".ogg", ".wav"}
    files = []
    for path in DOWNLOAD_DIR.iterdir():
        if path.is_file() and path.suffix.lower() in supported:
            files.append(
                {
                    "name": path.name,
                    "url": f"/media/{public_download_name(path)}",
                    "size": path.stat().st_size,
                    "modified": path.stat().st_mtime,
                    "is_audio": path.suffix.lower() in {".mp3", ".m4a", ".ogg", ".wav"},
                }
            )
    return sorted(files, key=lambda item: item["modified"], reverse=True)


def progress_hook(job_id: str):
    def hook(data: dict[str, Any]) -> None:
        job = jobs.get(job_id)
        if not job:
            return
        status = data.get("status")
        if status == "downloading":
            job["status"] = "downloading"
            job["downloaded"] = data.get("downloaded_bytes", 0)
            job["total"] = data.get("total_bytes") or data.get("total_bytes_estimate") or 0
            job["percent"] = data.get("_percent_str", "0%")
            job["speed"] = data.get("_speed_str", "-")
            job["eta"] = data.get("_eta_str", "-")
        elif status == "finished":
            job["status"] = "processing"
            job["percent"] = "100%"
            job["message"] = "Finalisation du fichier…"

    return hook


def run_download(job_id: str, url: str, quality: str) -> None:
    job = jobs[job_id]
    is_audio = quality == "audio"
    options: dict[str, Any] = {
        "outtmpl": str(DOWNLOAD_DIR / "%(title).200s [%(id)s].%(ext)s"),
        "noplaylist": False,
        "quiet": True,
        "no_warnings": True,
        "progress_hooks": [progress_hook(job_id)],
        "retries": 3,
        "fragment_retries": 3,
        "ignoreerrors": False,
    }
    if is_audio:
        options.update(
            {
                "format": "bestaudio/best",
                "postprocessors": [
                    {
                        "key": "FFmpegExtractAudio",
                        "preferredcodec": "mp3",
                        "preferredquality": "192",
                    }
                ],
            }
        )
    else:
        options.update(
            {
                "format": QUALITY_FORMATS.get(quality, QUALITY_FORMATS["best"]),
                "merge_output_format": "mp4",
            }
        )

    try:
        job["status"] = "starting"
        with yt_dlp.YoutubeDL(options) as downloader:
            downloader.download([url])
        job.update({"status": "completed", "percent": "100%", "message": "Téléchargement terminé."})
    except Exception as exc:
        job.update({"status": "error", "message": str(exc)[:500]})


@asynccontextmanager
async def lifespan(_: FastAPI):
    # L'ouverture est différée pour laisser Uvicorn commencer à écouter.
    asyncio.get_running_loop().call_later(1.0, lambda: webbrowser.open("http://127.0.0.1:8000"))
    yield


app = FastAPI(title="yt-dlp Enhanced Mod", lifespan=lifespan)
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))


@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


@app.get("/api/files")
async def files():
    return {"files": list_downloads()}


@app.post("/api/download")
async def start_download(payload: DownloadRequest):
    if payload.quality not in {"best", "1080p", "720p", "audio"}:
        raise HTTPException(status_code=400, detail="Qualité non supportée.")
    job_id = uuid.uuid4().hex
    jobs[job_id] = {
        "id": job_id,
        "url": str(payload.url),
        "quality": payload.quality,
        "status": "queued",
        "percent": "0%",
        "downloaded": 0,
        "total": 0,
        "speed": "-",
        "eta": "-",
        "message": "En attente…",
    }
    threading.Thread(target=run_download, args=(job_id, str(payload.url), payload.quality), daemon=True).start()
    return {"job_id": job_id}


@app.get("/api/jobs/{job_id}")
async def job_status(job_id: str):
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail="Téléchargement introuvable.")
    return jobs[job_id]


@app.get("/media/{file_path:path}")
async def media(file_path: str):
    requested = (DOWNLOAD_DIR / file_path).resolve()
    if DOWNLOAD_DIR.resolve() not in requested.parents or not requested.is_file():
        raise HTTPException(status_code=404, detail="Fichier introuvable.")
    return FileResponse(requested)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app:app", host="127.0.0.1", port=8000, reload=False)
