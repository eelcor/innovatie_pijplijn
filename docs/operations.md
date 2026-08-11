# Innovatiepijplijn — IT Operations Handleiding

## Sneloverzicht

| Onderwerp | Detail |
|-----------|--------|
| **Tech stack** | Python 3.11, FastAPI, SQLite, HTMX |
| **Versie** | v0.2.1 (beleidsmatrix, governance, bugfix formulieren) |
| **Default poort** | `8000` |
| **Database** | SQLite (WAL mode) in `/app/data/innovatiepijplijn.db` |
| **Health check** | `GET /health` → HTTP 200 + JSON |
| **Admin API** | `GET /api/admin/status`, `GET /api/admin/config` |
| **Backups** | `POST /api/admin/backup`, `GET /api/admin/backup/export/{name}` |

---

## Installatie & Configuratie

### 1. Omgevingsvariabelen instellen

```bash
# Kopieer het voorbeeld en pas aan
cp .env.example .env

# Minimale configuratie:
APP_PORT=8000
MODEL_URL=http://taalmodel.local:8033   # AI model URL
MODEL_NAME=Qwen3.6-27B-UD-Q4_K_XL.gguf  # Model naam
AI_ENABLED=true                          # Zet op false als geen AI nodig
```

Volledige lijst van variabelen: zie `.env.example`.

### 2. Docker (aanbevolen voor productie)

```bash
# Start de applicatie
docker compose up -d --build

# Check of alles draait
docker compose ps

# Bekijk logs
docker compose logs -f innovatiepijplijn
```

Of gebruik het geautomatiseerde installatiescript:

```bash
./scripts/install.sh
```

### 3. Lokaal (ontwikkeling)

```bash
# Virtual environment
python -m venv .venv
source .venv/bin/activate
pip install uv && uv sync --frozen

# Start
APP_PORT=8000 python -m uvicorn app.main:app --reload --host 0.0.0.0
```

---

## Database Migratie (v0.2)

### Nieuwe velden in Initiative model

Versie 0.2 voegt 12 nieuwe kolommen toe aan de `initiatives` tabel:
| Kolom | Type | Doel |
|-------|------|------|
| `cluster` | TEXT | Domeinindeling (Beheer, Dienstverlening, etc.) |
| `afdeling` | TEXT | Organisatorische eenheid |
| `team` | TEXT | Team naam |
| `potentie` | TEXT | Potentiewaardering (hoog/midden/onbekend) |
| `capaciteitsvraag` | TEXT | Capaciteitseis (hoog/midden/laag/onbekend) |
| `risico` | TEXT | Risicowaardering (hoog/midden/laag) |
| `bron_initiatief` | TEXT | Oorsprong van het initiatief |
| `externe_partners` | TEXT | Externe samenwerking |
| `betrokkenheid_iv` | TEXT | IV-betrokkenheidsniveau |
| `gerelateerde_initiatieven` | TEXT | Koppelingen naar andere initiatieven (IDs) |
| `volgende_stap` | TEXT | Actiepunten en volgende stappen |
| `opmerkingen` | TEXT | Algemene notities |

### Migratie uitvoeren

Bij een upgrade van v0.1 naar v0.2:
```bash
# Optioneel: handmatige migratie (meestal automatisch bij Docker rebuild)
docker compose exec innovatiepijplijn python3 /app/scripts/migrate_v02.py
```

### Excel import

Importeer initiatieven uit een Excel-bestand:
```bash
# Kopieer bestand naar container
docker compose cp inventarisatie.xlsx innovatiepijplijn:/tmp/import.xlsx

# Voer import uit
docker compose exec innovatiepijplijn python3 /app/scripts/import_excel_v02.py
```

---

## Monitoring

### Health Check

```bash
# Snel check
curl http://localhost:8000/health

# Gedetailleerd output
curl http://localhost:8000/health | python -m json.tool
```

Voorbeeld respons:

```json
{
  "status": "healthy",
  "timestamp": "2025-01-01T12:00:00Z",
  "components": {
    "database": {"status": "healthy"},
    "ai": {"status": "enabled (Qwen3.6-27B-UD-Q4_K_XL.gguf)"},
    "uploads": {"status": "healthy", "path": "/app/data/uploads"}
  }
}
```

### Applicatiestatus

```bash
# Overzicht van entiteiten en database-grootte
curl http://localhost:8000/api/admin/status | python -m json.tool

# Huidige configuratie (zonder secrets)
curl http://localhost:8000/api/admin/config | python -m json.tool
```

### Logging

**Console mode** (leesbaar, voor ontwikkeling):

```bash
# In .env:
LOG_FORMAT=console
LOG_LEVEL=DEBUG
```

```
[2025-01-01 12:00:00] INFO     app.main: Innovatiepijplijn start-up
[2025-01-01 12:00:00] INFO     app.main: Database: /app/data/innovatiepijplijn.db
```

**JSON mode** (standaard, voor productie en log-aggregators):

```bash
# In .env:
LOG_FORMAT=json
LOG_LEVEL=INFO
```

```json
{"timestamp": "2025-...", "level": "INFO", "logger": "app.main", "message": "..."}
```

---

## Backups

### Database backup maken (via API)

```bash
curl -X POST http://localhost:8000/api/admin/backup | python -m json.tool
```

Voorbeeld respons:

```json
{
  "success": true,
  "database_backup": "/app/data/backups/innovatiepijplijn_db_20250101_120000.db",
  "uploads_backup": "/app/data/backups/innovatiepijplijn_uploads_20250101_120000.zip"
}
```

> **Let op:** Er worden maximaal 10 database backups automatisch bewaard. Oudere backups worden verwijderd bij een nieuwe backup.

