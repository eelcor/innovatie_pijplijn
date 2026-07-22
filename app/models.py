"""SQLAlchemy modellen — alle entiteiten uit het datamodel van de PRD."""

import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.orm import relationship

from app.database import Base


class Initiative(Base):
    __tablename__ = "initiatives"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    title = Column(Text, nullable=False)
    description = Column(Text, nullable=True)  # markdown
    phase = Column(
        Enum("idee", "verkenning", "experiment", "pilot", "opschaling", name="initiative_phase"),
        nullable=False,
        default="idee",
    )
    status = Column(
        Enum("actief", "gestopt", "afgerond", name="initiative_status"),
        nullable=False,
        default="actief",
    )
    horizon = Column(
        Enum("h1", "h2", "h3", name="horizon"),
        nullable=True,
    )
    mds = Column(Text, nullable=True)  # legacy: vrij tekstveld in MVP
    mds_id = Column(
        String(36), ForeignKey("mds.id", ondelete="SET NULL"), nullable=True
    )  # H2: MDS als entiteit
    central_question = Column(Text, nullable=True)  # legacy: vrij tekstveld in MVP
    trekker = Column(Text, nullable=True)  # wie initieert/trekt (verschilt van owner)
    owner = Column(Text, nullable=True)  # vrij tekstveld
    type_ai_gebruik = Column(
        Enum(
            "bouwen_met_ai",
            "ai_in_bouwsels",
            "ai_in_bestaande_tools",
            "persoonlijke_productiviteit",
            "mix",
            name="type_ai_gebruik",
        ),
        nullable=True,
    )  # type AI-inzet
    stop_reason = Column(Text, nullable=True)  # verplicht als status = gestopt
    created_at = Column(DateTime, default=func.now(), nullable=False)
    updated_at = Column(
        DateTime, default=func.now(), onupdate=func.now(), nullable=False
    )

    # Relaties
    hypotheses = relationship(
        "Hypothesis", back_populates="initiative", cascade="all, delete-orphan"
    )
    dossier_notes = relationship(
        "DossierNote", back_populates="initiative", cascade="all, delete-orphan"
    )
    dossier_files = relationship(
        "DossierFile", back_populates="initiative", cascade="all, delete-orphan"
    )
    curation_items = relationship(
        "CurationItem", back_populates="initiative", cascade="all, delete-orphan"
    )
    initiative_questions = relationship(
        "InitiativeQuestion", back_populates="initiative", cascade="all, delete-orphan"
    )
    mds_rel = relationship("MDS", back_populates="initiatives")
    initiative_tags = relationship(
        "InitiativeTag", back_populates="initiative", cascade="all, delete-orphan"
    )
    timeline_events = relationship(
        "TimelineEvent", back_populates="initiative", cascade="all, delete-orphan"
    )


class TimelineEvent(Base):
    __tablename__ = "timeline_events"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    initiative_id = Column(
        String(36), ForeignKey("initiatives.id", ondelete="CASCADE"), nullable=False,
    )
    event_type = Column(
        Enum(
            "created", "phase_change", "status_change",
            "hypothesis_added", "hypothesis_resolved",
            "file_uploaded", "note_added",
            "milestone", "custom",
            name="timeline_event_type",
        ),
        nullable=False,
    )
    title = Column(Text, nullable=False)  # korte titel
    description = Column(Text, nullable=True)  # toelichting (markdown)
    metadata_json = Column(Text, nullable=True)  # extra data als JSON string
    created_at = Column(DateTime, default=func.now(), nullable=False)

    # Relaties
    initiative = relationship("Initiative", back_populates="timeline_events")


class Hypothesis(Base):
    __tablename__ = "hypotheses"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    initiative_id = Column(
        String(36), ForeignKey("initiatives.id", ondelete="CASCADE"), nullable=False
    )
    parent_hypothesis_id = Column(
        String(36), ForeignKey("hypotheses.id", ondelete="CASCADE"), nullable=True
    )
    type = Column(
        Enum("value", "growth", "compliance", name="hypothesis_type"),
        nullable=False,
    )
    description = Column(Text, nullable=False)
    status = Column(
        Enum("open", "bevestigd", "weerlegd", "vervallen", name="hypothesis_status"),
        nullable=False,
        default="open",
    )
    learning = Column(Text, nullable=True)  # verplicht als status in (bevestigd, weerlegd)
    commentary = Column(Text, nullable=True)  # toelichting waarom deze status is gekozen
    created_at = Column(DateTime, default=func.now(), nullable=False)
    updated_at = Column(
        DateTime, default=func.now(), onupdate=func.now(), nullable=False
    )

    # Relaties
    initiative = relationship("Initiative", back_populates="hypotheses")
    parent_hypothesis = relationship(
        "Hypothesis", remote_side=[id], back_populates="sub_hypotheses"
    )
    sub_hypotheses = relationship(
        "Hypothesis", back_populates="parent_hypothesis", cascade="all, delete-orphan"
    )


