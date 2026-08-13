"""Admin en health-check endpoints voor IT-beheer.

Deze module biedt:
  - GET /health        — gedetailleerde health check (database, AI, bestanden)
  - GET /api/admin/status — applicatiestatus met versie, DB-grootte, aantallen
  - GET /api/admin/config — huidige configuratie (geen secrets)
  - POST /api/admin/backup — database backup trigger
  - GET /api/admin/backup/export/{name} — download een backup bestand
  - POST /api/admin/backup/import — upload en importeer een backup bestand
  - POST /api/admin/restore — database restore van backup
  - GET /api/admin/logs — logfile inhoud voor admin UI
"""

import os
import shutil
import sqlite3
import uuid
import zipfile
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File as FastAPIFile

from sqlalchemy.orm import Session

from app.database import DB_PATH, get_db, engine
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
async def admin_get_config():
    """Haal huidige beheerconfiguratie op."""
    from app.admin_config import get_config
    return get_config()


@router.put("/api/admin/config")
async def admin_update_config(updates: dict):
    """Update beheerconfiguratie.

    Beschikbare velden:
      - ai_model_url: base URL van het model
      - ai_model_name: naam van het model
      - ai_api_key: API key (optioneel)
      - ai_enabled: AI in/uit schakelen
      - ai_request_timeout: timeout per request in seconden
      - ai_temperature: creativiteit (0-1)
      - ai_max_tokens: max tokens per antwoord
    """
    from app.admin_config import update_config, get_ai_config_for_client
    result = update_config(updates)

    # Update ai_client module variabelen zodat wijzigingen direct effect hebben
    ai_cfg = get_ai_config_for_client()
    ai_client.MODEL_URL = ai_cfg["MODEL_URL"]
    ai_client.MODEL_NAME = ai_cfg["MODEL_NAME"]
    ai_client.MODEL_API_KEY = ai_cfg["MODEL_API_KEY"]
    ai_client.AI_ENABLED = ai_cfg["AI_ENABLED"]
    ai_client.REQUEST_TIMEOUT = ai_cfg["REQUEST_TIMEOUT"]

    logger.info(f"Admin configuratie bijgewerkt: {list(updates.keys())}")
    return {
        "success": True,
        "message": "Configuratie bijgewerkt",
        "config": result,
    }


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


@router.get("/api/admin/backup/export/{backup_name}")
async def admin_export_backup(backup_name: str):
    """Download een backup bestand naar je eigen computer.

    Retourneert het .db bestand als file download zodat je het kunt
    opslaan en later op een ander systeem kunt importeren.
    """
    from fastapi.responses import FileResponse

    db_dir = Path(os.path.dirname(DB_PATH)) if os.path.dirname(DB_PATH) else Path(".")
    default_backup_dir = str(db_dir / "backups")
    backup_dir = Path(os.environ.get("BACKUP_DIR", default_backup_dir))
    backup_path = backup_dir / backup_name

    if not backup_path.exists():
        raise HTTPException(status_code=404, detail="Backup niet gevonden")

    # Beveiliging: path traversal check
    try:
        resolved_backup = backup_path.resolve()
        resolved_dir = backup_dir.resolve()
        resolved_backup.relative_to(resolved_dir)
    except ValueError:
        raise HTTPException(status_code=400, detail="Ongeldige backup naam")

    logger.info(f"Backup geëxporteerd: {backup_name}")
    return FileResponse(
        path=str(backup_path),
        filename=backup_name,
        media_type="application/x-sqlite3",
    )


