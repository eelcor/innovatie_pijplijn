"""AI-routes voor de Innovatiepijplijn.

Model-agnostisch — gebruikt app.ai_client om elk OpenAI-compatible model aan te roepen.
Alle prompts zijn hier gedefinieerd zodat ze centraal beheerd kunnen worden.
"""

import re

from fastapi import APIRouter, Body, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.auth import (
    perm_ai_generate,
    perm_initiatives_read,
    perm_curations_read,
)
from app.database import get_db
from app import ai_client
from app.helpers import render_template
from app.models import (
    User, Initiative, Hypothesis, DossierNote, Curation, CurationItem,
    CentralQuestion, InitiativeQuestion, Tag, InitiativeTag, QuestionTag, MDS,
    OnePager, CurationNarrative,
)

router = APIRouter()


# ====================================================================
# PROMPTS — centraal beheer van alle AI-prompt templates
# ====================================================================

SYSTEM_PROMPT_NARRATIEF = """\
Je bent een ervaren programmamanager die narratieven schrijft voor \
directievoordrachten en show & tell sessies binnen de gemeente Leiden. \
Schrijf in heldere, toegankelijke Nederlandse taal. \
Gebruik de domeinbegrippen: initiatief, verkenning, hypothese, leeruitkomst, curatie.

BELANGRIJK — GEEN HALLUCINATIES:
- Gebruik uitsluitend informatie die in de context staat. Verzin geen feiten, cijfers, \
namen, uitkomsten of conclusies die niet expliciet zijn vermeld.
- Als een initiatief nog in verkenning is, presenteer het dan als verkenning — noem \
geen resultaten die er nog niet zijn.
- Als er geen leeruitkomsten bekend zijn, schrijf dan "nog in onderzoek" of vergelijkbaar. \
Noem geen specifieke bevindingen die niet in de context staan.
- Wees terughoudend: beter kort en accuraat dan lang en verzonnen."""

SYSTEM_PROMPT_HYPOTHESEN = """\
Je bent een innovatie-expert die helpt bij het formuleren van hypothesen \
voor gemeentelijke initiatieven. Je kent de Lean Startup methodiek en \
de drie hoofdcategorieën: value, growth, compliance.

BELANGRIJK — GEEN HALLUCINATIES:
- Baseer hypothesen uitsluitend op de beschikbare context van het initiatief.
- Verzin geen specifieke doelen, doelgroepen of uitkomsten die niet in de tekst staan.
- Een hypothese is een veronderstelling die nog moet worden getoetst — formuleer ze \
algemeer genoeg zodat ze realistisch zijn op basis van de beschikbare informatie.
- Als de context te weinig informatie bevat, geef dan algemene hypothesen die passen \
bij het type initiatief, maar noem geen specifieke details die je zelf bedacht hebt.

Geef je antwoord als JSON-array met **minimaal 9 hypothesen** (3-4 per beschikbare categorie).
Elk object heeft velden:
type (value/growth/compliance), description (een duidelijke hypothese in het Nederlands),
en rationale (korte toelichting waarom deze hypothese relevant is)."""

SYSTEM_PROMPT_ONEPAGER = """\
Je bent een communicatieadviseur die korte, heldere one-pagers schrijft \
voor beleidsmakers bij de gemeente Leiden. \
Schrijf in toegankelijk Nederlands, maximaal 400 woorden. \
Gebruik de structuur: Achtergrond → Doel → Stand van zaken → Verwachte impact.

BELANGRIJK — GEEN HALLUCINATIES:
- Gebruik uitsluitend informatie die in de context staat. Verzin geen feiten, cijfers, \
namen, uitkomsten of conclusies die niet expliciet zijn vermeld.
- Bij "Stand van zaken" beschrijf alleen wat er echt bekend is uit de hypothesen en \\nleeruitkomsten. Noem geen vorderingen die niet in de data staan.
- Bij "Verwachte impact" baseer je uitsluitend op de doelstelling en status van het \
initiatief. Projecteer geen resultaten die nog niet bestaan.
- Schrijf liever "nog te bepalen" dan iets te verzinnen."""

