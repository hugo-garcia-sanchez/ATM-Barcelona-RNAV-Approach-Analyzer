"""Análisis sobre las cabeceras (umbrales) 24L y 06R.

Reglas (PDF P3, pág. 63):
- Filtro geográfico rectangular alrededor de cada cabecera.
- Interpolación a 1 s para localizar el paso por el umbral.
- Para cada despegue se registra:
    * lat/lon/alt/IAS/heading en el instante de paso
    * distancia mínima al THR (NM)
    * tiempo de paso (interpolado linealmente)
    * flag "ya ha girado antes del THR" (turn_start_time < cross_time)
- Salida CSV con las columnas requeridas.
"""

from __future__ import annotations

import io
import math
from dataclasses import dataclass, asdict

import numpy as np
import pandas as pd

from . import reference_tables as rt
from .separations import build_departures, haversine_nm
from .turn_detection import compute_turns


# Rectángulo alrededor de cada THR (en grados aproximados; ~0.5 NM ≈ 0.0083°)
THR_BOX_HALF_LAT_DEG = 0.0083    # ~0.5 NM N-S
THR_BOX_HALF_LON_DEG = 0.0110    # ~0.5 NM E-W (compensa cos(lat))


@dataclass
class ThresholdEvent:
    callsign: str
    runway: str
    sid: str | None
    aircraft_type: str | None
    atot: str | None
    passes_thr_filter: bool
    cross_time: str | None
    cross_lat: float | None
    cross_lon: float | None
    cross_alt_ft: float | None
    cross_ias_kt: float | None
    cross_heading_deg: float | None
    min_dist_thr_nm: float | None
    turned_before_thr: bool | None
    turn_start_time: str | None


def _thr_for(runway: str) -> tuple[float, float] | None:
    """Devuelve el punto de medida del cruce de cabecera para un DESPEGUE
    desde `runway`. Para un despegue, el avión arranca rodaje en su propio
    umbral (THR de su pista) y, ya en vuelo, sobrevuela la cabecera OPUESTA
    (DER = Departure End of Runway). El PDF pág. 60 marca el filtro blanco
    en el DER, no en el THR de origen → usamos las coordenadas de la THR
    opuesta:

    - DEP 24L → DER 24L = THR_06R (extremo SW de la pista)
    - DEP 06R → DER 06R = THR_24L (extremo NE de la pista)
    """
    if runway == "24L":
        return rt.THR_06R
    if runway == "06R":
        return rt.THR_24L
    return None


def _filter_box(track: pd.DataFrame, thr: tuple[float, float]) -> pd.DataFrame:
    """Filtra puntos dentro del polígono exacto definido por Google Earth."""
    if track.empty:
        return track
    
    # Seleccionar el polígono según el threshold
    if thr == rt.THR_06R:
        polygon = rt.THR_06R_FILTER_POLYGON
    elif thr == rt.THR_24L:
        polygon = rt.THR_24L_FILTER_POLYGON
    else:
        # Fallback: caja rectangular para thresholds no mapeados
        lat0, lon0 = thr
        mask = (
            (track["latitude"].astype(float).between(lat0 - THR_BOX_HALF_LAT_DEG, lat0 + THR_BOX_HALF_LAT_DEG))
            & (track["longitude"].astype(float).between(lon0 - THR_BOX_HALF_LON_DEG, lon0 + THR_BOX_HALF_LON_DEG))
        )
        return track.loc[mask].reset_index(drop=True)
    
    # Aplicar filtro usando punto en polígono
    mask = track.apply(
        lambda r: _point_in_polygon(
            float(r["latitude"]), float(r["longitude"]), polygon
        ),
        axis=1
    )
    return track.loc[mask].reset_index(drop=True)