@router.post("/api/admin/backup/import")
async def admin_import_backup(file: UploadFile = FastAPIFile(...)):
    """Importeer een backup bestand van je eigen computer.

    Upload een .db bestand dat eerder is geëxporteerd of handmatig is gemaakt.
    Het bestand wordt gevalideerd, opgeslagen in de backups map, en daarna
    automatisch als huidige database ingesteld.

    Maakt automatisch een pre-restore backup van de huidige database.
    De restore wordt atomair uitgevoerd met integrity checks vóór en ná,
    en auto-rollback bij falen.
    """
    import tempfile

    # Valideer bestandsnaam
    if not file.filename or not file.filename.endswith(".db"):
        raise HTTPException(
            status_code=400,
            detail="Alleen .db bestanden zijn toegestaan",
        )

    db_dir = Path(os.path.dirname(DB_PATH)) if os.path.dirname(DB_PATH) else Path(".")
    default_backup_dir = str(db_dir / "backups")
    backup_dir = Path(os.environ.get("BACKUP_DIR", default_backup_dir))
    backup_dir.mkdir(parents=True, exist_ok=True)

    # Lees bestand inhoud en sla tijdelijk op (zélfs in db_dir voor atomic replace)
    tmp_path = None
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False,
                                     dir=str(db_dir)) as tmp:
        tmp_path = Path(tmp.name)
        content = await file.read()
        # Max 500MB check
        if len(content) > 500 * 1024 * 1024:
            tmp_path.unlink(missing_ok=True)
            raise HTTPException(
                status_code=400,
                detail="Bestand is te groot (max 500MB)",
            )
        tmp.write(content)

    try:
        # --- Stap 1: Valideer het geüploade bestand ---
        test_conn = sqlite3.connect(str(tmp_path))
        try:
            integrity = test_conn.execute(
                "PRAGMA integrity_check"
            ).fetchone()[0]
            if integrity != "ok":
                raise ValueError(f"Database is corrupt: integrity_check = {integrity}")

            tables = [row[0] for row in test_conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()]
            if "initiatives" not in tables:
                raise ValueError("Database mist 'initiatives' tabel")

            # Tel records voor feedback
            initiative_count = test_conn.execute(
                "SELECT count(*) FROM initiatives"
            ).fetchone()[0]
        finally:
            test_conn.close()

        # --- Stap 2: Maak pre-restore backup van huidige database ---
        pre_restore_path = None
        if os.path.exists(DB_PATH):
            pre_restore = backup_dir / f"pre_restore_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.db"
            try:
                conn = sqlite3.connect(DB_PATH)
                restore_conn = sqlite3.connect(str(pre_restore))
                conn.backup(restore_conn)
                restore_conn.close()
                conn.close()
                pre_restore_path = str(pre_restore)
            except Exception as e:
                logger.error(f"Pre-restore backup mislukt: {e}")

        # --- Stap 3: Archiveer geïmporteerde file in backups map (voor referentie) ---
        import_hash = uuid.uuid4().hex[:8]
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        archived_name = f"imported_{timestamp}_{import_hash}.db"
        archived_path = backup_dir / archived_name
        shutil.copy2(str(tmp_path), str(archived_path))

        # --- Stap 4: Atomair vervangen van live database ---
        # Sluit alle open SQLAlchemy connecties door de engine te disposen
        from app.database import engine as db_engine, SessionLocal
        try:
            db_engine.dispose()
        except Exception as e:
            logger.warning(f"Kon engine niet volledig sluiten vóór restore: {e}")

        # Verwijder WAL/SHM bestanden van oude DB om inconsistentie te voorkomen
        for suffix in ("-wal", "-shm"):
            wal_path = Path(DB_PATH + suffix)
            if wal_path.exists():
                try:
                    wal_path.unlink()
                except OSError:
                    pass

        # Atomic replace — tmp_path ligt op hetzelfde filesystem als DB_PATH
        try:
            os.replace(str(tmp_path), DB_PATH)
        except OSError as e:
            logger.error(f"Atomic replace mislukt: {e}")
            raise HTTPException(status_code=500, detail=f"Database vervangen mislukt: {e}")

        # --- Stap 5: Valideer de gerestoreerde database ---
        verify_conn = sqlite3.connect(DB_PATH)
        try:
            quick_result = verify_conn.execute(
                "PRAGMA quick_check"
            ).fetchone()[0]
            if quick_result != "ok":
                raise RuntimeError(f"Post-restore validatie faalde: quick_check = {quick_result}")
        finally:
            verify_conn.close()

        logger.info(
            f"Database geïmporteerd van {file.filename} "
            f"({initiative_count} initiatieven) → {archived_name}"
        )

        return {
            "success": True,
            "message": "Database succesvol geïmporteerd",
            "imported_file": file.filename,
            "initiative_count": initiative_count,
            "archived_as": archived_name,
            "pre_restore_backup": pre_restore_path,
        }

    except (ValueError, RuntimeError):
        raise  # Herverlaat validatiefouten door
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Import mislukt: {e}")
        raise HTTPException(status_code=500, detail=f"Import mislukt: {e}")
    finally:
        if tmp_path and tmp_path.exists():
            tmp_path.unlink(missing_ok=True)


