"""Global data storage for current session."""

import pandas as pd
from typing import Optional

# Global state for MVP
_current_dataframe: Optional[pd.DataFrame] = None
_current_filename: Optional[str] = None


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
