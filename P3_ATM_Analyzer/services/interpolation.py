"""Interpolación a 1 s de las trayectorias radar.

Las muestras ASTERIX llegan ~cada 4 s (ventana antena). Para cazar el paso por
umbrales, separaciones mínimas, etc., se interpola a 1 Hz.

Reglas (PDF P3):
- (x, y): interpolación lineal entre muestra `t` y `t+4 s`.
- Altitud: integrada con IVV (ft/min) → `alt(t+n) = alt(t) + IVV*n/60`.
- HDG e IAS: constantes dentro de la ventana de 4 s.
- RA, TTA, GS, TAR: constantes dentro de una ventana de 16 s (4 muestras).
"""

from __future__ import annotations

from typing import Iterable

import numpy as np
import pandas as pd


# Columnas que se mantienen constantes durante la ventana de 4 s.
HOLD_4S_COLS = ("heading", "ias", "tas", "mach", "bp")

# Columnas que se mantienen constantes durante la ventana de 16 s.
HOLD_16S_COLS = ("roll_angle", "tta", "ground_speed_kt", "ground_speed", "tar")

# Columnas que se interpolan linealmente cuando existen.
LINEAR_COLS = ("x_m", "y_m", "latitude", "longitude")


def _ensure_datetime(series: pd.Series) -> pd.Series:
    if pd.api.types.is_datetime64_any_dtype(series):
        return series
    return pd.to_datetime(series, errors="coerce")


def interpolate_track(
    track: pd.DataFrame,
    *,
    freq_seconds: int = 1,
    hold_short_window_s: int = 4,
    hold_long_window_s: int = 16,
) -> pd.DataFrame:
    """Interpola una traza de un único callsign a `freq_seconds` segundos.

    Args:
        track: DataFrame con al menos `time` y posición. Debe pertenecer a un
               solo callsign / sector continuo.
        freq_seconds: paso de interpolación (1 s por defecto).
        hold_short_window_s: ventana de mantenimiento corto (HDG/IAS).
        hold_long_window_s: ventana de mantenimiento largo (RA/TTA/GS/TAR).

    Returns:
        DataFrame con índice DatetimeIndex y columnas interpoladas.
    """
    if track.empty or "time" not in track.columns:
        return track.iloc[0:0].copy()

    t = track.copy()
    t["time"] = _ensure_datetime(t["time"])
    t = t.dropna(subset=["time"]).sort_values("time")
    if t.empty:
        return t

    t = t.drop_duplicates(subset="time", keep="first").set_index("time")

    # Rango temporal a 1 Hz
    new_index = pd.date_range(
        start=t.index[0],
        end=t.index[-1],
        freq=f"{freq_seconds}s",
    )
    if len(new_index) == 0:
        return t.reset_index()

    # Reindex sobre la unión, interpola linealmente los numéricos pertinentes
    union_idx = t.index.union(new_index)
    out = t.reindex(union_idx)

    # 1) Interpolación lineal 2D (x, y) y geográfica
    for col in LINEAR_COLS:
        if col in out.columns:
            out[col] = out[col].astype(float).interpolate(
                method="time", limit_direction="both"
            )

    # 2) Altitud usando IVV (ft/min). Si no hay IVV o NaN, fallback a lineal.
    if "altitude" in out.columns:
        out["altitude"] = _altitude_from_ivv(out["altitude"], out.get("ivv"))
    if "altitude_qnh_ft" in out.columns:
        out["altitude_qnh_ft"] = _altitude_from_ivv(
            out["altitude_qnh_ft"], out.get("ivv")
        )
    if "fl" in out.columns:
        out["fl"] = out["fl"].astype(float).interpolate(
            method="time", limit_direction="both"
        )

    # 3) Hold columns: forward-fill dentro de la ventana correspondiente
    short_window = max(1, hold_short_window_s // freq_seconds)
    long_window = max(1, hold_long_window_s // freq_seconds)

    for col in HOLD_4S_COLS:
        if col in out.columns:
            out[col] = out[col].ffill(limit=short_window).bfill(limit=short_window)

    for col in HOLD_16S_COLS:
        if col in out.columns:
            out[col] = out[col].ffill(limit=long_window).bfill(limit=long_window)

    # 4) Identificadores y plan de vuelo: ffill/bfill sin límite
    static_cols = (
        "callsign", "aircraft_id", "target_address", "mode3a", "track_number",
        "sid", "runway", "runway_fp", "aircraft_type", "wake_cat",
        "wake_category", "atot", "destination", "stat",
    )
    for col in static_cols:
        if col in out.columns:
            out[col] = out[col].ffill().bfill()

    # Quedarse solo con las marcas a 1 Hz
    out = out.loc[new_index].copy()
    out.index.name = "time"
    return out.reset_index()


def _altitude_from_ivv(alt_series: pd.Series, ivv_series: pd.Series | None) -> pd.Series:
    """Reconstruye altitud entre muestras conocidas usando IVV (ft/min).

    Para cada NaN entre dos muestras válidas, integra la IVV de la muestra
    anterior. Si no hay IVV, cae a interpolación lineal.
    """
    alt = alt_series.astype(float).copy()
    if ivv_series is None or ivv_series.isna().all():
        return alt.interpolate(method="time", limit_direction="both")

    ivv = ivv_series.astype(float).ffill()
    times = alt.index

    # Localiza segmentos NaN delimitados por valores válidos.
    valid_mask = alt.notna()
    if not valid_mask.any():
        return alt

    last_valid_t = None
    last_valid_alt = None
    last_valid_ivv = None

    rebuilt = alt.copy()
    for i, ts in enumerate(times):
        if valid_mask.iloc[i]:
            last_valid_t = ts
            last_valid_alt = float(alt.iloc[i])
            last_valid_ivv = float(ivv.iloc[i]) if pd.notna(ivv.iloc[i]) else 0.0
            continue
        if last_valid_t is None:
            # Antes de la primera muestra válida, deja NaN
            continue
        dt_min = (ts - last_valid_t).total_seconds() / 60.0
        rebuilt.iloc[i] = last_valid_alt + last_valid_ivv * dt_min

    # Si quedan NaN al inicio (antes de la primera muestra válida), bfill.
    rebuilt = rebuilt.interpolate(method="time", limit_direction="backward")
    return rebuilt


def interpolate_dataset(
    df: pd.DataFrame,
    *,
    group_col: str = "callsign",
    freq_seconds: int = 1,
) -> pd.DataFrame:
    """Aplica `interpolate_track` por cada callsign y concatena."""
    if df.empty or group_col not in df.columns:
        return df.copy()

    parts: list[pd.DataFrame] = []
    for cs, sub in df.groupby(group_col, dropna=True, sort=False):
        interp = interpolate_track(sub, freq_seconds=freq_seconds)
        if not interp.empty:
            interp[group_col] = cs
            parts.append(interp)

    if not parts:
        return df.iloc[0:0].copy()
    return pd.concat(parts, ignore_index=True)


__all__ = ["interpolate_track", "interpolate_dataset"]