### Beschikbare backups bekijken

```bash
curl http://localhost:8000/api/admin/backups | python -m json.tool
```

### Backup verwijderen

```bash
curl -X DELETE "http://localhost:8000/api/admin/backups/innovatiepijplijn_db_20250101_120000.db"
```

### Automatische backups (cron)

```bash
# Voeg toe aan crontab: crontab -e
# Dagelijks om 02:00 uur
0 2 * * * curl -X POST http://localhost:8000/api/admin/backup >> /var/log/innovatiepijplijn-backup.log 2>&1

# Of direct SQLite backup (zonder API):
0 2 * * * sqlite3 /app/data/innovatiepijplijn.db ".backup /app/data/backups/innovatiepijplijn_db_$(date +\%Y\%m\%d_\%H\%M\%S).db"
```

### Backup handmatig kopiëren (Docker)

```bash
# Database bestand downloaden uit container
docker compose cp innovatiepijplijn:/app/data/innovatiepijplijn.db ./backup.db

# Backups downloaden
docker compose cp innovatiepijplijn:/app/data/backups/ ./backups/
```

---

## Database beheer

### SQLite database inspecteren

```bash
# Verbinden met de database (Docker)
docker compose exec innovatiepijplijn sqlite3 /app/data/innovatiepijplijn.db

# Tabeloverzicht
.tables

# Aantal initiatieven
SELECT COUNT(*) FROM initiatives;

# Database grootte
SELECT page_count * page_size as size_bytes FROM pragma_page_count(), pragma_page_size();
```

### Database optimaliseren

```bash
# VACUUM — herpak de database (doe dit tijdens onderhoudsvenster)
docker compose exec innovatiepijplijn sqlite3 /app/data/innovatiepijplijn.db "VACUUM;"

# ANALYZE — update query planner statistics
docker compose exec innovatiepijplijn sqlite3 /app/data/innovatiepijplijn.db "ANALYZE;"
```

---

## AI Configuratie

### Model aansluiten

Het systeem ondersteunt elk model met een **OpenAI-compatible** `/v1/chat/completions` endpoint:

| Provider | MODEL_URL | MODEL_NAME |
|----------|-----------|------------|
| LM Studio | `http://localhost:8033` | zie models list |
| Ollama | `http://localhost:11434` | modelnaam |
| vLLM | `http://server:8000` | modelnaam |
| OpenAI | `https://api.openai.com/v1` | gpt-4o |

### AI testen zonder model

```bash
# Zet AI uit in .env
AI_ENABLED=false

# App start normaal, AI features tonen "AI is uitgeschakeld"
```

### Timeout aanpassen (voor grote modellen)

```bash
# Standaard 600s — verhoog bij zeer grote modellen
AI_REQUEST_TIMEOUT=900
```

---

## Upgrades

### Nieuwe versie installeren

Gebruik het updatescript:

```bash
./scripts/update.sh
```

Dit script maakt automatisch een database backup, haalt nieuwste code en rebuild het Docker image.

### Handmatige upgrade

```bash
# Git pull naar nieuwste commit
git pull origin master

# Dependencies updaten (indien nodig)
source .venv/bin/activate && uv sync --frozen

# Docker rebuilden (indien Docker gebruikt)
docker compose up -d --build

# Check of alles draait
curl http://localhost:8000/health
```

### Database schema wijzigingen

Het systeem gebruikt `create_all()` voor automatische tabel-creatie. Voor expliciete migraties kan Alembic worden toegevoegd bij toekomstige versies.

---

## Troubleshooting

### App start niet

```bash
# Check logs
docker compose logs innovatiepijplijn

# Check poort conflict
lsof -i :8000

# Check health status
docker inspect --format='{{.State.Health.Status}}' innovatiepijplijn
```

### Database fouten

```bash
# Check database integriteit
docker compose exec innovatiepijplijn sqlite3 /app/data/innovatiepijplijn.db "PRAGMA integrity_check;"

# Herstel van backup
cp /app/data/backups/innovatiepijplijn_db_LATEST.db /app/data/innovatiepijplijn.db
```

### AI timeouts

```bash
# Verhoog timeout in .env
AI_REQUEST_TIMEOUT=900

# Of verlaag max_tokens (minder creatief maar sneller)
# Zie app/routes/ai.py — temperature en max_tokens per endpoint
```

### Logs niet zichtbaar

```bash
# Docker logs bekijken
docker compose logs -f innovatiepijplijn

# Log level verlagen voor meer detail
LOG_LEVEL=DEBUG
```

---

## Resource-gebruik

| Component | Minimum | Aanbevolen |
|-----------|---------|------------|
| CPU | 1 core | 2 cores |
| RAM | 512 MB | 1 GB |
| Disk (app) | 100 MB | 500 MB |
| Disk (data) | 10 MB | 1 GB (met backups/uploads) |

> **Let op:** Het AI-model draait apart en heeft eigen resources nodig (afhankelijk van modelgrootte).

---

## Docker Compose — Geavanceerd

### Resource limits aanpassen

```bash
# Via .env of command line:
CPU_LIMIT=4.0 MEMORY_LIMIT=4G docker compose up -d
```

### Custom volumes (host-mounted in plaats van Docker volumes)

Pas `docker-compose.yml` aan:

```yaml
volumes:
  - ./data:/app/data
```

> **Waarschuwing:** Host-mounted volumes omzeilen de Docker volume isolatie. Zorg dat permissies correct zijn.

### Multiple instances (niet standaard ondersteund)

De applicatie is ontworpen voor single-instance draai met SQLite. Voor multiple instances zou een externe database (PostgreSQL) nodig zijn.
