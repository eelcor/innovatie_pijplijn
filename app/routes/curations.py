"""Curaties routes — F6: collecties van initiatieven."""

from fastapi import APIRouter, Depends, HTTPException, Request

from app.auth import (
    perm_curations_read,
    perm_curations_create,
    perm_curations_update,
    perm_curations_delete,
    perm_curation_items_manage,
)
from app.database import get_db
from app.helpers import render_template
from app.models import User, Curation, CurationItem, Initiative
from app.schemas import CurationCreate, CurationItemCreate, CurationUpdate
from app.search import update_fts_curation
from sqlalchemy.orm import Session

router = APIRouter()


@router.get("/lijst")
async def curaties_lijst(
    request: Request,
    user: User = Depends(perm_curations_read),
    db: Session = Depends(get_db),
):
    """Overzichtspagina van alle curaties."""
    curations = (
        db.query(Curation)
        .order_by(Curation.updated_at.desc())
        .all()
    )

    return render_template(
        "curations_list.html",
        request=request,
        curations=curations,
    )


@router.get("/json")
async def curaties_json(
    user: User = Depends(perm_curations_read),
    db: Session = Depends(get_db),
):
    """JSON endpoint voor alle curaties."""
    curations = (
        db.query(Curation)
        .order_by(Curation.updated_at.desc())
        .all()
    )

    result = []
    for c in curations:
        item_count = (
            db.query(CurationItem)
            .filter(CurationItem.curation_id == c.id)
            .count()
        )
        result.append({
            "id": c.id,
            "name": c.name,
            "purpose": c.purpose,
            "description": c.description,
            "item_count": item_count,
            "created_at": c.created_at.isoformat() if c.created_at else None,
            "updated_at": c.updated_at.isoformat() if c.updated_at else None,
        })

    return result


# /detail alias — consistente URL's met andere modules
@router.get("/detail/{curation_id}")
@router.get("/{curation_id}")
async def curatie_detail(
    request: Request,
    curation_id: str,
    user: User = Depends(perm_curations_read),
    db: Session = Depends(get_db),
):
    """Detailpagina voor een curatie met alle initiatieven."""
    curation = db.query(Curation).filter(
        Curation.id == curation_id
    ).first()
    if not curation:
        raise HTTPException(status_code=404, detail="Curatie niet gevonden")

    items = (
        db.query(CurationItem)
        .filter(CurationItem.curation_id == curation_id)
        .order_by(CurationItem.position)
        .all()
    )

    # Bouw een map van initiative_id → Initiative object (voor template)
    initiatives_map = {}
    for item in items:
        init = db.query(Initiative).filter(Initiative.id == item.initiative_id).first()
        if init:
            initiatives_map[item.initiative_id] = init

    return render_template(
        "curation_detail.html",
        request=request,
        curation=curation,
        items=items,
        initiatives_map=dict(initiatives_map),
    )


@router.post("/create")
async def curatie_aanmaken(
    data: CurationCreate,
    user: User = Depends(perm_curations_create),
    db: Session = Depends(get_db),
):
    """F6 — Nieuwe curatie aanmaken."""
    curation = Curation(
        name=data.name,
        purpose=data.purpose,
        description=data.description,
    )
    db.add(curation)
    db.commit()
    db.refresh(curation)

    update_fts_curation(db, curation.id, curation.name, curation.description or "")

    return {
        "id": curation.id,
        "name": curation.name,
        "message": "Curatie aangemaakt",
    }


@router.put("/{curation_id}")
async def curatie_bewerken(
    curation_id: str,
    data: CurationUpdate,
    user: User = Depends(perm_curations_update),
    db: Session = Depends(get_db),
):
    """F6 — Curatie bewerken."""
    curation = db.query(Curation).filter(
        Curation.id == curation_id
    ).first()
    if not curation:
        raise HTTPException(status_code=404, detail="Curatie niet gevonden")

    update_data = data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(curation, key, value)

    db.commit()
    db.refresh(curation)

    if "name" in update_data or "description" in update_data:
        update_fts_curation(db, curation.id, curation.name, curation.description or "")

    return {
        "id": curation.id,
        "name": curation.name,
        "message": "Curatie bijgewerkt",
    }


@router.delete("/{curation_id}")
async def curatie_verwijderen(
    curation_id: str,
    user: User = Depends(perm_curations_delete),
    db: Session = Depends(get_db),
):
    """Verwijder een curatie (en alle items)."""
    curation = db.query(Curation).filter(
        Curation.id == curation_id
    ).first()
    if not curation:
        raise HTTPException(status_code=404, detail="Curatie niet gevonden")

    db.delete(curation)
    db.commit()
    return {"message": "Curatie verwijderd"}


# --- Curatie items (initiatieven in een curatie) ---

