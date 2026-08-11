"""Dashboard routes — F8: Eenvoudig dashboard."""

from fastapi import APIRouter, Depends, Query, Request

from app.auth import perm_initiatives_read
from app.database import get_db
from app.helpers import render_template
from app.models import User, Initiative, Hypothesis, InitiativeQuestion, InitiativeTag, MDS, Tag
from sqlalchemy import func
from sqlalchemy.orm import Session

router = APIRouter()


@router.get("/")
async def dashboard_page(
    request: Request,
    user: User = Depends(perm_initiatives_read),
    db: Session = Depends(get_db),
):
    """Hoofdscherm — Dashboard met statistieken en lijsten.

    Uses SQL aggregation for counts instead of loading all records into memory.
    """
    # Aantal initiatieven per fase (SQL aggregation)
    phase_rows = (
        db.query(Initiative.phase, func.count(Initiative.id))
        .group_by(Initiative.phase)
        .all()
    )
    phase_counts = {row[0]: row[1] for row in phase_rows}
    for phase in ["idee", "verkenning", "experiment", "pilot", "opschaling"]:
        phase_counts.setdefault(phase, 0)

    # Aantal per horizon (SQL aggregation)
    horizon_rows = (
        db.query(Initiative.horizon, func.count(Initiative.id))
        .group_by(Initiative.horizon)
        .all()
    )
    horizon_counts = {}
    no_horizon = 0
    for row in horizon_rows:
        if row[0] and row[0].strip():
            horizon_counts[row[0]] = row[1]
        else:
            no_horizon = row[1]
    for h in ["h1", "h2", "h3"]:
        horizon_counts.setdefault(h, 0)

    # Aantal per status (SQL aggregation)
    status_rows = (
        db.query(Initiative.status, func.count(Initiative.id))
        .group_by(Initiative.status)
        .all()
    )
    status_counts = {row[0]: row[1] for row in status_rows}
    for s in ["actief", "gestopt", "afgerond"]:
        status_counts.setdefault(s, 0)

    # Totaal hypothesen getoetst (status != open) — SQL aggregation
    tested_count = (
        db.query(func.count(Hypothesis.id))
        .filter(Hypothesis.status != "open")
        .scalar()
    )

    # Aantal actieve initiatieven zonder centrale vraag (SQL subquery)
    without_question = (
        db.query(func.count(Initiative.id))
        .filter(
            Initiative.status == "actief",
            ~Initiative.id.in_(
                db.query(InitiativeQuestion.initiative_id).distinct()
            ),
        )
        .scalar()
    )

    # Totaal aantal initiatieven (SQL count)
    total_initiatives = db.query(func.count(Initiative.id)).scalar()

    # Laatste ingevoerde initiatieven (top 10, gesorteerd op created_at)
    recent = (
        db.query(Initiative)
        .order_by(Initiative.created_at.desc())
        .limit(10)
        .all()
    )

    # Recent gestopt met leeruitkomst (top 5) — SQL query
    recent_stopped = (
        db.query(Initiative)
        .filter(
            Initiative.status == "gestopt",
            Initiative.stop_reason.isnot(None),
        )
        .order_by(Initiative.updated_at.desc())
        .limit(5)
        .all()
    )

    # Haal actieve MDS en tags op voor dropdowns in modals
    all_mds = db.query(MDS).filter(MDS.is_active == True).order_by(MDS.name.asc()).all()
    all_tags = db.query(Tag).filter(Tag.is_active == True).order_by(Tag.name.asc()).all()

    return render_template(
        "dashboard.html",
        request=request,
        phase_counts=phase_counts,
        horizon_counts=horizon_counts,
        status_counts=status_counts,
        total_initiatives=total_initiatives,
        tested_count=tested_count,
        without_question=without_question,
        recent=recent,
        recent_stopped=recent_stopped,
        all_mds=all_mds,
        all_tags=all_tags,
    )