SYSTEM_PROMPT_CURATIE_SUGGESTIES = """\
Je bent een programmamanager die helpt bij het samenstellen van curaties \
binnen de gemeente Leiden. Een curatie is een verzameling initiatieven die \
samen een verhaal vertellen voor een directievoordracht of show & tell.

BELANGRIJK — GEEN HALLUCINATIES:
- Suggesteer uitsluitend initiatieven uit de lijst die je krijgt aangeboden.
- Baseer je redenering alleen op de titels en beschrijvingen van de initiatieven \
en het doel van de curatie. Verzin geen inhoud die niet in de tekst staat.
- Als geen enkel initiatief echt past, geef dan een lege lijst terug.

Geef je antwoord als JSON-array met objecten die elk velden hebben:
initiative_id (de UUID van het gesuggereerde initiatief),
title (de titel van het initiatief),
rationale (korte toelichting waarom dit initiatief past bij de curatie)."""


# Maximum aantal kandidaten dat naar het model wordt gestuurd
MAX_CANDIDATES = 30

# Nederlandse stopwoorden die we negeren bij keyword-extractie
_STOP_WORDS = {
    "de", "het", "een", "van", "voor", "in", "op", "met", "bij", "tot",
    "en", "is", "wordt", "zijn", "dat", "door", "uit", "als", "ook",
    "naar", "over", "maar", "te", "ze", "er", "aan", "om", "nog",
    "meer", "niet", "kan", "zal", "moet", "had", "heb", "heeft",
    "hun", "haar", "hem", "men", "dit", "die", "wie", "wat",
    "worden", "werd", "geweest", "alle", "ieder", "andere",
}


def _extract_keywords(text: str) -> list[str]:
    """Haal betekenisvolle keywords uit tekst."""
    words = re.findall(r"\b[a-z]{3,}\b", text.lower())
    return [w for w in words if w not in _STOP_WORDS]


def _score_initiative(initiative, keywords: list[str]) -> float:
    """Score een initiatief op basis van keyword-overlap."""
    score = 0.0
    searchable = f"{initiative.title or ''} {initiative.description or ''}".lower()

    for kw in keywords:
        if kw in searchable:
            # Titel-match telt dubbel
            if kw in (initiative.title or "").lower():
                score += 2.0
            else:
                score += 1.0

    return score


# ====================================================================
# HELPERS — data ophalen uit database
# ============================================================================

def _get_initiative_with_details(db: Session, initiative_id: str) -> dict | None:
    """Haal initiatief op met alle gerelateerde details."""
    init = db.query(Initiative).filter(Initiative.id == initiative_id).first()
    if not init:
        return None

    hypotheses = db.query(Hypothesis).filter(
        Hypothesis.initiative_id == initiative_id,
        Hypothesis.parent_hypothesis_id.is_(None),
    ).all()

    # Sub-hypothesen per hoofdhypothese
    all_sub_ids = [h.id for h in hypotheses]
    sub_hypotheses = db.query(Hypothesis).filter(
        Hypothesis.parent_hypothesis_id.in_(all_sub_ids)
    ).all()
    sub_map = {}
    for sh in sub_hypotheses:
        sub_map.setdefault(sh.parent_hypothesis_id, []).append(sh)

    notes = db.query(DossierNote).filter(
        DossierNote.initiative_id == initiative_id
    ).order_by(DossierNote.created_at.desc()).all()

    # Centrale vragen
    iqs = db.query(InitiativeQuestion).filter(
        InitiativeQuestion.initiative_id == initiative_id
    ).all()
    questions = []
    for iq in iqs:
        q = db.query(CentralQuestion).filter(
            CentralQuestion.id == iq.central_question_id
        ).first()
        if q:
            questions.append({"question": q.question, "description": q.description})

    # Tags — met naam én beschrijving voor AI-context
    itags = db.query(InitiativeTag).filter(
        InitiativeTag.initiative_id == initiative_id
    ).all()
    tag_info = []
    for it in itags:
        tag = db.query(Tag).filter(Tag.id == it.tag_id).first()
        if tag:
            tag_info.append({"name": tag.name, "description": tag.description or ""})

    # MDS
    mds_name = None
    if init.mds_id:
        mds = db.query(MDS).filter(MDS.id == init.mds_id).first()
        if mds:
            mds_name = mds.name

    return {
        "title": init.title,
        "description": init.description or "",
        "phase": init.phase,
        "status": init.status,
        "horizon": init.horizon,
        "mds": mds_name or init.mds or "",
        "owner": init.owner or "",
        "stop_reason": init.stop_reason or "",
        "hypotheses": [
            {
                "type": h.type,
                "description": h.description,
                "status": h.status,
                "learning": h.learning or "",
                "subs": [
                    {"type": s.type, "description": s.description, "status": s.status, "learning": s.learning or ""}
                    for s in sub_map.get(h.id, [])
                ],
            }
            for h in hypotheses
        ],
        "notes": [{"title": n.title, "body": n.body} for n in notes[:10]],
        "central_questions": questions,
        "tags": tag_info,
    }


