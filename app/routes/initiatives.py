"""Initiatieven routes — F1: aanmaken, F2: bewerken."""

from fastapi import APIRouter, Depends, HTTPException, Request

import json
from datetime import datetime

from app.database import get_db
from app.helpers import render_template
from app.models import (
    Initiative, Hypothesis, InitiativeQuestion, CentralQuestion,
    MDS, Tag, InitiativeTag, TimelineEvent,
)
from app.schemas import (
    InitiativeCreate,
    InitiativeUpdate,
    InitiativeStop,
)
from app.search import update_fts_initiative
from sqlalchemy.orm import Session

router = APIRouter()

# Geheugen-based wijzigingen-logboek (MVP, geen aparte tabel)
# Structuur: { initiative_id: [ { field, old_value, new_value, timestamp } ] }
_changes_log: dict = {}


def _log_change(db, initiative_id: str, field: str, old_value, new_value):
    """Log een wijziging aan een initiatief."""
    if initiative_id not in _changes_log:
        _changes_log[initiative_id] = []
    _changes_log[initiative_id].append({
        "field": field,
        "old_value": old_value,
        "new_value": new_value,
        "timestamp": datetime.now().isoformat(),
    })


def _get_changes(initiative_id: str) -> list:
    """Haal wijzigingen-logboek op voor een initiatief."""
    return _changes_log.get(initiative_id, [])


def _add_timeline_event(db, initiative_id: str, event_type: str, title: str, description: str = None):
    """Voeg een tijdlijn-gebeurtenis toe aan de database."""
    event = TimelineEvent(
        initiative_id=initiative_id,
        event_type=event_type,
        title=title,
        description=description,
    )
    db.add(event)
    db.flush()


@router.get("/lijst")
async def initiatieven_lijst(request: Request, db: Session = Depends(get_db)):
    """Initiatieven overzichtspagina."""
    initiatives = (
        db.query(Initiative)
        .order_by(Initiative.updated_at.desc())
        .all()
    )
    all_mds = db.query(MDS).filter(MDS.is_active == True).order_by(MDS.name.asc()).all()
    all_tags = db.query(Tag).filter(Tag.is_active == True).order_by(Tag.name.asc()).all()
    return render_template(
        "initiatives_list.html",
        request=request,
        initiatives=initiatives,
        all_mds=all_mds,
        all_tags=all_tags,
    )


@router.get("/detail/{initiative_id}")
async def initiatief_detail(request: Request, initiative_id: str, db: Session = Depends(get_db)):
    """Detailpagina voor een initiatief."""
    initiative = db.query(Initiative).filter(
        Initiative.id == initiative_id
    ).first()
    if not initiative:
        raise HTTPException(status_code=404, detail="Initiatief niet gevonden")

    hypotheses = db.query(Hypothesis).filter(
        Hypothesis.initiative_id == initiative_id,
        Hypothesis.parent_hypothesis_id.is_(None),
    ).all()

    # Haal gekoppelde centrale vragen op
    question_ids = (
        db.query(InitiativeQuestion.central_question_id)
        .filter(InitiativeQuestion.initiative_id == initiative_id)
        .all()
    )
    question_ids = [q[0] for q in question_ids]
    central_questions = []
    if question_ids:
        central_questions = (
            db.query(CentralQuestion)
            .filter(CentralQuestion.id.in_(question_ids))
            .order_by(CentralQuestion.question.asc())
            .all()
        )

    # Haal gekoppelde tags op
    tag_ids = (
        db.query(InitiativeTag.tag_id)
        .filter(InitiativeTag.initiative_id == initiative_id)
        .all()
    )
    tag_ids = [t[0] for t in tag_ids]
    tags = []
    if tag_ids:
        tags = (
            db.query(Tag)
            .filter(Tag.id.in_(tag_ids))
            .order_by(Tag.name.asc())
            .all()
        )

    # Haal alle actieve MDS op voor dropdown
    all_mds = db.query(MDS).filter(MDS.is_active == True).order_by(MDS.name.asc()).all()

    # Haal alle actieve tags op voor dropdown
    all_tags = db.query(Tag).filter(Tag.is_active == True).order_by(Tag.name.asc()).all()

    return render_template(
        "initiative_detail.html",
        request=request,
        initiative=initiative,
        hypotheses=hypotheses,
        central_questions=central_questions,
        tags=tags,
        all_mds=all_mds,
        all_tags=all_tags,
        initiative_tag_ids=tag_ids,
    )


