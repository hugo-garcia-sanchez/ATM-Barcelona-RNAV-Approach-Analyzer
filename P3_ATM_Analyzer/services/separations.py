"""Cálculo de separaciones radar / estela / LoA entre despegues consecutivos.

Pipeline:
    1. Construir lista de despegues por pista (24L y 06R) ordenados por ATOT.
    2. Para cada par consecutivo (precedente, siguiente):
        - Localizar la traza radar de cada uno.
        - Definir punto inicial: primer fix a ≥0,5 NM del THR alejándose.
        - Calcular separaciones:
            * Radar TWR  – 1 muestra; pérdida si <3 NM y Δalt <1000 ft.
            * Radar TMA  – distancia mínima durante todo el solapamiento TMA.
            * Estela TWR – tabla (NM, segundos).
            * Estela TMA – tabla (NM).
            * LoA TWR    – clase motor + misma/distinta familia SID.
    3. Volcar todo a DataFrame y permitir export CSV.

El módulo es defensivo: si faltan campos del plan de vuelo (SID, runway,
wake_cat, aircraft_type) intenta seguir y deja celdas vacías.
"""

from __future__ import annotations

import io
import math
from dataclasses import dataclass, field, asdict
from typing import Iterable

import numpy as np
import pandas as pd

from . import reference_tables as rt
from .interpolation import interpolate_track


NM_PER_DEG_LAT = 60.0
FT_PER_M = 3.28084
NM_PER_M = 1.0 / 1852.0


# ---------------------------------------------------------------------------
# Helpers geométricos
# ---------------------------------------------------------------------------