def _get_curation_with_details(db: Session, curation_id: str) -> dict | None:
    """Haal curatie op met alle initiatieven."""
    curation = db.query(Curation).filter(Curation.id == curation_id).first()
    if not curation:
        return None

    items = db.query(CurationItem).filter(
        CurationItem.curation_id == curation_id
    ).order_by(CurationItem.position).all()

    initiatives_data = []
    for item in items:
        data = _get_initiative_with_details(db, item.initiative_id)
        if data:
            data["_curation_note"] = item.note or ""
            initiatives_data.append(data)

    return {
        "name": curation.name,
        "purpose": curation.purpose or "",
        "description": curation.description or "",
        "initiatives": initiatives_data,
    }


# ====================================================================
# USER-FACING ROUTES — HTMX/template endpoints
# ====================================================================

@router.get("/ai/initiatieven/{initiative_id}/suggest-hypotheses")
async def suggest_hypotheses_page(
    request: Request,
    initiative_id: str,
    user: User = Depends(perm_ai_generate),
    db: Session = Depends(get_db),
):
    """Toon de hypothese-suggesties interface op het initiatief detail."""
    db.flush()
    data = _get_initiative_with_details(db, initiative_id)

    if not data:
        raise HTTPException(status_code=404, detail="Initiatief niet gevonden")

    return render_template(
        request, "partials/ai_hypothesis_suggest.html",
        initiative=data, initiative_id=initiative_id, result=None, error=None,
    )


