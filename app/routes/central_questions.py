"""Centrale vragen routes — F9: CRUD + koppeling met initiatieven."""

import os
import uuid as uuid_mod
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse

from app.auth import (
    perm_questions_read,
    perm_questions_create,
    perm_questions_update,
    perm_questions_delete,
    perm_questions_files_manage,
)
from app.database import get_db
from app.files import (
    UPLOAD_DIR,
    MAX_FILE_SIZE,
    ensure_storage_dir,
    generate_storage_path,
    safe_content_disposition,
)
from app.helpers import render_template
from app.models import User, CentralQuestion, CentralQuestionFile, Initiative, InitiativeQuestion, QuestionTag, Tag
from app.schemas import (
    CentralQuestionCreate,
    CentralQuestionUpdate,
)
from app.search import update_fts_central_question
from sqlalchemy import func
from sqlalchemy.orm import Session

router = APIRouter()


@router.get("/lijst")
async def centrale_vragen_lijst(
    request: Request,
    user: User = Depends(perm_questions_read),
    db: Session = Depends(get_db),
):
    """Overzichtspagina van alle actieve centrale vragen."""
    questions = (
        db.query(CentralQuestion)
        .filter(CentralQuestion.is_active == True)
        .order_by(CentralQuestion.question.asc())
        .all()
    )

    # Teller per vraag: hoeveel initiatieven gebruiken deze vraag (SQL aggregation)
    count_rows = (
        db.query(InitiativeQuestion.central_question_id, func.count(InitiativeQuestion.initiative_id))
        .group_by(InitiativeQuestion.central_question_id)
        .all()
    )
    question_counts = {row[0]: row[1] for row in count_rows}

    # Aantal initiatieven zonder centrale vraag
    total_initiatives = db.query(Initiative).filter(
        Initiative.status != "gestopt"
    ).count()
    with_question = (
        db.query(InitiativeQuestion.initiative_id)
        .distinct()
        .count()
    )
    without_question = max(0, total_initiatives - with_question)

    # Haal tags per vraag op
    all_qt_links = db.query(QuestionTag).all()
    question_to_tags = {}
    for qt in all_qt_links:
        question_to_tags.setdefault(qt.central_question_id, []).append(qt.tag_id)

    tag_ids_set = set()
    for ids in question_to_tags.values():
        tag_ids_set.update(ids)

    all_tag_records = db.query(Tag).filter(Tag.id.in_(tag_ids_set)).all() if tag_ids_set else []
    tag_map = {t.id: t for t in all_tag_records}

    question_tags = {}
    for qid, tids in question_to_tags.items():
        question_tags[qid] = [tag_map[tid] for tid in tids if tid in tag_map]

    # Haal alle actieve tags op voor dropdown
    all_tags = db.query(Tag).filter(Tag.is_active == True).order_by(Tag.name.asc()).all()

    return render_template(
        "central_questions_list.html",
        request=request,
        questions=questions,
        question_counts=question_counts,
        without_question=without_question,
        question_tags=question_tags,
        all_tags=all_tags,
    )


@router.get("/json")
async def centrale_vragen_json(
    user: User = Depends(perm_questions_read),
    db: Session = Depends(get_db),
):
    """JSON endpoint voor alle actieve centrale vragen."""
    questions = (
        db.query(CentralQuestion)
        .filter(CentralQuestion.is_active == True)
        .order_by(CentralQuestion.question.asc())
        .all()
    )

    result = []
    for q in questions:
        count = (
            db.query(InitiativeQuestion)
            .filter(InitiativeQuestion.central_question_id == q.id)
            .count()
        )
        file_count = (
            db.query(CentralQuestionFile)
            .filter(CentralQuestionFile.central_question_id == q.id)
            .count()
        )
        result.append({
            "id": q.id,
            "question": q.question,
            "description": q.description,
            "initiative_count": count,
            "file_count": file_count,
            "is_active": q.is_active,
            "created_at": q.created_at.isoformat() if q.created_at else None,
        })

    return result


