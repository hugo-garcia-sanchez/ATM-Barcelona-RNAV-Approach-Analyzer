from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict


class HealthResponse(BaseModel):
    status: str
    app_name: str


class UploadResponse(BaseModel):
    id: int
    filename: str
    file_format: str
    row_count: int
    column_names: list[str]
    has_geo: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class UploadListItem(UploadResponse):
    pass


class DatasetRecordOut(BaseModel):
    id: int
    upload_id: int
    row_index: int
    label: str | None
    latitude: float | None
    longitude: float | None
    payload: dict[str, Any]
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class DatasetSummary(BaseModel):
    upload_id: int
    total_records: int
    geo_records: int
    non_geo_records: int


class InputFileInfo(BaseModel):
    filename: str
    size_bytes: int


class DataRecordMVP(BaseModel):
    # Identificación
    callsign: str | None = None
    aircraft_id: str | None = None
    target_address: str | None = None
    mode3a: str | None = None
    track_number: int | None = None

    # Posición
    latitude: float
    longitude: float
    altitude: float                       # corregida QNH si <6000 ft
    altitude_qnh_ft: float | None = None
    fl: float | None = None
    x_m: float | None = None              # proyección estereográfica
    y_m: float | None = None
    time: str

    # Velocidades
    speed: float | None = None            # legado
    ias: float | None = None
    tas: float | None = None
    ground_speed: float | None = None
    mach: float | None = None

    # Ángulos
    heading: float | None = None
    tta: float | None = None              # true track angle
    roll_angle: float | None = None
    tar: float | None = None              # track angle rate

    # Verticales
    bp: float | None = None               # baro pressure
    ivv: float | None = None
    baro_alt_rate: float | None = None

    # Estado
    stat: str | None = None

    # Plan de vuelo (si mergeado)
    sid: str | None = None
    runway: str | None = None
    aircraft_type: str | None = None
    wake_category: str | None = None
    atot: str | None = None
    destination: str | None = None


class DataResponseMVP(BaseModel):
    total_rows: int
    returned_rows: int
    rows: list[DataRecordMVP]


class UploadDeleteResponse(BaseModel):
    deleted: bool