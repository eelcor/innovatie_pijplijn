"""FastAPI applicatie — Innovatiepijplijn."""

import os
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, Request
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session

from app.database import init_db, get_db, DB_PATH
from app.helpers import BASE_DIR, templates
from app.models import DossierFile
from app.search import create_fts_table
from app.routes import dashboard, initiatives, hypotheses, dossier, curations, central_questions, mds, tags, ai
from app.admin import router as admin_router
from app.logging_config import logger


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Start-up en shut-down logica inclusief configuratie-validatie."""
    init_db()

    # Maak FTS tabel aan
    db_next = next(get_db())
    try:
        create_fts_table(db_next)
    finally:
        db_next.close()

    # Zorg dat uploads directory bestaat
    uploads_dir = os.path.join(os.path.dirname(DB_PATH) or ".", "uploads")
    os.makedirs(uploads_dir, exist_ok=True)

    # Zorg dat backups directory bestaat
    backup_dir = os.environ.get("BACKUP_DIR", os.path.join(os.path.dirname(DB_PATH) or ".", "backups"))
    os.makedirs(backup_dir, exist_ok=True)

    # Startup validatie en logging
    logger.info("Innovatiepijplijn start-up")
    logger.info(f"Database: {DB_PATH}")
    logger.info(f"App environment: {os.environ.get('APP_ENV', 'development')}")
    logger.info(f"AI enabled: {os.environ.get('AI_ENABLED', 'true').lower() == 'true'}")

    from app import ai_client
    if ai_client.AI_ENABLED:
        if not ai_client.MODEL_URL:
            logger.warning("AI is ingeschakeld maar MODEL_URL is niet ingesteld — AI features zullen falen")
        else:
            logger.info(f"AI model: {ai_client.MODEL_NAME} @ {ai_client.MODEL_URL}")
    else:
        logger.info("AI is uitgeschakeld via AI_ENABLED=false")

    yield

    logger.info("Innovatiepijplijn shut-down")


app = FastAPI(
    title="Innovatiepijplijn",
    description="Registratie- en analysetool voor innovatie-initiatieven",
    version="0.1.0",
    lifespan=lifespan,
)

# Static files
app.mount("/static", StaticFiles(directory=os.path.join(BASE_DIR, "app", "static")), name="static")

# Route registries
app.include_router(dashboard.router, tags=["dashboard"])
app.include_router(initiatives.router, prefix="/api/initiatieven", tags=["initiatieven"])
app.include_router(hypotheses.router, prefix="/api/hypothesen", tags=["hypothesen"])
app.include_router(dossier.router, prefix="/api/dossier", tags=["dossier"])
app.include_router(curations.router, prefix="/api/curaties", tags=["curaties"])
app.include_router(central_questions.router, prefix="/api/vragen", tags=["centrale vragen"])
app.include_router(mds.router, prefix="/api/mds", tags=["mds"])
app.include_router(tags.router, prefix="/api/tags", tags=["tags"])
app.include_router(ai.router, tags=["ai"])
app.include_router(admin_router, tags=["admin"])


# --- Bestandsdownload ---

@app.get("/api/dossier/download/{initiative_id}/{file_id}")
async def download_file(request: Request, initiative_id: str, file_id: str, db: Session = Depends(get_db)):
    """Download een dossierbestand."""
    f = db.query(DossierFile).filter(
        DossierFile.id == file_id,
        DossierFile.initiative_id == initiative_id,
    ).first()
    if not f:
        return {"error": "Bestand niet gevonden"}
    filepath = os.path.join(BASE_DIR, f.storage_path)
    if os.path.exists(filepath):
        return FileResponse(
            filepath,
            filename=f.filename,
            media_type=f.mime_type,
        )
    return {"error": "Bestand niet gevonden op schijf"}
