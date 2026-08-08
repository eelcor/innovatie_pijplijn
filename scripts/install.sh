#!/usr/bin/env bash
# =============================================================================
# Innovatiepijplijn — Installatiescript
# Installeert de applicatie via Docker Compose op een frisse server.
#
# Gebruik:
#   ./scripts/install.sh              # Interactieve installatie
#   ./scripts/install.sh --non-interactive  # Automatisch met .env.example defaults
# =============================================================================

set -euo pipefail

# Kleuren voor output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Detecteer script locatie en ga naar project root
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$PROJECT_ROOT"

log_info()  { echo -e "${BLUE}[INFO]${NC}  $*"; }
log_ok()    { echo -e "${GREEN}[OK]${NC}    $*"; }
log_warn()  { echo -e "${YELLOW}[WARN]${NC}  $*"; }
log_error() { echo -e "${RED}[ERROR]${NC} $*"; }

# --- Voorwaarden controleren ---
check_prerequisites() {
    log_info "Controleer installatie-voorwaarden..."

    # Docker
    if ! command -v docker &>/dev/null; then
        log_error "Docker is niet geïnstalleerd. Zie: https://docs.docker.com/get-docker/"
        exit 1
    fi
    log_ok "Docker gevonden: $(docker --version)"

    # Docker Compose (v2 plugin)
    if ! docker compose version &>/dev/null; then
        log_error "Docker Compose plugin niet gevonden. Installeer Docker Compose v2."
        exit 1
    fi
    log_ok "Docker Compose gevonden: $(docker compose version --short)"

    # Docker daemon draait?
    if ! docker info &>/dev/null; then
        log_error "Docker daemon draait niet. Start Docker en probeer opnieuw."
        exit 1
    fi
    log_ok "Docker daemon is actief"

    # Check of poort vrij is
    APP_PORT="${APP_PORT:-8000}"
    if command -v lsof &>/dev/null && lsof -Pi ":${APP_PORT}" -sTCP:LISTEN -t &>/dev/null; then
        log_warn "Poort ${APP_PORT} is al in gebruik. De applicatie kan niet starten."
        log_info "Gebruik een andere poort: APP_PORT=9000 ./scripts/install.sh"
    fi
}

