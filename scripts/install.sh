#!/usr/bin/env bash
# =============================================================================
# Innovatiepijplijn — Installatiescript v0.2
# Installeert de applicatie via Docker Compose op een frisse server.
#
# Gebruik:
#   ./scripts/install.sh              # Interactieve installatie
#   ./scripts/install.sh --non-interactive  # Automatisch met defaults
# =============================================================================

set -euo pipefail

# Kleuren
R='\033[0;31m' G='\033[0;32m' Y='\033[1;33m' B='\033[0;34m' C='\033[0;36m' N='\033[0m'

# Script locatie en project root
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$PROJECT_ROOT"

info()  { echo -e "${B}[INFO]${N}  $*"; }
ok()    { echo -e "${G}[OK]${N}    $*"; }
warn()  { echo -e "${Y}[WARN]${N}  $*"; }
error() { echo -e "${R}[ERR]${N}   $*"; }
step()  { echo -e "\n${C}═══ $* ═══${N}"; }

NON_INTERACTIVE=false
[[ "${1:-}" == "--non-interactive" ]] && NON_INTERACTIVE=true

# ── Voorwaarden controleren ──────────────────────────────────────────────────
step "Controleer voorwaarden"

# Docker
if ! command -v docker &>/dev/null; then
    error "Docker is niet geïnstalleerd. Zie: https://docs.docker.com/get-docker/"
    exit 1
fi
ok "Docker $(docker --version | awk '{print $NF}')"

# Docker Compose
if ! docker compose version &>/dev/null; then
    error "Docker Compose v2 is niet beschikbaar"
    exit 1
fi
ok "Docker Compose $(docker compose version --short)"

# Git (optioneel, voor updates)
if command -v git &>/dev/null; then
    ok "Git $(git --version | awk '{print $3}')"
else
    warn "Git niet gevonden — updates zullen handmatig moeten"
fi

# ── .env configuratie ────────────────────────────────────────────────────────
step "Configureer .env"

if [[ -f .env ]]; then
    warn ".env bestaat al — wordt overslaan"
else
    cp .env.example .env
    ok ".env aangemaakt vanuit .env.example"
fi

# Genereer APP_SECRET_KEY als deze nog standaard is
CURRENT_SECRET=$(grep -oP 'APP_SECRET_KEY=\K.*' .env 2>/dev/null || echo "")
if [[ "$CURRENT_SECRET" == "verander-dit-naar-een-sterke-secret-key" || -z "$CURRENT_SECRET" ]]; then
    if command -v python3 &>/dev/null; then
        NEW_SECRET=$(python3 -c "import secrets; print(secrets.token_urlsafe(32))")
    elif command -v openssl &>/dev/null; then
        NEW_SECRET=$(openssl rand -base64 32 | tr -dc 'a-zA-Z0-9' | head -c 32)
    else
        NEW_SECRET="secret-$(date +%s)-$$-$(head /dev/urandom | tr -dc 'a-zA-Z0-9' | head -c 16)"
    fi
    sed -i "s|APP_SECRET_KEY=.*|APP_SECRET_KEY=$NEW_SECRET|" .env
    ok "APP_SECRET_KEY gegenereerd"
fi

# Vraag admin credentials (interactief)
if [[ "$NON_INTERACTIVE" == false ]]; then
    echo ""
    info "Admin account configuratie (druk op Enter voor defaults)"
    read -p "  Gebruikersnaam [admin]: " ADMIN_USER
    ADMIN_USER=${ADMIN_USER:-admin}

    # Vraag wachtwoord verborgen
    while true; do
        read -s -p "  Wachtwoord: " ADMIN_PASS
        echo ""
        read -s -p "  Bevestig wachtwoord: " ADMIN_PASS_CONFIRM
        echo ""
        if [[ "$ADMIN_PASS" == "$ADMIN_PASS_CONFIRM" && ${#ADMIN_PASS} -ge 4 ]]; then
            break
        elif [[ "$ADMIN_PASS" != "$ADMIN_PASS_CONFIRM" ]]; then
            warn "Wachtwoorden komen niet overeen — probeer opnieuw"
        else
            warn "Wachtwoord moet minimaal 4 karakters zijn — probeer opnieuw"
        fi
    done

    # Update .env met nieuwe credentials
    sed -i "s|APP_ADMIN_USERNAME=.*|APP_ADMIN_USERNAME=$ADMIN_USER|" .env
    sed -i "s|APP_ADMIN_PASSWORD=.*|APP_ADMIN_PASSWORD=$ADMIN_PASS|" .env
    ok "Admin credentials opgeslagen"
else
    ok "Non-interactive mode — gebruik defaults uit .env"
fi

# ── Docker image bouwen ─────────────────────────────────────────────────────
step "Bouw Docker image"

if ! docker compose build --quiet; then
    error "Docker build mislukt. Check logs hierboven."
    exit 1
fi
ok "Image gebouwd"

# ── Start applicatie ────────────────────────────────────────────────────────
step "Start applicatie"

# Bepaal poort uit .env
APP_PORT=$(grep -oP 'APP_PORT=\K.*' .env 2>/dev/null || echo "8000")

docker compose up -d
ok "Container gestart op poort $APP_PORT"

# ── Wacht op healthy ────────────────────────────────────────────────────────
step "Wacht op applicatie"

MAX_WAIT=60
WAITED=0
HEALTHY=false

while [[ $WAITED -lt $MAX_WAIT ]]; do
    HEALTH=$(docker compose exec innovatiepijplijn curl -s http://localhost:${APP_PORT}/health 2>/dev/null || echo "")
    if echo "$HEALTH" | grep -q "ok"; then
        HEALTHY=true
        break
    fi
    sleep 2
    WAITED=$((WAITED + 2))
    if [[ $((WAITED % 10)) -eq 0 ]]; then
        info "Wachten... ${WAITED}s"
    fi
done

if [[ "$HEALTHY" == true ]]; then
    ok "Applicatie is healthy na ${WAITED}s"
else
    warn "Applicatie reageert nog niet na ${MAX_WAIT}s — check logs:"
    warn "  docker compose logs innovatiepijplijn"
fi

# ── Samenvatting ────────────────────────────────────────────────────────────
echo ""
echo -e "${C}╔══════════════════════════════════════════════════════════╗${N}"
echo -e "${C}║${N}                INSTALLATIE VOLTOOID                      ${C}║${N}"
echo -e "${C}╚══════════════════════════════════════════════════════════╝${N}"
echo ""
info "Applicatie bereikbaar op:  http://localhost:$APP_PORT"
info "Admin dashboard:          http://localhost:$APP_PORT/admin"
info "API documentatie:         http://localhost:$APP_PORT/docs"
echo ""
info "Handige commando's:"
echo "  docker compose logs -f        # Logs bekijken"
echo "  docker compose restart        # Herstarten"
echo "  ./scripts/update.sh           # Upgraden"
echo ""
