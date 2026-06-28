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
        Enum("verkenning", "experiment", "pilot", "opschaling", name="initiative_phase"),
        nullable=False,
        default="verkenning",
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


# --- Auth ---

class User(Base):
    """Authenticatie-gebruiker.

    Eenvoudige sessie-based auth voor lokale/MVP gebruik.
    Passwords zijn gehashed met bcrypt.
    """
    __tablename__ = "users"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    username = Column(String(100), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)  # bcrypt hash
    is_admin = Column(Boolean, default=False, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=func.now(), nullable=False)
    last_login = Column(DateTime, nullable=True)