@router.post("/api/ai/initiatieven/{initiative_id}/suggest-hypotheses")
async def suggest_hypotheses_api(
    initiative_id: str,
    user: User = Depends(perm_ai_generate),
    db: Session = Depends(get_db),
):
    """Genereer hypothese-suggesties voor een initiatief."""
    db.flush()
    data = _get_initiative_with_details(db, initiative_id)

    if not data:
        raise HTTPException(status_code=404, detail="Initiatief niet gevonden")

    # Bouw user prompt met context
    existing_types = {h["type"] for h in data["hypotheses"]}
    type_hints = []
    for t in ("value", "growth", "compliance"):
        if t not in existing_types:
            type_hints.append(t)

    prompt_parts = [f"Initiatief: {data['title']}", f"Fase: {data['phase']}"]
    if data["description"]:
        prompt_parts.append(f"Beschrijving: {data['description']}")
    if data.get("mds"):
        prompt_parts.append(f"MDS: {data['mds']}")
    if data.get("horizon"):
        prompt_parts.append(f"Horizon: {data['horizon']}")
    # Tags met beschrijvingen
    if data.get("tags"):
        tag_lines = []
        for t in data["tags"]:
            if t.get("description"):
                tag_lines.append(f"  - {t['name']}: {t['description']}")
            else:
                tag_lines.append(f"  - {t['name']}")
        prompt_parts.append("Tags:\n" + "\n".join(tag_lines))

    # Bestaande hypothesen (ter vermeden van duplicaten)
    if data["hypotheses"]:
        prompt_parts.append("Bestaande hypothesen:")
        for h in data["hypotheses"]:
            prompt_parts.append(f"  - [{h['type']}] {h['description']} (status: {h['status']})")

    if type_hints:
        prompt_parts.append(
            f"Stel 3-4 nieuwe hypothesen per categorie voor, bij voorkeur in de categorieën: {', '.join(type_hints)}. "
            "Dus minimaal 9 hypothesen in totaal. Vermijd duplicaten van bestaande hypothesen."
        )
    else:
        prompt_parts.append("Stel 9-12 aanvullende hypothesen voor, verdeeld over value, growth en compliance. Vermijd duplicaten.")

    prompt_parts.append(
        "\nBELANGRIJK: Gebruik alleen de informatie hierboven. Verzin geen nieuwe feiten, "
        "doelgroepen, cijfers of uitkomsten die niet in deze context staan."
    )

    user_prompt = "\n".join(prompt_parts)

    result = await ai_client.call_model_structured(
        system_prompt=SYSTEM_PROMPT_HYPOTHESEN,
        user_prompt=user_prompt,
        temperature=0.3,
        max_tokens=16384,  # meer ruimte voor 9-12 hypothesen
    )
    # Timeout handling: als het model te lang doet over veel hypothesen,
    # kunnen we de timeout verhogen via AI_REQUEST_TIMEOUT environment variabele

    if isinstance(result, dict) and "error" in result:
        return {"success": False, "error": result["error"], "suggestions": []}

    suggestions = result if isinstance(result, list) else []
    return {"success": True, "suggestions": suggestions}


@router.get("/ai/curaties/{curation_id}/narratief")
async def narratief_page(
    request: Request,
    curation_id: str,
    user: User = Depends(perm_ai_generate),
    db: Session = Depends(get_db),
):
    """Toon de narratief-generatie interface op de curatie detailpagina."""
    db.flush()
    data = _get_curation_with_details(db, curation_id)

    if not data:
        raise HTTPException(status_code=404, detail="Curatie niet gevonden")

    return render_template(
        request, "partials/ai_narratief.html",
        curation=data, curation_id=curation_id, result=None, error=None,
    )


@router.post("/api/ai/curaties/{curation_id}/narratief")
async def narratief_api(
    curation_id: str,
    user: User = Depends(perm_ai_generate),
    db: Session = Depends(get_db),
):
    """Genereer een narratief voor een curatie."""
    db.flush()
    data = _get_curation_with_details(db, curation_id)

    if not data:
        raise HTTPException(status_code=404, detail="Curatie niet gevonden")

    prompt_parts = [
        f"Curatie: {data['name']}",
        f"Doel: {data['purpose']}",
    ]
    if data["description"]:
        prompt_parts.append(f"Beschrijving: {data['description']}")

    prompt_parts.append("\nInitiatieven in deze curatie:")
    for i, init in enumerate(data["initiatives"], 1):
        note = init.get("_curation_note", "")
        prompt_parts.append(
            f"{i}. **{init['title']}** (fase: {init['phase']}, status: {init['status']})"
        )
        if init.get("description"):
            prompt_parts.append(f"   Beschrijving: {init['description'][:200]}")
        if note:
            prompt_parts.append(f"   Toelichting: {note}")

    prompt_parts.append(
        "\nSchrijf een samenhangend narratief (3-5 alinea's) dat deze curatie vertelt "
        "als een verhaal. Leg de rode draad uit tussen de initiatieven en schets "
        "het verwachte effect voor de gemeente Leiden."
    )
    prompt_parts.append(
        "\nBELANGRIJK: Gebruik alleen de informatie hierboven. Verzin geen resultaten, "
        "cijfers, namen of conclusies die niet in deze context staan. "
        "Als een initiatief nog in verkenning is, presenteer het dan als verkenning. "
        "Schrijf 'nog te bepalen' in plaats van iets te verzinnen."
    )

    user_prompt = "\n".join(prompt_parts)

    narrative = await ai_client.call_model(
        system_prompt=SYSTEM_PROMPT_NARRATIEF,
        user_prompt=user_prompt,
        temperature=0.2,
        max_tokens=8192,
    )

    if not narrative or narrative.startswith("["):
        return {"success": False, "error": narrative or "[Model gaf een leeg antwoord]"}

    # Sla het gegenereerde narratief op in de database
    saved = CurationNarrative(
        curation_id=curation_id,
        content=narrative,
    )
    db.add(saved)
    db.commit()
    db.refresh(saved)

    return {"success": True, "narrative": narrative, "id": saved.id}


