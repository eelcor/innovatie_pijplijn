"""Authenticatie en autorisatie — sessie-based met bcrypt.

Werking:
- Gebruiker logt in via POST /api/auth/login → krijgt session cookie
- Sessies zijn server-side (gesigneerde cookies via itsdangerous)
- Auth dependency (`require_auth`) kan worden toegevoegd aan routes
- Admin dependency (`require_admin`) voor admin-only routes

Configuratie:
  APP_SECRET_KEY — secret voor sessie signing (verplicht, default fallback voor dev)
  APP_ADMIN_PASSWORD — wachtwoord voor eerste admin-gebruiker (auto-create bij startup)
"""

import os
import uuid
from datetime import datetime, timedelta
from typing import Optional

import bcrypt
import itsdangerous
from fastapi import Body, Cookie, Depends, HTTPException, Request, Response
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User

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


def create_session_token(user_id: str, username: str, is_admin: bool) -> str:
    """Creëer een gesigneerde sessie token."""
    payload = {
        "user_id": user_id,
        "username": username,
        "is_admin": is_admin,
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
        is_admin=True,
        is_active=True,
    )
    db.add(admin_user)
    db.commit()
    db.refresh(admin_user)


# --- FastAPI Dependencies ---

async def get_current_user(
    session_token: Optional[str] = Cookie(None, alias="session"),
    db: Session = Depends(get_db),
) -> User:
    """Haal de huidige gebruiker op uit de sessie cookie.

    Geeft 401 als er geen geldige sessie is.
    """
    if not session_token:
        raise HTTPException(
            status_code=401,
            detail="Authenticatie vereist — log in via /api/auth/login",
        )

    payload = decode_session_token(session_token)
    if not payload:
        raise HTTPException(status_code=401, detail="Sessie verlopen of ongeldig")

    user = db.query(User).filter(
        User.id == payload["user_id"],
        User.is_active == True,
    ).first()
    if not user:
        raise HTTPException(status_code=401, detail="Gebruiker niet gevonden of inactief")

    return user


async def require_admin(
    current_user: User = Depends(get_current_user),
) -> User:
    """Vereist dat de huidige gebruiker admin-rechten heeft.

    Geeft 403 als gebruiker geen admin is.
    """
    if not current_user.is_admin:
        raise HTTPException(
            status_code=403,
            detail="Toegang geweigerd — admin-rechten vereist",
        )
    return current_user


# --- Auth Routes (te importeren in main.py) ---

from fastapi import APIRouter

router = APIRouter()


class LoginRequest(BaseModel):
    """Login request body."""
    username: str
    password: str


@router.post("/login")
async def login(
    data: LoginRequest,
    response: Response,
    db: Session = Depends(get_db),
):
    """Log in en ontvang een sessie cookie.

    Accepteert JSON body: {"username": "...", "password": "..."}
    """
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
    token = create_session_token(user.id, user.username, user.is_admin)
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
        "is_admin": user.is_admin,
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
        "is_admin": current_user.is_admin,
        "last_login": current_user.last_login.isoformat() if current_user.last_login else None,
    }


@router.post("/users/create")
async def create_user(
    data: dict,
    db: Session = Depends(get_db),
    admin_user: User = Depends(require_admin),
):
    """Maak een nieuwe gebruiker aan (alleen door admin).

    Accepteert: {"username": "...", "password": "...", "is_admin": false}
    """
    username = data.get("username", "").strip()
    password = data.get("password")
    is_admin = bool(data.get("is_admin", False))

    if not username or not password:
        raise HTTPException(status_code=400, detail="Gebruikersnaam en wachtwoord zijn verplicht")

    # Check of gebruiker al bestaat
    existing = db.query(User).filter(
        User.username == username
    ).first()
    if existing:
        raise HTTPException(status_code=409, detail=f"Gebruiker '{username}' bestaat al")

    user = User(
        username=username,
        password_hash=hash_password(password),
        is_admin=is_admin,
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    return {
        "id": user.id,
        "username": user.username,
        "is_admin": user.is_admin,
        "message": "Gebruiker aangemaakt",
    }


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
        "is_admin": u.is_admin,
        "is_active": u.is_active,
        "created_at": u.created_at.isoformat() if u.created_at else None,
        "last_login": u.last_login.isoformat() if u.last_login else None,
    } for u in users]
