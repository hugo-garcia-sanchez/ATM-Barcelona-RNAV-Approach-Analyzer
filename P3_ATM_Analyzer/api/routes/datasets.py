from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile

from ...config import get_settings
from ...database import get_db
from ...database import delete_upload, fetch_records, fetch_summary, fetch_upload, fetch_uploads
from ...schemas import DatasetRecordOut, DatasetSummary, InputFileInfo, UploadListItem, UploadResponse
from ...services.ingest import ingest_existing_file, ingest_upload

router = APIRouter(prefix="/datasets", tags=["datasets"])


def _store_upload_file(upload_file: UploadFile, destination_dir: Path) -> Path:
    destination_dir.mkdir(parents=True, exist_ok=True)
    destination_path = destination_dir / (upload_file.filename or "upload")
    with destination_path.open("wb") as target_file:
        target_file.write(upload_file.file.read())
    return destination_path


@router.get("", response_model=list[UploadListItem])
def list_uploads(db=Depends(get_db)) -> list[dict[str, object]]:
    return fetch_uploads(db)


@router.get("/input-files", response_model=list[InputFileInfo])
def list_input_files() -> list[dict[str, object]]:
    settings = get_settings()
    files = sorted(settings.upload_dir.glob("*.csv"))
    return [{"filename": path.name, "size_bytes": path.stat().st_size} for path in files]


@router.post("/upload", response_model=UploadResponse)
def upload_dataset(upload_file: UploadFile = File(...), db=Depends(get_db)) -> dict[str, object]:
    settings = get_settings()
    suffix = Path(upload_file.filename or "").suffix.lower()
    if suffix != ".csv":
        raise HTTPException(status_code=400, detail="Only CSV files are supported with the current dependency set")

    stored_path = _store_upload_file(upload_file, settings.upload_dir)
    return ingest_upload(db, upload_file, stored_path)


@router.post("/import-existing/{filename}", response_model=UploadResponse)
def import_existing_dataset(filename: str, db=Depends(get_db)) -> dict[str, object]:
    settings = get_settings()
    source_path = (settings.upload_dir / filename).resolve()
    upload_root = settings.upload_dir.resolve()

    if upload_root not in source_path.parents and source_path != upload_root:
        raise HTTPException(status_code=400, detail="Invalid file path")
    if not source_path.exists() or source_path.suffix.lower() != ".csv":
        raise HTTPException(status_code=404, detail="CSV file not found in inputs folder")

    return ingest_existing_file(db, source_path)


@router.get("/{upload_id}", response_model=UploadResponse)
def get_upload(upload_id: int, db=Depends(get_db)) -> dict[str, object]:
    upload = fetch_upload(db, upload_id)
    if upload is None:
        raise HTTPException(status_code=404, detail="Upload not found")
    return upload


@router.get("/{upload_id}/summary", response_model=DatasetSummary)
def get_summary(upload_id: int, db=Depends(get_db)) -> DatasetSummary:
    summary = fetch_summary(db, upload_id)
    if summary is None:
        raise HTTPException(status_code=404, detail="Upload not found")
    return DatasetSummary(**summary)


@router.get("/{upload_id}/records", response_model=list[DatasetRecordOut])
def list_records(upload_id: int, limit: int = 100, offset: int = 0, db=Depends(get_db)) -> list[dict[str, object]]:
    return fetch_records(db, upload_id, limit=limit, offset=offset)


@router.delete("/{upload_id}")
def remove_upload(upload_id: int, db=Depends(get_db)) -> dict[str, bool]:
    upload = fetch_upload(db, upload_id)
    if upload is None:
        raise HTTPException(status_code=404, detail="Upload not found")

    stored_path = Path(upload["stored_path"])
    if stored_path.exists():
        stored_path.unlink()

    delete_upload(db, upload_id)
    return {"deleted": True}