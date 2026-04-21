from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pandas as pd
from fastapi import UploadFile

from ..database import fetch_upload

LATITUDE_COLUMNS = ("lat", "latitude", "y", "latitud")
LONGITUDE_COLUMNS = ("lon", "lng", "long", "longitude", "x", "longitud")
LABEL_COLUMNS = ("name", "label", "airport", "station", "description", "city")


def _normalise_columns(columns: list[str]) -> list[str]:
    return [str(column).strip().lower() for column in columns]


def _candidate_column(columns: list[str], candidates: tuple[str, ...]) -> str | None:
    normalised = _normalise_columns(columns)
    for candidate in candidates:
        if candidate in normalised:
            return columns[normalised.index(candidate)]
    return None


def _read_dataframe(source_path: Path) -> pd.DataFrame:
    suffix = source_path.suffix.lower()
    if suffix in {".xlsx", ".xls"}:
        raise ValueError("Excel files are not enabled with the current dependency set")

    lines = source_path.read_text(encoding="utf-8", errors="ignore").splitlines()
    first_line = lines[0] if lines else ""
    if first_line.count(";") > first_line.count(","):
        return pd.read_csv(source_path, sep=";", decimal=",", na_values=["N/A", "", "null", "None"])

    return pd.read_csv(source_path, na_values=["N/A", "", "null", "None"])


def _extract_label(row: pd.Series, columns: list[str]) -> str | None:
    candidate = _candidate_column(columns, LABEL_COLUMNS)
    if candidate is None:
        return None
    value = row.get(candidate)
    if pd.isna(value):
        return None
    return str(value)


def _extract_geo(row: pd.Series, columns: list[str]) -> tuple[float | None, float | None]:
    latitude_column = _candidate_column(columns, LATITUDE_COLUMNS)
    longitude_column = _candidate_column(columns, LONGITUDE_COLUMNS)
    latitude = None
    longitude = None

    if latitude_column is not None:
        value = row.get(latitude_column)
        if not pd.isna(value):
            latitude = float(value)

    if longitude_column is not None:
        value = row.get(longitude_column)
        if not pd.isna(value):
            longitude = float(value)

    return latitude, longitude


def ingest_upload(conn, upload_file: UploadFile, stored_path: Path) -> dict[str, object]:
    dataframe = _read_dataframe(stored_path)
    columns = list(dataframe.columns)
    has_geo = any(_candidate_column(columns, (candidate,)) for candidate in LATITUDE_COLUMNS) and any(
        _candidate_column(columns, (candidate,)) for candidate in LONGITUDE_COLUMNS
    )

    cursor = conn.execute(
        """
        INSERT INTO uploads (filename, stored_path, file_format, row_count, column_names, has_geo)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            upload_file.filename or stored_path.name,
            str(stored_path),
            stored_path.suffix.lstrip(".").lower(),
            int(len(dataframe)),
            json.dumps([str(column) for column in columns]),
            int(has_geo),
        ),
    )
    upload_id = int(cursor.lastrowid)

    records: list[tuple[object, ...]] = []
    for row_index, row in dataframe.iterrows():
        latitude, longitude = _extract_geo(row, columns)
        records.append(
            (
                upload_id,
                int(row_index),
                _extract_label(row, columns),
                latitude,
                longitude,
                json.dumps(row.to_dict(), default=str),
            )
        )

    conn.executemany(
        """
        INSERT INTO dataset_records (upload_id, row_index, label, latitude, longitude, payload)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        records,
    )
    conn.commit()
    return fetch_upload(conn, upload_id)


def ingest_existing_file(conn, source_path: Path) -> dict[str, object]:
    pseudo_upload = SimpleNamespace(filename=source_path.name)
    return ingest_upload(conn, pseudo_upload, source_path)