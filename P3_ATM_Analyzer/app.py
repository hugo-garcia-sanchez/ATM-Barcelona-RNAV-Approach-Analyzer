from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from .api.routes.datasets import router as datasets_router
from .api.routes.health import router as health_router
from .api.routes.websocket import router as websocket_router
from .config import get_runtime_root, get_settings
from .database import init_db


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title=settings.app_name)
    frontend_dir = get_runtime_root() / "frontend"

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(health_router, prefix=settings.api_prefix)
    app.include_router(datasets_router, prefix=settings.api_prefix)
    app.include_router(websocket_router)

    if frontend_dir.exists():
        app.mount("/frontend", StaticFiles(directory=frontend_dir), name="frontend")

        @app.get("/")
        def frontend_index() -> FileResponse:
            return FileResponse(frontend_dir / "index.html")

        @app.get("/{path:path}")
        def frontend_fallback(path: str):
            if path.startswith(("api/", "ws/", "docs", "redoc", "openapi")):
                return JSONResponse(status_code=404, content={"detail": "Not Found"})
            candidate = frontend_dir / path
            if candidate.exists() and candidate.is_file():
                return FileResponse(candidate)
            return FileResponse(frontend_dir / "index.html")

    @app.on_event("startup")
    def on_startup() -> None:
        init_db()

    return app