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
# Rumbo de pista 24L: la AIP España AD-2 LEBL declara 244° (magnético) para
# mantenimiento de rumbo de pista hasta 402 ft (PDF P3 pág. 13). Banda ±8°
# se considera "aún no ha virado".
RUNWAY_HDG_24L = 244.0
# Rumbo de pista 06R: equivalente (064°) por simetría.
RUNWAY_HDG_06R = 64.0
HDG_BAND_DEG = 8.0          # ±8° alrededor del rumbo de pista
ROLL_THRESHOLD_DEG = 5.0    # |RA| ≥ 5° → empieza a virar
TURN_RATE_THRESHOLD_DPS = 1.5  # |dHDG/dt| ≥ 1.5°/s → viraje
MIN_HOLD_SAMPLES = 3        # Debe mantenerse al menos 3 segundos

# Refinamiento dentro de la ventana de hold del Roll Angle (16 s):
# si RA es detectado a la altura t_r, el viraje pudo iniciarse hasta 16 s
# antes. Reconstruimos el inicio buscando en [t_r-16, t_r] el primer punto
# en que el rumbo ya se desvía del rumbo de pista por encima de este umbral.
HDG_REFINE_BAND_DEG = 5.0
RA_HOLD_LOOKBACK_S = 16
TURN_SEARCH_MAX_ALT_FT = 3000.0
TURN_SEARCH_MAX_DIST_THR_NM = 6.0


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
    turn_start_x_m: float | None
    turn_start_y_m: float | None
    turn_start_alt_ft: float | None
    turn_start_ias_kt: float | None
    turn_start_roll_angle_deg: float | None
    turn_start_heading_deg: float | None
    turn_start_tta_deg: float | None
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


def _signed_side_r234(lat: float, lon: float) -> float:
    """Signo (producto cruzado 2D) del punto respecto a la recta DVOR→costa.

    La línea se trata como recta infinita; el signo del producto cruzado entre
    el vector dirección y el vector hacia el punto distingue de qué lado está.
    """
    r_a, r_b = rt.R234_LINE_ENDPOINTS
    # x = lon, y = lat (consistente con _segments_intersect)
    ax, ay = r_a[1], r_a[0]
    bx, by = r_b[1], r_b[0]
    px, py = lon, lat
    return (bx - ax) * (py - ay) - (by - ay) * (px - ax)


def _check_r234_crossing(track: pd.DataFrame, turn_idx: int | None = None) -> tuple[bool, float | None, float | None]:
    """¿La traza cruza la radial R-234 desde DVOR BCN (solo segmento de despegue)?

    IMPORTANTE: Esta función ahora comprueba SOLO el segmento de despegue desde
    el inicio hasta el índice de viraje (turn_idx). Esto evita falsos positivos
    causados por cruces que ocurren DESPUES del viraje detectado.

    Parámetros:
    - track: DataFrame con la traza completa
    - turn_idx: Índice del inicio del viraje en la traza. 
        * Si es None: retorna (False, None, None) — no hay viraje detectado,
          no se puede verificar el segmento de despegue.
        * Si es int ≥ 0: busca cruce SOLO en el segmento [0:turn_idx+1] (inclusive).

    Algoritmo (sin cambios):
    R-234 es una semirrecta desde DVOR BCN; el segmento DVOR→costa (en el PDF
    pág. 56) es sólo un tramo representativo. Para detectar si una trayectoria
    "atraviesa" la radial usamos el signo del producto cruzado entre la
    dirección de la recta y el vector hacia cada fix: un cambio de signo entre
    dos fixes consecutivos = la trayectoria cruzó la recta entre esos dos
    puntos. Es robusto y no depende de la longitud del segmento.
    """
    # Si no hay viraje detectado, no se puede verificar el segmento de despegue
    if turn_idx is None:
        return False, None, None

    # Slice la traza SOLO hasta el índice de viraje (inclusive)
    segment = track.iloc[:turn_idx + 1]
    
    lats = segment["latitude"].astype(float).to_numpy()
    lons = segment["longitude"].astype(float).to_numpy()
    if len(lats) < 2:
        return False, None, None

    sides = np.array([_signed_side_r234(la, lo) for la, lo in zip(lats, lons)])
    prev_sign = 0  # 0 = aún no determinado (puntos exactamente sobre la línea)
    for i, s in enumerate(sides):
        cur_sign = 0 if s == 0 else (1 if s > 0 else -1)
        if prev_sign != 0 and cur_sign != 0 and cur_sign != prev_sign:
            # Interpolar lineal entre el fix anterior y el actual para hallar
            # el punto donde |side|=0.
            a = sides[i - 1]
            b = sides[i]
            t = a / (a - b) if a != b else 0.5
            cross_lat = float(lats[i - 1] + t * (lats[i] - lats[i - 1]))
            cross_lon = float(lons[i - 1] + t * (lons[i] - lons[i - 1]))
            return True, cross_lat, cross_lon
        if cur_sign != 0:
            prev_sign = cur_sign
    return False, None, None


# ---------------------------------------------------------------------------
# Detección sobre una traza interpolada a 1 Hz
# ---------------------------------------------------------------------------

