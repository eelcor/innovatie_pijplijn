"""Tag routes — H2-1: Tags op initiatieven en centrale vragen."""

from fastapi import APIRouter, Depends, HTTPException, Request

from app.database import get_db
from app.helpers import render_template
from app.models import (
    CentralQuestion,
    Initiative,
    InitiativeTag,
    QuestionTag,
    Tag,
)
from app.schemas import TagCreate, TagUpdate
from sqlalchemy.orm import Session

router = APIRouter()


@router.get("/lijst")
async def tags_lijst(request: Request, db: Session = Depends(get_db)):
    """Overzichtspagina van alle actieve tags."""
    tag_list = (
        db.query(Tag)
        .filter(Tag.is_active == True)
        .order_by(Tag.name.asc())
        .all()
    )

    # Teller per tag: hoeveel initiatieven en centrale vragen
    tag_counts = {}
    for t in tag_list:
        init_count = (
            db.query(InitiativeTag)
            .filter(InitiativeTag.tag_id == t.id)
            .count()
        )
        question_count = (
            db.query(QuestionTag)
            .filter(QuestionTag.tag_id == t.id)
            .count()
        )
        tag_counts[t.id] = {
            "initiative_count": init_count,
            "question_count": question_count,
        }

    return render_template(
        "tags_list.html",
        request=request,
        tag_list=tag_list,
        tag_counts=tag_counts,
    )


@router.get("/json")
async def tags_json(db: Session = Depends(get_db)):
    """JSON endpoint voor alle actieve tags."""
    tag_list = (
        db.query(Tag)
        .filter(Tag.is_active == True)
        .order_by(Tag.name.asc())
        .all()
    )

    result = []
    for t in tag_list:
        init_count = (
            db.query(InitiativeTag)
            .filter(InitiativeTag.tag_id == t.id)
            .count()
        )
        question_count = (
            db.query(QuestionTag)
            .filter(QuestionTag.tag_id == t.id)
            .count()
        )
        result.append({
            "id": t.id,
            "name": t.name,
            "description": t.description,
            "initiative_count": init_count,
            "question_count": question_count,
            "is_active": t.is_active,
            "created_at": t.created_at.isoformat() if t.created_at else None,
        })

    return result


@router.get("/{tag_id}")
async def tag_detail(request: Request, tag_id: str, db: Session = Depends(get_db)):
    """Detailpagina voor een tag met alle gekoppelde initiatieven en vragen."""
    tag = db.query(Tag).filter(Tag.id == tag_id).first()
    if not tag:
        raise HTTPException(status_code=404, detail="Tag niet gevonden")

    # Haal alle initiatieven op die aan deze tag gekoppeld zijn
    initiative_ids = (
        db.query(InitiativeTag.initiative_id)
        .filter(InitiativeTag.tag_id == tag_id)
        .all()
    )
    initiative_ids = [i[0] for i in initiative_ids]

    initiatives = (
        db.query(Initiative)
        .filter(Initiative.id.in_(initiative_ids))
        .order_by(Initiative.title.asc())
        .all()
    ) if initiative_ids else []

    # Haal alle centrale vragen op die aan deze tag gekoppeld zijn
    question_ids = (
        db.query(QuestionTag.central_question_id)
        .filter(QuestionTag.tag_id == tag_id)
        .all()
    )
    question_ids = [q[0] for q in question_ids]

    questions = (
        db.query(CentralQuestion)
        .filter(CentralQuestion.id.in_(question_ids))
        .order_by(CentralQuestion.question.asc())
        .all()
    ) if question_ids else []

    return render_template(
        "tag_detail.html",
        request=request,
        tag=tag,
        initiatives=initiatives,
        questions=questions,
    )


@router.post("/create")
async def tag_aanmaken(data: TagCreate, db: Session = Depends(get_db)):
    """Nieuwe tag aanmaken."""
    # Check of er al een identieke actieve tag bestaat
    existing = (
        db.query(Tag)
        .filter(Tag.name == data.name, Tag.is_active == True)
        .first()
    )
    if existing:
        return {
            "id": existing.id,
            "name": existing.name,
            "message": "Deze tag bestaat al",
            "already_exists": True,
        }

    tag = Tag(
        name=data.name,
        description=data.description or None,
    )
    db.add(tag)
    db.commit()
    db.refresh(tag)

    return {
        "id": tag.id,
        "name": tag.name,
        "description": tag.description,
        "message": "Tag aangemaakt",
        "already_exists": False,
    }


@router.put("/{tag_id}")
async def tag_bewerken(tag_id: str, data: TagUpdate, db: Session = Depends(get_db)):
    """Tag bewerken (hernoemen)."""
    tag = db.query(Tag).filter(Tag.id == tag_id).first()
    if not tag:
        raise HTTPException(status_code=404, detail="Tag niet gevonden")

    update_data = data.model_dump(exclude_unset=True)

    if "name" in update_data:
        # Check of naam al in gebruik door een andere actieve tag
        existing = (
            db.query(Tag)
            .filter(Tag.name == update_data["name"], Tag.is_active == True, Tag.id != tag_id)
            .first()
        )
        if existing:
            raise HTTPException(
                status_code=409,
                detail=f"Tag '{update_data['name']}' bestaat al",
            )

    for key, value in update_data.items():
        setattr(tag, key, value)

    db.commit()
    db.refresh(tag)

    return {
        "id": tag.id,
        "name": tag.name,
        "description": tag.description,
        "message": "Tag bijgewerkt",
    }


@router.delete("/{tag_id}")
async def tag_verwijderen(tag_id: str, db: Session = Depends(get_db)):
    """Tag soft-delete (zet op inactief)."""
    tag = db.query(Tag).filter(Tag.id == tag_id).first()
    if not tag:
        raise HTTPException(status_code=404, detail="Tag niet gevonden")

    tag.is_active = False
    db.commit()
    return {"message": "Tag inactief gezet"}