class DossierNote(Base):
    __tablename__ = "dossier_notes"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    initiative_id = Column(
        String(36), ForeignKey("initiatives.id", ondelete="CASCADE"), nullable=False
    )
    title = Column(Text, nullable=True)
    body = Column(Text, nullable=False)  # markdown
    created_at = Column(DateTime, default=func.now(), nullable=False)

    # Relaties
    initiative = relationship("Initiative", back_populates="dossier_notes")


class DossierFile(Base):
    __tablename__ = "dossier_files"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    initiative_id = Column(
        String(36), ForeignKey("initiatives.id", ondelete="CASCADE"), nullable=False
    )
    filename = Column(Text, nullable=False)
    mime_type = Column(Text, nullable=False)
    file_size = Column(Integer, nullable=False)  # bytes
    storage_path = Column(Text, nullable=False)  # relatief pad
    uploaded_at = Column(DateTime, default=func.now(), nullable=False)

    # Relaties
    initiative = relationship("Initiative", back_populates="dossier_files")


class Curation(Base):
    __tablename__ = "curations"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(Text, nullable=False)
    purpose = Column(Text, nullable=True)  # bijv. "Show & tell juli"
    description = Column(Text, nullable=True)  # markdown
    created_at = Column(DateTime, default=func.now(), nullable=False)
    updated_at = Column(
        DateTime, default=func.now(), onupdate=func.now(), nullable=False
    )

    # Relaties
    items = relationship(
        "CurationItem", back_populates="curation", cascade="all, delete-orphan"
    )


class CurationItem(Base):
    __tablename__ = "curation_items"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    curation_id = Column(
        String(36), ForeignKey("curations.id", ondelete="CASCADE"), nullable=False
    )
    initiative_id = Column(
        String(36), ForeignKey("initiatives.id", ondelete="CASCADE"), nullable=False
    )
    position = Column(Integer, nullable=False)  # volgorde binnen curatie
    note = Column(Text, nullable=True)  # toelichting per item

    # Relaties
    curation = relationship("Curation", back_populates="items")
    initiative = relationship("Initiative", back_populates="curation_items")


class CentralQuestion(Base):
    __tablename__ = "central_questions"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    question = Column(Text, nullable=False)  # de vraagstelling zelf
    description = Column(Text, nullable=True)  # toelichting, markdown
    is_active = Column(Boolean, default=True, nullable=False)  # soft delete
    created_at = Column(DateTime, default=func.now(), nullable=False)
    updated_at = Column(
        DateTime, default=func.now(), onupdate=func.now(), nullable=False
    )

    # Relaties
    initiative_questions = relationship(
        "InitiativeQuestion", back_populates="central_question",
        cascade="all, delete-orphan"
    )
    files = relationship(
        "CentralQuestionFile", back_populates="central_question",
        cascade="all, delete-orphan"
    )


class CentralQuestionFile(Base):
    __tablename__ = "central_question_files"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    central_question_id = Column(
        String(36), ForeignKey("central_questions.id", ondelete="CASCADE"), nullable=False
    )
    filename = Column(Text, nullable=False)
    mime_type = Column(Text, nullable=False)
    file_size = Column(Integer, nullable=False)  # bytes
    storage_path = Column(Text, nullable=False)  # relatief pad
    uploaded_at = Column(DateTime, default=func.now(), nullable=False)

    # Relaties
    central_question = relationship("CentralQuestion", back_populates="files")


class InitiativeQuestion(Base):
    __tablename__ = "initiative_questions"

    initiative_id = Column(
        String(36), ForeignKey("initiatives.id", ondelete="CASCADE"),
        primary_key=True, nullable=False,
    )
    central_question_id = Column(
        String(36), ForeignKey("central_questions.id", ondelete="CASCADE"),
        primary_key=True, nullable=False,
    )
    created_at = Column(DateTime, default=func.now(), nullable=False)

    # Relaties
    initiative = relationship("Initiative", back_populates="initiative_questions")
    central_question = relationship(
        "CentralQuestion", back_populates="initiative_questions"
    )


class MDS(Base):
    __tablename__ = "mds"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(Text, nullable=False, unique=True)  # naam van de MDS
    description = Column(Text, nullable=True)  # toelichting, markdown
    is_active = Column(Boolean, default=True, nullable=False)  # soft delete
    created_at = Column(DateTime, default=func.now(), nullable=False)
    updated_at = Column(
        DateTime, default=func.now(), onupdate=func.now(), nullable=False
    )

    # Relaties
    initiatives = relationship("Initiative", back_populates="mds_rel")


