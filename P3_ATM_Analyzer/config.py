import os
import sys
from functools import lru_cache
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field


def _default_data_root() -> Path:
    app_data_dir = os.getenv("APP_DATA_DIR")
    if app_data_dir:
        return Path(app_data_dir).expanduser()

    if os.name == "nt":
        app_data = os.getenv("APPDATA")
        if app_data:
            return Path(app_data) / "P3_ATM_Analyzer"

    config_home = os.getenv("XDG_CONFIG_HOME")
    if config_home:
        return Path(config_home) / "p3-atm-analyzer"

    return Path.home() / ".local" / "share" / "p3-atm-analyzer"


def get_runtime_root() -> Path:
    if getattr(sys, "frozen", False):
        bundle_root = getattr(sys, "_MEIPASS", None)
        if bundle_root:
            return Path(bundle_root)
    return Path(__file__).resolve().parent.parent


class Settings(BaseModel):
    model_config = ConfigDict(extra="ignore")

    app_name: str = os.getenv("APP_NAME", "P3 ATM Analyzer")
    api_prefix: str = os.getenv("API_PREFIX", "/api")
    data_root: Path = Field(default_factory=_default_data_root)
    database_url: str | None = os.getenv("DATABASE_URL") or None
    upload_dir: Path | None = Field(default=None)


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    if settings.database_url is None:
        settings.database_url = f"sqlite:///{(settings.data_root / 'app.db').as_posix()}"
    if settings.upload_dir is None:
        settings.upload_dir = settings.data_root / "inputs"

    settings.data_root.mkdir(parents=True, exist_ok=True)
    settings.upload_dir.mkdir(parents=True, exist_ok=True)
    return settings