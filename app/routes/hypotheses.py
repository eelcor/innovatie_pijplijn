"""Hypothesen routes — F3: hypothesen en sub-hypothesen."""

from fastapi import APIRouter, Depends, HTTPException

from app.database import get_db
from app.models import Hypothesis
from app.schemas import HypothesisCreate, HypothesisUpdate
from app.search import update_fts_hypothesis
from sqlalchemy.orm import Session

router = APIRouter()


@router.post("/create")
async def hypothese_aanmaken(data: HypothesisCreate, db: Session = Depends(get_db)):
    """F3 — Hypothese (of sub-hypothese) toevoegen."""
    if data.parent_hypothesis_id:
        parent = db.query(Hypothesis).filter(
            Hypothesis.id == data.parent_hypothesis_id
        ).first()
        if not parent:
            raise HTTPException(status_code=404, detail="Ouder-hypothese niet gevonden")

    hypothesis = Hypothesis(
        initiative_id=data.initiative_id,
        parent_hypothesis_id=data.parent_hypothesis_id,
        type=data.type,
        description=data.description,
        status=data.status,
        learning=data.learning,
        commentary=data.commentary,
    )
    db.add(hypothesis)
    db.commit()
    db.refresh(hypothesis)

    update_fts_hypothesis(
        db, hypothesis.id, hypothesis.description, hypothesis.learning or ""
    )

    return {
        "id": hypothesis.id,
        "type": hypothesis.type,
        "description": hypothesis.description,
        "status": hypothesis.status,
        "message": "Hypothese aangemaakt",
    }


@router.put("/{hypothesis_id}")
async def hypothese_bewerken(hypothesis_id: str, data: HypothesisUpdate, db: Session = Depends(get_db)):
    """F3 — Hypothese bewerken met validatie leeruitkomst."""
    hypothesis = db.query(Hypothesis).filter(
        Hypothesis.id == hypothesis_id
    ).first()
    if not hypothesis:
        raise HTTPException(status_code=404, detail="Hypothese niet gevonden")

    update_data = data.model_dump(exclude_unset=True)

    if "status" in update_data and update_data["status"] in ("bevestigd", "weerlegd"):
        if not update_data.get("learning"):
            raise HTTPException(
                status_code=400,
                detail="Leeruitkomst is verplicht bij bevestiging of weerlegging",
            )

    if "status" in update_data and update_data["status"] == "open":
        if "learning" not in update_data:
            update_data["learning"] = None

    for key, value in update_data.items():
        setattr(hypothesis, key, value)

    db.commit()
    db.refresh(hypothesis)

    update_fts_hypothesis(
        db, hypothesis.id, hypothesis.description, hypothesis.learning or ""
    )

    return {
        "id": hypothesis.id,
        "type": hypothesis.type,
        "description": hypothesis.description,
        "status": hypothesis.status,
        "learning": hypothesis.learning,
        "message": "Hypothese bijgewerkt",
    }


@router.delete("/{hypothesis_id}")
async def hypothese_verwijderen(hypothesis_id: str, db: Session = Depends(get_db)):
    """Verwijder een hypothese (en eventuele sub-hypothesen)."""
    hypothesis = db.query(Hypothesis).filter(
        Hypothesis.id == hypothesis_id
    ).first()
    if not hypothesis:
        raise HTTPException(status_code=404, detail="Hypothese niet gevonden")

    db.delete(hypothesis)
    db.commit()
    return {"message": "Hypothese verwijderd"}


@router.get("/initiative/{initiative_id}")
async def hypothesen_per_initiatief(initiative_id: str, db: Session = Depends(get_db)):
    """Alle hypothesen voor een initiatief (inclusief sub-hypothesen)."""
    hypotheses = (
        db.query(Hypothesis)
        .filter(Hypothesis.initiative_id == initiative_id)
        .order_by(Hypothesis.created_at)
        .all()
    )

    def build_tree(hyps, parent_id=None):
        result = []
        for h in hyps:
            if h.parent_hypothesis_id == parent_id:
                children = build_tree(hyps, h.id)
                result.append({
                    "id": h.id,
                    "type": h.type,
                    "description": h.description,
                    "status": h.status,
                    "learning": h.learning,
                    "commentary": h.commentary,
                    "is_sub": parent_id is not None,
                    "sub_hypotheses": children if children else [],
                })
        return result

    tree = build_tree(hypotheses)
    return tree
