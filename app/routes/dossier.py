"""Dossier routes — F4: notities en bestandsuploads."""

import mimetypes
import os
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, UploadFile
from fastapi.responses import FileResponse

from app.database import get_db
from app.files import (
    MAX_FILE_SIZE,
    BASE_DIR,
    UPLOAD_DIR,
    ensure_storage_dir,
    generate_storage_path,
    safe_content_disposition,
    _sanitize_filename,
)
from app.models import DossierFile, DossierNote
from app.schemas import DossierNoteCreate, DossierNoteUpdate
from app.search import update_fts_note
from sqlalchemy.orm import Session

router = APIRouter()


# --- Notities ---

@router.post("/notes/create")
async def notitie_aanmaken(data: DossierNoteCreate, db: Session = Depends(get_db)):
    """Notitie toevoegen aan dossier."""
    note = DossierNote(
        initiative_id=data.initiative_id,
        title=data.title,
        body=data.body,
    )
    db.add(note)
    db.commit()
    db.refresh(note)

    update_fts_note(db, note.id, note.body, note.title or "")

    return {
        "id": note.id,
        "title": note.title,
        "body": note.body,
        "created_at": note.created_at.isoformat() if note.created_at else None,
        "message": "Notitie toegevoegd",
    }


@router.put("/notes/{note_id}")
async def notitie_bewerken(note_id: str, data: DossierNoteUpdate, db: Session = Depends(get_db)):
    """Bewerk een notitie."""
    note = db.query(DossierNote).filter(DossierNote.id == note_id).first()
    if not note:
        raise HTTPException(status_code=404, detail="Notitie niet gevonden")

    if data.title is not None:
        note.title = data.title
    if data.body is not None:
        note.body = data.body

    db.commit()
    db.refresh(note)

    update_fts_note(db, note.id, note.body, note.title or "")

    return {"id": note.id, "message": "Notitie bijgewerkt"}


@router.delete("/notes/{note_id}")
async def notitie_verwijderen(note_id: str, db: Session = Depends(get_db)):
    """Verwijder een notitie."""
    note = db.query(DossierNote).filter(DossierNote.id == note_id).first()
    if not note:
        raise HTTPException(status_code=404, detail="Notitie niet gevonden")

    db.delete(note)
    db.commit()
    return {"message": "Notitie verwijderd"}


@router.get("/notes/{initiative_id}")
async def notities_per_initiatief(initiative_id: str, db: Session = Depends(get_db)):
    """Alle notities voor een initiatief."""
    notes = (
        db.query(DossierNote)
        .filter(DossierNote.initiative_id == initiative_id)
        .order_by(DossierNote.created_at.desc())
        .all()
    )
    return [
        {
            "id": n.id,
            "title": n.title,
            "body": n.body,
            "created_at": n.created_at.isoformat() if n.created_at else None,
        }
        for n in notes
    ]


# --- Bestanden ---

@router.post("/files/upload/{initiative_id}")
async def bestand_uploaden(initiative_id: str, file: UploadFile, db: Session = Depends(get_db)):
    """Bestand uploaden naar dossier.

    Uses UUID-based storage paths. Original filename stored only as metadata.
    """
    contents = await file.read()
    if len(contents) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=400,
            detail=f"Bestand is te groot. Maximum: {MAX_FILE_SIZE // (1024*1024)} MB",
        )

    storage_path, unique_name = generate_storage_path("initiatives", initiative_id, file.filename)
    ensure_storage_dir(storage_path)
    full_path = os.path.join(BASE_DIR, storage_path)

    with open(full_path, "wb") as f:
        f.write(contents)

    mime_type = mimetypes.guess_type(file.filename or "")[0] or "application/octet-stream"

    dossier_file = DossierFile(
        initiative_id=initiative_id,
        filename=file.filename,
        mime_type=mime_type,
        file_size=len(contents),
        storage_path=storage_path,
    )
    db.add(dossier_file)
    db.commit()
    db.refresh(dossier_file)

    return {
        "id": dossier_file.id,
        "filename": dossier_file.filename,
        "file_size": dossier_file.file_size,
        "message": "Bestand geüpload",
    }


@router.get("/files/{initiative_id}")
async def bestanden_per_initiatief(initiative_id: str, db: Session = Depends(get_db)):
    """Alle bestanden voor een initiatief."""
    files = (
        db.query(DossierFile)
        .filter(DossierFile.initiative_id == initiative_id)
        .order_by(DossierFile.uploaded_at.desc())
        .all()
    )
    return [
        {
            "id": f.id,
            "filename": f.filename,
            "mime_type": f.mime_type,
            "file_size": f.file_size,
            "uploaded_at": f.uploaded_at.isoformat() if f.uploaded_at else None,
        }
        for f in files
    ]


@router.get("/files/download/{file_id}")
async def bestand_downloaden(file_id: str, db: Session = Depends(get_db)):
    """Download een bestand uit het dossier."""
    f = db.query(DossierFile).filter(DossierFile.id == file_id).first()
    if not f:
        raise HTTPException(status_code=404, detail="Bestand niet gevonden")

    full_path = os.path.join(BASE_DIR, f.storage_path)
    if not os.path.exists(full_path):
        raise HTTPException(status_code=404, detail="Bestand bestaat niet meer op de schijf")

    return FileResponse(
        full_path,
        filename=_sanitize_filename(f.filename) if f.filename else None,
        media_type=f.mime_type or "application/octet-stream",
        headers={"Content-Disposition": safe_content_disposition(f.filename, "attachment")},
    )


@router.get("/files/view/{file_id}")
async def bestand_viewen(file_id: str, db: Session = Depends(get_db)):
    """Serveer een bestand voor inline weergave (afbeeldingen en PDFs)."""
    f = db.query(DossierFile).filter(DossierFile.id == file_id).first()
    if not f:
        raise HTTPException(status_code=404, detail="Bestand niet gevonden")

    mime = f.mime_type or ""
    # Alleen afbeeldingen en PDFs inline serveren
    if not (mime.startswith("image/") or mime == "application/pdf"):
        raise HTTPException(
            status_code=400,
            detail="Dit bestandstype kan niet worden weergegeven. Download het in plaats daarvan.",
        )

    full_path = os.path.join(BASE_DIR, f.storage_path)
    if not os.path.exists(full_path):
        raise HTTPException(status_code=404, detail="Bestand bestaat niet meer op de schijf")

    return FileResponse(
        full_path,
        filename=_sanitize_filename(f.filename) if f.filename else None,
        media_type=mime,
        headers={"Content-Disposition": safe_content_disposition(f.filename, "inline")},
    )


@router.delete("/files/{file_id}")
async def bestand_verwijderen(file_id: str, db: Session = Depends(get_db)):
    """Verwijder een bestand."""
    f = db.query(DossierFile).filter(DossierFile.id == file_id).first()
    if not f:
        raise HTTPException(status_code=404, detail="Bestand niet gevonden")

    full_path = os.path.join(BASE_DIR, f.storage_path)
    if os.path.exists(full_path):
        os.remove(full_path)

    db.delete(f)
    db.commit()
    return {"message": "Bestand verwijderd"}
