"""add_permissions_and_role_permissions

Revision ID: ce68ec0258d5
Revises: a1b2c3d4e5f6
Create Date: 2026-07-12 00:18:51.315463

Creates:
  - permissions table (named permissions like 'initiatives.create')
  - role_permissions table (links role_name to permission_id)
Seeds default permissions and role-permission mappings.
"""
from typing import Sequence, Union

import uuid
from alembic import op
import sqlalchemy as sa


revision: str = 'ce68ec0258d5'
down_revision: Union[str, Sequence[str], None] = 'a1b2c3d4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# Standaard permissies die geseed worden bij upgrade
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
    # Dossier
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


def upgrade() -> None:
    """Create permissions tables and seed default data."""

    # 1. Create permissions table
    op.create_table(
        "permissions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("name", sa.String(100), unique=True, nullable=False, index=True),
        sa.Column("description", sa.String(255), nullable=True),
        sa.Column("is_active", sa.Boolean, default=True, nullable=False),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now(), nullable=False),
    )

    # 2. Create role_permissions table
    op.create_table(
        "role_permissions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("role_name", sa.String(50), nullable=False, index=True),
        sa.Column("permission_id", sa.String(36), nullable=False),
        sa.ForeignKeyConstraint(["permission_id"], ["permissions.id"]),
    )

    # 3. Seed permissions
    conn = op.get_bind()
    perm_ids = {}
    for name, description in DEFAULT_PERMISSIONS:
        perm_id = str(uuid.uuid4())
        perm_ids[name] = perm_id
        conn.execute(
            sa.insert(sa.table(
                "permissions",
                sa.Column("id", sa.String(36)),
                sa.Column("name", sa.String(100)),
                sa.Column("description", sa.String(255)),
                sa.Column("is_active", sa.Boolean),
            )).values(id=perm_id, name=name, description=description, is_active=True)
        )

    # 4. Seed role_permissions
    for role_name, perm_names in DEFAULT_ROLE_PERMISSIONS.items():
        for perm_name in perm_names:
            if perm_name in perm_ids:
                conn.execute(
                    sa.insert(sa.table(
                        "role_permissions",
                        sa.Column("id", sa.String(36)),
                        sa.Column("role_name", sa.String(50)),
                        sa.Column("permission_id", sa.String(36)),
                    )).values(
                        id=str(uuid.uuid4()),
                        role_name=role_name,
                        permission_id=perm_ids[perm_name],
                    )
                )


def downgrade() -> None:
    """Drop permissions tables."""
    op.drop_table("role_permissions")
    op.drop_table("permissions")
