"""Admin en health-check endpoints voor IT-beheer.

Deze module biedt:
  - GET /health        — gedetailleerde health check (database, AI, bestanden)
  - GET /api/admin/status — applicatiestatus met versie, DB-grootte, aantallen
  - GET /api/admin/config — huidige configuratie (geen secrets)
  - POST /api/admin/backup — database backup trigger
"""

import os
import shutil
import zipfile
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException

from sqlalchemy.orm import Session

from app.database import DB_PATH, get_db
from app import ai_client
from app.logging_config import logger
from app.models import Initiative, Hypothesis, Curation, DossierNote, DossierFile

router = APIRouter()


@router.get("/health")
async def health_check(db: Session = Depends(get_db)):
    """Gedetailleerde health check voor Docker / load balancers.

    Retourneert 200 als de applicatie draait en database bereikbaar is.
    Extra component-statussen zijn inclusief in het antwoord.
    """
    components = {}

    # Database check — gebruik injected session (tests) of maak nieuwe (productie)
    try:
        from sqlalchemy import text as sa_text
        db.execute(sa_text("SELECT 1"))
        components["database"] = {"status": "healthy"}
    except Exception as e:
        components["database"] = {"status": "unhealthy", "error": str(e)}

    # AI component check
    ai_status = "disabled" if not ai_client.AI_ENABLED else "enabled"
    if ai_client.MODEL_URL and ai_status == "enabled":
        ai_status = f"enabled ({ai_client.MODEL_NAME})"
    components["ai"] = {"status": ai_status}

    # Upload directory check
    db_dir = Path(os.path.dirname(DB_PATH)) if os.path.dirname(DB_PATH) else Path(".")
    uploads_dir = Path(os.environ.get("UPLOADS_DIR", str(db_dir / "uploads")))
    if uploads_dir.exists():
        components["uploads"] = {"status": "healthy", "path": str(uploads_dir)}
    else:
        components["uploads"] = {"status": "unhealthy", "reason": "directory not found"}

    # Overall status
    db_healthy = components.get("database", {}).get("status") == "healthy"
    overall = "healthy" if db_healthy else "unhealthy"

    return {
        "status": overall,
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "components": components,
    }


@router.get("/api/admin/status")
async def admin_status(db: Session = Depends(get_db)):
    """Applicatiestatus voor IT-dashboard.

    Toont versie-informatie, database-grootte, en aantallen entiteiten.
    """
    counts = {
        "initiatives": db.query(Initiative).count(),
        "hypotheses": db.query(Hypothesis).count(),
        "curations": db.query(Curation).count(),
        "notes": db.query(DossierNote).count(),
        "files": db.query(DossierFile).count(),
    }

    # Database grootte
    try:
        db_size = os.path.getsize(DB_PATH) if os.path.exists(DB_PATH) else 0
    except OSError:
        db_size = 0

    return {
        "version": "0.1.0",
        "environment": os.environ.get("APP_ENV", "development"),
        "database_path": DB_PATH,
        "database_size_bytes": db_size,
        "counts": counts,
        "ai_enabled": ai_client.AI_ENABLED,
        "ai_model": ai_client.MODEL_NAME if ai_client.AI_ENABLED else None,
    }


@router.get("/api/admin/config")
async def admin_config():
    """Huidige configuratie (zonder secrets).

    Toont alle relevante omgevingsvariabelen zodat IT de setup kan verifiëren.
    """
    config = {
        "app": {
            "host": os.environ.get("APP_HOST", "0.0.0.0"),
            "port": os.environ.get("APP_PORT", "8000"),
            "env": os.environ.get("APP_ENV", "development"),
        },
        "database": {
            "path": DB_PATH,
        },
        "ai": {
            "enabled": ai_client.AI_ENABLED,
            "model_url": ai_client.MODEL_URL or "(niet ingesteld)",
            "model_name": ai_client.MODEL_NAME,
            "timeout_seconds": ai_client.REQUEST_TIMEOUT,
            "api_key_set": bool(ai_client.MODEL_API_KEY),
        },
        "logging": {
            "level": os.environ.get("LOG_LEVEL", "INFO"),
            "format": os.environ.get("LOG_FORMAT", "console"),
        },
    }
    return config


