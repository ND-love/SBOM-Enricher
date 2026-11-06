from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.config import STATIC_DIR, ensure_directories
from app.db import engine
from app.models import Base
from app.routes.ui import router as ui_router
from app.routes.sbom import router as sbom_router

ensure_directories()
Base.metadata.create_all(bind=engine)

app = FastAPI(title="Cert Checker")

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
app.include_router(ui_router)
app.include_router(sbom_router)
