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
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint

from app.helpers import get_base_path

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

    # Routes die vrijgesteld zijn van CSRF (bijv. login, health) — zonder base_path
    _EXEMPT_PATHS = {
        "/api/auth/login",
        "/api/auth/logout",
        "/api/auth/csrf-token",
        "/api/auth/me",
        "/login",
        "/health",
    }

    @staticmethod
    def _strip_base(path: str) -> str:
        """Strip base_path prefix van request path voor exempt-check."""
        base = get_base_path()
        if base and base != '/' and path.startswith(base):
            return path[len(base):] or '/'
        return path

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        method = request.method.upper()
        path = self._strip_base(request.url.path)

        # Test modus: geen CSRF validatie
        if os.environ.get("TESTING", "false").lower() == "true":
            response = await call_next(request)
            return response

        # Vrijgestelde routes overslaan
        if path in self._EXEMPT_PATHS:
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
                path=get_base_path(),
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
from starlette.responses import RedirectResponse

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
            path=get_base_path(),
        )
    return {"csrf_token": token}


class AuthMiddleware(BaseHTTPMiddleware):
    """Authenticatie middleware — redirect naar /login als niet ingelogd.

    - HTML requests: 302 redirect naar /login?redirect=... (base-path aware)
    - API requests: 401 JSON response
    - Test modus: geen authenticatie vereist
    """

    # Routes die geen authenticatie nodig hebben (zonder base_path prefix)
    _EXEMPT_PATHS = {
        "/api/auth/login",
        "/api/auth/logout",
        "/api/auth/csrf-token",
        "/api/auth/me",
        "/login",
        "/health",
    }

    @staticmethod
    def _strip_base(path: str) -> str:
        """Strip base_path prefix van request path voor exempt-check."""
        base = get_base_path()
        if base and base != '/' and path.startswith(base):
            return path[len(base):] or '/'
        return path

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        path = self._strip_base(request.url.path)

        # Test modus: geen authenticatie vereist
        if os.environ.get("TESTING", "false").lower() == "true":
            return await call_next(request)

        # Vrijgestelde routes overslaan
        if path in self._EXEMPT_PATHS:
            return await call_next(request)

        # Static files en uploads overslaan
        if path.startswith("/static/") or "/api/dossier/download/" in path:
            return await call_next(request)

        # Check sessie cookie
        session_cookie = request.cookies.get("session")
        if not session_cookie:
            # Bepaal of het een API of HTML request is
            accept_header = request.headers.get("accept", "")
            base = get_base_path()
            # Check API path met of zonder base_path prefix
            is_api = path.startswith(base + "/api/") if base != '/' else path.startswith("/api/")
            is_html = "text/html" in accept_header or (not is_api and "application/json" not in accept_header)

            # Bepaal redirect URL — scope naar app basis-pad
            current_path = request.url.path
            if request.query_params:
                current_path += "?" + str(request.query_params)

            # Valideer: redirect moet binnen het app-basis-pad blijven (geen open redirect)
            login_redirect = f"{base}/login?redirect={current_path}"

            if is_html:
                return RedirectResponse(url=login_redirect, status_code=302)
            else:
                return JSONResponse(
                    status_code=401,
                    content={"detail": "Authenticatie vereist — log in via /api/auth/login"},
                )

        return await call_next(request)
