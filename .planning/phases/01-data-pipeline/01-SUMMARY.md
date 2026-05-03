---
phase: "01"
plan: "01"
subsystem: data-pipeline
tags: [asterix, csv, geospatial, flight-plan, qnh]
dependency_graph:
  requires: []
  provides:
    - asterix-column-mapping
    - asterix-processor-filters
    - stereographic-projection
    - flight-plan-loader
    - processed-data-store
  affects:
    - api/routes/datasets.py
    - data_store.py
tech_stack:
  added: []
  patterns:
    - method-chaining filter pipeline
    - canonical column mapping via pattern lists
    - in-memory dual-DataFrame store (raw + processed)
key_files:
  created:
    - P3_ATM_Analyzer/data_processing/asterix_processor.py
    - P3_ATM_Analyzer/data_processing/flight_plan_loader.py
    - P3_ATM_Analyzer/geospatial/__init__.py
    - P3_ATM_Analyzer/geospatial/coordinate_transform.py
  modified:
    - P3_ATM_Analyzer/data_processing/csv_loader.py
    - P3_ATM_Analyzer/data_store.py
    - P3_ATM_Analyzer/api/routes/datasets.py
decisions:
  - "Stereographic projection uses azimuthal equidistant approximation centred at LEBL RWY 24L threshold (valid <500 km)"
  - "AsterixProcessor falls back to raw DataFrame if columns are missing (non-ASTERIX CSV gracefully handled)"
  - "Flight plan merge is best-effort (left join on callsign); missing plans produce NaN not error"
  - "data_store keeps both raw and processed DataFrames to support raw table view + filtered analysis simultaneously"
metrics:
  duration_minutes: 15
  completed_date: "2026-05-03"
  tasks_completed: 5
  tasks_total: 5
  files_created: 4
  files_modified: 3
---

# Phase 01 Plan 01: Data Pipeline & Procesamiento Core ASTERIX Summary

**One-liner:** Full ASTERIX Cat048 data pipeline — column mapping, geographic/airborne/FL/QNH filters, stereographic projection, flight plan merge, and dual-store API endpoints.

## Tasks Completed

| Task | Name | Commit | Key Files |
|------|------|--------|-----------|
| T01-01 | ASTERIX column mapping in CSVLoader | 0eb44cc | csv_loader.py |
| T01-02 | AsterixProcessor filters + QNH correction | 49b87ce | asterix_processor.py |
| T01-03 | Geospatial stereographic projection module | bc750d9 | geospatial/coordinate_transform.py |
| T01-04 | FlightPlanLoader CSV load + radar merge | 195a507 | flight_plan_loader.py |
| T01-05 | Pipeline integration in data_store + API | a3efd9b | data_store.py, datasets.py |

## What Was Built

### T01-01 — ASTERIX column mapping (csv_loader.py)
Added `ASTERIX_COLUMN_PATTERNS` dict with 17 entries covering all Cat048 fields (fl, tod, track_number, stat, callsign, bp, roll_angle, tta, ground_speed, tar, tas, mh, ias, baro_alt_rate, ivv, rho, theta). The `_map_asterix_columns(df)` method detects and renames columns before any further processing. The `is_asterix_data` property returns True when ≥5 ASTERIX columns are found.

### T01-02 — AsterixProcessor (asterix_processor.py)
Method-chaining class applying five filters in order:
1. Geographic bounding box: 40.9–41.7 N, 1.5–2.6 E
2. Airborne filter: excludes stat columns containing "ground"
3. FL null filter: drops rows without a Flight Level
4. QNH correction: `altitude_qnh_ft = FL*100 + (BP - 1013.25) * 30`
5. Altitude ceiling: keeps only records ≤ 6000 ft

### T01-03 — Geospatial module (geospatial/coordinate_transform.py)
Azimuthal equidistant projection centred at LEBL RWY 24L threshold (41.2865 N, 2.0759 E). Functions: `wgs84_to_stereographic`, `stereographic_to_wgs84`, `distance_nm` (haversine), `distance_m_stereo` (euclidean), `bearing_deg`, `add_stereo_columns(df)`, `dvor_bcn_radial` (FROM radial of DVOR BCN at 41.307111 N, 2.107806 E).

### T01-04 — FlightPlanLoader (flight_plan_loader.py)
Loads flight plan CSV with auto-delimiter detection and 8-column canonical mapping (callsign, destination, atot, route, aircraft_type, wake_cat, sid, runway). `WAKE_MAP` normalises J/H/M/L to Spanish labels. `merge_with_radar()` performs a left join on callsign adding wake_cat, sid, runway_fp, aircraft_type, destination, atot, route.

### T01-05 — API integration (data_store.py, datasets.py)
- `data_store.py`: added `_processed_df` and `_flight_plan_df` with getters/setters.
- `POST /api/datasets/mvp/upload`: now runs AsterixProcessor + add_stereo_columns + optional flight plan merge; response includes `rows_after_filters`.
- `POST /api/datasets/mvp/upload-flight-plan`: new endpoint for flight plan CSV; auto-merges with loaded radar data.
- `GET /api/datasets/mvp/processed`: serves post-filter DataFrame.
- `GET /api/datasets/mvp/info`: now includes `rows_after_filters`.

## Decisions Made

1. **Azimuthal equidistant vs full stereographic:** For distances <500 km the planar approximation is equivalent; avoids adding pyproj dependency.
2. **Graceful degradation:** If AsterixProcessor fails (e.g. CSV lacks required columns), the endpoint falls back to the raw DataFrame so the app remains functional.
3. **Dual DataFrame store:** Keeping raw and processed DataFrames separately allows the raw table view to show all data while analysis uses filtered data.
4. **Left-join flight plan merge:** Missing flight plans produce NaN columns rather than dropping radar rows, preserving all track data.

## Deviations from Plan

None — plan executed exactly as written. Minor addition: `_df_to_mvp_records` helper extracted into standalone function (avoids duplication between `/mvp/data` and `/mvp/processed` endpoints).

## Known Stubs

None. All implemented functionality is wired end-to-end.

## Self-Check

Files created/exist:
- P3_ATM_Analyzer/data_processing/asterix_processor.py — FOUND
- P3_ATM_Analyzer/data_processing/flight_plan_loader.py — FOUND
- P3_ATM_Analyzer/geospatial/__init__.py — FOUND
- P3_ATM_Analyzer/geospatial/coordinate_transform.py — FOUND

Commits:
- 0eb44cc — FOUND
- 49b87ce — FOUND
- bc750d9 — FOUND
- 195a507 — FOUND
- a3efd9b — FOUND

## Self-Check: PASSED