def haversine_nm(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Distancia en NM entre dos puntos lat/lon."""
    R_NM = 3440.065  # radio Tierra en NM
    p1 = math.radians(lat1)
    p2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlam = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlam / 2) ** 2
    return 2 * R_NM * math.asin(math.sqrt(a))


def distance_nm_xy(x1: float, y1: float, x2: float, y2: float) -> float:
    """Distancia en NM entre dos puntos en proyección estereográfica (m)."""
    return math.hypot(x2 - x1, y2 - y1) * NM_PER_M


def _runway_thr(runway: str | None) -> tuple[float, float] | None:
    if not runway:
        return None
    r = str(runway).upper().replace(" ", "")
    if "24L" in r:
        # El despegue por 24L termina en la cabecera opuesta (DER = 06R)
        return rt.THR_06R
    if "06R" in r:
        # El despegue por 06R termina en la cabecera opuesta (DER = 24L)
        return rt.THR_24L
    return None


# ---------------------------------------------------------------------------
# Modelo
# ---------------------------------------------------------------------------

@dataclass
class Departure:
    """Un despegue, con plan de vuelo y traza radar."""
    callsign: str
    runway: str
    atot: pd.Timestamp | None
    sid: str | None
    aircraft_type: str | None
    wake: str | None  # J/H/M/L
    track: pd.DataFrame  # traza interpolada a 1 Hz, ordenada
    start_idx: int | None = None  # primer fix ≥0.5 NM del THR alejándose


@dataclass
class SeparationResult:
    leader: str
    follower: str
    runway: str
    atot_leader: str | None
    atot_follower: str | None
    leader_sid: str | None
    follower_sid: str | None
    leader_sid_family: str | None
    follower_sid_family: str | None
    leader_aircraft_type: str | None
    follower_aircraft_type: str | None
    leader_wake: str | None
    follower_wake: str | None
    leader_class: str | None
    follower_class: str | None
    same_sid_family: bool | None
    radar_twr_time: str | None = None
    radar_tma_min_time: str | None = None
    twr_computable: bool = False
    tma_computable: bool = False
    computation_note: str | None = None
    radar_twr_nm: float | None = None
    radar_twr_dalt_ft: float | None = None
    radar_twr_loss: bool | None = None
    radar_tma_min_nm: float | None = None
    radar_tma_dalt_ft: float | None = None
    radar_tma_loss: bool | None = None
    wake_twr_required_nm: float | None = None
    wake_twr_required_s: float | None = None
    wake_twr_actual_nm: float | None = None
    wake_twr_actual_s: float | None = None
    wake_twr_loss: bool | None = None
    wake_tma_required_nm: float | None = None
    wake_tma_actual_nm: float | None = None
    wake_tma_loss: bool | None = None
    loa_required_nm: float | None = None
    loa_actual_nm: float | None = None
    loa_loss: bool | None = None


# ---------------------------------------------------------------------------
# Construcción de Departure list
# ---------------------------------------------------------------------------

def _wake_from_row(row: pd.Series) -> str | None:
    for c in ("wake_cat", "wake_category"):
        if c in row.index and pd.notna(row[c]):
            return rt.normalize_wake(str(row[c]))
    return None


def _runway_from_row(row: pd.Series) -> str | None:
    for c in ("runway_fp", "runway"):
        if c in row.index and pd.notna(row[c]):
            r = str(row[c]).upper().replace(" ", "")
            if "24L" in r:
                return "24L"
            if "06R" in r:
                return "06R"
            return r
    return None

def build_departures(processed_df: pd.DataFrame) -> list[Departure]:
    """Construye una lista de Departure por callsign con runway 24L/06R."""
    if processed_df is None or processed_df.empty or "callsign" not in processed_df.columns:
        return []

    df = processed_df.copy()
    if "time" in df.columns:
        df["time"] = pd.to_datetime(df["time"], errors="coerce")

    deps: list[Departure] = []
    for cs, sub in df.groupby("callsign", dropna=True, sort=False):
        if pd.isna(cs):
            continue
        first = sub.iloc[0]
        runway = _runway_from_row(first)
        if runway not in ("24L", "06R"):
            continue
        atot_raw = first.get("atot") if "atot" in sub.columns else None
        atot = pd.to_datetime(atot_raw, errors="coerce") if atot_raw is not None else None
        if pd.isna(atot):
            atot = None

        # Interpolación a 1 Hz
        track = interpolate_track(sub)
        if track.empty:
            continue

        # Localizar punto de inicio (>=0,5 NM del THR alejándose y posterior a ATOT)
        start_idx = _find_start_index(track, runway, atot)

        deps.append(Departure(
            callsign=str(cs),
            runway=runway,
            atot=atot,
            sid=str(first["sid"]) if "sid" in sub.columns and pd.notna(first.get("sid")) else None,
            aircraft_type=str(first["aircraft_type"]) if "aircraft_type" in sub.columns and pd.notna(first.get("aircraft_type")) else None,
            wake=_wake_from_row(first),
            track=track,
            start_idx=start_idx,
        ))

    deps.sort(key=lambda d: (d.runway, d.atot or pd.Timestamp.max))
    return deps

def _find_start_index(track: pd.DataFrame, runway: str, atot: pd.Timestamp | None) -> int | None:
    """Primer índice cuya distancia al DER sea >=0.5 NM, vaya alejándose y sea posterior al ATOT."""
    thr = _runway_thr(runway)
    if thr is None or track.empty:
        return None
        
    lats = track["latitude"].astype(float).to_numpy()
    lons = track["longitude"].astype(float).to_numpy()
    times = pd.to_datetime(track["time"])
    
    dists = np.array([haversine_nm(lat, lon, thr[0], thr[1]) for lat, lon in zip(lats, lons)])
    
    for i in range(1, len(dists)):
        # 1. Asegurar que la hora es estrictamente posterior al ATOT
        if atot is not None and times.iloc[i] <= atot:
            continue
            
        # 2. Distancia >= 0.5NM, alejándose (dist[i] > dist[i-1]), 
        # y forzamos que el punto anterior estuviese a < 0.5NM (como pide el profesor)
        if (dists[i] >= rt.START_FROM_THR_NM and 
            dists[i] > dists[i - 1] and 
            dists[i - 1] < rt.START_FROM_THR_NM):
            return i
            
    return None


# ---------------------------------------------------------------------------
# Cálculos por par de despegues
# ---------------------------------------------------------------------------

def _track_distance_at_time(track: pd.DataFrame, ts: pd.Timestamp) -> tuple[float, float, float] | None:
    """Devuelve (lat, lon, alt) en `ts` (o el más cercano) o None."""
    if track.empty or "time" not in track.columns:
        return None
    # Ensure times are comparable series
    times = pd.to_datetime(track["time"])
    if times.empty:
        return None
    
    # Check boundaries safely
    t_start = times.iloc[0]
    t_end = times.iloc[-1]
    if ts < t_start or ts > t_end:
        return None
    
    idx = times.searchsorted(ts)
    idx = min(idx, len(track) - 1)
    row = track.iloc[idx]
    alt_col = "altitude_qnh_ft" if "altitude_qnh_ft" in row.index and pd.notna(row.get("altitude_qnh_ft")) else "altitude"
    return float(row["latitude"]), float(row["longitude"]), float(row.get(alt_col, 0.0))


def _min_separation_overlap(
    leader: Departure, follower: Departure, after_time: str | None = None
) -> tuple[float | None, float | None, str | None]:
    """Mínima separación radar y mínima Δalt en el solapamiento TMA.
    
    Si after_time está definido, solo evalúa las detecciones estrictamente
    posteriores a esa hora (para que TMA empiece donde acaba TWR).
    """
    a = leader.track
    b = follower.track
    if a.empty or b.empty:
        return None, None, None

    # Solapamiento temporal
    t0 = max(a["time"].iloc[0], b["time"].iloc[0])
    t1 = min(a["time"].iloc[-1], b["time"].iloc[-1])
    
    # 1. FORZAR QUE LA BÚSQUEDA SEA POSTERIOR A LA HORA TWR
    if after_time is not None:
        t_after = pd.Timestamp(after_time)
        if t0 <= t_after:
            # Sumamos 1 segundo para que sea estrictamente "la resta de detecciones"
            t0 = t_after + pd.Timedelta(seconds=1)

    if t0 > t1:
        return None, None, None

    # Filtra ambas series al solapamiento e índiceá por tiempo
    a_ov = a[(a["time"] >= t0) & (a["time"] <= t1)].set_index("time")
    b_ov = b[(b["time"] >= t0) & (b["time"] <= t1)].set_index("time")
    common = a_ov.index.intersection(b_ov.index)
    if len(common) == 0:
        return None, None, None

    a_ov = a_ov.loc[common]
    b_ov = b_ov.loc[common]

    # Distancias
    if "x_m" in a_ov.columns and "x_m" in b_ov.columns:
        dx = a_ov["x_m"].to_numpy() - b_ov["x_m"].to_numpy()
        dy = a_ov["y_m"].to_numpy() - b_ov["y_m"].to_numpy()
        d_nm = np.hypot(dx, dy) * NM_PER_M
    else:
        d_nm = np.array([
            haversine_nm(la, lo, lb, lo2)
            for la, lo, lb, lo2 in zip(
                a_ov["latitude"], a_ov["longitude"],
                b_ov["latitude"], b_ov["longitude"],
            )
        ])

    alt_col = "altitude_qnh_ft" if "altitude_qnh_ft" in a_ov.columns else "altitude"
    dalt = np.abs(a_ov[alt_col].to_numpy() - b_ov[alt_col].to_numpy())

    min_idx = int(np.nanargmin(d_nm))
    min_time = pd.Timestamp(common[min_idx]).isoformat()
    return float(np.nanmin(d_nm)), float(dalt[min_idx]), min_time

def _radar_twr_at_first_sample(leader: Departure, follower: Departure) -> tuple[float | None, float | None, str | None]:
    """Una sola muestra: en el primer fix tras el despegue del follower, distancia
    al precedente y Δalt."""
    if follower.start_idx is None or follower.track.empty:
        return None, None, None
    fol_row = follower.track.iloc[follower.start_idx]
    ts = fol_row["time"]
    lead_pos = _track_distance_at_time(leader.track, ts)
    if lead_pos is None:
        return None, None, None
    d_nm = haversine_nm(
        float(fol_row["latitude"]), float(fol_row["longitude"]),
        lead_pos[0], lead_pos[1],
    )
    alt_col = "altitude_qnh_ft" if "altitude_qnh_ft" in follower.track.columns else "altitude"
    dalt = abs(float(fol_row.get(alt_col, 0.0)) - lead_pos[2])
    return d_nm, dalt, pd.Timestamp(ts).isoformat()


def _time_gap_first_detection_s(leader: Departure, follower: Departure) -> float | None:
    """Tiempo (segundos) entre la primera detección radar (≥0.5 NM del THR
    alejándose) del leader y la del follower. Esta es la "separación temporal"
    aplicable a la regla de estela TWR (PDF pág. 22) — corresponde a la
    diferencia de pasos por el mismo punto de referencia."""
    if leader.start_idx is None or follower.start_idx is None:
        return None
    if leader.track.empty or follower.track.empty:
        return None
    try:
        t_lead = pd.Timestamp(leader.track.iloc[leader.start_idx]["time"])
        t_foll = pd.Timestamp(follower.track.iloc[follower.start_idx]["time"])
    except Exception:
        return None
    if pd.isna(t_lead) or pd.isna(t_foll):
        return None
    return abs((t_foll - t_lead).total_seconds())


# ---------------------------------------------------------------------------
# Pipeline público
# ---------------------------------------------------------------------------
def compute_separations(processed_df: pd.DataFrame) -> pd.DataFrame:
    """Pipeline completo. Devuelve DataFrame con una fila por par consecutivo."""
    deps = build_departures(processed_df)
    if len(deps) < 2:
        return pd.DataFrame()

    results: list[SeparationResult] = []

    # Agrupa por pista y calcula sólo pares consecutivos
    by_rwy: dict[str, list[Departure]] = {}
    for d in deps:
        by_rwy.setdefault(d.runway, []).append(d)

    for rwy, lst in by_rwy.items():
        # Ya viene ordenado por ATOT. Si no hay ATOT, ordena por primer fix.
        lst.sort(key=lambda d: (
            d.atot if d.atot is not None else d.track["time"].iloc[0]
        ))

        for i in range(len(lst) - 1):
            leader = lst[i]
            follower = lst[i + 1]

            same_fam = (
                rt.same_sid_family(leader.sid, follower.sid, rwy)
                if leader.sid and follower.sid else None
            )
            leader_sid_family = rt.get_sid_family(leader.sid, rwy) if leader.sid else None
            follower_sid_family = rt.get_sid_family(follower.sid, rwy) if follower.sid else None
            l_class = rt.classify_aircraft(leader.aircraft_type)
            f_class = rt.classify_aircraft(follower.aircraft_type)

            # Radar TWR (1 muestra: primera detección del follower a ≥0.5 NM
            # del THR alejándose).
            r_nm, r_dalt, r_twr_time = _radar_twr_at_first_sample(leader, follower)
            r_loss = (
                (r_nm is not None and r_dalt is not None
                 and r_nm < rt.RADAR_MIN_NM and r_dalt < rt.RADAR_MIN_VERT_FT)
            )

            # Radar TMA (distancia mínima durante el solapamiento + Δalt
            # en ese instante)
            # AQUI ESTA EL CAMBIO: after_time=r_twr_time
            r_tma_min, r_tma_dalt, r_tma_time = _min_separation_overlap(leader, follower, after_time=r_twr_time)
            r_tma_loss = (
                r_tma_min is not None and r_tma_dalt is not None
                and r_tma_min < rt.RADAR_MIN_NM and r_tma_dalt < rt.RADAR_MIN_VERT_FT
            )
            notes: list[str] = []
            if r_nm is None:
                notes.append("TWR no computable: precedente sin posicion en la primera deteccion del siguiente")
            if r_tma_min is None:
                notes.append("TMA no computable: sin solape temporal dentro del filtro")

            # Estela TWR (distancia y tiempo en primera detección; pág. 22 PDF)
            # Distancia "actual" = la misma de la primera detección radar TWR
            # (PDF pág. 19: "Incumplimiento de TWR sólo aplica a la primera
            # detección radar del que despega respecto al precedente").
            # Tiempo "actual" = gap entre primeras detecciones de leader y
            # follower (paso por el mismo punto de referencia).
            wake_req = rt.get_wake_separation(leader.wake, follower.wake, "TWR")
            wake_tma_req = rt.get_wake_separation(leader.wake, follower.wake, "TMA")
            wake_act_nm = r_nm
            wake_act_s = _time_gap_first_detection_s(leader, follower)

            wake_twr_loss = None
            wake_tma_loss = None
            req_nm_twr: float | None = None
            req_s_twr: float | None = None
            if wake_req is not None and wake_act_nm is not None:
                req_nm_twr, req_s_twr = wake_req
                # PDF pág. 24: pérdida operativa por estela requiere
                # incumplimiento horizontal (distancia O tiempo) Y a la vez
                # |Δalt| < 1000 ft.
                horizontal_bust = wake_act_nm < req_nm_twr
                if req_s_twr is not None and wake_act_s is not None:
                    horizontal_bust = horizontal_bust or (wake_act_s < req_s_twr)
                alt_bust = (
                    r_dalt is not None and r_dalt < rt.RADAR_MIN_VERT_FT
                )
                wake_twr_loss = bool(horizontal_bust and alt_bust)
            if wake_tma_req is not None and r_tma_min is not None:
                # PDF pág. 24 aplica también a TMA: pérdida operativa requiere
                # |Δalt| < 1000 ft en el momento del mínimo.
                horizontal_bust_tma = r_tma_min < wake_tma_req
                alt_bust_tma = (
                    r_tma_dalt is not None and r_tma_dalt < rt.RADAR_MIN_VERT_FT
                )
                wake_tma_loss = bool(horizontal_bust_tma and alt_bust_tma)

            # LoA (sólo TWR, pág. 25 PDF). Distancia "actual" es la misma
            # primera detección radar.
            loa_req = (
                rt.get_loa_separation(l_class, f_class, same_fam)
                if same_fam is not None else None
            )
            loa_actual = r_nm
            loa_loss = (
                loa_actual is not None and loa_req is not None
                and loa_actual < loa_req
            )

            results.append(SeparationResult(
                leader=leader.callsign,
                follower=follower.callsign,
                runway=rwy,
                atot_leader=leader.atot.isoformat() if leader.atot is not None else None,
                atot_follower=follower.atot.isoformat() if follower.atot is not None else None,
                leader_sid=leader.sid,
                follower_sid=follower.sid,
                leader_sid_family=leader_sid_family,
                follower_sid_family=follower_sid_family,
                leader_aircraft_type=leader.aircraft_type,
                follower_aircraft_type=follower.aircraft_type,
                leader_wake=leader.wake,
                follower_wake=follower.wake,
                leader_class=l_class,
                follower_class=f_class,
                same_sid_family=same_fam,
                radar_twr_time=r_twr_time,
                radar_tma_min_time=r_tma_time,
                twr_computable=r_nm is not None,
                tma_computable=r_tma_min is not None,
                computation_note="; ".join(notes) if notes else None,
                radar_twr_nm=r_nm,
                radar_twr_dalt_ft=r_dalt,
                radar_twr_loss=r_loss,
                radar_tma_min_nm=r_tma_min,
                radar_tma_dalt_ft=r_tma_dalt,
                radar_tma_loss=bool(r_tma_loss) if r_tma_min is not None else None,
                wake_twr_required_nm=req_nm_twr,
                wake_twr_required_s=req_s_twr,
                wake_twr_actual_nm=wake_act_nm,
                wake_twr_actual_s=wake_act_s,
                wake_twr_loss=wake_twr_loss,
                wake_tma_required_nm=wake_tma_req,
                wake_tma_actual_nm=r_tma_min,
                wake_tma_loss=wake_tma_loss,
                loa_required_nm=loa_req,
                loa_actual_nm=loa_actual,
                loa_loss=loa_loss,
            ))

    return pd.DataFrame([asdict(r) for r in results])


def to_csv(df: pd.DataFrame) -> str:
    """Serializa el DataFrame de separaciones a CSV (formato pág. 51 PDF)."""
    if df is None or df.empty:
        return ""
    buf = io.StringIO()
    df.to_csv(buf, index=False)
    return buf.getvalue()


__all__ = [
    "Departure", "SeparationResult",
    "build_departures", "compute_separations", "to_csv",
    "haversine_nm",
]
