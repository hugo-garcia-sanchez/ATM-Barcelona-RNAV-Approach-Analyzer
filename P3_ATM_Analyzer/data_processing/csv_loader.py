"""CSV loading and validation module for ATM analyzer."""

import io
from pathlib import Path

import pandas as pd


# ---------------------------------------------------------------------------
# ASTERIX Cat048 column mapping patterns
# Key = canonical name used throughout the application
# Value = list of possible CSV column name variants (lowercase, stripped)
# ---------------------------------------------------------------------------
ASTERIX_COLUMN_PATTERNS: dict[str, list[str]] = {
    "fl":             ["fl", "i090_fl", "flight_level", "i090"],
    "tod":            ["tod", "i140_tod", "time_of_day"],
    "track_number":   ["tn", "track", "i161", "track_number", "track_num"],
    "stat":           ["stat", "i230_stat", "flight_status", "status"],
    "callsign":       ["callsign", "ti", "tid", "i240_tid", "indicativo"],
    "target_address": ["ta", "target_address", "icao24"],
    "mode3a":         ["mode3/a", "mode3a", "mode_3a", "m3a"],
    "bp":             ["bp", "i250_bp", "baro_pressure", "barometric_pressure"],
    "roll_angle":     ["ra", "roll_angle", "i250_ra", "roll"],
    "tta":            ["tta", "true_track_angle", "true_track"],
    "ground_speed":   ["gs", "ground_speed", "i250_gs"],
    "ground_speed_kt":["gs(kt)", "gs_kt", "ground_speed_kt"],
    "tar":            ["tar", "track_angle_rate"],
    "tas":            ["tas", "true_airspeed"],
    "heading":        ["hdg", "mh", "magnetic_heading", "heading"],
    "ias":            ["ias", "indicated_airspeed", "indicated_air_speed"],
    "mach":           ["mach"],
    "baro_alt_rate":  ["bar", "baro_alt_rate", "barometric_alt_rate"],
    "ivv":            ["ivv", "inertial_vertical_velocity"],
    "rho":            ["rho", "i040_rho"],
    "theta":          ["theta", "i040_theta"],
    "h_ft":           ["h(ft)", "h_ft"],
    "h_m":            ["h(m)", "h_m"],
}


