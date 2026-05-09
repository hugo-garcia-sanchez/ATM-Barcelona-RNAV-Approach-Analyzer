"""Carga de tablas de referencia (clasificación de aeronaves, familias SID)
desde los xlsx de `data/inputs/`.

Permite sustituir en caliente los valores hardcodeados de
`services.reference_tables` por los proporcionados por el cliente.
"""
from __future__ import annotations

from pathlib import Path
import logging

import pandas as pd

from ..services import reference_tables as rt

logger = logging.getLogger(__name__)


def load_aircraft_classification(path: Path) -> dict[str, str]:
    """Lee `Tabla_Clasificacion_aeronaves.xlsx` (columnas: HP, NR, NR+, NR-, LP)
    y devuelve {tipo_icao: clase_motor}.
    """
    df = pd.read_excel(path, sheet_name=0)
    out: dict[str, str] = {}
    for col in df.columns:
        cls = str(col).strip().upper()
        if cls not in rt.ENGINE_CLASSES:
            continue
        for v in df[col].dropna().astype(str):
            t = v.strip().upper()
            if t:
                out[t] = cls
    return out


def _strip_runway_suffix(name: str) -> str:
    """'LARPA-C' -> 'LARPA'  ;  'OLOXO-R' -> 'OLOXO'."""
    s = str(name).strip().upper()
    if "-" in s:
        s = s.split("-", 1)[0]
    return s


def load_sid_families(path: Path) -> dict[str, list[str]]:
    """Lee un xlsx con columnas Misma_SID_G1/G2/G3 y devuelve
    {grupo: [sid_root,...]}.
    """
    df = pd.read_excel(path, sheet_name=0)
    families: dict[str, list[str]] = {}
    for col in df.columns:
        key = str(col).strip()
        if not key.upper().startswith("MISMA_SID"):
            continue
        sids = [_strip_runway_suffix(v) for v in df[col].dropna().astype(str) if str(v).strip()]
        if sids:
            families[key.upper()] = sids
    return families


def apply_reference_files(inputs_dir: Path) -> dict[str, object]:
    """Carga los xlsx de referencia presentes en `inputs_dir` y actualiza los
    diccionarios globales de `reference_tables`.

    Devuelve un resumen con los ficheros cargados.
    """
    summary: dict[str, object] = {}

    ac_path = inputs_dir / "Tabla_Clasificacion_aeronaves.xlsx"
    if ac_path.exists():
        try:
            mapping = load_aircraft_classification(ac_path)
            rt.AIRCRAFT_CLASS.clear()
            rt.AIRCRAFT_CLASS.update(mapping)
            summary["aircraft_classification"] = {"file": ac_path.name, "rows": len(mapping)}
            logger.info("Aircraft classification loaded: %d types", len(mapping))
        except Exception as exc:
            logger.warning("Failed to load aircraft classification: %s", exc)
            summary["aircraft_classification_error"] = str(exc)

    sid24_path = inputs_dir / "Tabla_misma_SID_24L.xlsx"
    if sid24_path.exists():
        try:
            fam = load_sid_families(sid24_path)
            rt.SID_FAMILIES_24L.clear()
            rt.SID_FAMILIES_24L.update(fam)
            summary["sid_families_24L"] = {"file": sid24_path.name, "groups": list(fam.keys())}
            logger.info("SID families 24L loaded: %d groups", len(fam))
        except Exception as exc:
            logger.warning("Failed to load SID families 24L: %s", exc)
            summary["sid_families_24L_error"] = str(exc)

    sid06_path = inputs_dir / "Tabla_misma_SID_06R.xlsx"
    if sid06_path.exists():
        try:
            fam = load_sid_families(sid06_path)
            rt.SID_FAMILIES_06R.clear()
            rt.SID_FAMILIES_06R.update(fam)
            summary["sid_families_06R"] = {"file": sid06_path.name, "groups": list(fam.keys())}
            logger.info("SID families 06R loaded: %d groups", len(fam))
        except Exception as exc:
            logger.warning("Failed to load SID families 06R: %s", exc)
            summary["sid_families_06R_error"] = str(exc)

    return summary