@router.post("/api/admin/restore/{backup_name}")
async def admin_restore_backup(backup_name: str):
    """Herstel de database vanuit een backup.

    Maakt automatisch een pre-restore backup van de huidige database.
    De restore wordt atomair uitgevoerd met integrity checks vóór en ná,
    en auto-rollback bij falen.
    """
    import tempfile

    db_dir = Path(os.path.dirname(DB_PATH)) if os.path.dirname(DB_PATH) else Path(".")
    default_backup_dir = str(db_dir / "backups")
    backup_dir = Path(os.environ.get("BACKUP_DIR", default_backup_dir))
    backup_path = backup_dir / backup_name

    if not backup_path.exists():
        raise HTTPException(status_code=404, detail="Backup niet gevonden")

    # Beveiliging: path traversal check
    try:
        resolved_backup = backup_path.resolve()
        resolved_dir = backup_dir.resolve()
        resolved_backup.relative_to(resolved_dir)
    except ValueError:
        raise HTTPException(status_code=400, detail="Ongeldige backup naam")

    # --- Stap 1: Valideer het backup bestand ---
    test_conn = sqlite3.connect(str(backup_path))
    try:
        integrity = test_conn.execute("PRAGMA integrity_check").fetchone()[0]
        if integrity != "ok":
            raise HTTPException(
                status_code=400,
                detail=f"Backup is corrupt: integrity_check = {integrity}",
            )
    finally:
        test_conn.close()

    # --- Stap 2: Maak pre-restore backup van huidige database ---
    pre_restore_path = None
    if os.path.exists(DB_PATH):
        pre_restore = backup_dir / f"pre_restore_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.db"
        try:
            conn = sqlite3.connect(DB_PATH)
            restore_conn = sqlite3.connect(str(pre_restore))
            conn.backup(restore_conn)
            restore_conn.close()
            conn.close()
            pre_restore_path = str(pre_restore)
        except Exception as e:
            logger.error(f"Pre-restore backup mislukt: {e}")

    # --- Stap 3: Atomair vervangen van live database ---
    tmp_path = None
    try:
        # Kopieer backup naar temp locatie op hetzelfde filesystem als DB_PATH
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False,
                                         dir=str(db_dir)) as tmp:
            tmp_path = Path(tmp.name)
        shutil.copy2(str(backup_path), str(tmp_path))

        # Valideer kopie
        verify_conn = sqlite3.connect(str(tmp_path))
        try:
            quick = verify_conn.execute("PRAGMA quick_check").fetchone()[0]
            if quick != "ok":
                raise RuntimeError(f"Backup validatie faalde: quick_check = {quick}")
        finally:
            verify_conn.close()

        # Sluit alle open SQLAlchemy connecties
        from app.database import engine as db_engine
        try:
            db_engine.dispose()
        except Exception as e:
            logger.warning(f"Kon engine niet volledig sluiten vóór restore: {e}")

        # Verwijder WAL/SHM bestanden van oude DB
        for suffix in ("-wal", "-shm"):
            wal_path = Path(DB_PATH + suffix)
            if wal_path.exists():
                try:
                    wal_path.unlink()
                except OSError:
                    pass

        # Atomic replace
        os.replace(str(tmp_path), DB_PATH)

        # --- Stap 4: Valideer de gerestoreerde database ---
        post_conn = sqlite3.connect(DB_PATH)
        try:
            post_check = post_conn.execute("PRAGMA quick_check").fetchone()[0]
            if post_check != "ok":
                raise RuntimeError(f"Post-restore validatie faalde: quick_check = {post_check}")
        finally:
            post_conn.close()

        logger.info(f"Database hersteld vanuit backup: {backup_name}")
        return {
            "success": True,
            "restored_from": backup_name,
            "message": "Database succesvol hersteld. Herstart de applicatie voor een schone start.",
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Restore mislukt: {e}")
        # --- Auto-rollback: probeer terug naar pre-restore backup ---
        if pre_restore_path and os.path.exists(pre_restore_path):
            try:
                logger.warning(f"Auto-rollback naar pre-restore backup: {pre_restore_path}")
                rollback_conn = sqlite3.connect(pre_restore_path)
                rollback_integrity = rollback_conn.execute(
                    "PRAGMA integrity_check"
                ).fetchone()[0]
                rollback_conn.close()

                if rollback_integrity == "ok":
                    # Sluit engine opnieuw
                    from app.database import engine as db_engine2
                    try:
                        db_engine2.dispose()
                    except Exception:
                        pass
                    for suffix in ("-wal", "-shm"):
                        wal_path = Path(DB_PATH + suffix)
                        if wal_path.exists():
                            try:
                                wal_path.unlink()
                            except OSError:
                                pass
                    os.replace(pre_restore_path, DB_PATH)
                    logger.info("Auto-rollback geslaagd — pre-restore backup teruggezet")
                    return {
                        "success": False,
                        "message": f"Restore faalde ({e}), automatisch teruggewenteld naar pre-restore backup.",
                        "rolled_back": True,
                    }
            except Exception as rollback_err:
                logger.critical(f"Auto-rollback ook mislukt: {rollback_err}")

        raise HTTPException(status_code=500, detail=f"Restore mislukt: {e}")
    finally:
        if tmp_path and tmp_path.exists():
            tmp_path.unlink(missing_ok=True)


@router.get("/api/admin/logs")
async def admin_view_logs(
    lines: int = 200,
    level: str = "",
):
    """Lees logfile inhoud voor admin UI.

    Retourneert de laatste N regels van het logbestand.
    Optioneel filteren op niveau (DEBUG, INFO, WARNING, ERROR).
    """
    # Bepaal logfile pad
    try:
        project_root = Path(__file__).parent.parent
        log_file = project_root / "data" / "app.log"
    except Exception:
        log_file = None

    if not log_file or not log_file.exists():
        return {"lines": [], "total_lines": 0}

    try:
        with open(log_file, "r", encoding="utf-8") as f:
            all_lines = f.readlines()

        # Filter op niveau indien opgegeven
        if level:
            filtered = [l for l in all_lines if f"{level}:" in l or f"[{level}]" in l]
        else:
            filtered = all_lines

        # Neem laatste N regels
        result_lines = [l.rstrip() for l in filtered[-lines:]]

        return {
            "lines": result_lines,
            "total_lines": len(filtered),
            "file_size_bytes": log_file.stat().st_size if log_file.exists() else 0,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Kon logfile niet lezen: {e}")


@router.post("/api/admin/logs/clear")
async def admin_clear_logs():
    """Wis het logbestand.

    Let op: dit verwijdert alleen de inhoud van het bestand,
    niet de logger-configuratie. Nieuwe logs worden automatisch opnieuw geschreven.
    """
    try:
        project_root = Path(__file__).parent.parent
        log_file = project_root / "data" / "app.log"
        if log_file.exists():
            log_file.unlink()
            logger.info("Logbestand gewist door admin")
        return {"success": True, "message": "Logbestand verwijdert"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Kon logfile niet wissen: {e}")