class Tag(Base):
    __tablename__ = "tags"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(Text, nullable=False, unique=True)  # tag naam (bijv. "duurzaamheid")
    description = Column(Text, nullable=True)  # toelichting voor AI-suggesties en UI
    is_active = Column(Boolean, default=True, nullable=False)  # soft delete
    created_at = Column(DateTime, default=func.now(), nullable=False)

    # Relaties
    initiative_tags = relationship(
        "InitiativeTag", back_populates="tag", cascade="all, delete-orphan"
    )
    question_tags = relationship(
        "QuestionTag", back_populates="tag", cascade="all, delete-orphan"
    )


class OnePager(Base):
    __tablename__ = "one_pagers"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    initiative_id = Column(
        String(36), ForeignKey("initiatives.id", ondelete="CASCADE"), nullable=False,
    )
    content = Column(Text, nullable=False)  # de gegenereerde markdown
    purpose = Column(Text, nullable=True)  # doel van de one-pager (bijv. "directievoordracht")
    audience = Column(Text, nullable=True)  # doelgroep (bijv. "directie", "raad")
    created_at = Column(DateTime, default=func.now(), nullable=False)
    updated_at = Column(
        DateTime, default=func.now(), onupdate=func.now(), nullable=False
    )

    # Relaties
    initiative = relationship("Initiative")


class CurationNarrative(Base):
    __tablename__ = "curation_narratives"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    curation_id = Column(
        String(36), ForeignKey("curations.id", ondelete="CASCADE"), nullable=False,
    )
    content = Column(Text, nullable=False)  # de gegenereerde markdown
    created_at = Column(DateTime, default=func.now(), nullable=False)
    updated_at = Column(
        DateTime, default=func.now(), onupdate=func.now(), nullable=False
    )

    # Relaties
    curation = relationship("Curation")


class InitiativeTag(Base):
    __tablename__ = "initiative_tags"

    initiative_id = Column(
        String(36), ForeignKey("initiatives.id", ondelete="CASCADE"),
        primary_key=True, nullable=False,
    )
    tag_id = Column(
        String(36), ForeignKey("tags.id", ondelete="CASCADE"),
        primary_key=True, nullable=False,
    )

    # Relaties
    initiative = relationship("Initiative", back_populates="initiative_tags")
    tag = relationship("Tag", back_populates="initiative_tags")


class QuestionTag(Base):
    __tablename__ = "question_tags"

    central_question_id = Column(
        String(36), ForeignKey("central_questions.id", ondelete="CASCADE"),
        primary_key=True, nullable=False,
    )
    tag_id = Column(
        String(36), ForeignKey("tags.id", ondelete="CASCADE"),
        primary_key=True, nullable=False,
    )

    # Relaties
    central_question = relationship("CentralQuestion")
    tag = relationship("Tag", back_populates="question_tags")


# --- Auth (RBAC + Permissions) ---

# Rol-constanten
ROLE_ADMIN = "admin"     # Alles: initiatieven, beheer, backups, gebruikers
ROLE_EDITOR = "editor"   # Initiatieven CRUD, hypothesen, dossier, curaties, tags, MDS, vragen
ROLE_VIEWER = "viewer"   # Alleen lezen: dashboard, detailpagina's
ALL_ROLES = [ROLE_ADMIN, ROLE_EDITOR, ROLE_VIEWER]


class Permission(Base):
    """Permissie die aan rollen toegewezen kan worden.

    Naming convention: <resource>.<action> (bijv. initiatives.create, users.delete)
    """
    __tablename__ = "permissions"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String(100), unique=True, nullable=False, index=True)
    description = Column(String(255), nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=func.now(), nullable=False)


class RolePermission(Base):
    """Koppeling tussen een rol en een permissie.

    Elke rij betekent: deze rol heeft deze permissie.
    """
    __tablename__ = "role_permissions"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    role_name = Column(String(50), nullable=False, index=True)
    permission_id = Column(String(36), ForeignKey("permissions.id"), nullable=False)

    permission = relationship("Permission")