# /detail alias — consistente URL's met andere modules
@router.get("/detail/{question_id}")
@router.get("/{question_id}")
async def centrale_vraag_detail(
    request: Request,
    question_id: str,
    user: User = Depends(perm_questions_read),
    db: Session = Depends(get_db),
):
    """Detailpagina voor een centrale vraag met alle gekoppelde initiatieven."""
    question = db.query(CentralQuestion).filter(
        CentralQuestion.id == question_id
    ).first()
    if not question:
        raise HTTPException(status_code=404, detail="Centrale vraag niet gevonden")

    # Haal alle initiatieven op die aan deze vraag gekoppeld zijn
    initiative_ids = (
        db.query(InitiativeQuestion.initiative_id)
        .filter(InitiativeQuestion.central_question_id == question_id)
        .all()
    )
    initiative_ids = [i[0] for i in initiative_ids]

    initiatives = []
    if initiative_ids:
        initiatives = (
            db.query(Initiative)
            .filter(Initiative.id.in_(initiative_ids))
            .order_by(Initiative.title.asc())
            .all()
        )

    # Haal bestanden op
    files = (
        db.query(CentralQuestionFile)
        .filter(CentralQuestionFile.central_question_id == question_id)
        .order_by(CentralQuestionFile.uploaded_at.desc())
        .all()
    )

    # Haal gekoppelde tags op
    question_tag_ids = (
        db.query(QuestionTag.tag_id)
        .filter(QuestionTag.central_question_id == question_id)
        .all()
    )
    question_tag_ids = [t[0] for t in question_tag_ids]
    tags = []
    if question_tag_ids:
        tags = (
            db.query(Tag)
            .filter(Tag.id.in_(question_tag_ids))
            .order_by(Tag.name.asc())
            .all()
        )

    # Haal alle actieve tags op voor dropdown
    all_tags = db.query(Tag).filter(Tag.is_active == True).order_by(Tag.name.asc()).all()

    return render_template(
        "central_question_detail.html",
        request=request,
        question=question,
        initiatives=initiatives,
        files=files,
        tags=tags,
        all_tags=all_tags,
        question_tag_ids=question_tag_ids,
    )


@router.post("/create")
async def centrale_vraag_aanmaken(
    data: CentralQuestionCreate,
    user: User = Depends(perm_questions_create),
    db: Session = Depends(get_db),
):
    """F9 — Nieuwe centrale vraag aanmaken."""
    # Check of er al een identieke vraag bestaat (soft duplicate detection)
    existing = (
        db.query(CentralQuestion)
        .filter(
            CentralQuestion.question == data.question,
            CentralQuestion.is_active == True,
        )
        .first()
    )
    if existing:
        return {
            "id": existing.id,
            "question": existing.question,
            "message": "Deze vraag bestaat al",
            "already_exists": True,
        }

    question = CentralQuestion(
        question=data.question,
        description=data.description,
    )
    db.add(question)
    db.commit()
    db.refresh(question)

    # Koppel tags indien opgegeven
    if data.tag_ids:
        for tid in data.tag_ids:
            tag_link = QuestionTag(
                central_question_id=question.id,
                tag_id=tid,
            )
            db.add(tag_link)
        db.commit()

    update_fts_central_question(db, question.id, question.question, question.description or "")

    return {
        "id": question.id,
        "question": question.question,
        "description": question.description,
        "message": "Centrale vraag aangemaakt",
        "already_exists": False,
    }


@router.put("/{question_id}")
async def centrale_vraag_bewerken(
    question_id: str,
    data: CentralQuestionUpdate,
    user: User = Depends(perm_questions_update),
    db: Session = Depends(get_db),
):
    """F9 — Centrale vraag bewerken."""
    question = db.query(CentralQuestion).filter(
        CentralQuestion.id == question_id
    ).first()
    if not question:
        raise HTTPException(status_code=404, detail="Centrale vraag niet gevonden")

    update_data = data.model_dump(exclude_unset=True)

    # Verwerk tag_ids apart (niet als regulier attribuut)
    tag_ids = update_data.pop("tag_ids", None)

    for key, value in update_data.items():
        setattr(question, key, value)

    db.commit()
    db.refresh(question)

    # Update tags koppelingen indien opgegeven
    if tag_ids is not None:
        db.query(QuestionTag).filter(
            QuestionTag.central_question_id == question_id
        ).delete()
        for tid in tag_ids:
            tag_link = QuestionTag(
                central_question_id=question_id,
                tag_id=tid,
            )
            db.add(tag_link)
        db.commit()

    if "question" in update_data or "description" in update_data:
        update_fts_central_question(db, question.id, question.question, question.description or "")

    return {
        "id": question.id,
        "question": question.question,
        "description": question.description,
        "is_active": question.is_active,
        "message": "Centrale vraag bijgewerkt",
    }


@router.delete("/{question_id}")
async def centrale_vraag_verwijderen(
    question_id: str,
    user: User = Depends(perm_questions_delete),
    db: Session = Depends(get_db),
):
    """F9 — Centrale vraag soft-delete (zet op inactief)."""
    question = db.query(CentralQuestion).filter(
        CentralQuestion.id == question_id
    ).first()
    if not question:
        raise HTTPException(status_code=404, detail="Centrale vraag niet gevonden")

    question.is_active = False
    db.commit()
    return {"message": "Centrale vraag inactief gezet"}


# --- Koppeling initiatief ↔ centrale vraag ---