@router.post("/api/admin/backup")
async def admin_backup():
    """Maak een backup van de SQLite database en uploads.

    Retourneert het pad naar het backup-bestand.
    """
    if not os.path.exists(DB_PATH):
        raise HTTPException(status_code=500, detail="Database bestand niet gevonden")

    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    db_dir = Path(os.path.dirname(DB_PATH)) if os.path.dirname(DB_PATH) else Path(".")
    default_backup_dir = str(db_dir / "backups")
    backup_dir = Path(os.environ.get("BACKUP_DIR", default_backup_dir))
    backup_dir.mkdir(parents=True, exist_ok=True)

    # Backup database
    db_backup = backup_dir / f"innovatiepijplijn_db_{timestamp}.db"
    try:
        # SQLite online backup via PRAGMA voor consistentie
        import sqlite3
        conn = sqlite3.connect(DB_PATH)
        backup_conn = sqlite3.connect(str(db_backup))
        conn.backup(backup_conn)
        backup_conn.close()
        conn.close()
    except Exception as e:
        logger.error(f"Database backup mislukt: {e}")
        raise HTTPException(status_code=500, detail=f"Backup mislukt: {e}")

    # Backup uploads als zip
    uploads_dir = Path(os.path.dirname(DB_PATH)) / "uploads"
    uploads_backup = None
    if uploads_dir.exists():
        uploads_backup = backup_dir / f"innovatiepijplijn_uploads_{timestamp}.zip"
        try:
            with zipfile.ZipFile(uploads_backup, "w", zipfile.ZIP_DEFLATED) as zf:
                for root, dirs, files in os.walk(uploads_dir):
                    for file in files:
                        file_path = Path(root) / file
                        arc_name = file_path.relative_to(os.path.dirname(DB_PATH))
                        zf.write(file_path, arc_name)
        except Exception as e:
            logger.warning(f"Uploads backup mislukt (database is wel gebackupt): {e}")

    # Cleanup oude backups (houd laatste 10)
    existing_backups = sorted(backup_dir.glob("innovatiepijplijn_db_*.db"), reverse=True)
    for old_backup in existing_backups[10:]:
        try:
            old_backup.unlink()
        except OSError:
            pass

    return {
        "success": True,
        "database_backup": str(db_backup),
        "uploads_backup": str(uploads_backup) if uploads_backup else None,
        "backup_dir": str(backup_dir),
    }


@router.get("/api/admin/backups")
async def admin_list_backups():
    """Lijst van beschikbare backups."""
    db_dir = Path(os.path.dirname(DB_PATH)) if os.path.dirname(DB_PATH) else Path(".")
    default_backup_dir = str(db_dir / "backups")
    backup_dir = Path(os.environ.get("BACKUP_DIR", default_backup_dir))
    if not backup_dir.exists():
        return {"backups": []}

    backups = []
    for f in sorted(backup_dir.glob("innovatiepijplijn_db_*.db"), reverse=True):
        backups.append({
            "filename": f.name,
            "size_bytes": f.stat().st_size,
            "created_at": datetime.fromtimestamp(f.stat().st_mtime).isoformat(),
        })

    return {"backups": backups}


@router.delete("/api/admin/backups/{backup_name}")
async def admin_delete_backup(backup_name: str):
    """Verwijder een specifieke backup."""
    db_dir = Path(os.path.dirname(DB_PATH)) if os.path.dirname(DB_PATH) else Path(".")
    default_backup_dir = str(db_dir / "backups")
    backup_dir = Path(os.environ.get("BACKUP_DIR", default_backup_dir))
    backup_path = backup_dir / backup_name

    if not backup_path.exists():
        raise HTTPException(status_code=404, detail="Backup niet gevonden")

    # Beveiliging: gebruik Path.resolve() en controleer dat het bestand echt onder backup_dir ligt
    try:
        resolved_backup = backup_path.resolve()
        resolved_dir = backup_dir.resolve()
        resolved_backup.relative_to(resolved_dir)
    except ValueError:
        raise HTTPException(status_code=400, detail="Ongeldige backup naam")

    backup_path.unlink()
    return {"success": True, "deleted": backup_name}