@router.post("/api/ai/curaties/{curation_id}/suggest-initiatives")
async def suggest_initiatives_api(
    curation_id: str,
    user: User = Depends(perm_ai_generate),
    db: Session = Depends(get_db),
):
    """Suggesteer initiatieven die passen bij een curatie.

    Schaalbaar tot honderden initiatieven via keyword pre-filtering:
    1. Extract keywords uit curatie-naam/doel/beschrijving
    2. Score alle beschikbare initiatieven op keyword-overlap
    3. Stuur alleen top-{MAX_CANDIDATES} naar het LLM voor selectie
    """
    db.flush()
    curation = db.query(Curation).filter(Curation.id == curation_id).first()

    if not curation:
        raise HTTPException(status_code=404, detail="Curatie niet gevonden")

    # Haal alle initiatieven op die nog NIET in deze curatie zitten
    existing_items = db.query(CurationItem.initiative_id).filter(
        CurationItem.curation_id == curation_id
    ).all()
    existing_ids = [item[0] for item in existing_items]

    all_initiatives = db.query(Initiative).all()
    available = [
        i for i in all_initiatives if i.id not in existing_ids and i.status != "gestopt"
    ]

    if not available:
        return {"success": True, "suggestions": []}

    # --- Keyword pre-filtering (schaalbaar naar 400-500 initiatieven) ---
    keywords = _extract_keywords(
        f"{curation.name} {curation.purpose or ''} {curation.description or ''}"
    )

    if keywords:
        scored = sorted(
            available,
            key=lambda i: _score_initiative(i, keywords),
            reverse=True,
        )
        candidates = scored[:MAX_CANDIDATES]
    else:
        # Geen keywords gevonden → neem eerste MAX_CANDIDATES
        candidates = available[:MAX_CANDIDATES]

    if not candidates:
        return {"success": True, "suggestions": []}

    # Bouw prompt met curatie-context én gefilterde kandidaten
    prompt_parts = [
        f"Curatie: {curation.name}",
        f"Doel: {curation.purpose or 'niet opgegeven'}",
    ]
    if curation.description:
        prompt_parts.append(f"Beschrijving: {curation.description}")

    # Initiatieven die al in de curatie zitten (voor context)
    if existing_ids:
        prompt_parts.append("\nInitiatieven die AL in deze curatie zitten:")
        for iid in existing_ids:
            init = db.query(Initiative).filter(Initiative.id == iid).first()
            if init:
                prompt_parts.append(
                    f"  - {init.title} (fase: {init.phase})"
                )
                if init.description:
                    prompt_parts.append(f"    {init.description[:150]}")

    # Gefilterde kandidaten
    prompt_parts.append(
        f"\nBeschikbare initiatieven (top {len(candidates)} op relevantie):"
    )
    for i, init in enumerate(candidates, 1):
        prompt_parts.append(
            f"{i}. id={init.id} | {init.title} (fase: {init.phase}, status: {init.status})"
        )
        if init.description:
            desc = init.description[:200]
            prompt_parts.append(f"   Beschrijving: {desc}")

    prompt_parts.append(
        "\nSelecteer de 3-6 initiatieven die het beste passen bij deze curatie. "
        "Leeg als er geen goede matches zijn."
    )
    prompt_parts.append(
        "\nBELANGRIJK: Suggesteer alleen initiatieven uit de lijst hierboven. "
        "Verzin geen initiatieven die niet in deze context staan."
    )

    user_prompt = "\n".join(prompt_parts)

    result = await ai_client.call_model_structured(
        system_prompt=SYSTEM_PROMPT_CURATIE_SUGGESTIES,
        user_prompt=user_prompt,
        temperature=0.2,
        max_tokens=8192,
    )

    if isinstance(result, dict) and "error" in result:
        return {"success": False, "error": result["error"], "suggestions": []}

    suggestions = result if isinstance(result, list) else []
    return {"success": True, "suggestions": suggestions}


