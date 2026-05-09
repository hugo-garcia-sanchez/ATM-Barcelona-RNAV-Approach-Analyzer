from __future__ import annotations

import logging
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
import numpy as np
import pandas as pd

from ...config import get_settings
from ...database import get_db
from ...database import delete_upload, fetch_records, fetch_summary, fetch_upload, fetch_uploads
from ...schemas import DatasetRecordOut, DatasetSummary, InputFileInfo, UploadListItem, UploadResponse, DataResponseMVP, DataRecordMVP
from ...services.ingest import ingest_existing_file, ingest_upload
from ...services import separations as separations_svc
from ...services import turn_detection as turn_svc
from ...services import nadp as nadp_svc
from ...services import threshold_analysis as threshold_svc
from ...services import stats as stats_svc
from fastapi import Query
from fastapi.responses import PlainTextResponse
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
logger = logging.getLogger(__name__)


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
            logger.warning("ASTERIX processing failed, returning raw data: %s", exc)
            df_processed = df_raw.copy()
            filters_applied = False

        rows_after_filters = len(df_processed)

        # 3. Add stereographic projection columns (x_m, y_m)
        try:
            df_processed = add_stereo_columns(df_processed)
        except Exception:
            pass  # non-critical; coords may be missing in test data

        # 4. Merge with flight plan if one is already loaded
        merge_warning = None
        fp_df = get_flight_plan()
        if fp_df is not None:
            try:
                fp_loader = FlightPlanLoader()
                fp_loader.df = fp_df
                df_processed = fp_loader.merge_with_radar(df_processed)
            except Exception as exc:
                merge_warning = str(exc)
                logger.warning("Flight plan merge failed during radar upload: %s", exc)

        # Store processed data
        set_processed_data(df_processed)

        response_body: dict[str, object] = {
            "status": "success",
            "filename": file.filename,
            "rows": rows_raw,
            "rows_after_filters": rows_after_filters,
            "columns": len(df_processed.columns),
            "filters_applied": filters_applied,
        }
        if merge_warning:
            response_body["merge_warning"] = merge_warning
        return response_body
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
        merge_warning = None
        radar_df = get_processed_data()
        if radar_df is not None:
            try:
                merged = loader.merge_with_radar(radar_df)
                set_processed_data(merged)
                merged_rows = len(merged)
            except Exception as exc:
                merge_warning = str(exc)
                logger.warning("Flight plan merge failed during flight-plan upload: %s", exc)

        response: dict[str, object] = {
            "status": "success",
            "filename": file.filename,
            "rows": len(fp_df),
            "columns": len(fp_df.columns),
        }
        if merged_rows is not None:
            response["merged_radar_rows"] = merged_rows
        if merge_warning:
            response["merge_warning"] = merge_warning

        return response
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Processing error: {str(e)}")


@router.get("/mvp/data", response_model=DataResponseMVP)
def mvp_get_data(limit: int = 1000, offset: int = 0) -> DataResponseMVP:
    """Get current loaded raw data as table records."""
    if limit < 1 or limit > 10_000:
        raise HTTPException(status_code=400, detail="limit must be between 1 and 10000")
    if offset < 0:
        raise HTTPException(status_code=400, detail="offset must be non-negative")

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
    if limit < 1 or limit > 10_000:
        raise HTTPException(status_code=400, detail="limit must be between 1 and 10000")
    if offset < 0:
        raise HTTPException(status_code=400, detail="offset must be non-negative")

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


@router.get("/mvp/separations", response_model=dict[str, object])
def mvp_get_separations(format: str = "json") -> dict[str, object] | PlainTextResponse:
    """Calcula separaciones radar/estela/LoA entre despegues consecutivos.

    Query params:
        format: "json" (default) o "csv"
    """
    df = get_processed_data()
    if df is None or df.empty:
        raise HTTPException(status_code=404, detail="No processed data available. Upload a radar CSV first.")

    try:
        result_df = separations_svc.compute_separations(df)
    except Exception as exc:
        logger.exception("Separation computation failed")
        raise HTTPException(status_code=500, detail=f"Separation computation error: {exc}")

    if format.lower() == "csv":
        csv_text = separations_svc.to_csv(result_df)
        return PlainTextResponse(content=csv_text, media_type="text/csv")

    if result_df.empty:
        return {"total_pairs": 0, "rows": []}

    rows = result_df.replace({np.nan: None}).to_dict(orient="records")
    return {
        "total_pairs": len(rows),
        "metrics": {
            "radar_twr_losses": int(result_df["radar_twr_loss"].fillna(False).sum()),
            "wake_twr_losses": int(result_df["wake_twr_loss"].fillna(False).sum()),
            "wake_tma_losses": int(result_df["wake_tma_loss"].fillna(False).sum()),
            "loa_losses": int(result_df["loa_loss"].fillna(False).sum()),
        },
        "rows": rows,
    }


