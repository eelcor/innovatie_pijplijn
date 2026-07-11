"""RBAC Authenticatie — sessie-based met bcrypt en rollen.

Rollen (hoger = meer rechten):
  - admin:   alles inclusief gebruikersbeheer en backups
  - editor:  initiatieven CRUD, hypothesen, dossier, curaties, tags, MDS, vragen
  - viewer:  alleen lezen (dashboard, detailpagina's)

Configuratie:
  APP_SECRET_KEY    — secret voor sessie signing
  APP_ADMIN_USERNAME — gebruikersnaam eerste admin (default: "admin")
  APP_ADMIN_PASSWORD — wachtwoord eerste admin (auto-create bij startup)
"""

import os
import uuid
from datetime import datetime, timedelta
from typing import Optional

import bcrypt
import itsdangerous
from fastapi import Cookie, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import (
    User, ROLE_ADMIN, ROLE_EDITOR, ROLE_VIEWER, ALL_ROLES,
    Permission, RolePermission,
    DEFAULT_PERMISSIONS, DEFAULT_ROLE_PERMISSIONS,
)

# --- Permissions cache ---
# In-memory cache: { role_name: {perm_name1, perm_name2, ...} }
# Geladen bij app startup via load_permissions_cache().
_role_permissions_cache: dict[str, set[str]] = {}


def load_permissions_cache(db: Session) -> None:
    """Laad rol→permissies mapping in de cache.

    Wordt aangeroepen bij app startup via on_event("startup").
    Haalt alle actieve permissies op en groepeert ze per rol.
    
    Als de DB nog geen permissions heeft (bijv. test-DB zonder migration),
    wordt de cache gevuld met DEFAULT_ROLE_PERMISSIONS uit models.py.
    """
    cache: dict[str, set[str]] = {}
    rp_rows = db.query(RolePermission).all()
    perm_map = {p.id: p.name for p in db.query(Permission).filter(Permission.is_active == True).all()}

    for rp in rp_rows:
        perm_name = perm_map.get(rp.permission_id)
        if perm_name:
            cache.setdefault(rp.role_name, set()).add(perm_name)

    # Fallback: als DB geen permissions heeft (test-DB, eerste start),
    # gebruik de hardcoded defaults uit models.py
    if not cache:
        for role_name, perm_names in DEFAULT_ROLE_PERMISSIONS.items():
            cache[role_name] = set(perm_names)

    _role_permissions_cache.clear()
    _role_permissions_cache.update(cache)


def get_role_permissions_cache() -> dict[str, set[str]]:
    """Retourneert de permissions cache.

    Fallback naar lege dict als cache nog niet geladen is.
    """
    return _role_permissions_cache


def user_has_permission(user: User, perm_name: str) -> bool:
    """Check of een gebruiker een specifieke permissie heeft via zijn rol."""
    return perm_name in user.permissions


# --- Configuratie ---

SECRET_KEY = os.environ.get("APP_SECRET_KEY", "dev-secret-key-change-in-production")
SESSION_EXPIRY_HOURS = int(os.environ.get("SESSION_EXPIRY_HOURS", "24"))

# Serializer voor sessie cookies
serializer = itsdangerous.URLSafeTimedSerializer(
    SECRET_KEY,
    salt="innovatiepijplijn-session",
)


# --- Helpers ---

def hash_password(password: str) -> str:
    """Hash een wachtwoord met bcrypt."""
    password_bytes = password.encode("utf-8")[:72]  # bcrypt max 72 bytes
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password_bytes, salt).decode("utf-8")


def verify_password(password: str, hash_value: str) -> bool:
    """Verifieer een wachtwoord tegen een bcrypt hash."""
    try:
        password_bytes = password.encode("utf-8")[:72]
        hash_bytes = hash_value.encode("utf-8")
        return bcrypt.checkpw(password_bytes, hash_bytes)
    except Exception:
        return False


def create_session_token(user_id: str, username: str, role: str) -> str:
    """Creëer een gesigneerde sessie token."""
    payload = {
        "user_id": user_id,
        "username": username,
        "role": role,
        "exp": (datetime.utcnow() + timedelta(hours=SESSION_EXPIRY_HOURS)).timestamp(),
        "jti": str(uuid.uuid4()),  # session ID voor revocation
    }
    return serializer.dumps(payload)


def decode_session_token(token: str) -> Optional[dict]:
    """Decodeer en valideer een sessie token.

    Retourneert None bij ongeldig/verlopen token.
    """
    try:
        payload = serializer.loads(token, max_age=SESSION_EXPIRY_HOURS * 3600)
        return payload
    except itsdangerous.BadData:
        return None


def has_role(user_role: str, required_role: str) -> bool:
    """Check of een rol voldoet aan de vereiste.

    Rollen zijn hiërarchisch: admin > editor > viewer
    """
    role_hierarchy = {ROLE_ADMIN: 3, ROLE_EDITOR: 2, ROLE_VIEWER: 1}
    user_level = role_hierarchy.get(user_role, 0)
    required_level = role_hierarchy.get(required_role, 0)
    return user_level >= required_level


