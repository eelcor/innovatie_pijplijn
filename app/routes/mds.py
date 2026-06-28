"""MDS routes — H2-2: MDS als entiteit."""

from fastapi import APIRouter, Depends, HTTPException, Request

from app.database import get_db
from app.helpers import render_template
from app.models import MDS, Initiative
from app.schemas import MDSCreate, MDSUpdate
from sqlalchemy.orm import Session

router = APIRouter()


@router.get("/lijst")
async def mds_lijst(request: Request, db: Session = Depends(get_db)):
    """Overzichtspagina van alle actieve MDS."""
    mds_list = (
        db.query(MDS)
        .filter(MDS.is_active == True)
        .order_by(MDS.name.asc())
        .all()
    )

    # Teller per MDS: hoeveel initiatieven behoren tot deze MDS
    mds_counts = {}
    for m in mds_list:
        count = (
            db.query(Initiative)
            .filter(Initiative.mds_id == m.id)
            .count()
        )
        mds_counts[m.id] = count

    return render_template(
        "mds_list.html",
        request=request,
        mds_list=mds_list,
        mds_counts=mds_counts,
    )


@router.get("/json")
async def mds_json(db: Session = Depends(get_db)):
    """JSON endpoint voor alle actieve MDS."""
    mds_list = (
        db.query(MDS)
        .filter(MDS.is_active == True)
        .order_by(MDS.name.asc())
        .all()
    )

    result = []
    for m in mds_list:
        count = (
            db.query(Initiative)
            .filter(Initiative.mds_id == m.id)
            .count()
        )
        result.append({
            "id": m.id,
            "name": m.name,
            "description": m.description,
            "initiative_count": count,
            "is_active": m.is_active,
            "created_at": m.created_at.isoformat() if m.created_at else None,
        })

    return result


@router.get("/{mds_id}")
async def mds_detail(request: Request, mds_id: str, db: Session = Depends(get_db)):
    """Detailpagina voor een MDS met alle gekoppelde initiatieven."""
    mds = db.query(MDS).filter(MDS.id == mds_id).first()
    if not mds:
        raise HTTPException(status_code=404, detail="MDS niet gevonden")

    # Haal alle initiatieven op die tot deze MDS behoren
    initiatives = (
        db.query(Initiative)
        .filter(Initiative.mds_id == mds_id)
        .order_by(Initiative.title.asc())
        .all()
    )

    return render_template(
        "mds_detail.html",
        request=request,
        mds=mds,
        initiatives=initiatives,
    )


@router.post("/create")
async def mds_aanmaken(data: MDSCreate, db: Session = Depends(get_db)):
    """Nieuwe MDS aanmaken."""
    # Check of er al een identieke MDS bestaat
    existing = (
        db.query(MDS)
        .filter(MDS.name == data.name, MDS.is_active == True)
        .first()
    )
    if existing:
        return {
            "id": existing.id,
            "name": existing.name,
            "message": "Deze MDS bestaat al",
            "already_exists": True,
        }

    mds = MDS(
        name=data.name,
        description=data.description,
    )
    db.add(mds)
    db.commit()
    db.refresh(mds)

    return {
        "id": mds.id,
        "name": mds.name,
        "description": mds.description,
        "message": "MDS aangemaakt",
        "already_exists": False,
    }


@router.put("/{mds_id}")
async def mds_bewerken(mds_id: str, data: MDSUpdate, db: Session = Depends(get_db)):
    """MDS bewerken."""
    mds = db.query(MDS).filter(MDS.id == mds_id).first()
    if not mds:
        raise HTTPException(status_code=404, detail="MDS niet gevonden")

    update_data = data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(mds, key, value)

    db.commit()
    db.refresh(mds)

    return {
        "id": mds.id,
        "name": mds.name,
        "description": mds.description,
        "message": "MDS bijgewerkt",
    }


@router.delete("/{mds_id}")
async def mds_verwijderen(mds_id: str, db: Session = Depends(get_db)):
    """MDS soft-delete (zet op inactief)."""
    mds = db.query(MDS).filter(MDS.id == mds_id).first()
    if not mds:
        raise HTTPException(status_code=404, detail="MDS niet gevonden")

    mds.is_active = False
    db.commit()
    return {"message": "MDS inactief gezet"}
