"""Carga automática de los ficheros por defecto al arrancar la aplicación.

Lee de `data/inputs/` (relativo al runtime root del proyecto) los siguientes
ficheros si existen:

- `Tabla_Clasificacion_aeronaves.xlsx`  (clasificación motor)
- `Tabla_misma_SID_24L.xlsx`            (familias SID 24L)
- `Tabla_misma_SID_06R.xlsx`            (familias SID 06R)
- `P3_DEP_LEBL.xlsx`                    (plan de vuelo)
- `P3_*.csv`                             (radar)

El bootstrap es best-effort: cualquier fallo se loguea pero no aborta el
arranque del servidor.
"""
from __future__ import annotations

from pathlib import Path
import logging

from ..config import get_runtime_root
from ..data_processing.reference_loader import apply_reference_files
from ..data_processing.flight_plan_loader import FlightPlanLoader
from ..data_processing.csv_loader import CSVLoader
from ..data_processing.asterix_processor import AsterixProcessor
from ..geospatial.coordinate_transform import add_stereo_columns
from ..data_store import (
    set_current_data,
    set_processed_data,
    set_flight_plan,
    get_processed_data,
)

logger = logging.getLogger(__name__)


def project_inputs_dir() -> Path:
    return get_runtime_root() / "data" / "inputs"


def bootstrap_inputs() -> dict[str, object]:
    """Carga referencias + plan de vuelo + radar por defecto. Devuelve un resumen."""
    inputs = project_inputs_dir()
    summary: dict[str, object] = {"inputs_dir": str(inputs)}

    if not inputs.exists():
        logger.info("No project inputs dir at %s — skipping bootstrap", inputs)
        return summary

    # 1) Referencias (aeronaves + SIDs)
    summary["reference"] = apply_reference_files(inputs)

    # 2) Plan de vuelo (xlsx preferente)
    fp_path = next(
        (inputs / n for n in ("P3_DEP_LEBL.xlsx", "P3_DEP_LEBL.xls", "P3_DEP_LEBL.csv") if (inputs / n).exists()),
        None,
    )
    fp_loader = FlightPlanLoader()
    if fp_path is not None:
        try:
            fp_df = fp_loader.load(file_path=str(fp_path))
            set_flight_plan(fp_df, filename=fp_path.name)
            summary["flight_plan"] = {"file": fp_path.name, "rows": len(fp_df)}
            logger.info("Flight plan loaded: %s (%d rows)", fp_path.name, len(fp_df))
        except Exception as exc:
            logger.warning("Bootstrap flight plan failed: %s", exc)
            summary["flight_plan_error"] = str(exc)

    # 3) Radar (primer CSV que encuentre)
    radar_path = next(iter(sorted(inputs.glob("P3_*.csv"))), None)
    if radar_path is not None:
        try:
            content = radar_path.read_bytes()
            df_raw = CSVLoader(file_content=content).load()
            set_current_data(df_raw, filename=radar_path.name)
            try:
                df_proc = AsterixProcessor(df_raw).process()
            except Exception as exc:
                logger.warning("Asterix processing failed during bootstrap: %s", exc)
                df_proc = df_raw.copy()
            try:
                df_proc = add_stereo_columns(df_proc)
            except Exception:
                pass
            # Merge con plan si está disponible
            if fp_loader.df is not None:
                try:
                    df_proc = fp_loader.merge_with_radar(df_proc)
                except Exception as exc:
                    logger.warning("Bootstrap merge failed: %s", exc)
            set_processed_data(df_proc)
            summary["radar"] = {
                "file": radar_path.name,
                "rows_raw": len(df_raw),
                "rows_after_filters": len(df_proc),
            }
            logger.info(
                "Radar dataset bootstrapped: %s (raw=%d, processed=%d)",
                radar_path.name, len(df_raw), len(df_proc),
            )
        except Exception as exc:
            logger.warning("Bootstrap radar failed: %s", exc)
            summary["radar_error"] = str(exc)

    return summary