# --- .env bestand configureren ---
setup_env() {
    log_info "Configureer omgevingsvariabelen..."

    if [[ -f ".env" ]]; then
        log_warn ".env bestand bestaat al. Overslaan."
        return
    fi

    # Kopieer template
    cp .env.example .env
    log_ok ".env aangemaakt (gebaseerd op .env.example)"

    # Vraag admin wachtwoord bij interactieve modus
    if [[ "${NON_INTERACTIVE:-false}" != "true" ]]; then
        echo ""
        log_info "--- Admin Account ---"
        read -p "Admin username [admin]: " ADMIN_USER
        ADMIN_USER="${ADMIN_USER:-admin}"

        # Vraag wachtwoord (verborgen input)
        while true; do
            read -s -p "Admin password: " ADMIN_PASS
            echo ""
            read -s -p "Bevestig password: " ADMIN_PASS_CONFIRM
            echo ""
            if [[ "$ADMIN_PASS" == "$ADMIN_PASS_CONFIRM" ]]; then
                if [[ ${#ADMIN_PASS} -lt 6 ]]; then
                    log_warn "Wachtwoord moet minimaal 6 karakters bevatten."
                else
                    break
                fi
            else
                log_warn "Wachtwoorden komen niet overeen."
            fi
        done

        # Update .env met admin credentials
        sed -i.bak "s/^APP_ADMIN_USERNAME=.*/APP_ADMIN_USERNAME=${ADMIN_USER}/" .env
        sed -i.bak "s/^APP_ADMIN_PASSWORD=.*/APP_ADMIN_PASSWORD=${ADMIN_PASS}/" .env
        rm -f .env.bak

        # AI configuratie
        echo ""
        log_info "--- AI Configuratie (optioneel) ---"
        read -p "AI inschakelen? (yes/no) [no]: " AI_CHOICE
        if [[ "$AI_CHOICE" =~ ^([Yy][Ee][Ss]|[Yy])$ ]]; then
            sed -i.bak "s/^AI_ENABLED=.*/AI_ENABLED=true/" .env
            read -p "Model URL (bijv. http://taalmodel.local:8033): " MODEL_URL_INPUT
            if [[ -n "$MODEL_URL_INPUT" ]]; then
                sed -i.bak "s|^MODEL_URL=.*|MODEL_URL=${MODEL_URL_INPUT}|" .env
            fi
            read -p "Model naam (bijv. qwen3.6): " MODEL_NAME_INPUT
            if [[ -n "$MODEL_NAME_INPUT" ]]; then
                sed -i.bak "s/^MODEL_NAME=.*|MODEL_NAME=${MODEL_NAME_INPUT}|" .env
            fi
            log_ok "AI is ingeschakeld"
        else
            sed -i.bak "s/^AI_ENABLED=.*/AI_ENABLED=false/" .env
            log_info "AI is uitgeschakeld (kan later via admin panel worden aangezet)"
        fi
        rm -f .env.bak
    else
        log_info "Non-interactive modus: gebruik standaardwaarden uit .env.example"
    fi

    # Update APP_BASE_URL met correcte poort
    sed -i.bak "s|^APP_BASE_URL=.*|APP_BASE_URL=http://localhost:${APP_PORT:-8000}|" .env
    rm -f .env.bak
}

# --- Docker bouwen en starten ---
build_and_start() {
    log_info "Bouw Docker image..."
    docker compose build --quiet

    log_ok "Docker image gebouwd"

    log_info "Start applicatie..."
    docker compose up -d

    # Wacht op healthy status
    log_info "Wacht op applicatie startup..."
    local max_wait=60
    local waited=0
    while [[ $waited -lt $max_wait ]]; do
        if docker inspect --format='{{.State.Health.Status}}' innovatiepijplijn 2>/dev/null | grep -q "healthy"; then
            log_ok "Applicatie is healthy en draait!"
            return 0
        fi
        sleep 2
        waited=$((waited + 2))
        printf "."
    done
    echo ""

    # Geef logs als niet healthy binnen timeout
    if ! docker inspect --format='{{.State.Health.Status}}' innovatiepijplijn 2>/dev/null | grep -q "healthy"; then
        log_warn "Applicatie is nog niet healthy na ${max_wait}s. Check de logs:"
        docker compose logs --tail=20 innovatiepijplijn
    else
        log_ok "Installatie voltooid!"
    fi
}

# --- Toon samenvatting ---
show_summary() {
    local app_port="${APP_PORT:-8000}"
    echo ""
    echo -e "${GREEN}========================================${NC}"
    echo -e "${GREEN}  Innovatiepijplijn is geïnstalleerd!   ${NC}"
    echo -e "${GREEN}========================================${NC}"
    echo ""
    echo -e "  Applicatie:     ${BLUE}http://localhost:${app_port}${NC}"
    echo -e "  Admin login:    ${BLUE}/login${NC}"
    echo ""
    echo -e "  Handige commando's:"
    echo -e "    Logs bekijken:    docker compose logs -f"
    echo -e "    Stoppen:          docker compose stop"
    echo -e "    Opnieuw starten:  docker compose start"
    echo -e "    Updaten:          ./scripts/update.sh"
    echo ""
    echo -e "  Documentatie:"
    echo -e "    README:           cat README.md"
    echo -e "    Docker gebruik:   cat docker/README.md"
    echo -e "    Operations:       cat docs/operations.md"
    echo ""
}

# --- Main ---
main() {
    NON_INTERACTIVE="${1:-}"
    if [[ "$NON_INTERACTIVE" == "--non-interactive" ]]; then
        NON_INTERACTIVE="true"
    else
        NON_INTERACTIVE="false"
    fi

    echo -e "${BLUE}========================================${NC}"
    echo -e "${BLUE}  Innovatiepijplijn — Installatie       ${NC}"
    echo -e "${BLUE}========================================${NC}"
    echo ""

    check_prerequisites
    setup_env
    build_and_start
    show_summary
}

main "$@"
