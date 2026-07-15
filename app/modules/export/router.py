import os
import json

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from app.scraper.emulator_parser import process_emulator_json

from . import service

router = APIRouter(prefix="/api/v1/compiled-jsons", tags=["export"])


@router.get("")
def list_compiled_jsons():
    os.makedirs(service.COMPILED_FOLDER, exist_ok=True)

    files = []
    for filename in os.listdir(service.COMPILED_FOLDER):
        if filename.endswith(".json"):
            path = os.path.join(service.COMPILED_FOLDER, filename)
            stat = os.stat(path)
            files.append({
                "filename": filename,
                "size_bytes": stat.st_size,
                "modified": stat.st_mtime
            })

    files.sort(key=lambda x: x["modified"], reverse=True)
    return files


@router.get("/{filename}")
def download_compiled_json(filename: str):
    try:
        path = service.resolve_safe_path(filename)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid file path.")

    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="File not found.")

    return FileResponse(path, filename=filename, media_type="application/json")


@router.delete("/{filename}")
def delete_compiled_json(filename: str):
    try:
        path = service.resolve_safe_path(filename)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid file path.")

    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="File not found.")

    try:
        os.remove(path)
        return {"status": "deleted", "message": f"Deleted {filename} successfully."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{filename}/ingest")
def ingest_compiled_json(filename: str):
    try:
        path = service.resolve_safe_path(filename)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid file path.")

    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="File not found.")

    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)

        # Try to infer district from filename (e.g. Thiruvananthapuram_Fast Food_Compiled.json)
        district = "Unknown"
        if "_" in filename:
            district = filename.split("_")[0]

        count = process_emulator_json(data, district)
        return {"status": "success", "message": f"Successfully ingested {count} listings from {filename}.", "count": count}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to ingest: {str(e)}")