class CSVLoader:
    """Loads and validates CSV files containing radar/flight data."""

    REQUIRED_COLUMNS = {"latitude", "longitude", "altitude", "time"}
    OPTIONAL_COLUMNS = {"callsign", "aircraft_id", "icao", "registration", "track_id", "speed", "heading"}

    def __init__(self, file_path: str | Path = None, file_content: bytes = None):
        """
        Initialize loader with either file path or raw file content.

        Args:
            file_path: Path to CSV file
            file_content: Raw bytes of CSV file
        """
        self.file_path = file_path
        self.file_content = file_content
        self.dataframe = None
        self.column_mapping = {}
        self._asterix_columns_found: int = 0

    def _map_asterix_columns(self, df: pd.DataFrame) -> pd.DataFrame:
        """Detect and rename ASTERIX Cat048 columns to canonical names.

        Iterates ASTERIX_COLUMN_PATTERNS and renames matching columns.
        Columns not found are NOT added (remain absent / will appear as NaN
        when accessed). No error is raised for missing optional fields.

        Updates self._asterix_columns_found with the count of matched columns.
        """
        found_cols = set(df.columns)
        rename_map: dict[str, str] = {}
        matched = 0
        for canonical, patterns in ASTERIX_COLUMN_PATTERNS.items():
            # Skip if canonical name already exists (e.g. mapped in earlier step)
            if canonical in found_cols:
                matched += 1
                continue
            for pattern in patterns:
                if pattern in found_cols:
                    rename_map[pattern] = canonical
                    matched += 1
                    break
        self._asterix_columns_found = matched
        if rename_map:
            df = df.rename(columns=rename_map)
        return df

    @property
    def is_asterix_data(self) -> bool:
        """Return True if at least 5 ASTERIX columns were detected in the last load()."""
        return self._asterix_columns_found >= 5

    @staticmethod
    def _detect_delimiter(content: str) -> str:
        """Auto-detect CSV delimiter by frequency in the first line.

        Uses the most-frequent candidate delimiter rather than the first found,
        which avoids misdetection when a delimiter appears inside a field value.
        """
        first_line = content.split("\n")[0] if content else ""
        candidates = [";", ",", "|", "\t"]
        counts = {d: first_line.count(d) for d in candidates}
        best = max(counts, key=counts.get)
        return best if counts[best] > 0 else ","

    def load(self) -> pd.DataFrame:
        """
        Load CSV and return cleaned DataFrame.

        Returns:
            Pandas DataFrame with validated data

        Raises:
            ValueError: If file is invalid or missing required columns
        """
        if self.file_path:
            try:
                content = Path(self.file_path).read_text(encoding="utf-8", errors="replace")
            except Exception as e:
                raise ValueError(f"Cannot read file: {e}")
        elif self.file_content:
            content = self.file_content.decode("utf-8", errors="replace")
        else:
            raise ValueError("Either file_path or file_content must be provided")

        # Auto-detect delimiter
        delimiter = self._detect_delimiter(content)

        # Read CSV
        try:
            df = pd.read_csv(
                io.StringIO(content),
                sep=delimiter,
                decimal=",",  # Spanish format uses comma as decimal
                skipinitialspace=True,
                dtype_backend="numpy_nullable",
            )
        except Exception as e:
            raise ValueError(f"Failed to parse CSV: {str(e)}")

        # Normalize column names (lowercase, strip whitespace)
        df.columns = [col.strip().lower() for col in df.columns]

        # Map ASTERIX-specific columns to canonical names BEFORE any other logic
        df = self._map_asterix_columns(df)

        found_columns = set(df.columns)

        # Smart column mapping - find columns that match patterns
        col_mapping = {}

        # Find latitude column
        lat_col = next((c for c in found_columns if "lat" in c), None)
        if not lat_col:
            raise ValueError("Missing latitude column (looking for 'lat', 'latitude', etc.)")
        col_mapping["latitude"] = lat_col

        # Find longitude column
        lon_col = next((c for c in found_columns if "lon" in c), None)
        if not lon_col:
            raise ValueError("Missing longitude column (looking for 'lon', 'longitude', etc.)")
        col_mapping["longitude"] = lon_col

        # Find altitude column
        alt_col = next((c for c in found_columns if "alt" in c or "h(ft)" in c or "h(m)" in c), None)
        if not alt_col:
            raise ValueError("Missing altitude column (looking for 'alt', 'altitude', 'h(ft)', 'h(m)', etc.)")
        col_mapping["altitude"] = alt_col

        # Find time column
        time_col = next((c for c in found_columns if "time" in c), None)
        if not time_col:
            raise ValueError("Missing time column")
        col_mapping["time"] = time_col

        # Try to find optional columns
        for opt_col in ["callsign", "aircraft_id", "icao", "registration", "speed"]:
            for found_col in found_columns:
                if opt_col in found_col or found_col in opt_col:
                    col_mapping[opt_col] = found_col
                    break

        self.column_mapping = col_mapping

        # Remove duplicate rows FIRST
        df = df.drop_duplicates()

        # Remove rows with critical missing values (BEFORE renaming, using original column names)
        critical_cols = [col_mapping["latitude"], col_mapping["longitude"], col_mapping["time"]]
        df = df.dropna(subset=critical_cols)

        # Rename ONLY the required columns (latitude, longitude, altitude, time)
        rename_map = {
            col_mapping["latitude"]: "latitude",
            col_mapping["longitude"]: "longitude",
            col_mapping["altitude"]: "altitude",
            col_mapping["time"]: "time",
        }
        # Add optional columns if they exist
        for opt_col_key, opt_col_val in col_mapping.items():
            if opt_col_key not in ["latitude", "longitude", "altitude", "time"] and opt_col_val:
                rename_map[opt_col_val] = opt_col_key
        
        df = df.rename(columns=rename_map)

        # Coerce numeric columns. Mixed values like "N/A" force string dtype,
        # so decimal="," from read_csv is bypassed. We re-coerce manually.
        numeric_cols = [
            "latitude", "longitude", "altitude",
            "speed", "fl", "bp", "roll_angle", "tta", "ground_speed",
            "ground_speed_kt", "tar", "tas", "heading", "ias", "mach",
            "baro_alt_rate", "ivv", "rho", "theta", "h_ft", "h_m",
            "track_number",
        ]
        for col in numeric_cols:
            if col in df.columns:
                s = df[col]
                if s.dtype == object or pd.api.types.is_string_dtype(s):
                    s = (
                        s.astype(str)
                        .str.replace(",", ".", regex=False)
                        .str.strip()
                        .replace({"N/A": None, "n/a": None, "": None, "nan": None})
                    )
                df[col] = pd.to_numeric(s, errors="coerce")

        # Parse time column to datetime
        try:
            # Handle HH:MM:SS:mmm format (milliseconds with 3 digits)
            def parse_time_with_millis(time_str):
                """Convert HH:MM:SS:mmm format to datetime using today's date."""
                if pd.isna(time_str) or not isinstance(time_str, str):
                    return pd.NaT
                
                parts = time_str.split(':')
                if len(parts) != 4:
                    # Try standard format if not HH:MM:SS:mmm
                    return pd.to_datetime(time_str, errors='coerce')
                
                try:
                    hour, minute, second, millis = parts
                    # Convert 3-digit milliseconds to 6-digit microseconds
                    micros = millis.ljust(6, '0')
                    # Use today's date + time to avoid 1900 default
                    today = pd.Timestamp.today().date()
                    time_str_with_date = f"{today} {hour}:{minute}:{second}.{micros}"
                    return pd.to_datetime(time_str_with_date, format='%Y-%m-%d %H:%M:%S.%f')
                except Exception:
                    return pd.NaT
            
            df["time"] = df["time"].apply(parse_time_with_millis)

            # Validate that at least some timestamps were parsed successfully
            nat_count = df["time"].isna().sum()
            if nat_count == len(df):
                raise ValueError(
                    "Time column could not be parsed. Expected HH:MM:SS:mmm or standard datetime format."
                )
            # Drop rows where time could not be parsed (NaT)
            if nat_count > 0:
                df = df.dropna(subset=["time"])
        except ValueError:
            raise
        except Exception as e:
            raise ValueError(f"Failed to parse time column: {str(e)}")

        # Validate coordinate ranges (WGS84)
        if (df["latitude"].abs() > 90).any() or (df["longitude"].abs() > 180).any():
            raise ValueError("Invalid coordinate ranges (latitude must be ±90, longitude must be ±180)")

        self.dataframe = df
        return df.copy()

    def validate_schema(self) -> dict:
        """
        Validate data schema and return report.

        Returns:
            Dict with validation status and any warnings
        """
        if self.dataframe is None:
            return {"valid": False, "error": "Data not loaded"}

        report = {
            "valid": True,
            "total_rows": len(self.dataframe),
            "total_columns": len(self.dataframe.columns),
            "columns": list(self.dataframe.columns),
            "warnings": [],
        }

        # Check for null values
        null_counts = self.dataframe.isnull().sum()
        if null_counts.any():
            report["warnings"].append(
                f"Found null values: {null_counts[null_counts > 0].to_dict()}"
            )

        # Check coordinate bounds (Barcelona area)
        lat_min, lat_max = 41.2, 41.4
        lon_min, lon_max = 1.9, 2.2

        out_of_bounds = self.dataframe[
            (self.dataframe["latitude"] < lat_min)
            | (self.dataframe["latitude"] > lat_max)
            | (self.dataframe["longitude"] < lon_min)
            | (self.dataframe["longitude"] > lon_max)
        ]

        if len(out_of_bounds) > 0:
            report["warnings"].append(
                f"Found {len(out_of_bounds)} records outside Barcelona area bounds"
            )

        return report

    def to_dict_records(self, limit: int = None) -> list[dict]:
        """Convert DataFrame to list of dicts, optionally limited."""
        if self.dataframe is None:
            return []

        df = self.dataframe.head(limit) if limit else self.dataframe

        # Select relevant columns for output
        output_cols = ["callsign", "aircraft_id", "latitude", "longitude", "altitude", "time", "speed"]
        available_cols = [col for col in output_cols if col in df.columns]

        return df[available_cols].to_dict("records")