@router.post("/api/ai/initiatieven/{initiative_id}/one-pager")
async def one_pager_api(
    initiative_id: str,
    payload: dict = Body(default={}),
    user: User = Depends(perm_ai_generate),
    db: Session = Depends(get_db),
):
    """Genereer een one-pager samenvatting voor een initiatief.

    Body (optioneel): { "purpose": "directievoordracht", "audience": "directie" }
    """
    purpose = payload.get("purpose", "").strip() or None
    audience = payload.get("audience", "").strip() or None

    db.flush()
    data = _get_initiative_with_details(db, initiative_id)

    if not data:
        raise HTTPException(status_code=404, detail="Initiatief niet gevonden")

    prompt_parts = [f"Initiatief: {data['title']}"]
    if data["description"]:
        prompt_parts.append(f"Beschrijving: {data['description']}")
    prompt_parts.append(f"Fase: {data['phase']}, Status: {data['status']}")
    if data.get("horizon"):
        prompt_parts.append(f"Horizon: {data['horizon']}")
    if data.get("mds"):
        prompt_parts.append(f"MDS: {data['mds']}")

    if data["hypotheses"]:
        prompt_parts.append("\nHypothesen:")
        for h in data["hypotheses"]:
            status_info = f" (status: {h['status']}"
            if h.get("learning"):
                status_info += f", leeruitkomst: {h['learning']}"
            status_info += ")"
            prompt_parts.append(f"  - [{h['type']}] {h['description']}{status_info}")

    if data.get("central_questions"):
        prompt_parts.append("\nCentrale vragen:")
        for q in data["central_questions"]:
            prompt_parts.append(f"  - {q['question']}")

    if data.get("tags"):
        tag_lines = []
        for t in data["tags"]:
            name = t["name"] if isinstance(t, dict) else str(t)
            desc = t.get("description", "") if isinstance(t, dict) else ""
            if desc:
                tag_lines.append(f"{name} ({desc})")
            else:
                tag_lines.append(name)
        prompt_parts.append(f"\nTags: {', '.join(tag_lines)}")

    if data.get("stop_reason"):
        prompt_parts.append(f"\nLeeruitkomst bij stoppen: {data['stop_reason']}")

    # Pas de instructie aan op basis van doel en doelgroep
    instruction = "\nGenereer een one-pager samenvatting."
    if audience:
        instruction += f" Schrijf specifiek voor het publiek: {audience}."
    elif purpose:
        instruction += f" Geschikt voor: {purpose}."
    else:
        instruction += " Geschikt voor een directievoordracht."

    if purpose:
        instruction += f" Het doel van deze one-pager is: {purpose}."

    prompt_parts.append(instruction)
    prompt_parts.append(
        "\nBELANGRIJK: Gebruik alleen de informatie hierboven. Verzin geen feiten, "
        "cijfers, namen, uitkomsten of conclusies die niet in deze context staan. "
        "Schrijf 'nog te bepalen' in plaats van iets te verzinnen."
    )

    user_prompt = "\n".join(prompt_parts)

    one_pager = await ai_client.call_model(
        system_prompt=SYSTEM_PROMPT_ONEPAGER,
        user_prompt=user_prompt,
        temperature=0.2,
        max_tokens=8192,
    )

    if not one_pager or one_pager.startswith("["):
        return {"success": False, "error": one_pager or "[Model gaf een leeg antwoord]"}

    # Sla de gegenereerde one-pager op in de database
    saved = OnePager(
        initiative_id=initiative_id,
        content=one_pager,
        purpose=purpose,
        audience=audience,
    )
    db.add(saved)
    db.commit()
    db.refresh(saved)

    return {"success": True, "one_pager": one_pager, "id": saved.id}


