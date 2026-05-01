"""CSV loading and validation module for ATM analyzer."""

import io
from pathlib import Path

import pandas as pd


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

    @staticmethod
    def _detect_delimiter(content: str) -> str:
        """Auto-detect CSV delimiter (;, ,, or |)."""
        first_line = content.split("\n")[0] if content else ""
        delimiters = [";", ",", "|", "\t"]
        for delim in delimiters:
            if delim in first_line:
                return delim
        return ","

    def load(self) -> pd.DataFrame:
        """
        Load CSV and return cleaned DataFrame.

        Returns:
            Pandas DataFrame with validated data

        Raises:
            ValueError: If file is invalid or missing required columns
        """
        if self.file_path:
            content = Path(self.file_path).read_text(encoding="utf-8")
        elif self.file_content:
            content = self.file_content.decode("utf-8")
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

        # Ensure numeric types for coordinates and altitude
        try:
            df["latitude"] = pd.to_numeric(df["latitude"], errors="coerce")
            df["longitude"] = pd.to_numeric(df["longitude"], errors="coerce")
            df["altitude"] = pd.to_numeric(df["altitude"], errors="coerce")
            if "speed" in df.columns:
                df["speed"] = pd.to_numeric(df["speed"], errors="coerce")
        except Exception as e:
            raise ValueError(f"Failed to convert numeric columns: {str(e)}")

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
