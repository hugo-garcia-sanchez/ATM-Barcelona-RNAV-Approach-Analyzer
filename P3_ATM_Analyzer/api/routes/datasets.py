from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
import pandas as pd

from ...config import get_settings
from ...database import get_db
from ...database import delete_upload, fetch_records, fetch_summary, fetch_upload, fetch_uploads
from ...schemas import DatasetRecordOut, DatasetSummary, InputFileInfo, UploadListItem, UploadResponse, DataResponseMVP, DataRecordMVP
from ...services.ingest import ingest_existing_file, ingest_upload
from ...data_processing.csv_loader import CSVLoader
from ...data_processing.asterix_processor import AsterixProcessor
from ...data_processing.flight_plan_loader import FlightPlanLoader
from ...geospatial.coordinate_transform import add_stereo_columns
from ...data_store import (
    set_current_data, get_current_data, get_current_filename,
    set_processed_data, get_processed_data,
    set_flight_plan, get_flight_plan,
)

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

    # Correct containment check — no "or" branch that widens the allowed set
    if not source_path.is_relative_to(upload_root):
        raise HTTPException(status_code=400, detail="Invalid file path")
    if not source_path.is_file() or source_path.suffix.lower() != ".csv":
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


# ============== MVP ENDPOINTS ==============

@router.post("/mvp/upload", response_model=dict[str, object])
async def mvp_upload(file: UploadFile = File(...)) -> dict[str, object]:
    """Upload and process radar CSV file using full ASTERIX pipeline."""
    try:
        content = await file.read()

        # 1. Load raw CSV and map ASTERIX columns
        loader = CSVLoader(file_content=content)
        df_raw = loader.load()
        rows_raw = len(df_raw)

        # Store raw data
        set_current_data(df_raw, filename=file.filename)

        # 2. Apply ASTERIX filters + QNH correction
        filters_applied = True
        try:
            df_processed = AsterixProcessor(df_raw).process()
        except Exception as exc:
            # Log failure explicitly so the caller knows filtering was skipped
            import logging as _logging
            _logging.getLogger(__name__).warning(
                "ASTERIX processing failed, returning raw data: %s", exc
            )
            df_processed = df_raw.copy()
            filters_applied = False

        rows_after_filters = len(df_processed)

        # 3. Add stereographic projection columns (x_m, y_m)
        try:
            df_processed = add_stereo_columns(df_processed)
        except Exception:
            pass  # non-critical; coords may be missing in test data

        # 4. Merge with flight plan if one is already loaded
        fp_df = get_flight_plan()
        if fp_df is not None:
            try:
                fp_loader = FlightPlanLoader()
                fp_loader.df = fp_df
                df_processed = fp_loader.merge_with_radar(df_processed)
            except Exception:
                pass  # merge is best-effort

        # Store processed data
        set_processed_data(df_processed)

        return {
            "status": "success",
            "filename": file.filename,
            "rows": rows_raw,
            "rows_after_filters": rows_after_filters,
            "columns": len(df_processed.columns),
            "filters_applied": filters_applied,
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Processing error: {str(e)}")


@router.post("/mvp/upload-flight-plan", response_model=dict[str, object])
async def mvp_upload_flight_plan(file: UploadFile = File(...)) -> dict[str, object]:
    """Upload flight plan CSV and optionally merge with already-loaded radar data."""
    try:
        content = await file.read()

        loader = FlightPlanLoader()
        fp_df = loader.load(file_content=content)

        # Store flight plan
        set_flight_plan(fp_df, filename=file.filename)

        # If radar data is already loaded, merge automatically
        merged_rows = None
        radar_df = get_processed_data()
        if radar_df is not None:
            try:
                merged = loader.merge_with_radar(radar_df)
                set_processed_data(merged)
                merged_rows = len(merged)
            except Exception:
                pass

        response: dict[str, object] = {
            "status": "success",
            "filename": file.filename,
            "rows": len(fp_df),
            "columns": len(fp_df.columns),
        }
        if merged_rows is not None:
            response["merged_radar_rows"] = merged_rows

        return response
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Processing error: {str(e)}")


@router.get("/mvp/data", response_model=DataResponseMVP)
def mvp_get_data(limit: int = 1000, offset: int = 0) -> DataResponseMVP:
    """Get current loaded raw data as table records."""
    df = get_current_data()

    if df is None:
        raise HTTPException(status_code=404, detail="No data loaded. Please upload a CSV first.")

    total_rows = len(df)
    end_idx = min(offset + limit, total_rows)
    slice_df = df.iloc[offset:end_idx]

    records = _df_to_mvp_records(slice_df)

    return DataResponseMVP(
        total_rows=total_rows,
        returned_rows=len(records),
        rows=records,
    )


@router.get("/mvp/processed", response_model=DataResponseMVP)
def mvp_get_processed(limit: int = 1000, offset: int = 0) -> DataResponseMVP:
    """Get post-filter processed data (ASTERIX filters + QNH correction + stereo coords)."""
    df = get_processed_data()

    if df is None:
        raise HTTPException(status_code=404, detail="No processed data available. Please upload a radar CSV first.")

    total_rows = len(df)
    end_idx = min(offset + limit, total_rows)
    slice_df = df.iloc[offset:end_idx]

    records = _df_to_mvp_records(slice_df)

    return DataResponseMVP(
        total_rows=total_rows,
        returned_rows=len(records),
        rows=records,
    )


@router.get("/mvp/info", response_model=dict[str, object])
def mvp_get_info() -> dict[str, object]:
    """Get info about current loaded data."""
    df = get_current_data()
    filename = get_current_filename()
    processed_df = get_processed_data()

    if df is None:
        return {
            "status": "empty",
            "rows": 0,
            "columns": 0,
            "filename": None,
        }

    return {
        "status": "loaded",
        "filename": filename or "unknown",
        "rows": len(df),
        "columns": len(df.columns),
        "rows_after_filters": len(processed_df) if processed_df is not None else None,
    }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _df_to_mvp_records(slice_df: pd.DataFrame) -> list[DataRecordMVP]:
    """Convert a DataFrame slice to a list of DataRecordMVP objects."""
    records = []
    for _, row in slice_df.iterrows():
        # callsign
        callsign = None
        for col in ["callsign", "registration", "tn", "ti"]:
            if col in row.index and pd.notna(row[col]):
                callsign = str(row[col])
                break

        # aircraft_id
        aircraft_id = None
        for col in ["aircraft_id", "icao", "mode3/a"]:
            if col in row.index and pd.notna(row[col]):
                aircraft_id = str(row[col])
                break

        # speed
        speed = None
        for col in ["speed", "ias", "ground_speed", "gs(kt)", "tas"]:
            if col in row.index and pd.notna(row[col]):
                try:
                    speed = float(row[col])
                    break
                except (ValueError, TypeError):
                    pass

        # altitude — prefer QNH-corrected value
        alt_val = 0.0
        for col in ["altitude_qnh_ft", "altitude"]:
            if col in row.index and pd.notna(row[col]):
                try:
                    alt_val = float(row[col])
                    break
                except (ValueError, TypeError):
                    pass

        record = DataRecordMVP(
            callsign=callsign,
            aircraft_id=aircraft_id,
            latitude=float(row["latitude"]),
            longitude=float(row["longitude"]),
            altitude=alt_val,
            time=pd.Timestamp(row["time"]).isoformat() if pd.notna(row.get("time")) else "",
            speed=speed,
        )
        records.append(record)
    return records
