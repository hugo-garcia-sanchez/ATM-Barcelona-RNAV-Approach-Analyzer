"""Clasificación NADP (Noise Abatement Departure Procedure) para despegues 24L.

Reglas (PDF P3, pág. 57):
- Para cada despegue 24L, medir IAS al pasar 800 ft y al pasar 3000 ft (QNH).
- ΔIAS = IAS@3000 − IAS@800.
- Umbral configurable (`NADP_IAS_DELTA_THRESHOLD`, por defecto 30 kt):
    * ΔIAS < umbral  → NADP1 (acelera tarde, mantiene V2 hasta >3000 ft).
    * ΔIAS ≥ umbral  → NADP2 (acelera pronto, limpia flaps a 800 ft).
- Si no se puede medir alguna de las dos altitudes → NADP=None.
"""

from __future__ import annotations

import io
from dataclasses import dataclass, asdict

import numpy as np
import pandas as pd

from . import reference_tables as rt
from .separations import build_departures


NADP_IAS_DELTA_THRESHOLD = 30.0   # kt
ALT_LOW_FT = 800.0
ALT_HIGH_FT = 3000.0


@dataclass
class NadpEvent:
    callsign: str
    runway: str
    sid: str | None
    aircraft_type: str | None
    atot: str | None
    ias_at_800ft: float | None
    ias_at_3000ft: float | None
    delta_ias_kt: float | None
    nadp: str | None              # "NADP1" | "NADP2" | None
    time_at_800ft: str | None
    time_at_3000ft: str | None


def _ias_at_altitude(track: pd.DataFrame, target_alt: float) -> tuple[float | None, pd.Timestamp | None]:
    """IAS interpolada en el primer cruce ascendente de `target_alt` (QNH)."""
    if track.empty:
        return None, None

    alt_col = "altitude_qnh_ft" if "altitude_qnh_ft" in track.columns else "altitude"
    if alt_col not in track.columns or "ias" not in track.columns:
        return None, None

    alt = track[alt_col].astype(float).to_numpy()
    ias = track["ias"].astype(float).to_numpy()
    times = track["time"].to_numpy()

    # Primer cruce ascendente
    for i in range(1, len(alt)):
        a0, a1 = alt[i - 1], alt[i]
        if np.isnan(a0) or np.isnan(a1):
            continue
        if a0 <= target_alt <= a1 and a1 > a0:
            # Interpolación lineal de IAS entre i-1 e i
            if a1 == a0:
                frac = 0.0
            else:
                frac = (target_alt - a0) / (a1 - a0)
            i0 = ias[i - 1] if not np.isnan(ias[i - 1]) else ias[i]
            i1 = ias[i] if not np.isnan(ias[i]) else ias[i - 1]
            if np.isnan(i0) or np.isnan(i1):
                return None, None
            ias_at = float(i0 + frac * (i1 - i0))
            # Timestamp interpolado
            t0 = pd.Timestamp(times[i - 1])
            t1 = pd.Timestamp(times[i])
            ts = t0 + (t1 - t0) * frac
            return ias_at, ts
    return None, None


def _classify(delta_ias: float | None, threshold: float = NADP_IAS_DELTA_THRESHOLD) -> str | None:
    if delta_ias is None:
        return None
    return "NADP2" if delta_ias >= threshold else "NADP1"


def compute_nadp(
    processed_df: pd.DataFrame,
    *,
    threshold_kt: float = NADP_IAS_DELTA_THRESHOLD,
) -> pd.DataFrame:
    """Para cada despegue 24L produce un NadpEvent."""
    deps = build_departures(processed_df)
    if not deps:
        return pd.DataFrame()

    events: list[NadpEvent] = []
    for d in deps:
        if d.runway != "24L":
            continue

        ias_low, t_low = _ias_at_altitude(d.track, ALT_LOW_FT)
        ias_high, t_high = _ias_at_altitude(d.track, ALT_HIGH_FT)

        delta = (ias_high - ias_low) if (ias_low is not None and ias_high is not None) else None
        nadp = _classify(delta, threshold_kt)

        events.append(NadpEvent(
            callsign=d.callsign,
            runway=d.runway,
            sid=d.sid,
            aircraft_type=d.aircraft_type,
            atot=d.atot.isoformat() if d.atot is not None else None,
            ias_at_800ft=ias_low,
            ias_at_3000ft=ias_high,
            delta_ias_kt=delta,
            nadp=nadp,
            time_at_800ft=t_low.isoformat() if t_low is not None else None,
            time_at_3000ft=t_high.isoformat() if t_high is not None else None,
        ))

    return pd.DataFrame([asdict(e) for e in events])


def to_csv(df: pd.DataFrame) -> str:
    if df is None or df.empty:
        return ""
    buf = io.StringIO()
    df.to_csv(buf, index=False)
    return buf.getvalue()


__all__ = ["NadpEvent", "compute_nadp", "to_csv", "NADP_IAS_DELTA_THRESHOLD"]