@router.post("/create")
async def initiatief_aanmaken(data: InitiativeCreate, db: Session = Depends(get_db)):
    """F1 — Initiatief aanmaken.

    Gebruikt een atomaire transactie: initiatief + koppelingen + FTS + changelog
    worden in één commit gedaan. Bij fout wordt alles teruggedraaid.
    """
    try:
        initiative = Initiative(
            title=data.title,
            description=data.description,
            phase=data.phase,
            horizon=data.horizon,
            mds=data.mds,
            mds_id=data.mds_id,
            central_question=data.central_question,
            trekker=data.trekker,
            owner=data.owner,
            type_ai_gebruik=data.type_ai_gebruik,
        )
        db.add(initiative)
        db.flush()  # Genereer ID zonder te committen

        # Koppel centrale vragen indien opgegeven
        if data.central_question_ids:
            for qid in data.central_question_ids:
                link = InitiativeQuestion(
                    initiative_id=initiative.id,
                    central_question_id=qid,
                )
                db.add(link)

        # Koppel tags indien opgegeven
        if data.tag_ids:
            for tid in data.tag_ids:
                tag_link = InitiativeTag(
                    initiative_id=initiative.id,
                    tag_id=tid,
                )
                db.add(tag_link)

        # Update FTS index
        update_fts_initiative(
            db, initiative.id, initiative.title, initiative.description or ""
        )

        # Log creation
        _log_change(db, initiative.id, "created", None, {
            "title": initiative.title,
            "phase": initiative.phase,
            "status": initiative.status,
        })

        # Log tijdlijn-gebeurtenis: initiatief aangemaakt
        _add_timeline_event(
            db, initiative.id,
            "created",
            f"Initiatief '{initiative.title}' is aangemaakt",
        )

        # Één atomaire commit voor alle wijzigingen
        db.commit()
    except Exception:
        db.rollback()
        raise

    return {
        "id": initiative.id,
        "title": initiative.title,
        "phase": initiative.phase,
        "message": "Initiatief aangemaakt",
    }


@router.put("/{initiative_id}")
async def initiatief_bewerken(initiative_id: str, data: InitiativeUpdate, db: Session = Depends(get_db)):
    """F2 — Initiatief bewerken."""
    initiative = db.query(Initiative).filter(
        Initiative.id == initiative_id
    ).first()
    if not initiative:
        raise HTTPException(status_code=404, detail="Initiatief niet gevonden")

    update_data = data.model_dump(exclude_unset=True)

    # Validatie: gestopt vereist stop_reason
    if "status" in update_data and update_data["status"] == "gestopt":
        if not update_data.get("stop_reason"):
            raise HTTPException(
                status_code=400,
                detail="Leeruitkomst is verplicht bij het stoppen van een initiatief",
            )

    # Log wijzigingen voor fase en status
    tracked_fields = {"phase", "status", "horizon"}
    for field in tracked_fields:
        if field in update_data:
            old_value = getattr(initiative, field)
            new_value = update_data[field]
            if old_value != new_value:
                _log_change(db, initiative.id, field, old_value, new_value)

                # Log ook tijdlijn-gebeurtenis voor fase/status wijzigingen
                if field == "phase":
                    phase_labels = {"verkenning": "Verkenning", "experiment": "Experiment", "pilot": "Pilot", "opschaling": "Opschaling"}
                    _add_timeline_event(
                        db, initiative.id,
                        "phase_change",
                        f"Fase gewijzigd: {phase_labels.get(old_value, old_value)} → {phase_labels.get(new_value, new_value)}",
                    )
                elif field == "status":
                    _add_timeline_event(
                        db, initiative.id,
                        "status_change",
                        f"Status gewijzigd: {old_value} → {new_value}",
                    )

    # Verwerk special fields apart (niet als reguliere attributen)
    cq_ids = update_data.pop("central_question_ids", None)
    tag_ids = update_data.pop("tag_ids", None)

    for key, value in update_data.items():
        setattr(initiative, key, value)

    db.commit()
    db.refresh(initiative)

    # Update centrale vragen koppelingen indien opgegeven
    if cq_ids is not None:
        # Verwijder bestaande koppelingen
        db.query(InitiativeQuestion).filter(
            InitiativeQuestion.initiative_id == initiative_id
        ).delete()
        # Maak nieuwe koppelingen
        for qid in cq_ids:
            link = InitiativeQuestion(
                initiative_id=initiative_id,
                central_question_id=qid,
            )
            db.add(link)
        db.commit()

    # Update tags koppelingen indien opgegeven
    if tag_ids is not None:
        # Verwijder bestaande tags
        db.query(InitiativeTag).filter(
            InitiativeTag.initiative_id == initiative_id
        ).delete()
        # Maak nieuwe tags
        for tid in tag_ids:
            tag_link = InitiativeTag(
                initiative_id=initiative_id,
                tag_id=tid,
            )
            db.add(tag_link)
        db.commit()

    update_fts_initiative(
        db, initiative.id, initiative.title, initiative.description or ""
    )

    return {
        "id": initiative.id,
        "title": initiative.title,
        "phase": initiative.phase,
        "status": initiative.status,
        "message": "Initiatief bijgewerkt",
    }