def _refine_with_heading(
    track: pd.DataFrame, idx_roll: int, runway: str,
) -> int:
    """Refina el índice detectado por roll usando el HDG dentro de la ventana
    de retención de 16 s previa.

    El roll angle (RA) sólo se actualiza cada 16 s, pero el HDG cada 4 s. Si
    RA pasa a ≥5° en `idx_roll`, el viraje empezó *en algún momento* dentro
    de los 16 s anteriores. Buscamos en esa ventana el primer instante en
    que el HDG ya se había desviado del rumbo de pista — es una estimación
    mejor del verdadero inicio de viraje.
    """
    if idx_roll <= 0 or "heading" not in track.columns:
        return idx_roll
    runway_hdg = RUNWAY_HDG_24L if runway == "24L" else RUNWAY_HDG_06R
    hdg = track["heading"].astype(float).to_numpy()
    window_start = max(0, idx_roll - RA_HOLD_LOOKBACK_S)
    for j in range(window_start, idx_roll):
        h = hdg[j]
        if not np.isnan(h):
            dev = abs(_angle_diff_deg(float(h), runway_hdg))
            if dev >= HDG_REFINE_BAND_DEG:
                return j
    return idx_roll


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
            # El RA se actualiza cada 16 s — afinar hacia atrás con el HDG
            # (que se actualiza cada 4 s) para acercarnos al inicio real.
            refined = _refine_with_heading(track, idx, runway)
            return refined, ("roll+hdg" if refined != idx else "roll")

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

    # 3) Desviación del rumbo de pista (24L o 06R).
    if hdg_col is not None:
        runway_hdg = RUNWAY_HDG_24L if runway == "24L" else RUNWAY_HDG_06R
        hdg = track[hdg_col].astype(float).to_numpy()
        deviation = np.array([abs(_angle_diff_deg(h, runway_hdg)) for h in hdg])
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

        alt_col = "altitude_qnh_ft" if "altitude_qnh_ft" in sub.columns else "altitude"
        search_mask = pd.Series(True, index=sub.index)
        if alt_col in sub.columns:
            search_mask &= sub[alt_col].astype(float) <= TURN_SEARCH_MAX_ALT_FT
        if {"latitude", "longitude"}.issubset(sub.columns):
            dist_thr = sub.apply(
                lambda r: haversine_nm(float(r["latitude"]), float(r["longitude"]), thr_24l[0], thr_24l[1]),
                axis=1,
            )
            search_mask &= dist_thr <= TURN_SEARCH_MAX_DIST_THR_NM
        search = sub.loc[search_mask].reset_index(drop=True)

        idx, method = _detect_turn_start(search, d.runway)
        
        # Map turn index from 'search' coordinates back to 'sub' coordinates
        # (search is filtered, so idx needs to be mapped to the original sub indices)
        turn_idx_in_sub = None
        if idx is not None:
            search_indices_in_sub = np.where(search_mask.values)[0]
            if idx < len(search_indices_in_sub):
                turn_idx_in_sub = search_indices_in_sub[idx]
        
        # Check R-234 crossing ONLY in the departure segment (0 to turn_idx)
        crosses, cx_lat, cx_lon = _check_r234_crossing(sub, turn_idx=turn_idx_in_sub)

        if idx is None:
            events.append(TurnEvent(
                callsign=d.callsign, runway=d.runway, sid=d.sid,
                aircraft_type=d.aircraft_type,
                atot=d.atot.isoformat() if d.atot is not None else None,
                turn_start_time=None, turn_start_lat=None, turn_start_lon=None,
                turn_start_x_m=None, turn_start_y_m=None,
                turn_start_alt_ft=None, turn_start_ias_kt=None,
                turn_start_roll_angle_deg=None,
                turn_start_heading_deg=None,
                turn_start_tta_deg=None,
                turn_start_dist_thr_nm=None, detection_method=None,
                crosses_r234=crosses, r234_cross_lat=cx_lat, r234_cross_lon=cx_lon,
            ))
            continue

        row = search.iloc[idx]
        alt_col = "altitude_qnh_ft" if "altitude_qnh_ft" in search.columns else "altitude"
        alt_val = float(row.get(alt_col)) if pd.notna(row.get(alt_col)) else None
        ias_val = float(row.get("ias")) if "ias" in sub.columns and pd.notna(row.get("ias")) else None
        x_val = float(row.get("x_m")) if "x_m" in sub.columns and pd.notna(row.get("x_m")) else None
        y_val = float(row.get("y_m")) if "y_m" in sub.columns and pd.notna(row.get("y_m")) else None
        roll_val = float(row.get("roll_angle")) if "roll_angle" in sub.columns and pd.notna(row.get("roll_angle")) else None
        hdg_val = float(row.get("heading")) if "heading" in sub.columns and pd.notna(row.get("heading")) else None
        tta_val = float(row.get("tta")) if "tta" in sub.columns and pd.notna(row.get("tta")) else None
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
            turn_start_x_m=x_val,
            turn_start_y_m=y_val,
            turn_start_alt_ft=alt_val,
            turn_start_ias_kt=ias_val,
            turn_start_roll_angle_deg=roll_val,
            turn_start_heading_deg=hdg_val,
            turn_start_tta_deg=tta_val,
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
    df.to_csv(buf, index=False, sep=';')
    return buf.getvalue()


__all__ = ["TurnEvent", "compute_turns", "to_csv"]