def _point_in_polygon(lat: float, lon: float, polygon: list[tuple[float, float]]) -> bool:
    """Comprueba si un punto (lat, lon) está dentro de un polígono.
    
    Usa el algoritmo de winding number (cuenta cuántas vueltas da el polígono
    alrededor del punto). Si el número es distinto de cero, el punto está dentro.
    
    polygon: lista de (lat, lon) en orden.
    """
    if len(polygon) < 3:
        return False
    
    def is_left(p0, p1, p2):
        """Test si el punto p2 está a la izquierda de la línea p0-p1."""
        return ((p1[0] - p0[0]) * (p2[1] - p0[1]) - 
                (p2[0] - p0[0]) * (p1[1] - p0[1]))
    
    wn = 0  # winding number
    n = len(polygon)
    
    for i in range(n):
        p0 = polygon[i]
        p1 = polygon[(i + 1) % n]
        
        if p0[1] <= lon:  # p0 está en el lado izquierdo o en la línea
            if p1[1] > lon:  # p1 está en el lado derecho
                if is_left(p0, p1, (lat, lon)) > 0:  # punto a la izquierda de p0->p1
                    wn += 1
        else:  # p0 está en el lado derecho
            if p1[1] <= lon:  # p1 está en el lado izquierdo o en la línea
                if is_left(p0, p1, (lat, lon)) < 0:  # punto a la derecha de p0->p1
                    wn -= 1
    
    return wn != 0


def _interp_at_min_dist(track: pd.DataFrame, thr: tuple[float, float]) -> dict | None:
    """Encuentra el índice de mínima distancia al THR e interpola linealmente
    entre el par de fixes adyacentes para obtener un punto de paso suavizado."""
    if track.empty:
        return None
    lats = track["latitude"].astype(float).to_numpy()
    lons = track["longitude"].astype(float).to_numpy()
    dists = np.array([haversine_nm(la, lo, thr[0], thr[1]) for la, lo in zip(lats, lons)])
    if dists.size == 0:
        return None
    i = int(np.argmin(dists))

    # Selecciona el segmento (i-1,i) o (i,i+1) cuya proyección minimice la distancia.
    candidates = []
    if i > 0:
        candidates.append((i - 1, i))
    if i < len(track) - 1:
        candidates.append((i, i + 1))
    if not candidates:
        return _row_to_event(track.iloc[i], dists[i])

    best = None
    for a, b in candidates:
        ra = track.iloc[a]
        rb = track.iloc[b]
        # Proyección de THR sobre el segmento en lat/lon
        ax, ay = float(ra["longitude"]), float(ra["latitude"])
        bx, by = float(rb["longitude"]), float(rb["latitude"])
        px, py = thr[1], thr[0]
        dx, dy = bx - ax, by - ay
        denom = dx * dx + dy * dy
        if denom <= 1e-15:
            t = 0.0
        else:
            t = max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / denom))
        cross_lon = ax + t * dx
        cross_lat = ay + t * dy
        d = haversine_nm(cross_lat, cross_lon, thr[0], thr[1])
        if best is None or d < best["min_dist_thr_nm"]:
            best = _interp_row(track, a, b, t, d, cross_lat, cross_lon)
    return best


def _row_to_event(row: pd.Series, d_nm: float) -> dict:
    alt_col = "altitude_qnh_ft" if "altitude_qnh_ft" in row.index and pd.notna(row.get("altitude_qnh_ft")) else "altitude"
    return {
        "cross_time": pd.Timestamp(row["time"]).isoformat() if "time" in row.index and pd.notna(row.get("time")) else None,
        "cross_lat": float(row["latitude"]),
        "cross_lon": float(row["longitude"]),
        "cross_alt_ft": float(row.get(alt_col)) if pd.notna(row.get(alt_col)) else None,
        "cross_ias_kt": float(row["ias"]) if "ias" in row.index and pd.notna(row.get("ias")) else None,
        "cross_heading_deg": float(row["heading"]) if "heading" in row.index and pd.notna(row.get("heading")) else None,
        "min_dist_thr_nm": float(d_nm),
    }


def _interp_row(
    track: pd.DataFrame, a: int, b: int, t: float, d: float,
    cross_lat: float, cross_lon: float,
) -> dict:
    ra = track.iloc[a]
    rb = track.iloc[b]

    def _lerp(col: str) -> float | None:
        if col not in track.columns:
            return None
        va, vb = ra.get(col), rb.get(col)
        if pd.isna(va) and pd.isna(vb):
            return None
        if pd.isna(va):
            return float(vb)
        if pd.isna(vb):
            return float(va)
        return float(va) + t * (float(vb) - float(va))

    alt_col = "altitude_qnh_ft" if "altitude_qnh_ft" in track.columns else "altitude"
    ts = None
    if "time" in track.columns and pd.notna(ra.get("time")) and pd.notna(rb.get("time")):
        t0 = pd.Timestamp(ra["time"])
        t1 = pd.Timestamp(rb["time"])
        ts = (t0 + (t1 - t0) * t).isoformat()

    return {
        "cross_time": ts,
        "cross_lat": float(cross_lat),
        "cross_lon": float(cross_lon),
        "cross_alt_ft": _lerp(alt_col),
        "cross_ias_kt": _lerp("ias"),
        "cross_heading_deg": _lerp("heading"),
        "min_dist_thr_nm": float(d),
    }


