"""Global data storage for current session."""

import pandas as pd
from typing import Optional

# Global state for MVP
_current_dataframe: Optional[pd.DataFrame] = None
_current_filename: Optional[str] = None

# Post-filter processed DataFrame (after AsterixProcessor + stereo coords)
_processed_df: Optional[pd.DataFrame] = None

# Flight plan DataFrame
_flight_plan_df: Optional[pd.DataFrame] = None
_flight_plan_filename: Optional[str] = None


# ---------------------------------------------------------------------------
# Raw radar data (as loaded by CSVLoader, before ASTERIX filters)
# ---------------------------------------------------------------------------

def set_current_data(dataframe: pd.DataFrame, filename: str = None):
    """Store current dataframe in memory."""
    global _current_dataframe, _current_filename
    _current_dataframe = dataframe.copy()
    _current_filename = filename


def get_current_data() -> Optional[pd.DataFrame]:
    """Get current dataframe."""
    return _current_dataframe.copy() if _current_dataframe is not None else None


def get_current_filename() -> Optional[str]:
    """Get current filename."""
    return _current_filename


def clear_current_data():
    """Clear current data."""
    global _current_dataframe, _current_filename
    _current_dataframe = None
    _current_filename = None


# ---------------------------------------------------------------------------
# Processed radar data (after AsterixProcessor filters + stereo coordinates)
# ---------------------------------------------------------------------------

def set_processed_data(dataframe: pd.DataFrame):
    """Store post-filter processed dataframe in memory."""
    global _processed_df
    _processed_df = dataframe.copy()


def get_processed_data() -> Optional[pd.DataFrame]:
    """Get post-filter processed dataframe."""
    return _processed_df.copy() if _processed_df is not None else None


def clear_processed_data():
    """Clear processed data."""
    global _processed_df
    _processed_df = None


# ---------------------------------------------------------------------------
# Flight plan data
# ---------------------------------------------------------------------------

def set_flight_plan(dataframe: pd.DataFrame, filename: str = None):
    """Store flight plan dataframe in memory."""
    global _flight_plan_df, _flight_plan_filename
    _flight_plan_df = dataframe.copy()
    _flight_plan_filename = filename


def get_flight_plan() -> Optional[pd.DataFrame]:
    """Get flight plan dataframe."""
    return _flight_plan_df.copy() if _flight_plan_df is not None else None


def get_flight_plan_filename() -> Optional[str]:
    """Get flight plan filename."""
    return _flight_plan_filename


def clear_flight_plan():
    """Clear flight plan data."""
    global _flight_plan_df, _flight_plan_filename
    _flight_plan_df = None
    _flight_plan_filename = None
