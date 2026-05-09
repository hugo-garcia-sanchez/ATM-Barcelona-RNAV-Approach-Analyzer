"""Detección del inicio de viraje para despegues por la 24L.

Reglas (PDF P3, pág. 55):
- Solo despegues 24L.
- Inicio del viraje: primer instante en que la aeronave deja de mantener
  rumbo de pista. Se detecta por:
    * cambio sostenido de Roll Angle (RA) por encima de un umbral, o
    * derivada del TTA / HDG por encima de un umbral (rate of turn).
- Para cada despegue se devuelve lat/lon/alt/time del inicio.
- Adicionalmente se chequea si la trayectoria 2D cruza la radial R-234
  trazada desde el DVOR BCN hasta su extremo en costa.
"""

from __future__ import annotations

import io
import math
from dataclasses import dataclass, asdict

import numpy as np
import pandas as pd

from . import reference_tables as rt
from .separations import build_departures, haversine_nm, Departure


# ---------------------------------------------------------------------------
# Umbrales de detección
# ---------------------------------------------------------------------------
# Rumbo de pista 24L ≈ 238° (224° magnético + ~14° declinación inversa). Usamos
# una banda alrededor del rumbo nominal mientras sea válido considerar que la
# aeronave aún no ha virado.
RUNWAY_HDG_24L = 238.0
HDG_BAND_DEG = 8.0          # ±8° alrededor del rumbo de pista
ROLL_THRESHOLD_DEG = 5.0    # |RA| ≥ 5° → empieza a virar
TURN_RATE_THRESHOLD_DPS = 1.5  # |dHDG/dt| ≥ 1.5°/s → viraje
MIN_HOLD_SAMPLES = 3        # Debe mantenerse al menos 3 segundos


@dataclass
class TurnEvent:
    callsign: str
    runway: str
    sid: str | None
    aircraft_type: str | None
    atot: str | None
    turn_start_time: str | None
    turn_start_lat: float | None
    turn_start_lon: float | None
    turn_start_alt_ft: float | None
    turn_start_ias_kt: float | None
    turn_start_dist_thr_nm: float | None
    detection_method: str | None         # "roll", "turn_rate", "hdg_deviation"
    crosses_r234: bool | None
    r234_cross_lat: float | None
    r234_cross_lon: float | None


# ---------------------------------------------------------------------------
# Helpers geométricos
# ---------------------------------------------------------------------------

def _angle_diff_deg(a: float, b: float) -> float:
    """Diferencia angular mínima en grados (-180, 180]."""
    d = (a - b + 540.0) % 360.0 - 180.0
    return d


def _segments_intersect(
    p1: tuple[float, float], p2: tuple[float, float],
    q1: tuple[float, float], q2: tuple[float, float],
) -> tuple[float, float] | None:
    """Intersección de dos segmentos 2D en lat/lon. Devuelve el punto o None.

    Implementación clásica con producto cruzado paramétrico.
    """
    x1, y1 = p1[1], p1[0]   # x = lon, y = lat
    x2, y2 = p2[1], p2[0]
    x3, y3 = q1[1], q1[0]
    x4, y4 = q2[1], q2[0]

    den = (x1 - x2) * (y3 - y4) - (y1 - y2) * (x3 - x4)
    if abs(den) < 1e-12:
        return None
    t = ((x1 - x3) * (y3 - y4) - (y1 - y3) * (x3 - x4)) / den
    u = -((x1 - x2) * (y1 - y3) - (y1 - y2) * (x1 - x3)) / den
    if 0.0 <= t <= 1.0 and 0.0 <= u <= 1.0:
        x = x1 + t * (x2 - x1)
        y = y1 + t * (y2 - y1)
        return (y, x)  # (lat, lon)
    return None


def _check_r234_crossing(track: pd.DataFrame) -> tuple[bool, float | None, float | None]:
    """Detecta si la traza cruza la R-234 desde DVOR BCN."""
    r_a, r_b = rt.R234_LINE_ENDPOINTS
    lats = track["latitude"].astype(float).to_numpy()
    lons = track["longitude"].astype(float).to_numpy()
    for i in range(1, len(lats)):
        p1 = (lats[i - 1], lons[i - 1])
        p2 = (lats[i], lons[i])
        cross = _segments_intersect(p1, p2, r_a, r_b)
        if cross is not None:
            return True, cross[0], cross[1]
    return False, None, None


# ---------------------------------------------------------------------------
# Detección sobre una traza interpolada a 1 Hz
# ---------------------------------------------------------------------------