@router.get("/api/ai/initiatieven/{initiative_id}/one-pagers")
async def list_one_pagers(
    initiative_id: str,
    user: User = Depends(perm_initiatives_read),
    db: Session = Depends(get_db),
):
    """Haal alle opgeslagen one-pagers op voor een initiatief."""
    initiative = db.query(Initiative).filter(Initiative.id == initiative_id).first()
    if not initiative:
        raise HTTPException(status_code=404, detail="Initiatief niet gevonden")

    pagers = db.query(OnePager).filter(
        OnePager.initiative_id == initiative_id,
    ).order_by(OnePager.created_at.desc()).all()

    return {
        "one_pagers": [
            {
                "id": p.id,
                "created_at": p.created_at.isoformat(),
                "purpose": p.purpose,
                "audience": p.audience,
                "preview": (p.content[:120] + "…") if len(p.content) > 120 else p.content,
            }
            for p in pagers
        ],
    }


@router.get("/api/ai/initiatieven/{initiative_id}/one-pagers/{one_pager_id}")
async def get_one_pager(
    initiative_id: str,
    one_pager_id: str,
    user: User = Depends(perm_initiatives_read),
    db: Session = Depends(get_db),
):
    """Haal één specifieke one-pager op."""
    p = db.query(OnePager).filter(
        OnePager.id == one_pager_id,
        OnePager.initiative_id == initiative_id,
    ).first()
    if not p:
        raise HTTPException(status_code=404, detail="One-pager niet gevonden")

    return {
        "id": p.id,
        "content": p.content,
        "purpose": p.purpose,
        "audience": p.audience,
        "created_at": p.created_at.isoformat(),
        "updated_at": p.updated_at.isoformat() if p.updated_at else None,
    }


@router.put("/api/ai/initiatieven/{initiative_id}/one-pagers/{one_pager_id}")
async def update_one_pager(
    initiative_id: str,
    one_pager_id: str,
    payload: dict = Body(default={}),
    user: User = Depends(perm_ai_generate),
    db: Session = Depends(get_db),
):
    """Bewerk een opgeslagen one-pager."""
    p = db.query(OnePager).filter(
        OnePager.id == one_pager_id,
        OnePager.initiative_id == initiative_id,
    ).first()
    if not p:
        raise HTTPException(status_code=404, detail="One-pager niet gevonden")

    if "content" in payload:
        p.content = payload["content"]
    if "purpose" in payload:
        p.purpose = payload["purpose"] or None
    if "audience" in payload:
        p.audience = payload["audience"] or None

    db.commit()
    db.refresh(p)

    return {
        "success": True,
        "id": p.id,
        "content": p.content,
        "purpose": p.purpose,
        "audience": p.audience,
    }


@router.delete("/api/ai/initiatieven/{initiative_id}/one-pagers/{one_pager_id}")
async def delete_one_pager(
    initiative_id: str,
    one_pager_id: str,
    user: User = Depends(perm_ai_generate),
    db: Session = Depends(get_db),
):
    """Verwijder een opgeslagen one-pager."""
    p = db.query(OnePager).filter(
        OnePager.id == one_pager_id,
        OnePager.initiative_id == initiative_id,
    ).first()
    if not p:
        raise HTTPException(status_code=404, detail="One-pager niet gevonden")

    db.delete(p)
    db.commit()
    return {"success": True}


