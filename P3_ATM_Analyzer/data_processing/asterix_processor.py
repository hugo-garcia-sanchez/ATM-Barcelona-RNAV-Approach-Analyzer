"""Filtrado y enriquecimiento de datos ASTERIX Cat048."""
import pandas as pd
import numpy as np

# Bounding box Barcelona TMA
GEO_LAT_MIN, GEO_LAT_MAX = 40.9, 41.7
GEO_LON_MIN, GEO_LON_MAX = 1.5, 2.6
MAX_ALTITUDE_FT = 6000.0
QNH_STD_HPA = 1013.25


class AsterixProcessor:
    """Applies mandatory ASTERIX Cat048 filters and QNH altitude correction.

    Usage::

        processed_df = AsterixProcessor(raw_df).process()

    Or step-by-step::

        proc = AsterixProcessor(raw_df)
        proc.apply_geographic_filter()
        proc.apply_airborne_filter()
        proc.apply_fl_filter()
        proc.correct_altitude_qnh()
        proc.apply_altitude_ceiling()
        result = proc.df
    """

    def __init__(self, df: pd.DataFrame):
        self.df = df.copy()

    # ------------------------------------------------------------------
    # Individual filter steps (each returns self for method chaining)
    # ------------------------------------------------------------------

    def apply_geographic_filter(self) -> "AsterixProcessor":
        """Filtro: 40.9°N < Lat < 41.7°N, 1.5°E < Lon < 2.6°E"""
        mask = (
            (self.df["latitude"] >= GEO_LAT_MIN)
            & (self.df["latitude"] <= GEO_LAT_MAX)
            & (self.df["longitude"] >= GEO_LON_MIN)
            & (self.df["longitude"] <= GEO_LON_MAX)
        )
        self.df = self.df[mask].copy()
        return self

    def apply_airborne_filter(self) -> "AsterixProcessor":
        """Filtro: solo registros airborne (excluir on-ground).

        I230 STAT: 0=no alert/no SPI/airborne, 1=alert/no SPI/airborne, etc.
        El campo 'stat' puede contener texto o número.
        Si no hay columna stat: asumir todos airborne (ya filtrado en origen).
        """
        if "stat" not in self.df.columns:
            return self
        # Excluir registros con 'ground' en stat (case insensitive) o stat=2 (on-ground)
        stat_col = self.df["stat"].astype(str).str.lower()
        mask = ~(stat_col.str.contains("ground") | stat_col.str.contains("on.ground"))
        self.df = self.df[mask].copy()
        return self

    def apply_fl_filter(self) -> "AsterixProcessor":
        """Filtro: solo detecciones con FL recibido (no null)."""
        if "fl" not in self.df.columns:
            return self
        self.df = self.df[self.df["fl"].notna()].copy()
        return self

    def correct_altitude_qnh(self) -> "AsterixProcessor":
        """Corrección QNH para altitudes < 6000 ft.

        Real_Alt_ft = FL * 100 + (BP - 1013.25) * 30
        Almacena resultado en columna 'altitude_qnh_ft'.
        Si no hay BP disponible, usa FL * 100 sin corregir.
        """
        if "fl" not in self.df.columns:
            return self

        fl_ft = self.df["fl"].astype(float) * 100.0

        if "bp" in self.df.columns and self.df["bp"].notna().any():
            bp = self.df["bp"].astype(float).fillna(QNH_STD_HPA)
            correction = (bp - QNH_STD_HPA) * 30.0
            alt_corrected = fl_ft + correction
        else:
            alt_corrected = fl_ft

        self.df = self.df.copy()
        self.df["altitude_qnh_ft"] = alt_corrected
        # Overwrite the main altitude column with the corrected value
        self.df["altitude"] = alt_corrected
        return self

    def apply_altitude_ceiling(self) -> "AsterixProcessor":
        """Filtro: solo detecciones con altitud QNH corregida <= 6000 ft."""
        alt_col = "altitude_qnh_ft" if "altitude_qnh_ft" in self.df.columns else "altitude"
        if alt_col not in self.df.columns:
            return self
        self.df = self.df[self.df[alt_col] <= MAX_ALTITUDE_FT].copy()
        return self

    # ------------------------------------------------------------------
    # Convenience: run all filters in the correct order
    # ------------------------------------------------------------------

    def process(self) -> pd.DataFrame:
        """Aplicar todos los filtros en orden correcto y retornar DataFrame procesado."""
        return (
            self
            .apply_geographic_filter()
            .apply_airborne_filter()
            .apply_fl_filter()
            .correct_altitude_qnh()
            .apply_altitude_ceiling()
            .df
        )