def _detect_turn_start(track: pd.DataFrame, runway: str) -> tuple[int | None, str | None]:
    """Devuelve (índice del primer fix de viraje, método). None si no detectado."""
    if track.empty:
        return None, None

    n = len(track)

    # 1) Roll angle: |RA| ≥ umbral mantenido MIN_HOLD_SAMPLES segundos.
    if "roll_angle" in track.columns:
        ra = track["roll_angle"].astype(float).to_numpy()
        mask = np.abs(ra) >= ROLL_THRESHOLD_DEG
        idx = _first_sustained(mask, MIN_HOLD_SAMPLES)
        if idx is not None:
            return idx, "roll"

    # 2) Rate of turn: |dHDG/dt| ≥ umbral.
    hdg_col = "heading" if "heading" in track.columns else ("tta" if "tta" in track.columns else None)
    if hdg_col is not None:
        hdg = track[hdg_col].astype(float).to_numpy()
        # derivada con wrap-around angular
        dh = np.array([_angle_diff_deg(hdg[i], hdg[i - 1]) for i in range(1, n)])
        # Δt = 1 s tras la interpolación → la derivada coincide con la diferencia
        mask = np.concatenate([[False], np.abs(dh) >= TURN_RATE_THRESHOLD_DPS])
        idx = _first_sustained(mask, MIN_HOLD_SAMPLES)
        if idx is not None:
            return idx, "turn_rate"

    # 3) Desviación del rumbo de pista (solo 24L).
    if runway == "24L" and hdg_col is not None:
        hdg = track[hdg_col].astype(float).to_numpy()
        deviation = np.array([abs(_angle_diff_deg(h, RUNWAY_HDG_24L)) for h in hdg])
        mask = deviation >= HDG_BAND_DEG
        idx = _first_sustained(mask, MIN_HOLD_SAMPLES)
        if idx is not None:
            return idx, "hdg_deviation"

    return None, None


def _first_sustained(mask: np.ndarray, hold: int) -> int | None:
    """Primer índice donde `mask` es True durante `hold` muestras seguidas."""
    if mask.size == 0:
        return None
    count = 0
    for i, v in enumerate(mask):
        if v:
            count += 1
            if count >= hold:
                return i - hold + 1
        else:
            count = 0
    return None


# ---------------------------------------------------------------------------
# Pipeline público
# ---------------------------------------------------------------------------

def compute_turns(processed_df: pd.DataFrame) -> pd.DataFrame:
    """Para cada despegue 24L produce un TurnEvent."""
    deps = build_departures(processed_df)
    if not deps:
        return pd.DataFrame()

    events: list[TurnEvent] = []
    thr_24l = rt.THR_24L

    for d in deps:
        if d.runway != "24L":
            continue
        track = d.track
        if track.empty:
            continue

        # Recorta desde el punto de inicio (≥0.5 NM del THR alejándose)
        start = d.start_idx if d.start_idx is not None else 0
        sub = track.iloc[start:].reset_index(drop=True)
        if sub.empty:
            continue

        idx, method = _detect_turn_start(sub, d.runway)
        crosses, cx_lat, cx_lon = _check_r234_crossing(sub)

        if idx is None:
            events.append(TurnEvent(
                callsign=d.callsign, runway=d.runway, sid=d.sid,
                aircraft_type=d.aircraft_type,
                atot=d.atot.isoformat() if d.atot is not None else None,
                turn_start_time=None, turn_start_lat=None, turn_start_lon=None,
                turn_start_alt_ft=None, turn_start_ias_kt=None,
                turn_start_dist_thr_nm=None, detection_method=None,
                crosses_r234=crosses, r234_cross_lat=cx_lat, r234_cross_lon=cx_lon,
            ))
            continue

        row = sub.iloc[idx]
        alt_col = "altitude_qnh_ft" if "altitude_qnh_ft" in sub.columns else "altitude"
        alt_val = float(row.get(alt_col)) if pd.notna(row.get(alt_col)) else None
        ias_val = float(row.get("ias")) if "ias" in sub.columns and pd.notna(row.get("ias")) else None
        lat = float(row["latitude"])
        lon = float(row["longitude"])
        d_thr = haversine_nm(lat, lon, thr_24l[0], thr_24l[1])
        ts = row["time"]

        events.append(TurnEvent(
            callsign=d.callsign,
            runway=d.runway,
            sid=d.sid,
            aircraft_type=d.aircraft_type,
            atot=d.atot.isoformat() if d.atot is not None else None,
            turn_start_time=pd.Timestamp(ts).isoformat() if pd.notna(ts) else None,
            turn_start_lat=lat,
            turn_start_lon=lon,
            turn_start_alt_ft=alt_val,
            turn_start_ias_kt=ias_val,
            turn_start_dist_thr_nm=d_thr,
            detection_method=method,
            crosses_r234=crosses,
            r234_cross_lat=cx_lat,
            r234_cross_lon=cx_lon,
        ))

    return pd.DataFrame([asdict(e) for e in events])


def to_csv(df: pd.DataFrame) -> str:
    if df is None or df.empty:
        return ""
    buf = io.StringIO()
    df.to_csv(buf, index=False)
    return buf.getvalue()


__all__ = ["TurnEvent", "compute_turns", "to_csv"]