@router.post("/{curation_id}/items/add")
async def initiatief_toevoegen_aan_curatie(
    curation_id: str,
    data: dict,
    user: User = Depends(perm_curation_items_manage),
    db: Session = Depends(get_db),
):
    """Voeg een initiatief toe aan een curatie.

    Accepteert: {"initiative_id": "uuid", "position": 0, "note": "..."}
    """
    curation = db.query(Curation).filter(
        Curation.id == curation_id
    ).first()
    if not curation:
        raise HTTPException(status_code=404, detail="Curatie niet gevonden")

    initiative_id = data.get("initiative_id")
    position = data.get("position", 0)
    note = data.get("note")

    if not initiative_id:
        raise HTTPException(status_code=400, detail="initiative_id is verplicht")

    initiative = db.query(Initiative).filter(
        Initiative.id == initiative_id
    ).first()
    if not initiative:
        raise HTTPException(status_code=404, detail="Initiatief niet gevonden")

    # Check of initiatief al in curatie zit
    existing = db.query(CurationItem).filter(
        CurationItem.curation_id == curation_id,
        CurationItem.initiative_id == initiative_id,
    ).first()
    if existing:
        return {"message": "Initiatief zit al in deze curatie", "id": existing.id}

    item = CurationItem(
        curation_id=curation_id,
        initiative_id=initiative_id,
        position=position,
        note=note,
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return {
        "message": "Initiatief toegevoegd aan curatie",
        "id": item.id,
        "position": item.position,
        "note": item.note,
    }


@router.delete("/{curation_id}/items/{item_id}")
async def initiatief_verwijderen_uit_curatie(
    curation_id: str,
    item_id: str,
    user: User = Depends(perm_curation_items_manage),
    db: Session = Depends(get_db),
):
    """Verwijder een initiatief uit een curatie."""
    item = db.query(CurationItem).filter(
        CurationItem.id == item_id,
        CurationItem.curation_id == curation_id,
    ).first()
    if not item:
        raise HTTPException(status_code=404, detail="Item niet gevonden in deze curatie")

    db.delete(item)
    db.commit()
    return {"message": "Initiatief verwijderd uit curatie"}


@router.put("/{curation_id}/items/{item_id}")
async def item_bewerken(
    curation_id: str,
    item_id: str,
    data: dict,
    user: User = Depends(perm_curation_items_manage),
    db: Session = Depends(get_db),
):
    """Bewerk een curatie item (positie of notitie)."""
    item = db.query(CurationItem).filter(
        CurationItem.id == item_id,
        CurationItem.curation_id == curation_id,
    ).first()
    if not item:
        raise HTTPException(status_code=404, detail="Item niet gevonden")

    if "position" in data:
        item.position = data["position"]
    if "note" in data:
        item.note = data["note"]

    db.commit()
    return {"message": "Item bijgewerkt"}


@router.post("/{curation_id}/items/reorder")
async def items_herschikken(
    curation_id: str,
    data: dict,
    user: User = Depends(perm_curation_items_manage),
    db: Session = Depends(get_db),
):
    """Herschik de volgorde van initiatieven in een curatie.

    Accepteert: {"order": [{"initiative_id": "uuid", "position": 0, "note": "..."}, ...]}
    """
    curation = db.query(Curation).filter(
        Curation.id == curation_id
    ).first()
    if not curation:
        raise HTTPException(status_code=404, detail="Curatie niet gevonden")

    order = data.get("order", [])
    for item_data in order:
        initiative_id = item_data.get("initiative_id")
        position = item_data.get("position", 0)
        note = item_data.get("note")

        if not initiative_id:
            continue

        item = db.query(CurationItem).filter(
            CurationItem.curation_id == curation_id,
            CurationItem.initiative_id == initiative_id,
        ).first()
        if item:
            item.position = position
            if note is not None:
                item.note = note

    db.commit()
    return {"message": "Volgorde bijgewerkt"}


@router.get("/{curation_id}/json")
async def curatie_json(
    curation_id: str,
    user: User = Depends(perm_curations_read),
    db: Session = Depends(get_db),
):
    """JSON endpoint voor één curatie met items."""
    curation = db.query(Curation).filter(
        Curation.id == curation_id
    ).first()
    if not curation:
        raise HTTPException(status_code=404, detail="Curatie niet gevonden")

    items = (
        db.query(CurationItem)
        .filter(CurationItem.curation_id == curation_id)
        .order_by(CurationItem.position)
        .all()
    )

    items_data = []
    for item in items:
        init = db.query(Initiative).filter(Initiative.id == item.initiative_id).first()
        items_data.append({
            "item_id": item.id,
            "initiative_id": item.initiative_id,
            "initiative_title": init.title if init else "Onbekend",
            "position": item.position,
            "note": item.note,
        })

    return {
        "id": curation.id,
        "name": curation.name,
        "purpose": curation.purpose,
        "description": curation.description,
        "items": items_data,
        "created_at": curation.created_at.isoformat() if curation.created_at else None,
        "updated_at": curation.updated_at.isoformat() if curation.updated_at else None,
    }
