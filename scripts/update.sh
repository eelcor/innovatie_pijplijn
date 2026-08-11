#!/usr/bin/env bash
# =============================================================================
# Innovatiepijplijn — Updatescript v0.2
# Haalt nieuwste code, maakt backup, rebuild en restart met minimale downtime.
#
# Gebruik:
#   ./scripts/update.sh           # Automatische update
#   ./scripts/update.sh --dry-run # Toon wat er gaat veranderen
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

DRY_RUN=false
[[ "${1:-}" == "--dry-run" ]] && DRY_RUN=true

if [[ "$DRY_RUN" == true ]]; then
    warn "DRY-RUN modus — niets wordt gewijzigd"
fi

# ── Controleer git status ───────────────────────────────────────────────────
step "Controleer repository"

if ! command -v git &>/dev/null; then
    error "Git is niet geïnstalleerd"
    exit 1
fi

# Huidige commit en branch
CURRENT_COMMIT=$(git rev-parse --short HEAD 2>/dev/null || echo "onbekend")
CURRENT_BRANCH=$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo "onbekend")
info "Huidige versie: $CURRENT_COMMIT (branch: $CURRENT_BRANCH)"

# Check of er lokale wijzigingen zijn
if ! git diff --quiet 2>/dev/null || ! git diff --cached --quiet 2>/dev/null; then
    warn "Er zijn oncommitterde wijzigingen in de repository"
    if [[ "$DRY_RUN" == false ]]; then
        read -p "Doorgaan? (lokaal werk gaat verloren) [y/N]: " CONFIRM
        [[ "${CONFIRM,,}" != "y" && "${CONFIRM,,}" != "yes" ]] && exit 0
    fi
fi

# Haal nieuwste code
if [[ "$DRY_RUN" == false ]]; then
    info "Haal nieuwste code..."
    git pull origin "$CURRENT_BRANCH"
    ok "Code bijgewerkt"
else
    info "Zou uitvoeren: git pull origin $CURRENT_BRANCH"
fi

# Nieuwe commit?
NEW_COMMIT=$(git rev-parse --short HEAD 2>/dev/null || echo "onbekend")
if [[ "$CURRENT_COMMIT" == "$NEW_COMMIT" ]]; then
    info "Al op laatste versie — geen update nodig"
    exit 0
fi
info "Update: $CURRENT_COMMIT → $NEW_COMMIT"

# ── Backup database ─────────────────────────────────────────────────────────
step "Maak backup van database"

if [[ "$DRY_RUN" == false ]]; then
    # Check of container draait
    if docker compose ps --status running 2>/dev/null | grep -q innovatiepijplijn; then
        TIMESTAMP=$(date +%Y%m%d_%H%M%S)
        BACKUP_FILE="/tmp/innovatiepijplijn_preupdate_${TIMESTAMP}.db"

        info "Kopieer database naar $BACKUP_FILE..."
        if docker compose cp innovatiepijplijn:/app/data/innovatiepijplijn.db "$BACKUP_FILE" 2>/dev/null; then
            SIZE=$(du -h "$BACKUP_FILE" | cut -f1)
            ok "Backup gemaakt (${SIZE})"
            info "Backup locatie: $BACKUP_FILE"
        else
            warn "Kon database niet kopiëren — ga door zonder backup"
        fi
    else
        warn "Container draait niet — skip backup"
    fi
else
    info "Zou database backup maken"
fi

# ── Rebuild Docker image ────────────────────────────────────────────────────
step "Rebuild Docker image"

if [[ "$DRY_RUN" == false ]]; then
    if ! docker compose build --quiet 2>&1; then
        error "Docker build mislukt!"
        info "Backup is beschikbaar op /tmp/innovatiepijplijn_preupdate_*.db"
        exit 1
    fi
    ok "Image gerebuild"
else
    info "Zou uitvoeren: docker compose build"
fi

# ── Restart container ───────────────────────────────────────────────────────
step "Herstart applicatie"

if [[ "$DRY_RUN" == false ]]; then
    # Bepaal poort
    APP_PORT=$(grep -oP 'APP_PORT=\K.*' .env 2>/dev/null || echo "8000")

    info "Container herstarten..."
    docker compose up -d

    # Wacht op healthy
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
    done

    if [[ "$HEALTHY" == true ]]; then
        ok "Update voltooid — applicatie healthy na ${WAITED}s"
    else
        warn "Applicatie reageert nog niet na ${MAX_WAIT}s"
        warn "Check logs: docker compose logs innovatiepijplijn"
    fi
else
    info "Zou uitvoeren: docker compose up -d"
fi

# ── Samenvatting ────────────────────────────────────────────────────────────
if [[ "$DRY_RUN" == false ]]; then
    echo ""
    info "Update samenvatting:"
    info "  Van: $CURRENT_COMMIT → Naar: $NEW_COMMIT"
    info "  Branch: $CURRENT_BRANCH"
    info "  Status: $(docker compose ps --status running 2>/dev/null | grep -q innovatiepijplijn && echo 'running' || echo 'onbekend')"
fi