@router.get("/mvp/turns", response_model=dict[str, object])
def mvp_get_turns(format: str = "json") -> dict[str, object] | PlainTextResponse:
    """Detecta el inicio del viraje para despegues 24L.

    Query params:
        format: "json" (default) o "csv"
    """
    df = get_processed_data()
    if df is None or df.empty:
        raise HTTPException(status_code=404, detail="No processed data available. Upload a radar CSV first.")

    try:
        result_df = turn_svc.compute_turns(df)
    except Exception as exc:
        logger.exception("Turn detection failed")
        raise HTTPException(status_code=500, detail=f"Turn detection error: {exc}")

    if format.lower() == "csv":
        return PlainTextResponse(content=turn_svc.to_csv(result_df), media_type="text/csv")

    if result_df.empty:
        return {"total_departures": 0, "rows": []}

    rows = result_df.replace({np.nan: None}).to_dict(orient="records")
    detected = int(result_df["turn_start_time"].notna().sum())
    crosses = int(result_df["crosses_r234"].fillna(False).sum())
    return {
        "total_departures": len(rows),
        "metrics": {
            "turns_detected": detected,
            "crosses_r234": crosses,
        },
        "rows": rows,
    }


@router.get("/mvp/nadp", response_model=dict[str, object])
def mvp_get_nadp(format: str = "json", threshold_kt: float = 30.0) -> dict[str, object] | PlainTextResponse:
    """Clasifica cada despegue 24L como NADP1 (acelera tarde) o NADP2 (acelera pronto).

    Query params:
        format: "json" (default) o "csv"
        threshold_kt: umbral ΔIAS para distinguir NADP1/NADP2 (default 30 kt)
    """
    df = get_processed_data()
    if df is None or df.empty:
        raise HTTPException(status_code=404, detail="No processed data available. Upload a radar CSV first.")

    try:
        result_df = nadp_svc.compute_nadp(df, threshold_kt=threshold_kt)
    except Exception as exc:
        logger.exception("NADP classification failed")
        raise HTTPException(status_code=500, detail=f"NADP classification error: {exc}")

    if format.lower() == "csv":
        return PlainTextResponse(content=nadp_svc.to_csv(result_df), media_type="text/csv")

    if result_df.empty:
        return {"total_departures": 0, "rows": []}

    rows = result_df.replace({np.nan: None}).to_dict(orient="records")
    nadp1 = int((result_df["nadp"] == "NADP1").sum())
    nadp2 = int((result_df["nadp"] == "NADP2").sum())
    return {
        "total_departures": len(rows),
        "threshold_kt": threshold_kt,
        "metrics": {
            "nadp1": nadp1,
            "nadp2": nadp2,
            "unclassified": len(rows) - nadp1 - nadp2,
        },
        "rows": rows,
    }


@router.get("/mvp/thresholds", response_model=dict[str, object])
def mvp_get_thresholds(format: str = "json") -> dict[str, object] | PlainTextResponse:
    """Análisis sobre cabeceras 24L/06R: IAS, alt y % giro antes del THR.

    Query params:
        format: "json" (default) o "csv"
    """
    df = get_processed_data()
    if df is None or df.empty:
        raise HTTPException(status_code=404, detail="No processed data available. Upload a radar CSV first.")

    try:
        result_df = threshold_svc.compute_thresholds(df)
    except Exception as exc:
        logger.exception("Threshold analysis failed")
        raise HTTPException(status_code=500, detail=f"Threshold analysis error: {exc}")

    if format.lower() == "csv":
        return PlainTextResponse(content=threshold_svc.to_csv(result_df), media_type="text/csv")

    if result_df.empty:
        return {"total": 0, "rows": [], "summary": {}}

    rows = result_df.replace({np.nan: None}).to_dict(orient="records")
    return {
        "total": len(rows),
        "summary": threshold_svc.summary_metrics(result_df),
        "rows": rows,
    }


