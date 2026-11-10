"""MDS routes — H2-2: MDS als entiteit."""

import csv
import io

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from openpyxl import Workbook

from app.auth import (
    perm_mds_read,
    perm_mds_create,
    perm_mds_update,
    perm_mds_delete,
)
from app.database import get_db
from app.helpers import (
    render_template,
    phase_label,
    status_label,
    horizon_label,
    ai_type_label,
    ai_applicatie_model_label,
)
from app.models import User, MDS, Initiative
from app.schemas import MDSCreate, MDSUpdate
from app.routes.export import _style_header, _style_data_rows, _auto_width, _add_title
from sqlalchemy import or_
from sqlalchemy.orm import Session

router = APIRouter()

# Export-kolommen voor MDS-initiatieven: (attribuut, header, label-functie of None)
_EXPORT_COLUMNS = [
    ("title", "Titel", None),
    ("phase", "Fase", phase_label),
    ("status", "Status", status_label),
    ("horizon", "Horizon", horizon_label),
    ("type_ai_gebruik", "Type AI-gebruik", ai_type_label),
    ("ai_applicatie_model", "AI-toepassing", ai_applicatie_model_label),
    ("central_question", "Centrale vraag", None),
    ("owner", "Eigenaar / team", None),
    ("trekker", "Trekker", None),
    ("cluster", "Cluster", None),
    ("afdeling", "Afdeling", None),
    ("team", "Team", None),
    ("potentie", "Potentie", None),
    ("capaciteitsvraag", "Capaciteitsvraag", None),
    ("risico", "Risico", None),
    ("bron_initiatief", "Bron initiatief", None),
    ("externe_partners", "Externe partners", None),
    ("betrokkenheid_iv", "Betrokkenheid IV", None),
    ("volgende_stap", "Volgende stap", None),
    ("stop_reason", "Stopredenen", None),
    ("gerelateerde_initiatieven", "Gerelateerde initiatieven", None),
    ("opmerkingen", "Opmerkingen", None),
    ("description", "Beschrijving", None),
    ("created_at", "Aangemaakt", lambda v: v.strftime("%d-%m-%Y %H:%M") if v else ""),
    ("updated_at", "Bijgewerkt", lambda v: v.strftime("%d-%m-%Y %H:%M") if v else ""),
]


def _export_row(initiative) -> list:
    """Zet een Initiative om naar een export-rij (leesbare waarden)."""
    row = []
    for attr, _header, label_func in _EXPORT_COLUMNS:
        val = getattr(initiative, attr, None)
        if label_func:
            val = label_func(val) if val else ""
        elif val is None:
            val = ""
        row.append(val)
    return row


@router.get("/lijst")
async def mds_lijst(
    request: Request,
    user: User = Depends(perm_mds_read),
    db: Session = Depends(get_db),
):
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
async def mds_json(
    user: User = Depends(perm_mds_read),
    db: Session = Depends(get_db),
):
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
async def mds_detail(
    request: Request,
    mds_id: str,
    user: User = Depends(perm_mds_read),
    db: Session = Depends(get_db),
):
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

    # Initiatieven die nog gekoppeld KUNNEN worden aan deze MDS
    # (niet-gekoppeld, of aan een ander MDS gekoppeld)
    linkable_initiatives = (
        db.query(Initiative)
        .filter(
            or_(
                Initiative.mds_id.is_(None),
                Initiative.mds_id == "",
                Initiative.mds_id != mds_id,
            )
        )
        .order_by(Initiative.title.asc())
        .all()
    )

    return render_template(
        "mds_detail.html",
        request=request,
        mds=mds,
        initiatives=initiatives,
        linkable_initiatives=linkable_initiatives,
    )


@router.get("/{mds_id}/export/csv")
async def mds_export_csv(
    mds_id: str,
    user: User = Depends(perm_mds_read),
    db: Session = Depends(get_db),
):
    """Exporteer alle initiatieven van dit MDS als CSV."""
    mds = db.query(MDS).filter(MDS.id == mds_id).first()
    if not mds:
        raise HTTPException(status_code=404, detail="MDS niet gevonden")

    initiatives = (
        db.query(Initiative)
        .filter(Initiative.mds_id == mds_id)
        .order_by(Initiative.title.asc())
        .all()
    )

    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow([header for _a, header, _f in _EXPORT_COLUMNS])
    for init in initiatives:
        writer.writerow(_export_row(init))

    # BOM zodat Excel de UTF-8 (accenten) correct leest
    content = "\ufeff" + buf.getvalue()
    filename = f"{mds.name.replace(' ', '_')}_initiatieven.csv"
    return StreamingResponse(
        io.BytesIO(content.encode("utf-8")),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/{mds_id}/export/xlsx")
async def mds_export_xlsx(
    mds_id: str,
    user: User = Depends(perm_mds_read),
    db: Session = Depends(get_db),
):
    """Exporteer alle initiatieven van dit MDS als opgemaakt Excel-bestand."""
    mds = db.query(MDS).filter(MDS.id == mds_id).first()
    if not mds:
        raise HTTPException(status_code=404, detail="MDS niet gevonden")

    initiatives = (
        db.query(Initiative)
        .filter(Initiative.mds_id == mds_id)
        .order_by(Initiative.title.asc())
        .all()
    )

    wb = Workbook()
    ws = wb.active
    ws.title = "Initiatieven"

    headers = [header for _a, header, _f in _EXPORT_COLUMNS]
    ws.append(headers)
    for init in initiatives:
        ws.append(_export_row(init))

    _style_header(ws, 1)
    _style_data_rows(ws, 2, 1 + len(initiatives))
    _auto_width(ws)
    ws.freeze_panes = "A2"

    output = io.BytesIO()
    wb.save(output)
    output.seek(0)

    filename = f"{mds.name.replace(' ', '_')}_initiatieven.xlsx"
    return StreamingResponse(
        output,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/create")
async def mds_aanmaken(
    data: MDSCreate,
    user: User = Depends(perm_mds_create),
    db: Session = Depends(get_db),
):
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
async def mds_bewerken(
    mds_id: str,
    data: MDSUpdate,
    user: User = Depends(perm_mds_update),
    db: Session = Depends(get_db),
):
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
async def mds_verwijderen(
    mds_id: str,
    user: User = Depends(perm_mds_delete),
    db: Session = Depends(get_db),
):
    """MDS soft-delete (zet op inactief)."""
    mds = db.query(MDS).filter(MDS.id == mds_id).first()
    if not mds:
        raise HTTPException(status_code=404, detail="MDS niet gevonden")

    mds.is_active = False
    db.commit()
    return {"message": "MDS inactief gezet"}
