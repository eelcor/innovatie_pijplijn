"""Pydantic schemas voor validatie en serialisatie."""

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field, field_validator


# --- Enums als Literals voor validatie ---

InitiativePhase = Literal["idee", "verkenning", "experiment", "pilot", "opschaling"]
InitiativeStatus = Literal["actief", "gestopt", "afgerond", "onduidelijk", "pauze", "idee"]
Potentie = Literal["hoog", "midden", "onbekend"]
Capaciteitsvraag = Literal["hoog", "midden", "laag", "onbekend"]
Risico = Literal["hoog", "midden", "laag"]
BetrokkenheidIV = Literal["actief_begeleidend", "passief_volgend", "nog_niet_betrokken"]
Horizon = Literal["h1", "h2", "h3"]
TypeAiGebruik = Literal[
    "bouwen_met_ai",
    "ai_in_bouwsels",
    "ai_in_bestaande_tools",
    "persoonlijke_productiviteit",
    "mix",
]
HypothesisType = Literal["value", "growth", "compliance"]
HypothesisStatus = Literal["open", "bevestigd", "weerlegd", "vervallen"]


# --- Initiative ---

class InitiativeCreate(BaseModel):
    title: str = Field(..., min_length=1)
    description: Optional[str] = None
    phase: InitiativePhase = Field(default="idee")
    horizon: Optional[Horizon] = None
    mds: Optional[str] = None  # legacy: vrij tekstveld
    mds_id: Optional[str] = None  # H2: MDS als entiteit
    central_question: Optional[str] = None  # legacy fallback
    central_question_ids: list[str] = Field(default_factory=list)  # nieuwe vragen te koppelen
    tag_ids: list[str] = Field(default_factory=list)  # H2: tags te koppelen
    trekker: Optional[str] = None
    owner: Optional[str] = None
    type_ai_gebruik: Optional[TypeAiGebruik] = None
    # v0.2: nieuwe velden
    cluster: Optional[str] = None
    afdeling: Optional[str] = None
    team: Optional[str] = None
    potentie: Optional[Potentie] = None
    capaciteitsvraag: Optional[Capaciteitsvraag] = None
    risico: Optional[Risico] = None
    bron_initiatief: Optional[str] = None
    externe_partners: Optional[str] = None
    betrokkenheid_iv: Optional[BetrokkenheidIV] = None
    gerelateerde_initiatieven: Optional[str] = None
    volgende_stap: Optional[str] = None
    opmerkingen: Optional[str] = None


class InitiativeUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    phase: Optional[InitiativePhase] = None
    status: Optional[InitiativeStatus] = None
    horizon: Optional[Horizon] = None
    mds: Optional[str] = None  # legacy
    mds_id: Optional[str] = None  # H2: MDS als entiteit
    central_question: Optional[str] = None  # legacy fallback
    central_question_ids: Optional[list[str]] = None  # update gekoppelde vragen (None = niet wijzigen)
    tag_ids: Optional[list[str]] = None  # H2: tags bijwerken (None = niet wijzigen)
    trekker: Optional[str] = None
    owner: Optional[str] = None
    type_ai_gebruik: Optional[TypeAiGebruik] = None
    stop_reason: Optional[str] = None
    # v0.2: nieuwe velden
    cluster: Optional[str] = None
    afdeling: Optional[str] = None
    team: Optional[str] = None
    potentie: Optional[Potentie] = None
    capaciteitsvraag: Optional[Capaciteitsvraag] = None
    risico: Optional[Risico] = None
    bron_initiatief: Optional[str] = None
    externe_partners: Optional[str] = None
    betrokkenheid_iv: Optional[BetrokkenheidIV] = None
    gerelateerde_initiatieven: Optional[str] = None  # comma-sep string (legacy/import)
    gerelateerde_initiatieven_ids: Optional[list[str]] = None  # multi-select uit UI
    volgende_stap: Optional[str] = None
    opmerkingen: Optional[str] = None


class InitiativeStop(BaseModel):
    """Specifiek schema voor stoppen met leeruitkomst."""
    stop_reason: str = Field(..., min_length=1)

    @field_validator("stop_reason")
    @classmethod
    def strip_and_check_not_empty(cls, v: str) -> str:
        stripped = v.strip()
        if not stripped:
            raise ValueError("Leeruitkomst mag niet leeg zijn")
        return stripped


# --- Hypothesis ---