def ensure_admin_user(db: Session) -> None:
    """Zorg dat er minstens één admin-gebruiker bestaat.

    Als APP_ADMIN_USERNAME en APP_ADMIN_PASSWORD zijn ingesteld,
    wordt die gebruiker aangemaakt als deze nog niet bestaat.
    Bestaande admin krijgt wachtwoord en rol gesync't met .env.
    """
    admin_username = os.environ.get("APP_ADMIN_USERNAME", "admin")
    admin_password = os.environ.get("APP_ADMIN_PASSWORD")

    if not admin_password:
        return  # Geen wachtwoord ingesteld — skip auto-create

    existing = db.query(User).filter(
        User.username == admin_username
    ).first()
    if existing:
        # Sync wachtwoord en rol met .env config
        existing.password_hash = hash_password(admin_password)
        existing.role = ROLE_ADMIN
        existing.is_active = True
        db.commit()
        return

    admin_user = User(
        username=admin_username,
        password_hash=hash_password(admin_password),
        role=ROLE_ADMIN,
        is_active=True,
    )
    db.add(admin_user)
    db.commit()
    db.refresh(admin_user)


# --- FastAPI Dependencies ---

async def get_current_user(
    session: Optional[str] = Cookie(None, alias="session"),
    db: Session = Depends(get_db),
) -> User:
    """Haal de huidige gebruiker op uit de sessie cookie.

    Geeft 401 als er geen geldige sessie is.
    """
    if not session:
        raise HTTPException(
            status_code=401,
            detail="Authenticatie vereist — log in via /api/auth/login",
        )

    payload = decode_session_token(session)
    if not payload:
        raise HTTPException(status_code=401, detail="Sessie verlopen of ongeldig")

    user = db.query(User).filter(
        User.id == payload["user_id"],
        User.is_active == True,
    ).first()
    if not user:
        raise HTTPException(status_code=401, detail="Gebruiker niet gevonden of inactief")

    return user


def require_role(required_role: str):
    """Dependency factory — vereist een specifieke rol of hoger.

    Gebruik:
        async def my_route(user: User = Depends(require_role(ROLE_EDITOR))):
            ...
    """
    async def _check(current_user: User = Depends(get_current_user)) -> User:
        if not has_role(current_user.role, required_role):
            raise HTTPException(
                status_code=403,
                detail=f"Toegang geweigerd — vereiste rol: {required_role}",
            )
        return current_user
    return _check


# Convenience dependencies voor common role checks (backward compat)
require_editor = require_role(ROLE_EDITOR)
require_admin = require_role(ROLE_ADMIN)


def require_permission(perm_name: str):
    """Dependency factory — vereist een specifieke permissie.

    Checkt of de huidige gebruiker via zijn rol de gevraagde permissie heeft.
    De permissies worden opgehaald uit de in-memory cache (geladen bij startup).

    In test modus (TESTING=true): slaat authenticatie + permissie-check over,
    retourneert None zodat bestaande tests blijven werken.

    Gebruik:
        async def my_route(user: User = Depends(require_permission("initiatives.create"))):
            ...
    """
    async def _check(current_user: User = Depends(get_current_user)) -> User:
        if not user_has_permission(current_user, perm_name):
            raise HTTPException(
                status_code=403,
                detail=f"Toegang geweigerd — vereiste permissie: {perm_name}",
            )
        return current_user

    async def _test_bypass() -> None:
        """In test modus: geen auth/check nodig."""
        return None

    # Test modus: bypass volledig
    if os.environ.get("TESTING", "false").lower() == "true":
        return _test_bypass
    return _check


# --- Permission shortcuts voor veelgebruikte checks ---
# Dit maakt de route-bestanden leesbaarder en centraliseert de mapping.

# Initiatieven
perm_initiatives_read = require_permission("initiatives.read")
perm_initiatives_create = require_permission("initiatives.create")
perm_initiatives_update = require_permission("initiatives.update")
perm_initiatives_delete = require_permission("initiatives.delete")

# Hypothesen
perm_hypotheses_read = require_permission("hypotheses.read")
perm_hypotheses_create = require_permission("hypotheses.create")
perm_hypotheses_update = require_permission("hypotheses.update")
perm_hypotheses_delete = require_permission("hypotheses.delete")

# Dossier
perm_dossier_read = require_permission("dossier.read")
perm_dossier_create = require_permission("dossier.create")
perm_dossier_update = require_permission("dossier.update")
perm_dossier_delete = require_permission("dossier.delete")

# Curaties
perm_curations_read = require_permission("curations.read")
perm_curations_create = require_permission("curations.create")
perm_curations_update = require_permission("curations.update")
perm_curations_delete = require_permission("curations.delete")
perm_curation_items_manage = require_permission("curation_items.manage")

# Centrale vragen
perm_questions_read = require_permission("questions.read")
perm_questions_create = require_permission("questions.create")
perm_questions_update = require_permission("questions.update")
perm_questions_delete = require_permission("questions.delete")
perm_questions_files_manage = require_permission("questions.files.manage")

