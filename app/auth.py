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
from app.models import User, ROLE_ADMIN, ROLE_EDITOR, ROLE_VIEWER, ALL_ROLES

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
    """
    admin_username = os.environ.get("APP_ADMIN_USERNAME", "admin")
    admin_password = os.environ.get("APP_ADMIN_PASSWORD")

    if not admin_password:
        return  # Geen wachtwoord ingesteld — skip auto-create

    existing = db.query(User).filter(
        User.username == admin_username
    ).first()
    if existing:
        return  # Admin bestaat al

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


# Convenience dependencies voor common role checks
require_editor = require_role(ROLE_EDITOR)  # async callable, used as Depends(require_editor)
require_admin = require_role(ROLE_ADMIN)    # async callable, used as Depends(require_admin)


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
    admin_user: User = Depends(require_admin),
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
    admin_user: User = Depends(require_admin),
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
    admin_user: User = Depends(require_admin),
):
    """Verwijder een gebruiker (alleen door admin)."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Gebruiker niet gevonden")

    # Voorkom dat admin zichzelf verwijdert
    if user.id == admin_user.id:
        raise HTTPException(status_code=400, detail="Je kunt jezelf niet verwijderen")

    db.delete(user)
    db.commit()
    return {"message": "Gebruiker verwijderd"}


@router.get("/users")
async def list_users(
    db: Session = Depends(get_db),
    admin_user: User = Depends(require_admin),
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
