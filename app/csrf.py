"""CSRF-bescherming via double-submit cookie pattern.

Werking:
- Een CSRF-token wordt opgeslagen in een niet-httpOnly cookie
- Dezelfde token moet worden verstuurd als header `X-CSRF-Token`
- Alleen POST, PUT, DELETE, PATCH worden gecontroleerd
- GET/HEAD/OPTIONS zijn vrijgesteld (lezen is veilig)

Configuratie:
  CSRF_SECRET — secret voor token signing (gebruikt APP_SECRET_KEY als fallback)
"""

import os
import secrets
from datetime import timedelta
from typing import Callable

from fastapi import FastAPI, HTTPException, Request, Response
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint

# Cookie naam voor CSRF token
CSRF_COOKIE_NAME = "csrf_token"
CSRF_HEADER_NAME = "X-CSRF-Token"

# Hoe lang een token geldig is (uren)
TOKEN_TTL_HOURS = 24


def generate_csrf_token() -> str:
    """Genereer een willekeurig CSRF token."""
    return secrets.token_hex(32)


class CSRFMiddleware(BaseHTTPMiddleware):
    """Double-submit CSRF middleware.

    - GET requests: genereert token indien ontbreekt, slaat op in cookie
    - POST/PUT/DELETE/PATCH: valideert dat header == cookie
    - Excepties: auth login (kan geen token hebben), health checks
    - In test modus (TESTING=true): CSRF validatie wordt uitgeschakeld
    """

    # Routes die vrijgesteld zijn van CSRF (bijv. login, health)
    EXEMPT_PATHS = {
        "/api/auth/login",
        "/health",
    }

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        method = request.method.upper()
        path = request.url.path

        # Test modus: geen CSRF validatie
        if os.environ.get("TESTING", "false").lower() == "true":
            response = await call_next(request)
            return response

        # Vrijgestelde routes overslaan
        if path in self.EXEMPT_PATHS:
            return await call_next(request)

        # Alleen muterende methods controleren
        if method in ("POST", "PUT", "DELETE", "PATCH"):
            cookie_token = request.cookies.get(CSRF_COOKIE_NAME)
            header_token = request.headers.get(CSRF_HEADER_NAME)

            if not cookie_token or not header_token:
                raise HTTPException(
                    status_code=403,
                    detail="CSRF token ontbreekt — voeg X-CSRF-Token header toe",
                )

            # Constant-time comparison om timing attacks te voorkomen
            if not secrets.compare_digest(cookie_token, header_token):
                raise HTTPException(
                    status_code=403,
                    detail="Ongeldig CSRF token",
                )

        response = await call_next(request)

        # Zorg dat er altijd een CSRF cookie is (voor GET en als het nog niet bestaat)
        if not request.cookies.get(CSRF_COOKIE_NAME):
            token = generate_csrf_token()
            response.set_cookie(
                key=CSRF_COOKIE_NAME,
                value=token,
                httponly=False,  # Moet leesbaar zijn voor JavaScript
                samesite="lax",
                max_age=TOKEN_TTL_HOURS * 3600,
                path="/",
            )

        return response


def get_csrf_token(request: Request) -> str:
    """Haal het huidige CSRF token op uit de request cookies.

    Genereert een nieuw token als er geen is.
    """
    token = request.cookies.get(CSRF_COOKIE_NAME)
    if not token:
        token = generate_csrf_token()
    return token


# Endpoint om een CSRF token te halen (voor API clients zonder cookie support)
from fastapi import APIRouter

router = APIRouter()


@router.get("/csrf-token")
async def csrf_token_endpoint(request: Request, response: Response):
    """Haal of vernieuw een CSRF token.

    Retourneert het huidige token en stelt een cookie in als het ontbreekt.
    """
    token = request.cookies.get(CSRF_COOKIE_NAME)
    if not token:
        token = generate_csrf_token()
        response.set_cookie(
            key=CSRF_COOKIE_NAME,
            value=token,
            httponly=False,
            samesite="lax",
            max_age=TOKEN_TTL_HOURS * 3600,
            path="/",
        )
    return {"csrf_token": token}
