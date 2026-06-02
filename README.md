# Local AI Image Search

An installable local-first PWA for searching photo folders with AI-style natural-language matching.

The frontend can be hosted from GitHub Pages or another static repo host. The Python backend runs locally on your machine because static hosting cannot read private folders or run local image indexing.

## What It Does

- Adds explicit local folders that you choose.
- Indexes image files and creates local thumbnails.
- Searches indexed images from natural-language prompts using a local CLIP model when installed.
- Shows real search progress stages in the UI.
- Shows app and backend version information.
- Lets you select results, view filename/path, open the image, or reveal it in its folder.

## Start The Local Backend

Use Python 3.11, 3.12, or 3.13. Python 3.14 is still too new for some Windows binary packages used by the backend.

## One-Click Windows Launcher

Double-click:

```text
start-ai-image-search.bat
```

The launcher creates the backend virtual environment if needed, installs dependencies, starts the backend and frontend in separate windows, then opens the PWA in your browser.

Keep the two service windows open while using the app.

The launcher starts the backend on `0.0.0.0:8765`, which allows other devices on your Wi-Fi to reach it at:

```text
http://YOUR-PC-LAN-IP:8765
```

On Windows, you may need to allow Python through the firewall when prompted.

## Manual Startup

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
pip install -r requirements-ai.txt
uvicorn app.main:app --host 127.0.0.1 --port 8765
```

The backend stores its local database and thumbnails in:

```text
%USERPROFILE%\.local-ai-image-search
```

You can override that with:

```powershell
$env:IMAGE_SEARCH_DATA_DIR="G:\AIImageSearchData"
uvicorn app.main:app --host 127.0.0.1 --port 8765
```

## Start The Frontend Locally

```powershell
npm install
npm run dev
```

Open the Vite URL shown in the terminal. The one-click launcher uses:

```text
http://127.0.0.1:5317
```

Manual `npm run dev` defaults to:

```text
http://127.0.0.1:5173
```

The backend health endpoint is:

```text
http://127.0.0.1:8765/api/health
```

## Build The Installable PWA

```powershell
npm run build
```

The static PWA is generated in `dist`.

## Deploy From GitHub Pages

For a repository hosted at `https://USERNAME.github.io/REPOSITORY/`, build with:

```powershell
$env:VITE_BASE_PATH="/REPOSITORY/"
npm run build
```

Then publish `dist` through your preferred GitHub Pages workflow.

Important: the deployed PWA still needs the local backend running on your computer to access your folders and search your images. Use `http://127.0.0.1:8765` on the same computer, or `http://YOUR-PC-LAN-IP:8765` from another device on your Wi-Fi.

### Phone Use

You can install the GitHub Pages frontend as a PWA on your phone, but the backend still runs on your PC.

Set the app's Backend URL field to your PC's LAN address:

```text
http://YOUR-PC-LAN-IP:8765
```

Some mobile browsers block `https://` GitHub Pages apps from calling an `http://` local-network backend. If that happens, use an HTTPS tunnel or reverse proxy for the backend, or run the frontend from your PC on the same network for local testing.

## Current AI Model

Version `0.1.0` uses a local CLIP model through `torch` and `transformers` when `backend/requirements-ai.txt` is installed. The default model is:

```text
openai/clip-vit-base-patch32
```

The first backend start may download the model. Search quality will be much better after you rebuild the index with CLIP active.

If the AI packages are not installed, the backend falls back to a lightweight color/texture adapter so the app still opens, but natural-language results will be poor.

No face recognition, no cloud upload, and no automatic folder scanning are included in v1.