@router.get("/mvp/stats", response_model=dict[str, object])
def mvp_get_stats(
    dataset: str = Query("separations", description="Dataset: separations|turns|nadp|thresholds"),
    metric: str | None = Query(None, description="Columna numérica a describir"),
    groupby: str | None = Query(None, description="Columnas separadas por coma (sid,airline,aircraft_type,wake,runway,...)"),
    violation_col: str | None = Query(None, description="Columna boolean para % incumplimientos"),
) -> dict[str, object]:
    """Estadísticas (media, σ, p95, min, max, % incumplimientos) sobre cualquiera
    de los pipelines, agrupables por SID, aerolínea, tipo de aeronave, estela, etc.
    """
    df = get_processed_data()
    if df is None or df.empty:
        raise HTTPException(status_code=404, detail="No processed data available. Upload a radar CSV first.")

    gb = [c.strip() for c in groupby.split(",")] if groupby else None

    try:
        return stats_svc.compute_stats(
            df,
            dataset=dataset,
            metric=metric,
            groupby=gb,
            violation_col=violation_col,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        logger.exception("Stats computation failed")
        raise HTTPException(status_code=500, detail=f"Stats error: {exc}")


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

def _pick_str(row: pd.Series, *cols: str) -> str | None:
    for c in cols:
        if c in row.index and pd.notna(row[c]):
            return str(row[c])
    return None


def _pick_float(row: pd.Series, *cols: str) -> float | None:
    for c in cols:
        if c in row.index and pd.notna(row[c]):
            try:
                return float(row[c])
            except (ValueError, TypeError):
                continue
    return None


def _pick_int(row: pd.Series, *cols: str) -> int | None:
    v = _pick_float(row, *cols)
    return int(v) if v is not None else None


def _df_to_mvp_records(slice_df: pd.DataFrame) -> list[DataRecordMVP]:
    """Volcado completo de un slice de DataFrame a DataRecordMVP."""
    records: list[DataRecordMVP] = []
    for _, row in slice_df.iterrows():
        alt_val = _pick_float(row, "altitude_qnh_ft", "altitude", "h_ft") or 0.0
        time_val = (
            pd.Timestamp(row["time"]).isoformat()
            if "time" in row.index and pd.notna(row.get("time"))
            else ""
        )
        atot_val = (
            pd.Timestamp(row["atot"]).isoformat()
            if "atot" in row.index and pd.notna(row.get("atot"))
            else _pick_str(row, "atot")
        )

        records.append(DataRecordMVP(
            callsign=_pick_str(row, "callsign", "registration"),
            aircraft_id=_pick_str(row, "aircraft_id", "icao", "registration"),
            target_address=_pick_str(row, "target_address"),
            mode3a=_pick_str(row, "mode3a"),
            track_number=_pick_int(row, "track_number"),
            latitude=float(row["latitude"]),
            longitude=float(row["longitude"]),
            altitude=alt_val,
            altitude_qnh_ft=_pick_float(row, "altitude_qnh_ft"),
            fl=_pick_float(row, "fl"),
            x_m=_pick_float(row, "x_m"),
            y_m=_pick_float(row, "y_m"),
            time=time_val,
            speed=_pick_float(row, "speed", "ias", "ground_speed_kt", "tas"),
            ias=_pick_float(row, "ias"),
            tas=_pick_float(row, "tas"),
            ground_speed=_pick_float(row, "ground_speed_kt", "ground_speed"),
            mach=_pick_float(row, "mach"),
            heading=_pick_float(row, "heading"),
            tta=_pick_float(row, "tta"),
            roll_angle=_pick_float(row, "roll_angle"),
            tar=_pick_float(row, "tar"),
            bp=_pick_float(row, "bp"),
            ivv=_pick_float(row, "ivv"),
            baro_alt_rate=_pick_float(row, "baro_alt_rate"),
            stat=_pick_str(row, "stat"),
            sid=_pick_str(row, "sid"),
            runway=_pick_str(row, "runway_fp", "runway"),
            aircraft_type=_pick_str(row, "aircraft_type"),
            wake_category=_pick_str(row, "wake_cat"),
            atot=atot_val,
            destination=_pick_str(row, "destination"),
        ))
    return records