# Standaard permissies — wordt geseed bij migration / startup
DEFAULT_PERMISSIONS = [
    # Initiatieven
    ("initiatives.read", "Initiatieven lezen"),
    ("initiatives.create", "Initiatief aanmaken"),
    ("initiatives.update", "Initiatief bewerken"),
    ("initiatives.delete", "Initiatief verwijderen"),
    # Hypothesen
    ("hypotheses.read", "Hypothesen lezen"),
    ("hypotheses.create", "Hypothese aanmaken"),
    ("hypotheses.update", "Hypothese bewerken"),
    ("hypotheses.delete", "Hypothese verwijderen"),
    # Dossier notities
    ("dossier.read", "Dossier lezen (notities & bestanden)"),
    ("dossier.create", "Dossier item toevoegen (notitie of bestand)"),
    ("dossier.update", "Notitie bewerken"),
    ("dossier.delete", "Dossier item verwijderen"),
    # Curaties
    ("curations.read", "Curaties lezen"),
    ("curations.create", "Curatie aanmaken"),
    ("curations.update", "Curatie bewerken"),
    ("curations.delete", "Curatie verwijderen"),
    ("curation_items.manage", "Initiatieven in curatie beheren"),
    # Centrale vragen
    ("questions.read", "Centrale vragen lezen"),
    ("questions.create", "Centrale vraag aanmaken"),
    ("questions.update", "Centrale vraag bewerken"),
    ("questions.delete", "Centrale vraag inactief zetten"),
    ("questions.files.manage", "Bestanden bij vragen beheren"),
    # MDS
    ("mds.read", "MDS lezen"),
    ("mds.create", "MDS aanmaken"),
    ("mds.update", "MDS bewerken"),
    ("mds.delete", "MDS inactief zetten"),
    # Tags
    ("tags.read", "Tags lezen"),
    ("tags.create", "Tag aanmaken"),
    ("tags.update", "Tag bewerken"),
    ("tags.delete", "Tag inactief zetten"),
    # AI
    ("ai.generate", "AI-content genereren (hypothesen, narratief, one-pager)"),
    # Export
    ("export.excel", "Data exporteren naar Excel"),
    # Gebruikersbeheer
    ("users.read", "Gebruikerslijst bekijken"),
    ("users.create", "Gebruiker aanmaken"),
    ("users.update", "Gebruiker bewerken"),
    ("users.delete", "Gebruiker verwijderen"),
]

# Standaard rol→permissie mapping
DEFAULT_ROLE_PERMISSIONS = {
    "admin": [
        "initiatives.read", "initiatives.create", "initiatives.update", "initiatives.delete",
        "hypotheses.read", "hypotheses.create", "hypotheses.update", "hypotheses.delete",
        "dossier.read", "dossier.create", "dossier.update", "dossier.delete",
        "curations.read", "curations.create", "curations.update", "curations.delete",
        "curation_items.manage",
        "questions.read", "questions.create", "questions.update", "questions.delete",
        "questions.files.manage",
        "mds.read", "mds.create", "mds.update", "mds.delete",
        "tags.read", "tags.create", "tags.update", "tags.delete",
        "ai.generate",
        "export.excel",
        "users.read", "users.create", "users.update", "users.delete",
    ],
    "editor": [
        "initiatives.read", "initiatives.create", "initiatives.update", "initiatives.delete",
        "hypotheses.read", "hypotheses.create", "hypotheses.update", "hypotheses.delete",
        "dossier.read", "dossier.create", "dossier.update", "dossier.delete",
        "curations.read", "curations.create", "curations.update", "curations.delete",
        "curation_items.manage",
        "questions.read", "questions.create", "questions.update", "questions.delete",
        "questions.files.manage",
        "mds.read", "mds.create", "mds.update", "mds.delete",
        "tags.read", "tags.create", "tags.update", "tags.delete",
        "ai.generate",
        "export.excel",
    ],
    "viewer": [
        "initiatives.read",
        "hypotheses.read",
        "dossier.read",
        "curations.read",
        "questions.read",
        "mds.read",
        "tags.read",
        "export.excel",
    ],
}


class User(Base):
    """Authenticatie-gebruiker met RBAC rollen.

    Rollen (hoger = meer rechten):
      - admin:   alles inclusief gebruikersbeheer en backups
      - editor:  initiatieven CRUD, hypothesen, dossier, curaties, tags, MDS, vragen
      - viewer:  alleen lezen (dashboard, detailpagina's)

    Permissies worden opgehaald uit de RolePermission tabel.
    """
    __tablename__ = "users"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    username = Column(String(100), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)  # bcrypt hash
    role = Column(Enum(*ALL_ROLES, name="user_roles"), default=ROLE_VIEWER, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=func.now(), nullable=False)
    last_login = Column(DateTime, nullable=True)

    @property
    def is_admin(self) -> bool:
        """Backward-compatible property — returns True if role is admin."""
        return self.role == ROLE_ADMIN

    @property
    def permissions(self) -> set:
        """Haal cached permissies voor deze gebruiker op.

        Retourneert een set van perm names (bijv. {'initiatives.read', ...}).
        """
        from app.auth import get_role_permissions_cache
        return get_role_permissions_cache().get(self.role, set())