@router.post("/{question_id}/initiatives/add/{initiative_id}")
async def vraag_koppelen_aan_initiatief(
    question_id: str,
    initiative_id: str,
    user: User = Depends(perm_questions_update),
    db: Session = Depends(get_db),
):
    """Koppel een centrale vraag aan een initiatief."""
    question = db.query(CentralQuestion).filter(
        CentralQuestion.id == question_id,
        CentralQuestion.is_active == True,
    ).first()
    if not question:
        raise HTTPException(status_code=404, detail="Centrale vraag niet gevonden")

    initiative = db.query(Initiative).filter(
        Initiative.id == initiative_id
    ).first()
    if not initiative:
        raise HTTPException(status_code=404, detail="Initiatief niet gevonden")

    # Check of koppeling al bestaat
    existing = db.query(InitiativeQuestion).filter(
        InitiativeQuestion.initiative_id == initiative_id,
        InitiativeQuestion.central_question_id == question_id,
    ).first()
    if existing:
        return {"message": "Koppeling bestaat al"}

    link = InitiativeQuestion(
        initiative_id=initiative_id,
        central_question_id=question_id,
    )
    db.add(link)
    db.commit()
    return {"message": "Centrale vraag gekoppeld aan initiatief"}


@router.delete("/{question_id}/initiatives/remove/{initiative_id}")
async def vraag_verwijderen_van_initiatief(
    question_id: str,
    initiative_id: str,
    user: User = Depends(perm_questions_update),
    db: Session = Depends(get_db),
):
    """Verwijder koppeling tussen centrale vraag en initiatief."""
    link = db.query(InitiativeQuestion).filter(
        InitiativeQuestion.initiative_id == initiative_id,
        InitiativeQuestion.central_question_id == question_id,
    ).first()
    if not link:
        raise HTTPException(status_code=404, detail="Koppeling niet gevonden")

    db.delete(link)
    db.commit()
    return {"message": "Centrale vraag losgekoppeld van initiatief"}


@router.get("/{question_id}/initiatives")
async def initiatieven_per_vraag(
    question_id: str,
    user: User = Depends(perm_questions_read),
    db: Session = Depends(get_db),
):
    """Alle initiatieven die gekoppeld zijn aan een centrale vraag."""
    question = db.query(CentralQuestion).filter(
        CentralQuestion.id == question_id
    ).first()
    if not question:
        raise HTTPException(status_code=404, detail="Centrale vraag niet gevonden")

    initiative_ids = (
        db.query(InitiativeQuestion.initiative_id)
        .filter(InitiativeQuestion.central_question_id == question_id)
        .all()
    )
    initiative_ids = [i[0] for i in initiative_ids]

    initiatives = (
        db.query(Initiative)
        .filter(Initiative.id.in_(initiative_ids))
        .order_by(Initiative.title.asc())
        .all()
    ) if initiative_ids else []

    return [{
        "id": i.id,
        "title": i.title,
        "phase": i.phase,
        "status": i.status,
    } for i in initiatives]


@router.get("/initiative/{initiative_id}")
async def vragen_per_initiatief(
    initiative_id: str,
    user: User = Depends(perm_questions_read),
    db: Session = Depends(get_db),
):
    """Alle centrale vragen die gekoppeld zijn aan een initiatief."""
    initiative = db.query(Initiative).filter(
        Initiative.id == initiative_id
    ).first()
    if not initiative:
        raise HTTPException(status_code=404, detail="Initiatief niet gevonden")

    question_ids = (
        db.query(InitiativeQuestion.central_question_id)
        .filter(InitiativeQuestion.initiative_id == initiative_id)
        .all()
    )
    question_ids = [q[0] for q in question_ids]

    questions = (
        db.query(CentralQuestion)
        .filter(CentralQuestion.id.in_(question_ids))
        .order_by(CentralQuestion.question.asc())
        .all()
    ) if question_ids else []

    return [{
        "id": q.id,
        "question": q.question,
        "is_active": q.is_active,
    } for q in questions]


@router.post("/initiative/{initiative_id}/set")
async def initiatief_vragen_instellen(
    initiative_id: str,
    data: dict,
    user: User = Depends(perm_questions_update),
    db: Session = Depends(get_db),
):
    """Stel de centrale vragen voor een initiatief in (vervangt bestaande koppelingen).

    Accepteert: {"question_ids": ["uuid1", "uuid2", ...]}
    """
    initiative = db.query(Initiative).filter(
        Initiative.id == initiative_id
    ).first()
    if not initiative:
        raise HTTPException(status_code=404, detail="Initiatief niet gevonden")

    question_ids = data.get("question_ids", [])

    # Valideer dat alle vragen bestaan en actief zijn
    for qid in question_ids:
        q = db.query(CentralQuestion).filter(
            CentralQuestion.id == qid,
            CentralQuestion.is_active == True,
        ).first()
        if not q:
            raise HTTPException(status_code=404, detail=f"Centrale vraag {qid} niet gevonden of inactief")

    # Verwijder bestaande koppelingen
    db.query(InitiativeQuestion).filter(
        InitiativeQuestion.initiative_id == initiative_id
    ).delete()

    # Maak nieuwe koppelingen
    for qid in question_ids:
        link = InitiativeQuestion(
            initiative_id=initiative_id,
            central_question_id=qid,
        )
        db.add(link)

    db.commit()
    return {"message": f"Centrale vragen bijgewerkt ({len(question_ids)} gekoppeld)"}