@router.post("/{initiative_id}/stop")
async def initiatief_stoppen(initiative_id: str, data: InitiativeStop, db: Session = Depends(get_db)):
    """F5 — Stoppen met leeruitkomst."""
    initiative = db.query(Initiative).filter(
        Initiative.id == initiative_id
    ).first()
    if not initiative:
        raise HTTPException(status_code=404, detail="Initiatief niet gevonden")

    # Log status change
    _log_change(db, initiative.id, "status", initiative.status, "gestopt")

    # Log tijdlijn-gebeurtenis: initiatief gestopt
    _add_timeline_event(
        db, initiative.id,
        "status_change",
        f"Initiatief gestopt — {data.stop_reason[:80]}{'…' if data.stop_reason and len(data.stop_reason) > 80 else ''}",
        description=data.stop_reason,
    )

    initiative.status = "gestopt"
    initiative.stop_reason = data.stop_reason
    db.commit()
    db.refresh(initiative)

    return {
        "id": initiative.id,
        "status": initiative.status,
        "stop_reason": initiative.stop_reason,
        "message": "Initiatief gestopt met leeruitkomst",
    }


@router.delete("/{initiative_id}")
async def initiatief_verwijderen(initiative_id: str, db: Session = Depends(get_db)):
    """Verwijder een initiatief."""
    initiative = db.query(Initiative).filter(
        Initiative.id == initiative_id
    ).first()
    if not initiative:
        raise HTTPException(status_code=404, detail="Initiatief niet gevonden")

    db.delete(initiative)
    db.commit()
    return {"message": "Initiatief verwijderd"}


@router.get("/json")
async def initiatieven_json(db: Session = Depends(get_db)):
    """JSON endpoint voor HTMX / AJAX."""
    initiatives = (
        db.query(Initiative)
        .order_by(Initiative.updated_at.desc())
        .all()
    )

    # Haal alle koppelingen op voor efficiëntie
    all_links = db.query(InitiativeQuestion).all()
    init_to_questions = {}
    for link in all_links:
        init_to_questions.setdefault(link.initiative_id, []).append(link.central_question_id)

    # Haal tags op voor efficiëntie
    all_tags = db.query(InitiativeTag).all()
    init_to_tags = {}
    for tag_link in all_tags:
        init_to_tags.setdefault(tag_link.initiative_id, []).append(tag_link.tag_id)

    return [
        {
            "id": i.id,
            "title": i.title,
            "description": i.description,
            "phase": i.phase,
            "status": i.status,
            "horizon": i.horizon,
            "mds": i.mds,  # legacy
            "mds_id": i.mds_id,
            "central_question": i.central_question,  # legacy fallback
            "central_question_ids": init_to_questions.get(i.id, []),
            "tag_ids": init_to_tags.get(i.id, []),
            "trekker": i.trekker,
            "owner": i.owner,
            "type_ai_gebruik": i.type_ai_gebruik,
            "stop_reason": i.stop_reason,
            "created_at": i.created_at.isoformat() if i.created_at else None,
            "updated_at": i.updated_at.isoformat() if i.updated_at else None,
        }
        for i in initiatives
    ]


