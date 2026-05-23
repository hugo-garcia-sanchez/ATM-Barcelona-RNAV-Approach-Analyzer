from pathlib import Path

import pandas as pd

from P3_ATM_Analyzer.app import create_app
from P3_ATM_Analyzer.data_processing.csv_loader import CSVLoader
from P3_ATM_Analyzer.data_store import get_processed_data
from P3_ATM_Analyzer.services import reference_tables as rt
from P3_ATM_Analyzer.services.bootstrap import bootstrap_inputs
from P3_ATM_Analyzer.services.combined_export import compute_combined_results
from P3_ATM_Analyzer.services.separations import compute_separations
from P3_ATM_Analyzer.services.threshold_analysis import compute_thresholds


ROOT = Path(__file__).parent
CSV_FILE = ROOT / "data" / "inputs" / "P3_04h_08h.csv"


def test_csv_loader_maps_real_asterix_csv() -> None:
    df = CSVLoader(file_path=CSV_FILE).load()

    assert len(df) == 20_767
    assert {"latitude", "longitude", "altitude", "time"}.issubset(df.columns)
    assert {"callsign", "track_number", "mode3a", "target_address"}.issubset(df.columns)
    assert pd.api.types.is_numeric_dtype(df["latitude"])
    assert pd.api.types.is_numeric_dtype(df["longitude"])
    assert df["time"].notna().all()


def test_reference_tables_match_pdf_values() -> None:
    assert rt.get_wake_separation("J", "H", "TWR") == (6.0, 120)
    assert rt.get_wake_separation("J", "M", "TWR") == (7.0, 180)
    assert rt.get_wake_separation("J", "L", "TWR") == (8.0, 180)
    assert rt.get_wake_separation("H", "M", "TMA") == 5.0
    assert rt.get_wake_separation("M", "M", "TMA") is None

    assert rt.get_loa_separation("HP", "HP", True) == 5.0
    assert rt.get_loa_separation("HP", "HP", False) == 3.0
    assert rt.get_loa_separation("NR+", "HP", True) == 11.0
    assert rt.get_loa_separation("NR-", "NR+", False) == 6.0
    assert rt.get_loa_separation("NR", "NR", True) == 5.0


def test_bootstrap_and_analysis_outputs_are_complete() -> None:
    summary = bootstrap_inputs()
    processed = get_processed_data()

    assert summary["radar"]["rows_after_filters"] == 20_679
    assert processed is not None
    assert len(processed) == 20_679

    separations = compute_separations(processed)
    thresholds = compute_thresholds(processed)
    combined = compute_combined_results(processed)

    assert len(separations) == 121
    assert len(thresholds) == 123
    assert len(combined) == 123
    assert "passes_thr_filter" in thresholds.columns
    assert int(thresholds["passes_thr_filter"].fillna(False).sum()) == 120
    assert "sep_radar_twr_nm" in combined.columns
    assert "turn_turn_start_time" in combined.columns
    assert "nadp_nadp" in combined.columns
    assert "thr_passes_thr_filter" in combined.columns


def test_fastapi_routes_are_registered() -> None:
    app = create_app()
    routes = {route.path for route in app.routes}

    assert "/api/health" in routes
    assert "/api/datasets/mvp/upload" in routes
    assert "/api/datasets/mvp/separations" in routes
    assert "/api/datasets/mvp/combined-results" in routes