# --- Bestanden voor centrale vragen ---

# Upload constants imported from app.files


@router.post("/{question_id}/files/upload")
async def upload_vraag_bestand(
    question_id: str,
    file: UploadFile,
    user: User = Depends(perm_questions_files_manage),
    db: Session = Depends(get_db),
):
    """Upload een bestand bij een centrale vraag."""
    question = db.query(CentralQuestion).filter(
        CentralQuestion.id == question_id,
        CentralQuestion.is_active == True,
    ).first()
    if not question:
        raise HTTPException(status_code=404, detail="Centrale vraag niet gevonden")

    # Lees bestand en valideer grootte
    content = await file.read()
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(status_code=400, detail="Bestand is te groot (max 25 MB)")

    # Centralized storage path generation (UUID-only, original name as metadata)
    storage_path, unique_name = generate_storage_path("vragen", question_id, file.filename)
    ensure_storage_dir(storage_path)
    full_path = os.path.join(UPLOAD_DIR, storage_path)

    try:
        # Eerst bestand schrijven
        with open(full_path, "wb") as f:
            f.write(content)

        # Database record — originele filename als metadata
        db_file = CentralQuestionFile(
            central_question_id=question_id,
            filename=file.filename,
            mime_type=file.content_type or "application/octet-stream",
            file_size=len(content),
            storage_path=storage_path,
        )
        db.add(db_file)
        db.commit()
        db.refresh(db_file)

    except Exception:
        # Ruim bestand op bij DB-fout
        if os.path.exists(full_path):
            os.remove(full_path)
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail="Bestand kon niet worden opgeslagen",
        )

    return {
        "id": db_file.id,
        "filename": db_file.filename,
        "file_size": db_file.file_size,
        "message": "Bestand geüpload",
    }


@router.get("/{question_id}/files")
async def vraag_bestanden_lijst(
    question_id: str,
    user: User = Depends(perm_questions_read),
    db: Session = Depends(get_db),
):
    """Lijst van bestanden bij een centrale vraag."""
    question = db.query(CentralQuestion).filter(
        CentralQuestion.id == question_id,
    ).first()
    if not question:
        raise HTTPException(status_code=404, detail="Centrale vraag niet gevonden")

    files = (
        db.query(CentralQuestionFile)
        .filter(CentralQuestionFile.central_question_id == question_id)
        .order_by(CentralQuestionFile.uploaded_at.desc())
        .all()
    )

    return [{
        "id": f.id,
        "filename": f.filename,
        "mime_type": f.mime_type,
        "file_size": f.file_size,
        "uploaded_at": f.uploaded_at.isoformat() if f.uploaded_at else None,
    } for f in files]


@router.get("/{question_id}/files/download/{file_id}")
async def download_vraag_bestand(
    request: Request,
    question_id: str,
    file_id: str,
    user: User = Depends(perm_questions_read),
    db: Session = Depends(get_db),
):
    """Download een bestand van een centrale vraag."""
    f = db.query(CentralQuestionFile).filter(
        CentralQuestionFile.id == file_id,
        CentralQuestionFile.central_question_id == question_id,
    ).first()
    if not f:
        raise HTTPException(status_code=404, detail="Bestand niet gevonden")

    filepath = os.path.join(UPLOAD_DIR, f.storage_path)
    if os.path.exists(filepath):
        return FileResponse(
            filepath,
            headers={"Content-Disposition": safe_content_disposition(f.filename, "attachment")},
            media_type=f.mime_type,
        )
    raise HTTPException(status_code=404, detail="Bestand niet gevonden op schijf")


@router.delete("/{question_id}/files/{file_id}")
async def verwijder_vraag_bestand(
    question_id: str,
    file_id: str,
    user: User = Depends(perm_questions_files_manage),
    db: Session = Depends(get_db),
):
    """Verwijder een bestand van een centrale vraag."""
    f = db.query(CentralQuestionFile).filter(
        CentralQuestionFile.id == file_id,
        CentralQuestionFile.central_question_id == question_id,
    ).first()
    if not f:
        raise HTTPException(status_code=404, detail="Bestand niet gevonden")

    # Verwijder van schijf
    filepath = os.path.join(UPLOAD_DIR, f.storage_path)
    if os.path.exists(filepath):
        os.remove(filepath)

    db.delete(f)
    db.commit()
    return {"message": "Bestand verwijderd"}