# MDS
perm_mds_read = require_permission("mds.read")
perm_mds_create = require_permission("mds.create")
perm_mds_update = require_permission("mds.update")
perm_mds_delete = require_permission("mds.delete")

# Tags
perm_tags_read = require_permission("tags.read")
perm_tags_create = require_permission("tags.create")
perm_tags_update = require_permission("tags.update")
perm_tags_delete = require_permission("tags.delete")

# AI
perm_ai_generate = require_permission("ai.generate")

# Export
perm_export_excel = require_permission("export.excel")

# Gebruikersbeheer
perm_users_read = require_permission("users.read")
perm_users_create = require_permission("users.create")
perm_users_update = require_permission("users.update")
perm_users_delete = require_permission("users.delete")


# --- Auth Routes ---

from fastapi import APIRouter

router = APIRouter()


class LoginRequest(BaseModel):
    """Login request body."""
    username: str = Field(..., min_length=1)
    password: str = Field(..., min_length=1)


@router.post("/login")
async def login(
    data: LoginRequest,
    response: Response,
    db: Session = Depends(get_db),
):
    """Log in en ontvang een sessie cookie."""
    user = db.query(User).filter(
        User.username == data.username,
        User.is_active == True,
    ).first()
    if not user or not verify_password(data.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Ongeldige gebruikersnaam of wachtwoord")

    # Update last_login
    user.last_login = datetime.utcnow()
    db.commit()

    # Creëer sessie cookie
    token = create_session_token(user.id, user.username, user.role)
    response.set_cookie(
        key="session",
        value=token,
        httponly=True,
        samesite="lax",
        max_age=SESSION_EXPIRY_HOURS * 3600,
        path="/",
    )

    return {
        "message": "Ingelogd",
        "username": user.username,
        "role": user.role,
    }


@router.post("/logout")
async def logout(
    response: Response,
    current_user: User = Depends(get_current_user),
):
    """Log uit door de sessie cookie te verwijderen."""
    response.set_cookie(
        key="session",
        value="",
        httponly=True,
        samesite="lax",
        max_age=0,
        path="/",
    )
    return {"message": "Uitgelogd"}


@router.get("/me")
async def current_user_info(
    current_user: User = Depends(get_current_user),
):
    """Haal informatie over de huidige gebruiker op."""
    return {
        "id": current_user.id,
        "username": current_user.username,
        "role": current_user.role,
        "is_active": current_user.is_active,
        "last_login": current_user.last_login.isoformat() if current_user.last_login else None,
    }


class CreateUserRequest(BaseModel):
    """Gebruiker aanmaken request."""
    username: str = Field(..., min_length=1, max_length=100)
    password: str = Field(..., min_length=4, max_length=72)
    role: str = Field(default=ROLE_VIEWER)


@router.post("/users/create")
async def create_user(
    data: CreateUserRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(perm_users_create),
):
    """Maak een nieuwe gebruiker aan (alleen door admin)."""
    if data.role not in ALL_ROLES:
        raise HTTPException(status_code=400, detail=f"Ongeldige rol — kies uit: {', '.join(ALL_ROLES)}")

    # Check of gebruiker al bestaat
    existing = db.query(User).filter(
        User.username == data.username
    ).first()
    if existing:
        raise HTTPException(status_code=409, detail=f"Gebruiker '{data.username}' bestaat al")

    user = User(
        username=data.username,
        password_hash=hash_password(data.password),
        role=data.role,
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    return {
        "id": user.id,
        "username": user.username,
        "role": user.role,
        "message": "Gebruiker aangemaakt",
    }


@router.put("/users/{user_id}")
async def update_user(
    user_id: str,
    data: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(perm_users_update),
):
    """Update een gebruiker (alleen door admin)."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Gebruiker niet gevonden")

    if "role" in data and data["role"] in ALL_ROLES:
        user.role = data["role"]
    if "is_active" in data:
        user.is_active = bool(data["is_active"])
    if "password" in data and data["password"]:
        user.password_hash = hash_password(data["password"])

    db.commit()
    return {"message": "Gebruiker bijgewerkt"}


@router.delete("/users/{user_id}")
async def delete_user(
    user_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(perm_users_delete),
):
    """Verwijder een gebruiker (alleen door admin)."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Gebruiker niet gevonden")

    # Voorkom dat admin zichzelf verwijdert
    if user.id == current_user.id:
        raise HTTPException(status_code=400, detail="Je kunt jezelf niet verwijderen")

    db.delete(user)
    db.commit()
    return {"message": "Gebruiker verwijderd"}


@router.get("/users")
async def list_users(
    db: Session = Depends(get_db),
    current_user: User = Depends(perm_users_read),
):
    """Lijst alle gebruikers (alleen door admin)."""
    users = db.query(User).order_by(User.username.asc()).all()
    return [{
        "id": u.id,
        "username": u.username,
        "role": u.role,
        "is_active": u.is_active,
        "created_at": u.created_at.isoformat() if u.created_at else None,
        "last_login": u.last_login.isoformat() if u.last_login else None,
    } for u in users]
