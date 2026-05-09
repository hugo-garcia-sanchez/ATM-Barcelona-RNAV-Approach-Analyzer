"""Estadísticas agregadas sobre los DataFrames de análisis (separations, turns,
NADP, thresholds).

Funciones principales:
- `describe(df, metric, groupby=None)` → media, σ, p95, min, max, count.
- `violation_rate(df, flag_col, groupby=None)` → % filas donde `flag_col` es True.
- `compute_stats(...)` → entry point usado por la API: combina describe +
  violation_rate sobre un dataset y agrupación elegidos.

El módulo es independiente del origen del DataFrame (separations, turns, NADP,
thresholds…). El caller indica nombre del dataset y, si hace falta, derivar
columnas auxiliares como aerolínea (3 primeros chars del callsign).
"""

from __future__ import annotations

from typing import Iterable

import numpy as np
import pandas as pd

from .separations import compute_separations
from .turn_detection import compute_turns
from .nadp import compute_nadp
from .threshold_analysis import compute_thresholds


# Datasets disponibles -> función productora
DATASETS = {
    "separations": compute_separations,
    "turns": compute_turns,
    "nadp": compute_nadp,
    "thresholds": compute_thresholds,
}

# Sugerencia de columnas-flag de incumplimiento por dataset
DEFAULT_VIOLATION_COLS: dict[str, list[str]] = {
    "separations": ["radar_twr_loss", "wake_twr_loss", "wake_tma_loss", "loa_loss"],
    "turns": [],
    "nadp": [],
    "thresholds": ["turned_before_thr"],
}


def _airline_from_callsign(cs: str | None) -> str | None:
    if not cs or not isinstance(cs, str):
        return None
    s = cs.strip().upper()
    return s[:3] if len(s) >= 3 else s


def _ensure_groupby_cols(df: pd.DataFrame, cols: Iterable[str]) -> pd.DataFrame:
    """Añade columnas derivadas (airline) si las pide el caller."""
    if df.empty:
        return df
    out = df
    for c in cols:
        if c == "airline" and "airline" not in out.columns and "callsign" in out.columns:
            out = out.copy()
            out["airline"] = out["callsign"].map(_airline_from_callsign)
    return out


def describe(
    df: pd.DataFrame,
    metric: str,
    groupby: list[str] | None = None,
) -> list[dict[str, object]]:
    """Estadísticas básicas de una columna numérica, opcionalmente agrupada."""
    if df is None or df.empty or metric not in df.columns:
        return []

    df = _ensure_groupby_cols(df, groupby or [])
    series = pd.to_numeric(df[metric], errors="coerce")

    def _row(label_dict: dict[str, object], s: pd.Series) -> dict[str, object]:
        s = s.dropna()
        if s.empty:
            return {**label_dict, "count": 0, "mean": None, "std": None, "p95": None, "min": None, "max": None}
        return {
            **label_dict,
            "count": int(s.size),
            "mean": float(s.mean()),
            "std": float(s.std(ddof=0)) if s.size > 1 else 0.0,
            "p95": float(np.percentile(s, 95)),
            "min": float(s.min()),
            "max": float(s.max()),
        }

    if not groupby:
        return [_row({"group": "ALL"}, series)]

    out: list[dict[str, object]] = []
    grp = df.assign(_metric=series).groupby(groupby, dropna=False)
    for keys, sub in grp:
        if not isinstance(keys, tuple):
            keys = (keys,)
        labels = {col: (None if pd.isna(k) else k) for col, k in zip(groupby, keys)}
        out.append(_row(labels, sub["_metric"]))
    return out


def violation_rate(
    df: pd.DataFrame,
    flag_col: str,
    groupby: list[str] | None = None,
) -> list[dict[str, object]]:
    """% de filas donde `flag_col` es True (NaN se cuenta como False)."""
    if df is None or df.empty or flag_col not in df.columns:
        return []

    df = _ensure_groupby_cols(df, groupby or [])
    flags = df[flag_col].fillna(False).astype(bool)

    def _row(label_dict: dict[str, object], f: pd.Series) -> dict[str, object]:
        total = int(f.size)
        viol = int(f.sum())
        return {
            **label_dict,
            "total": total,
            "violations": viol,
            "pct_violations": round(100.0 * viol / total, 2) if total else 0.0,
        }

    if not groupby:
        return [_row({"group": "ALL", "flag": flag_col}, flags)]

    out: list[dict[str, object]] = []
    grp = df.assign(_flag=flags).groupby(groupby, dropna=False)
    for keys, sub in grp:
        if not isinstance(keys, tuple):
            keys = (keys,)
        labels = {col: (None if pd.isna(k) else k) for col, k in zip(groupby, keys)}
        labels["flag"] = flag_col
        out.append(_row(labels, sub["_flag"]))
    return out


def compute_stats(
    processed_df: pd.DataFrame,
    dataset: str,
    metric: str | None = None,
    groupby: list[str] | None = None,
    violation_col: str | None = None,
) -> dict[str, object]:
    """Entry point: ejecuta el pipeline `dataset` y devuelve estadísticas.

    - `metric`: columna numérica a describir (e.g. "radar_twr_nm", "delta_ias_kt").
    - `groupby`: lista de columnas o "airline" (se deriva del callsign).
    - `violation_col`: columna boolean a contar como % incumplimientos.

    Si no se indica `metric` ni `violation_col`, devuelve los flags por defecto
    del dataset.
    """
    if dataset not in DATASETS:
        raise ValueError(f"Unknown dataset '{dataset}'. Use one of: {list(DATASETS)}")

    df = DATASETS[dataset](processed_df)
    if df is None or df.empty:
        return {"dataset": dataset, "rows": 0, "metric": metric, "groupby": groupby, "stats": [], "violations": []}

    metric_stats = describe(df, metric, groupby) if metric else []

    viol_cols: list[str] = []
    if violation_col:
        viol_cols = [violation_col]
    elif metric is None:
        viol_cols = [c for c in DEFAULT_VIOLATION_COLS.get(dataset, []) if c in df.columns]

    viol_stats: list[dict[str, object]] = []
    for col in viol_cols:
        viol_stats.extend(violation_rate(df, col, groupby))

    return {
        "dataset": dataset,
        "rows": int(len(df)),
        "metric": metric,
        "groupby": groupby or [],
        "stats": metric_stats,
        "violations": viol_stats,
    }


__all__ = ["describe", "violation_rate", "compute_stats", "DATASETS", "DEFAULT_VIOLATION_COLS"]