@router.get("/api/initiatieven/filter")
async def filter_initiatives(
    user: User = Depends(perm_initiatives_read),
    phase: str = Query(None, description="Filter op fase"),
    status: str = Query(None, description="Filter op status"),
    horizon: str = Query(None, description="Filter op horizon"),
    tag_id: str = Query(None, description="Filter op tag ID (legacy)"),
    tag_ids: str = Query(None, description="Filter op meerdere tag IDs (komma-gescheiden)"),
    mds_id: str = Query(None, description="Filter op MDS team ID"),
    no_central_question: bool = Query(False, description="Alleen initiatieven zonder centrale vraag"),
    search: str = Query(None, description="Zoekterm in titel/beschrijving"),
    # v0.2: nieuwe filtercriteria
    cluster: str = Query(None, description="Filter op cluster"),
    potentie: str = Query(None, description="Filter op potentie"),
    risico: str = Query(None, description="Filter op risico"),
    sort: str = Query("updated_at", description="Sorteer veld"),
    order: str = Query("desc", description="Sorteer richting (asc/desc)"),
    limit: int = Query(50, ge=1, le=200, description="Max aantal resultaten"),
    db: Session = Depends(get_db),
):
    """Server-side filtering en sorting van initiatieven.

    Retourneert een lijst met initiatieven die voldoen aan de filters,
    inclusief totale telling voor pagination.

    Ondersteunt:
    - Enkelvoudige filter op fase, status, horizon, mds_id
    - Meervoudige filter op tag_ids (komma-gescheiden string)
    - Legacy: tag_id (enkele tag) blijft werken
    """
    query = db.query(Initiative)

    # Filter op fase (of 'gestopt' status als aparte filter)
    if phase:
        if phase == "gestopt":
            query = query.filter(Initiative.status == "gestopt")
        else:
            query = query.filter(Initiative.phase == phase)

    # Filter op status
    if status:
        query = query.filter(Initiative.status == status)

    # Filter op horizon
    if horizon:
        if horizon == "none":
            query = query.filter((Initiative.horizon.is_(None)) | (Initiative.horizon == ""))
        else:
            query = query.filter(Initiative.horizon == horizon)

    # Filter op MDS team
    if mds_id:
        query = query.filter(Initiative.mds_id == mds_id)

    # v0.2: Filter op cluster
    if cluster:
        query = query.filter(Initiative.cluster == cluster)

    # v0.2: Filter op potentie
    if potentie:
        query = query.filter(Initiative.potentie == potentie)

    # v0.2: Filter op risico
    if risico:
        query = query.filter(Initiative.risico == risico)

    # Zoekterm in titel of beschrijving
    if search:
        search_pattern = f"%{search}%"
        query = query.filter(
            (Initiative.title.ilike(search_pattern)) |
            (Initiative.description.ilike(search_pattern))
        )

    # Filter op tags — ondersteunt zowel tag_id (legacy, één) als tag_ids (meerdere)
    selected_tag_ids = []
    if tag_ids:
        # Komma-gescheiden lijst van UUIDs
        selected_tag_ids = [t.strip() for t in tag_ids.split(",") if t.strip()]
    elif tag_id:
        # Legacy: enkele tag_id
        selected_tag_ids = [tag_id]

    if selected_tag_ids:
        query = query.filter(
            Initiative.id.in_(
                db.query(InitiativeTag.initiative_id).filter(
                    InitiativeTag.tag_id.in_(selected_tag_ids)
                )
            )
        )

    # Filter: alleen initiatieven zonder centrale vraag
    if no_central_question:
        query = query.filter(
            ~Initiative.id.in_(
                db.query(InitiativeQuestion.initiative_id).distinct()
            )
        )

    # Sorting — extendeerd met v0.2 velden
    sort_fields = {"updated_at", "title", "phase", "status", "created_at",
                   "cluster", "potentie", "risico", "capaciteitsvraag"}
    if sort in sort_fields:
        column = getattr(Initiative, sort, None)
        if column:
            if order == "asc":
                query = query.order_by(column.asc())
            else:
                query = query.order_by(column.desc())
    else:
        query = query.order_by(Initiative.updated_at.desc())

    # Totaal aantal (voor pagination indicator)
    total = query.count()

    # Haal resultaten op
    initiatives = query.limit(limit).all()

    return {
        "initiatives": [
            {
                "id": i.id,
                "title": i.title,
                "description": (i.description or "")[:100],
                "phase": i.phase,
                "status": i.status,
                "horizon": i.horizon,
                # v0.2: nieuwe velden
                "cluster": i.cluster,
                "afdeling": i.afdeling,
                "team": i.team,
                "potentie": i.potentie,
                "capaciteitsvraag": i.capaciteitsvraag,
                "risico": i.risico,
                "bron_initiatief": i.bron_initiatief,
                "externe_partners": i.externe_partners,
                "betrokkenheid_iv": i.betrokkenheid_iv,
                "gerelateerde_initiatieven": i.gerelateerde_initiatieven,
                "volgende_stap": i.volgende_stap,
                "opmerkingen": i.opmerkingen,
                "updated_at": i.updated_at.isoformat() if i.updated_at else None,
            }
            for i in initiatives
        ],
        "total": total,
        "limit": limit,
    }
