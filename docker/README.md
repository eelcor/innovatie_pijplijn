# Docker Gebruik — Innovatiepijplijn

## Snelstart

```bash
# Bouw en start de container
docker compose up -d --build

# Check of de service draait
docker compose ps

# Bekijk logs
docker compose logs -f
```

De applicatie is standaard bereikbaar op `http://localhost:8000`.

---

## Installatie Scripts

Voor geautomatiseerde installatie en updates:

```bash
# Eerste installatie (interactief)
./scripts/install.sh

# Eerste installatie (zonder prompts)
./scripts/install.sh --non-interactive

# Update naar nieuwste versie
./scripts/update.sh

# Update voorbeeld (geen wijzigingen toepassen)
./scripts/update.sh --dry-run
```

---

## Poorten configureren

### Via omgevingsvariabele (aanbevolen)

```bash
APP_PORT=9000 docker compose up -d
```

### Via .env bestand

1. Kopieer het voorbeeld: `cp .env.example .env`
2. Pas de waarden aan:
   ```
   APP_PORT=9000
   ```
3. Start: `docker compose up -d`

---

## Data persistentie

De SQLite database en geüploade bestanden worden opgeslagen in een Docker volume:

| Volume | Container pad | Inhoud |
|--------|--------------|--------|
| `innovatiepijplijn-data` | `/app/data/` | Database, uploads, backups |

### Data behouden bij herbouw

```bash
docker compose down   # Volume blijft bestaan
docker compose up -d  # Data is weer beschikbaar
```

### Alle data verwijderen

```bash
docker compose down -v
```

### Backup maken vanuit container

```bash
# Database bestand downloaden
docker compose cp innovatiepijplijn:/app/data/innovatiepijplijn.db ./backup.db

# Backups downloaden
docker compose cp innovatiepijplijn:/app/data/backups/ ./backups/
```

---

## Handige commando's

```bash
# Bouw opnieuw (na code-wijzigingen)
docker compose build --no-cache

# Stop de service (data behouden)
docker compose stop

# Start de service weer
docker compose start

# Herstart
docker compose restart

# Complete cleanup (inclusief data!)
docker compose down -v

# Voer commando in container uit
docker compose exec innovatiepijplijn python -c "print('hello')"

# Shell in container
docker compose exec innovatiepijplijn /bin/sh
```

---

## Docker image details

De `Dockerfile` gebruikt een **multi-stage build**:

1. **Builder stage** — Installeer Python dependencies via `uv` (snel)
2. **Runtime stage** — Minimale Python image met alleen productie dependencies

### Security features

- Non-root gebruiker (`appuser`)
- Minimal base image (`python:3.11-slim`)
- Alleen productie dependencies (`--no-dev`)
- Health checks via `/health` endpoint
- Resource limits via `deploy.resources`

---

## Troubleshooting

### Poort al in gebruik

```bash
# Check welke processen op poort 8000 luisteren
lsof -i :8000

# Of gebruik een andere poort
APP_PORT=9000 docker compose up -d
```

### Database fouten

```bash
# Check of volume correct is gemount
docker compose exec innovatiepijplijn ls -la /app/data/

# Database integriteit checken
docker compose exec innovatiepijplijn sqlite3 /app/data/innovatiepijplijn.db "PRAGMA integrity_check;"
```

### Container start niet

```bash
# Bekijk logs
docker compose logs --tail=50 innovatiepijplijn

# Check health status
docker inspect --format='{{.State.Health.Status}}' innovatiepijplijn

# Handmatig herstarten
docker compose restart innovatiepijplijn
```

### Image rebuilden na code wijzigingen

```bash
# Normale rebuild (gebrukt cache)
docker compose build

# Volledige rebuild (geen cache)
docker compose build --no-cache

# Rebuild en direct starten
docker compose up -d --build
```