@router.get("/{initiative_id}")
async def initiatief_json(initiative_id: str, db: Session = Depends(get_db)):
    """JSON endpoint voor één initiatief."""
    initiative = db.query(Initiative).filter(
        Initiative.id == initiative_id
    ).first()
    if not initiative:
        raise HTTPException(status_code=404, detail="Initiatief niet gevonden")

    # Haal koppelingen op
    question_ids = (
        db.query(InitiativeQuestion.central_question_id)
        .filter(InitiativeQuestion.initiative_id == initiative_id)
        .all()
    )
    question_ids = [q[0] for q in question_ids]

    tag_ids = (
        db.query(InitiativeTag.tag_id)
        .filter(InitiativeTag.initiative_id == initiative_id)
        .all()
    )
    tag_ids = [t[0] for t in tag_ids]

    return {
        "id": initiative.id,
        "title": initiative.title,
        "description": initiative.description,
        "phase": initiative.phase,
        "status": initiative.status,
        "horizon": initiative.horizon,
        "mds": initiative.mds,
        "mds_id": initiative.mds_id,
        "central_question": initiative.central_question,
        "central_question_ids": question_ids,
        "tag_ids": tag_ids,
        "trekker": initiative.trekker,
        "owner": initiative.owner,
        "type_ai_gebruik": initiative.type_ai_gebruik,
        "stop_reason": initiative.stop_reason,
        "created_at": initiative.created_at.isoformat() if initiative.created_at else None,
        "updated_at": initiative.updated_at.isoformat() if initiative.updated_at else None,
    }


@router.get("/{initiative_id}/changes")
async def initiatief_changes(initiative_id: str, db: Session = Depends(get_db)):
    """Wijzigingen-logboek voor een initiatief (F2)."""
    initiative = db.query(Initiative).filter(
        Initiative.id == initiative_id
    ).first()
    if not initiative:
        raise HTTPException(status_code=404, detail="Initiatief niet gevonden")

    # Haal changes op uit de metadata (opgeslagen als JSON in extra veld)
    # Voor MVP: we gebruiken een geheugen-based log per sessie
    return _get_changes(initiative_id)


# --- Tijdlijn API ---

@router.get("/{initiative_id}/timeline")
async def initiatief_tijdlijn(initiative_id: str, db: Session = Depends(get_db)):
    """Haal alle tijdlijn-gebeurtenissen op voor een initiatief."""
    initiative = db.query(Initiative).filter(
        Initiative.id == initiative_id
    ).first()
    if not initiative:
        raise HTTPException(status_code=404, detail="Initiatief niet gevonden")

    events = (
        db.query(TimelineEvent)
        .filter(TimelineEvent.initiative_id == initiative_id)
        .order_by(TimelineEvent.created_at.asc())
        .all()
    )

    return [{
        "id": e.id,
        "event_type": e.event_type,
        "title": e.title,
        "description": e.description,
        "created_at": e.created_at.isoformat() if e.created_at else None,
    } for e in events]


@router.post("/{initiative_id}/timeline/milestone")
async def add_milestone(initiative_id: str, data: dict, db: Session = Depends(get_db)):
    """Voeg een handmatige mijlpaal toe aan de tijdlijn."""
    initiative = db.query(Initiative).filter(
        Initiative.id == initiative_id
    ).first()
    if not initiative:
        raise HTTPException(status_code=404, detail="Initiatief niet gevonden")

    title = data.get("title", "Mijlpaal bereikt").strip()
    description = data.get("description", "").strip() or None

    if not title:
        raise HTTPException(status_code=400, detail="Titel is verplicht")

    event = TimelineEvent(
        initiative_id=initiative_id,
        event_type="milestone",
        title=title,
        description=description,
    )
    db.add(event)
    db.commit()
    db.refresh(event)

    return {
        "id": event.id,
        "title": event.title,
        "description": event.description,
        "created_at": event.created_at.isoformat(),
        "message": "Mijlpaal toegevoegd",
    }
