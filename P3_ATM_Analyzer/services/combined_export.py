"""Export combinado de resultados del P3.

El CSV final usa una fila por despegue 24L/06R. Los calculos por pareja
consecutiva se asignan al avion que despega en segundo lugar, porque ese es el
trafico sobre el que se comprueba la separacion respecto al precedente.
"""

from __future__ import annotations

import io
from pathlib import Path

import pandas as pd

from . import reference_tables as rt
from .separations import build_departures, compute_separations
from .turn_detection import compute_turns
from .nadp import compute_nadp
from .threshold_analysis import compute_thresholds


def _airline_from_callsign(callsign: str | None) -> str | None:
    if not callsign:
        return None
    cs = str(callsign).strip().upper()
    return cs[:3] if len(cs) >= 3 else cs


def _iso(value: object) -> str | None:
    if value is None or pd.isna(value):
        return None
    try:
        return pd.Timestamp(value).isoformat()
    except Exception:
        return str(value)


def _prefixed_values(row: pd.Series, prefix: str, skip: set[str]) -> dict[str, object]:
    out: dict[str, object] = {}
    for col, value in row.items():
        if col in skip:
            continue
        out[f"{prefix}{col}"] = value
    return out


def _lookup_by(df: pd.DataFrame, keys: list[str]) -> dict[tuple[object, ...], pd.Series]:
    if df is None or df.empty:
        return {}
    out: dict[tuple[object, ...], pd.Series] = {}
    for _, row in df.iterrows():
        key = tuple(row.get(k) for k in keys)
        out[key] = row
    return out

def compute_combined_results(processed_df: pd.DataFrame) -> pd.DataFrame:
    """Devuelve una tabla unica con todos los resultados principales.

    Columnas:
    - bloque base: identificacion del despegue y rango temporal de traza;
    - `sep_*`: separacion respecto al despegue precedente de la misma pista;
    - `turn_*`: inicio de viraje 24L y cruce R-234;
    - `nadp_*`: IAS 800/3000 ft y clase NADP;
    - `thr_*`: paso por filtro de cabecera/DER.
    """
    deps = build_departures(processed_df)
    if not deps:
        return pd.DataFrame()

    sep_df = compute_separations(processed_df)
    turns_df = compute_turns(processed_df)
    nadp_df = compute_nadp(processed_df)
    thr_df = compute_thresholds(processed_df)

    sep_lookup = _lookup_by(sep_df, ["follower", "runway"])
    turn_lookup = _lookup_by(turns_df, ["callsign"])
    nadp_lookup = _lookup_by(nadp_df, ["callsign"])
    thr_lookup = _lookup_by(thr_df, ["callsign"])

    rows: list[dict[str, object]] = []
    for d in deps:
        track = d.track
        row: dict[str, object] = {
            "callsign": d.callsign,
            "airline": _airline_from_callsign(d.callsign),
            "runway": d.runway,
            "atot": d.atot.isoformat() if d.atot is not None else None,
            "sid": d.sid,
            "sid_family": rt.get_sid_family(d.sid, d.runway) if d.sid else None,
            "aircraft_type": d.aircraft_type,
            "wake": d.wake,
            "engine_class": rt.classify_aircraft(d.aircraft_type),
            "track_start_time": _iso(track["time"].iloc[0]) if not track.empty else None,
            "track_end_time": _iso(track["time"].iloc[-1]) if not track.empty else None,
            "start_from_thr_time": (
                _iso(track.iloc[d.start_idx]["time"])
                if d.start_idx is not None and not track.empty else None
            ),
        }

        sep = sep_lookup.get((d.callsign, d.runway))
        if sep is None:
            row["sep_is_first_departure_for_runway"] = True
        else:
            row["sep_is_first_departure_for_runway"] = False
            
            # ELIMINAMOS REDUNDANCIAS DE SEPARACIONES (Para cumplir con el feedback)
            sep_skip = {
                "follower", "runway", "atot_follower", "follower_sid", 
                "follower_sid_family", "follower_aircraft_type", "follower_wake", 
                "follower_class", "wake_twr_actual_nm", "loa_actual_nm"
            }
            row.update(_prefixed_values(sep, "sep_", skip=sep_skip))
            
            # Renombramos la distancia radar para que sea la distancia genérica TWR
            if "sep_radar_twr_nm" in row:
                row["sep_dist_twr_nm"] = row.pop("sep_radar_twr_nm")

        # ELIMINAMOS ATOT, SID, TYPE Y WAKE REDUNDANTES DEL RESTO DE TABLAS
        turn = turn_lookup.get((d.callsign,))
        if turn is not None:
            row.update(_prefixed_values(turn, "turn_", skip={"callsign", "runway", "atot", "sid", "aircraft_type"}))

        nadp = nadp_lookup.get((d.callsign,))
        if nadp is not None:
            row.update(_prefixed_values(nadp, "nadp_", skip={"callsign", "runway", "atot", "sid", "aircraft_type", "wake"}))

        thr = thr_lookup.get((d.callsign,))
        if thr is not None:
            row.update(_prefixed_values(thr, "thr_", skip={"callsign", "runway", "atot", "sid", "aircraft_type"}))

        rows.append(row)

    out = pd.DataFrame(rows)
    out = out.sort_values(["runway", "atot", "callsign"], na_position="last").reset_index(drop=True)
    return out

def summary_metrics(df: pd.DataFrame) -> dict[str, object]:
    if df is None or df.empty:
        return {}
    total = len(df)
    return {
        "departures": int(total),
        "runways": df["runway"].value_counts(dropna=False).to_dict() if "runway" in df.columns else {},
        "pairs_with_twr": int(df.get("sep_twr_computable", pd.Series(dtype=bool)).eq(True).sum()),
        "pairs_with_tma": int(df.get("sep_tma_computable", pd.Series(dtype=bool)).eq(True).sum()),
        "threshold_passes": int(df.get("thr_passes_thr_filter", pd.Series(dtype=bool)).eq(True).sum()),
        "turns_detected": int(df.get("turn_turn_start_time", pd.Series(dtype=object)).notna().sum()),
        "nadp_classified": int(df.get("nadp_nadp", pd.Series(dtype=object)).notna().sum()),
    }


def to_csv(df: pd.DataFrame) -> str:
    if df is None or df.empty:
        return ""
    buf = io.StringIO()
    df.to_csv(buf, index=False)
    return buf.getvalue()


def write_combined_csv(processed_df: pd.DataFrame, path: str | Path) -> Path:
    output_path = Path(path)
    print(f"DEBUG: Intentando escribir en {output_path.absolute()}")
    result = compute_combined_results(processed_df)
    print(f"DEBUG: Filas del DataFrame a exportar: {len(result)}")
    
    if result.empty:
        print("¡Atención! El DataFrame está vacío, por eso no se descarga nada.")
        return output_path
        
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(to_csv(result), encoding="utf-8")
    return output_path


__all__ = [
    "compute_combined_results",
    "summary_metrics",
    "to_csv",
    "write_combined_csv",
]
