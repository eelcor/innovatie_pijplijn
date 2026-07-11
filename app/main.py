"""FastAPI applicatie — Innovatiepijplijn."""

import os
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, Request
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session

from app.auth import ensure_admin_user, router as auth_router, require_admin
from app.csrf import CSRFMiddleware, AuthMiddleware, router as csrf_router
from app.database import init_db, get_db, DB_PATH
from app.helpers import BASE_DIR, templates, get_base_url
from app.models import DossierFile, User
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

    # Migratie: maak timeline_events tabel als deze nog niet bestaat
    db_migrate = next(get_db())
    try:
        from sqlalchemy import text as sa_text
        db_migrate.execute(sa_text("""
            CREATE TABLE IF NOT EXISTS timeline_events (
                id TEXT PRIMARY KEY,
                initiative_id TEXT NOT NULL REFERENCES initiatives(id) ON DELETE CASCADE,
                event_type TEXT NOT NULL,
                title TEXT NOT NULL,
                description TEXT,
                metadata_json TEXT,
                created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
        """))
        db_migrate.commit()
    finally:
        db_migrate.close()

    # Zorg dat uploads directory bestaat
    uploads_dir = os.path.join(os.path.dirname(DB_PATH) or ".", "uploads")
    os.makedirs(uploads_dir, exist_ok=True)

    # Zorg dat backups directory bestaat
    backup_dir = os.environ.get("BACKUP_DIR", os.path.join(os.path.dirname(DB_PATH) or ".", "backups"))
    os.makedirs(backup_dir, exist_ok=True)

    # Creëer admin gebruiker als APP_ADMIN_PASSWORD is ingesteld
    db_admin = next(get_db())
    try:
        ensure_admin_user(db_admin)
    finally:
        db_admin.close()

    # Laad admin config en update ai_client (admin config heeft prioriteit)
    try:
        from app.admin_config import get_ai_config_for_client
        from app import ai_client
        ai_cfg = get_ai_config_for_client()
        if ai_cfg["MODEL_URL"]:
            ai_client.MODEL_URL = ai_cfg["MODEL_URL"]
            ai_client.MODEL_NAME = ai_cfg["MODEL_NAME"]
            ai_client.MODEL_API_KEY = ai_cfg["MODEL_API_KEY"]
            ai_client.AI_ENABLED = ai_cfg["AI_ENABLED"]
            ai_client.REQUEST_TIMEOUT = ai_cfg["REQUEST_TIMEOUT"]
            logger.info(f"Admin config geladen: model={ai_cfg['MODEL_NAME']}, url={ai_cfg['MODEL_URL']}")
    except Exception as e:
        logger.warning(f"Kon admin config niet laden (geen probleem bij eerste start): {e}")

    # Startup validatie en logging
    logger.info("Innovatiepijplijn start-up")
    logger.info(f"Database: {DB_PATH}")
    logger.info(f"App environment: {os.environ.get('APP_ENV', 'development')}")
    logger.info(f"AI enabled: {os.environ.get('AI_ENABLED', 'true').lower() == 'true'}")

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

# CSRF middleware — beschermt alle POST/PUT/DELETE/PATCH routes
app.add_middleware(CSRFMiddleware)

# Auth middleware — redirect naar /login als niet ingelogd
app.add_middleware(AuthMiddleware)

# Static files
app.mount("/static", StaticFiles(directory=os.path.join(BASE_DIR, "app", "static")), name="static")

# Injecteer APP_BASE_URL in alle template responses via context processor
@app.middleware("http")
async def add_base_url_to_context(request: Request, call_next):
    response = await call_next(request)
    return response

# Registreer base_url als Jinja2 globale waarde
templates.env.globals["base_url"] = get_base_url

# Auth routes (login/logout/user management) — geen CSRF nodig op deze endpoints
# (CSRF wordt toegepast via middleware maar auth routes hebben eigen sessie-beheer)
app.include_router(auth_router, prefix="/api/auth", tags=["authenticatie"])
app.include_router(csrf_router, prefix="/api/auth", tags=["csrf"])


@app.get("/login")
async def login_page(request: Request):
    """Login pagina — wordt geserveerd als HTML template."""
    from app.helpers import render_template
    return render_template("login.html", request=request, error="")


@app.get("/admin")
async def admin_page(
    request: Request,
    current_user: "User" = Depends(require_admin),
):
    """Admin beheerpagina — alleen toegankelijk voor admins."""
    from app.helpers import render_template
    return render_template(
        "admin.html",
        request=request,
        active_page="admin",
        current_user=current_user,
    )

# Route registries
# Route registries — alle routes krijgen een prefix-prefix van APP_BASE_URL indien ingesteld
# Dashboard (geen prefix)
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
from app.routes import export as export_routes
app.include_router(export_routes.router, prefix="/api/export", tags=["export"])


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