@router.post("/api/ai/initiatieven/{initiative_id}/accept-hypothesis")
async def accept_hypothesis(
    initiative_id: str,
    payload: dict = Body(default={}),
    user: User = Depends(perm_ai_generate),
    db: Session = Depends(get_db),
):
    """Accepteer een AI-gesuggereerde hypothese en voeg toe aan het initiatief."""
    init = db.query(Initiative).filter(Initiative.id == initiative_id).first()
    if not init:
        raise HTTPException(status_code=404, detail="Initiatief niet gevonden")

    hypothesis_type = payload.get("type")
    description = payload.get("description", "").strip()

    if not hypothesis_type or hypothesis_type not in ("value", "growth", "compliance"):
        raise HTTPException(status_code=400, detail="Ongeldig hypothese-type")
    if not description:
        raise HTTPException(status_code=400, detail="Beschrijving is verplicht")

    # Check op duplicaat
    existing = db.query(Hypothesis).filter(
        Hypothesis.initiative_id == initiative_id,
        Hypothesis.description == description,
    ).first()
    if existing:
        raise HTTPException(status_code=409, detail="Deze hypothese bestaat al")

    new_h = Hypothesis(
        initiative_id=initiative_id,
        type=hypothesis_type,
        description=description,
        status="open",
    )
    db.add(new_h)
    db.commit()
    db.refresh(new_h)

    return {"success": True, "hypothesis_id": new_h.id}


# ====================================================================
# Curation Narratives — CRUD routes voor opgeslagen narratieven
# ====================================================================

@router.get("/api/ai/curaties/{curation_id}/narratieven")
async def list_curation_narratives(
    curation_id: str,
    user: User = Depends(perm_curations_read),
    db: Session = Depends(get_db),
):
    """Haal alle opgeslagen narratieven op voor een curatie."""
    curation = db.query(Curation).filter(Curation.id == curation_id).first()
    if not curation:
        raise HTTPException(status_code=404, detail="Curatie niet gevonden")

    narratives = db.query(CurationNarrative).filter(
        CurationNarrative.curation_id == curation_id,
    ).order_by(CurationNarrative.created_at.desc()).all()

    return {
        "narratives": [
            {
                "id": n.id,
                "created_at": n.created_at.isoformat(),
                "updated_at": n.updated_at.isoformat() if n.updated_at else None,
                "preview": (n.content[:120] + "…") if len(n.content) > 120 else n.content,
            }
            for n in narratives
        ],
    }


@router.get("/api/ai/curaties/{curation_id}/narratieven/{narrative_id}")
async def get_curation_narrative(
    curation_id: str,
    narrative_id: str,
    user: User = Depends(perm_curations_read),
    db: Session = Depends(get_db),
):
    """Haal één specifiek narratief op."""
    n = db.query(CurationNarrative).filter(
        CurationNarrative.id == narrative_id,
        CurationNarrative.curation_id == curation_id,
    ).first()
    if not n:
        raise HTTPException(status_code=404, detail="Narratief niet gevonden")

    return {
        "id": n.id,
        "content": n.content,
        "created_at": n.created_at.isoformat(),
        "updated_at": n.updated_at.isoformat() if n.updated_at else None,
    }


@router.put("/api/ai/curaties/{curation_id}/narratieven/{narrative_id}")
async def update_curation_narrative(
    curation_id: str,
    narrative_id: str,
    payload: dict = Body(default={}),
    user: User = Depends(perm_ai_generate),
    db: Session = Depends(get_db),
):
    """Bewerk een opgeslagen narratief."""
    n = db.query(CurationNarrative).filter(
        CurationNarrative.id == narrative_id,
        CurationNarrative.curation_id == curation_id,
    ).first()
    if not n:
        raise HTTPException(status_code=404, detail="Narratief niet gevonden")

    if "content" in payload:
        n.content = payload["content"]

    db.commit()
    db.refresh(n)

    return {
        "success": True,
        "id": n.id,
        "content": n.content,
    }


@router.delete("/api/ai/curaties/{curation_id}/narratieven/{narrative_id}")
async def delete_curation_narrative(
    curation_id: str,
    narrative_id: str,
    user: User = Depends(perm_ai_generate),
    db: Session = Depends(get_db),
):
    """Verwijder een opgeslagen narratief."""
    n = db.query(CurationNarrative).filter(
        CurationNarrative.id == narrative_id,
        CurationNarrative.curation_id == curation_id,
    ).first()
    if not n:
        raise HTTPException(status_code=404, detail="Narratief niet gevonden")

    db.delete(n)
    db.commit()
    return {"success": True}
