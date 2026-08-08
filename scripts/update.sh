#!/usr/bin/env bash
# =============================================================================
# Innovatiepijplijn — Updatescript
# Haalt de nieuwste code, rebuild het Docker image en start opnieuw.
#
# Gebruik:
#   ./scripts/update.sh               # Automatische update
#   ./scripts/update.sh --dry-run     # Toon wat er gaat veranderen
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

DRY_RUN=false
if [[ "${1:-}" == "--dry-run" ]]; then
    DRY_RUN=true
fi

# --- Controleer of container draait ---
check_container() {
    if ! docker compose ps --status running 2>/dev/null | grep -q innovatiepijplijn; then
        log_warn "Container is niet actief. Start manual met: docker compose up -d"
    else
        log_ok "Container is actief"
    fi
}

# --- Backup huidige database ---
backup_database() {
    log_info "Maak backup van huidige database..."

    local timestamp
    timestamp=$(date +%Y%m%d_%H%M%S)
    local backup_file="/tmp/innovatiepijplijn_db_${timestamp}.db"

    if docker compose cp innovatiepijplijn:/app/data/innovatiepijplijn.db "$backup_file" 2>/dev/null; then
        log_ok "Backup gemaakt: ${backup_file}"
        echo "$backup_file"
    else
        log_warn "Kon geen backup maken (database bestaat mogelijk nog niet)"
        echo ""
    fi
}

# --- Haal nieuwste code ---
pull_latest() {
    if [[ -d ".git" ]]; then
        log_info "Haal nieuwste code van Git..."

        # Sla huidige commit op voor rollback info
        local current_commit
        current_commit=$(git rev-parse --short HEAD 2>/dev/null || echo "unknown")
        log_info "Huidige commit: ${current_commit}"

        if git pull origin "$(git branch --show HEAD)" 2>/dev/null; then
            local new_commit
            new_commit=$(git rev-parse --short HEAD 2>/dev/null || echo "unknown")
            if [[ "$current_commit" != "$new_commit" ]]; then
                log_ok "Code geüpdate: ${current_commit} → ${new_commit}"
            else
                log_info "Geen nieuwe code gevonden (al op latest)"
            fi
        else
            log_warn "Git pull mislukt of geen remote geconfigureerd. Ga door met lokale code."
        fi
    else
        log_info "Geen Git repo gevonden. Gebruik bestaande lokale code."
    fi
}

# --- Rebuild en restart ---
rebuild() {
    log_info "Rebuild Docker image..."
    docker compose build --pull

    log_ok "Image gerebuild"

    log_info "Restart container..."
    docker compose up -d

    # Wacht op healthy
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

    if ! docker inspect --format='{{.State.Health.Status}}' innovatiepijplijn 2>/dev/null | grep -q "healthy"; then
        log_warn "Applicatie is nog niet healthy na ${max_wait}s."
        docker compose logs --tail=30 innovatiepijplijn
    fi
}

# --- Toon update samenvatting ---
show_summary() {
    local app_port
    app_port=$(grep -oP 'APP_PORT=\K.*' .env 2>/dev/null || echo "8000")
    app_port="${app_port:-8000}"

    echo ""
    echo -e "${GREEN}========================================${NC}"
    echo -e "${GREEN}  Update voltooid!                      ${NC}"
    echo -e "${GREEN}========================================${NC}"
    echo ""
    echo -e "  Applicatie:     ${BLUE}http://localhost:${app_port}${NC}"
    echo ""
    echo -e "  Handige commando's:"
    echo -e "    Logs bekijken:   docker compose logs -f"
    echo -e "    Restart:         docker compose restart"
    echo -e "    Rollback image:  zie docs/operations.md"
    echo ""
}

# --- Main ---
main() {
    echo -e "${BLUE}========================================${NC}"
    echo -e "${BLUE}  Innovatiepijplijn — Update            ${NC}"
    echo -e "${BLUE}========================================${NC}"
    echo ""

    if $DRY_RUN; then
        log_info "--- DRY RUN --- Toon wat er gaat veranderen:"
        echo ""
        check_container
        pull_latest
        echo ""
        log_info "Bij echte run: docker image rebuilden en container restarten"
        exit 0
    fi

    check_container
    local backup_path
    backup_path=$(backup_database)
    pull_latest
    rebuild
    show_summary

    if [[ -n "$backup_path" ]]; then
        echo ""
        log_info "Database backup opgeslagen op: ${backup_path}"
    fi
}

main "$@"
