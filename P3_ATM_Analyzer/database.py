from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Iterator

from .config import get_settings


def _database_path() -> Path:
    settings = get_settings()
    database_url = settings.database_url
    if not database_url.startswith("sqlite:///"):
        raise ValueError("Only sqlite:/// database URLs are supported in the initial implementation")
    return Path(database_url.removeprefix("sqlite:///"))


def get_connection() -> sqlite3.Connection:
    database_path = _database_path()
    database_path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(database_path, check_same_thread=False)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def get_db() -> Iterator[sqlite3.Connection]:
    connection = get_connection()
    try:
        yield connection
    finally:
        connection.close()


def init_db() -> None:
    connection = get_connection()
    try:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS uploads (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                filename TEXT NOT NULL,
                stored_path TEXT NOT NULL,
                file_format TEXT NOT NULL,
                row_count INTEGER NOT NULL DEFAULT 0,
                column_names TEXT NOT NULL DEFAULT '[]',
                has_geo INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS dataset_records (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                upload_id INTEGER NOT NULL,
                row_index INTEGER NOT NULL,
                label TEXT,
                latitude REAL,
                longitude REAL,
                payload TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (upload_id) REFERENCES uploads (id) ON DELETE CASCADE
            );
            """
        )
        connection.commit()
    finally:
        connection.close()


def _parse_upload_row(row: sqlite3.Row) -> dict[str, object]:
    return {
        "id": row["id"],
        "filename": row["filename"],
        "stored_path": row["stored_path"],
        "file_format": row["file_format"],
        "row_count": row["row_count"],
        "column_names": json.loads(row["column_names"]),
        "has_geo": bool(row["has_geo"]),
        "created_at": row["created_at"],
    }


def _parse_record_row(row: sqlite3.Row) -> dict[str, object]:
    return {
        "id": row["id"],
        "upload_id": row["upload_id"],
        "row_index": row["row_index"],
        "label": row["label"],
        "latitude": row["latitude"],
        "longitude": row["longitude"],
        "payload": json.loads(row["payload"]),
        "created_at": row["created_at"],
    }


def fetch_uploads(connection: sqlite3.Connection) -> list[dict[str, object]]:
    rows = connection.execute("SELECT * FROM uploads ORDER BY created_at DESC, id DESC").fetchall()
    return [_parse_upload_row(row) for row in rows]


def fetch_upload(connection: sqlite3.Connection, upload_id: int) -> dict[str, object] | None:
    row = connection.execute("SELECT * FROM uploads WHERE id = ?", (upload_id,)).fetchone()
    if row is None:
        return None
    return _parse_upload_row(row)


def fetch_records(connection: sqlite3.Connection, upload_id: int, limit: int = 100, offset: int = 0) -> list[dict[str, object]]:
    rows = connection.execute(
        """
        SELECT *
        FROM dataset_records
        WHERE upload_id = ?
        ORDER BY row_index ASC, id ASC
        LIMIT ? OFFSET ?
        """,
        (upload_id, limit, offset),
    ).fetchall()
    return [_parse_record_row(row) for row in rows]


def fetch_summary(connection: sqlite3.Connection, upload_id: int) -> dict[str, object] | None:
    upload = fetch_upload(connection, upload_id)
    if upload is None:
        return None

    total_records = connection.execute(
        "SELECT COUNT(*) AS count FROM dataset_records WHERE upload_id = ?",
        (upload_id,),
    ).fetchone()["count"]
    geo_records = connection.execute(
        """
        SELECT COUNT(*) AS count
        FROM dataset_records
        WHERE upload_id = ? AND latitude IS NOT NULL AND longitude IS NOT NULL
        """,
        (upload_id,),
    ).fetchone()["count"]

    return {
        "upload_id": upload_id,
        "total_records": int(total_records),
        "geo_records": int(geo_records),
        "non_geo_records": int(total_records - geo_records),
    }


def delete_upload(connection: sqlite3.Connection, upload_id: int) -> None:
    connection.execute("DELETE FROM uploads WHERE id = ?", (upload_id,))
    connection.commit()