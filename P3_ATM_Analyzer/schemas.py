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


class UploadDeleteResponse(BaseModel):
    deleted: bool