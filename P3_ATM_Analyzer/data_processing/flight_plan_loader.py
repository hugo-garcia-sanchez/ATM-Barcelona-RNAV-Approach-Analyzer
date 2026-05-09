"""Carga y merge de planes de vuelo con datos radar ASTERIX."""
import io
import pandas as pd
import numpy as np
from pathlib import Path


FLIGHT_PLAN_COLUMN_PATTERNS: dict[str, list[str]] = {
    "callsign":      ["indicativo", "callsign", "ti", "indicatif"],
    "destination":   ["destino", "destination", "dest", "adep_ades"],
    "atot":          ["horadespegue", "atot", "hora_despegue", "departure_time", "tow"],
    "route":         ["ruta", "route", "sid_route"],
    "aircraft_type": ["tipoaeronave", "aircraft_type", "tipo_aeronave", "ac_type"],
    "wake_cat":      ["estela", "wake_cat", "wake", "turbulencia"],
    "sid":           ["procdesp", "sid", "proc_desp", "sid_name"],
    "runway":        ["pistadesp", "runway", "pista_desp", "rwy"],
}

# Mapping from various wake turbulence codes/words to canonical Spanish names
WAKE_MAP: dict[str, str] = {
    "j": "superpesada",
    "h": "pesada",
    "m": "media",
    "l": "ligera",
    "superpesada": "superpesada",
    "pesada": "pesada",
    "media": "media",
    "ligera": "ligera",
    "heavy": "pesada",
    "medium": "media",
    "light": "ligera",
}


def _atot_to_timestamp(value) -> pd.Timestamp:
    """Convierte un valor de ATOT (Timedelta, string HH:MM:SS, datetime) a un
    Timestamp anclado en la fecha de hoy para que sea comparable con la columna
    'time' del radar."""
    if pd.isna(value):
        return pd.NaT
    today = pd.Timestamp.today().normalize()
    if isinstance(value, pd.Timedelta):
        return today + value
    if isinstance(value, pd.Timestamp):
        # Si trae fecha 1900 o similar, reanclar a hoy preservando hora
        return today + pd.Timedelta(
            hours=int(value.hour),
            minutes=int(value.minute),
            seconds=int(value.second),
        )
    s = str(value).strip()
    try:
        td = pd.to_timedelta(s)
        if pd.notna(td):
            return today + td
    except Exception:
        pass
    try:
        ts = pd.to_datetime(s, errors="coerce")
        if pd.notna(ts):
            return today + pd.Timedelta(
                hours=int(ts.hour), minutes=int(ts.minute), seconds=int(ts.second)
            )
    except Exception:
        pass
    return pd.NaT


class FlightPlanLoader:
    """Carga planes de vuelo desde CSV y permite merge con datos radar ASTERIX."""

    def __init__(self):
        self.df: pd.DataFrame | None = None

    def load(self, file_path: str = None, file_content: bytes = None) -> pd.DataFrame:
        """Carga un fichero (CSV o XLSX) de planes de vuelo y normaliza columnas.

        Args:
            file_path: Ruta al fichero (csv|xlsx|xls).
            file_content: Contenido binario (alternativa a file_path). Para xlsx
                la detección se basa en la firma "PK" (zip).

        Returns:
            DataFrame con columnas canonicas.
        """
        is_xlsx = False
        if file_path:
            suffix = Path(file_path).suffix.lower()
            is_xlsx = suffix in (".xlsx", ".xls")
        elif file_content is not None:
            is_xlsx = file_content[:2] == b"PK"
        else:
            raise ValueError("Proporcionar file_path o file_content")

        if is_xlsx:
            source = file_path if file_path else io.BytesIO(file_content)
            df = pd.read_excel(source, sheet_name=0)
        else:
            if file_path:
                content = Path(file_path).read_text(encoding="utf-8", errors="replace")
            else:
                content = file_content.decode("utf-8", errors="replace")
            first_line = content.split("\n")[0]
            delim = ";" if first_line.count(";") > first_line.count(",") else ","
            df = pd.read_csv(
                io.StringIO(content),
                sep=delim,
                decimal=",",
                skipinitialspace=True,
            )

        df.columns = [c.strip().lower() for c in df.columns]

        # Map columns to canonical names
        found = set(df.columns)
        rename: dict[str, str] = {}
        for canonical, patterns in FLIGHT_PLAN_COLUMN_PATTERNS.items():
            if canonical in found:
                continue  # already named correctly
            for p in patterns:
                if p in found:
                    rename[p] = canonical
                    break
        df = df.rename(columns=rename)

        # Normalize wake_cat
        if "wake_cat" in df.columns:
            df["wake_cat"] = (
                df["wake_cat"]
                .astype(str)
                .str.strip()
                .str.lower()
                .map(lambda x: WAKE_MAP.get(x, x))
            )

        # Normalize runway (strip whitespace, uppercase)
        if "runway" in df.columns:
            df["runway"] = df["runway"].astype(str).str.strip().str.upper()

        # Normalize callsign (strip whitespace, uppercase)
        if "callsign" in df.columns:
            df["callsign"] = df["callsign"].astype(str).str.strip().str.upper()

        # Normalize ATOT to a Timestamp anchored on today's date so it is
        # comparable to the radar 'time' column (which uses today as base).
        if "atot" in df.columns:
            df["atot"] = df["atot"].apply(_atot_to_timestamp)

        self.df = df
        return df

    def merge_with_radar(
        self, radar_df: pd.DataFrame, time_window_minutes: float = 5.0
    ) -> pd.DataFrame:
        """Merge planes de vuelo con datos radar por callsign.

        Para cada registro radar, anade columnas del plan de vuelo si el
        callsign coincide. La hora de despegue del plan de vuelo se usa como
        referencia temporal (+/-time_window_minutes).

        Returns:
            radar_df con columnas extra: wake_cat, sid, runway_fp,
            aircraft_type, destination, atot, route (las que existan).
        """
        if self.df is None or "callsign" not in self.df.columns:
            return radar_df

        # Select only columns that exist in the flight plan df
        extra_cols = [
            c for c in ["wake_cat", "sid", "runway", "aircraft_type", "destination", "atot", "route"]
            if c in self.df.columns
        ]
        fp = self.df[["callsign"] + extra_cols].copy()

        # Rename 'runway' -> 'runway_fp' to avoid collision with radar columns
        fp = fp.rename(columns={"runway": "runway_fp"})

        # Merge on callsign (left join: radar records without a flight plan get NaN)
        merged = radar_df.merge(fp, on="callsign", how="left")
        return merged