def compute_thresholds(processed_df: pd.DataFrame) -> pd.DataFrame:
    """Para cada despegue 24L/06R produce un ThresholdEvent."""
    deps = build_departures(processed_df)
    if not deps:
        return pd.DataFrame()

    # Cruce con detección de viraje para flag "turned_before_thr"
    try:
        turns_df = compute_turns(processed_df)
    except Exception:
        turns_df = pd.DataFrame()
    turn_lookup: dict[str, str | None] = {}
    if not turns_df.empty:
        for _, r in turns_df.iterrows():
            turn_lookup[str(r["callsign"])] = r.get("turn_start_time")

    events: list[ThresholdEvent] = []
    for d in deps:
        thr = _thr_for(d.runway)
        if thr is None:
            continue
        turn_ts = turn_lookup.get(d.callsign)
        box = _filter_box(d.track, thr)
        passes_filter = not box.empty
        cross = _interp_at_min_dist(box, thr) if passes_filter else None
        nearest = _interp_at_min_dist(d.track, thr)

        if cross is None:
            # Mantener una fila por despegue aunque el avion no entre en el
            # filtro del umbral. La rubrica pide contabilizar estos casos.
            cross = {
                "cross_time": None,
                "cross_lat": None,
                "cross_lon": None,
                "cross_alt_ft": None,
                "cross_ias_kt": None,
                "cross_heading_deg": None,
                "min_dist_thr_nm": (
                    nearest.get("min_dist_thr_nm") if nearest is not None else None
                ),
            }

        turned_before = None
        if turn_ts and cross["cross_time"]:
            try:
                turned_before = pd.Timestamp(turn_ts) < pd.Timestamp(cross["cross_time"])
            except Exception:
                turned_before = None
        elif turn_ts and not passes_filter and d.runway == "24L":
            turned_before = True

        events.append(ThresholdEvent(
            callsign=d.callsign,
            runway=d.runway,
            sid=d.sid,
            aircraft_type=d.aircraft_type,
            atot=d.atot.isoformat() if d.atot is not None else None,
            passes_thr_filter=passes_filter,
            cross_time=cross["cross_time"],
            cross_lat=cross["cross_lat"],
            cross_lon=cross["cross_lon"],
            cross_alt_ft=cross["cross_alt_ft"],
            cross_ias_kt=cross["cross_ias_kt"],
            cross_heading_deg=cross["cross_heading_deg"],
            min_dist_thr_nm=cross["min_dist_thr_nm"],
            turned_before_thr=turned_before,
            turn_start_time=turn_ts,
        ))

    return pd.DataFrame([asdict(e) for e in events])


def summary_metrics(df: pd.DataFrame) -> dict[str, object]:
    """Métricas agregadas: % giro antes THR por pista, medias IAS/alt."""
    if df is None or df.empty:
        return {}
    out: dict[str, object] = {}
    for rwy, sub in df.groupby("runway"):
        total = len(sub)
        turned = int(sub["turned_before_thr"].eq(True).sum())
        passed = int(sub["passes_thr_filter"].eq(True).sum()) if "passes_thr_filter" in sub.columns else total
        out[str(rwy)] = {
            "total": total,
            "passed_thr_filter": passed,
            "missed_thr_filter": total - passed,
            "pct_passed_thr_filter": round(100.0 * passed / total, 2) if total else 0.0,
            "turned_before_thr": turned,
            "pct_turned_before_thr": round(100.0 * turned / total, 2) if total else 0.0,
            "ias_mean_kt": float(sub["cross_ias_kt"].mean(skipna=True)) if total else None,
            "alt_mean_ft": float(sub["cross_alt_ft"].mean(skipna=True)) if total else None,
        }
    return out


def to_csv(df: pd.DataFrame) -> str:
    if df is None or df.empty:
        return ""
    buf = io.StringIO()
    df.to_csv(buf, index=False, sep=';')
    return buf.getvalue()


__all__ = ["ThresholdEvent", "compute_thresholds", "summary_metrics", "to_csv"]