class HypothesisCreate(BaseModel):
    initiative_id: str
    parent_hypothesis_id: Optional[str] = None
    type: HypothesisType = Field(...)
    description: str = Field(..., min_length=1)
    status: HypothesisStatus = Field(default="open")
    learning: Optional[str] = None
    commentary: Optional[str] = None


class HypothesisUpdate(BaseModel):
    description: Optional[str] = None
    status: Optional[HypothesisStatus] = None
    learning: Optional[str] = None
    commentary: Optional[str] = None


# --- Dossier ---

class DossierNoteCreate(BaseModel):
    initiative_id: str
    title: Optional[str] = None
    body: str = Field(..., min_length=1)


class DossierNoteUpdate(BaseModel):
    title: Optional[str] = None
    body: Optional[str] = None


# --- Curation ---

class CurationCreate(BaseModel):
    name: str = Field(..., min_length=1)
    purpose: Optional[str] = None
    description: Optional[str] = None


class CurationUpdate(BaseModel):
    name: Optional[str] = None
    purpose: Optional[str] = None
    description: Optional[str] = None


class CurationItemCreate(BaseModel):
    initiative_id: str
    position: int
    note: Optional[str] = None


# --- Central Question (F9) ---

class CentralQuestionCreate(BaseModel):
    question: str = Field(..., min_length=1)
    description: Optional[str] = None
    tag_ids: list[str] = Field(default_factory=list)  # H2-1: tags te koppelen

    @field_validator("question")
    @classmethod
    def strip_and_check_not_empty(cls, v: str) -> str:
        stripped = v.strip()
        if not stripped:
            raise ValueError("Centrale vraag mag niet leeg zijn")
        return stripped


class CentralQuestionUpdate(BaseModel):
    question: Optional[str] = None
    description: Optional[str] = None
    is_active: Optional[bool] = None
    tag_ids: Optional[list[str]] = None  # H2-1: tags bijwerken (None = niet wijzigen)

    @field_validator("question")
    @classmethod
    def strip_question(cls, v: str) -> str:
        if v is not None:
            stripped = v.strip()
            if not stripped:
                raise ValueError("Centrale vraag mag niet leeg zijn")
            return stripped
        return v


# --- Search ---

class SearchQuery(BaseModel):
    q: Optional[str] = None
    phase: Optional[InitiativePhase] = None
    status: Optional[InitiativeStatus] = None
    horizon: Optional[Horizon] = None
    mds: Optional[str] = None


# --- Tag ---

class TagCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = Field(None, max_length=500)

    @field_validator("name")
    @classmethod
    def strip_and_lower(cls, v: str) -> str:
        stripped = v.strip().lower()
        if not stripped:
            raise ValueError("Naam mag niet leeg zijn")
        return stripped


class TagUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    description: Optional[str] = Field(None, max_length=500)

    @field_validator("name")
    @classmethod
    def strip_name(cls, v: str) -> str:
        if v is not None:
            stripped = v.strip().lower()
            if not stripped:
                raise ValueError("Naam mag niet leeg zijn")
            return stripped
        return v


# --- MDS ---

class MDSCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = Field(None, max_length=1000)

    @field_validator("name")
    @classmethod
    def strip_name(cls, v: str) -> str:
        stripped = v.strip()
        if not stripped:
            raise ValueError("Naam mag niet leeg zijn")
        return stripped


class MDSUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=200)
    description: Optional[str] = Field(None, max_length=1000)

    @field_validator("name")
    @classmethod
    def strip_name(cls, v: str) -> str:
        if v is not None:
            stripped = v.strip()
            if not stripped:
                raise ValueError("Naam mag niet leeg zijn")
            return stripped
        return v


# --- AI One-pager ---

class OnePagerRequest(BaseModel):
    purpose: Optional[str] = Field(None, max_length=500)
    audience: Optional[str] = Field(None, max_length=200)


class OnePagerUpdate(BaseModel):
    content: Optional[str] = None
    purpose: Optional[str] = Field(None, max_length=500)
    audience: Optional[str] = Field(None, max_length=200)


# --- AI Hypothesis accept ---

class AcceptHypothesisRequest(BaseModel):
    type: HypothesisType
    description: str = Field(..., min_length=1, max_length=2000)


# --- Central question set ---

class QuestionSetRequest(BaseModel):
    question_ids: list[str] = Field(default_factory=list)


# --- Curation item ---

class CurationItemAddRequest(BaseModel):
    initiative_id: str
    position: int = 0
    note: Optional[str] = Field(None, max_length=1000)
