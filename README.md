# Innovatiepijplijn

Registratie- en analysetool voor innovatie-initiatieven. Bouw een overzicht van alle AI- en innovatie-initiatieven binnen je organisatie, volg voortgang, beheer hypothesen en koppel dossiers aan centrale vraagstukken.

## Inhoud

- [Kenmerken](#kenmerken)
- [Snelstart](#snelstart)
- [Installatie](#installatie)
- [Update](#update)
- [Configuratie](#configuratie)
- [Docker](#docker)
- [Ontwikkeling](#ontwikkeling)
- [API](#api)
- [Documentatie](#documentatie)

---

## Kenmerken

| Functie | Beschrijving |
|---------|-------------|
| **Initiatiefbeheer** | Registratie en overzicht van innovatie-initiatieven |
| **Beleidsmatrix** | Potentie, risico en capaciteitsvraag per initiatief |
| **Cluster & Governance** | Domeinindeling, betrokkenheid IV, bronnen, externe partners |
| **Gerelateerde initiatieven** | Koppel initiatieven aan elkaar met zoekbare selector |
| **Card & List view** | Schakel tussen tegels en gedetailleerde lijstweergave |
| **Filteren & Sorteren** | Filter op cluster, potentie, risico; sorteer op elke kolom |
| **Hypothese tracking** | Formuleer, test en evalueer hypothesen per initiatief |
| **Dossier management** | Upload en beheer bestanden per initiatief |
| **Centrale vragen** | Koppel initiatieven aan strategische vraagstukken |
| **Tagging systeem** | Categoriseer met flexibele tags |
| **AI-assistentie** | Optionele AI-ondersteuning (model-agnostisch, OpenAI-compatible) |
| **Zoekfunctionaliteit** | Full-text zoekopdrachten over alle initiatieven |
| **Excel export** | Exporteer alle data naar Excel met 23 kolommen |
| **Backups** | Automatische en handmatige database backups |
| **Authenticatie** | Gebruikersbeheer met rollen en permissies |
| **Profielbeheer** | Wachtwoord wijzigen, accountinformatie, data export |

---

## Snelstart

```bash
# 1. Clone de repository
git clone https://github.com/eelcor/innovatie_pijplijn.git
cd innovatie_pijplijn

# 2. Start met Docker (aanbevolen)
docker compose up -d --build

# 3. Open http://localhost:8000 in je browser
```

De applicatie is direct bruikbaar. Een admin account wordt automatisch aangemaakt bij eerste start.

---

## Installatie

### Vereisten

- **Docker** en **Docker Compose v2** (aanbevolen voor productie)
- Of **Python 3.11+** met **uv** (voor lokale ontwikkeling)

### Optie A: Geautomatiseerde installatie (Docker)

```bash
./scripts/install.sh
```

Het script controleert voorwaarden, configureert `.env`, bouwt het Docker image en start de applicatie. Je wordt gevraagd om admin credentials en AI-instellingen.

Voor volledig automatische installatie zonder prompts:

```bash
./scripts/install.sh --non-interactive
```

### Optie B: Handmatige Docker installatie

```bash
# 1. Configureer omgevingsvariabelen
cp .env.example .env
# Pas .env aan naar wens (zie Configuratie hieronder)

# 2. Bouw en start
docker compose up -d --build

# 3. Check of alles draait
docker compose ps
curl http://localhost:8000/health
```

### Optie C: Lokaal zonder Docker

```bash
# 1. Virtual environment
python -m venv .venv
source .venv/bin/activate

# 2. Installeer dependencies via uv
pip install uv
uv sync --frozen

# 3. Configureer
cp .env.example .env

# 4. Start
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

---

## Update

### Met Docker (aanbevolen)

```bash
./scripts/update.sh
```

Het update script:
1. Maakt een backup van de huidige database
2. Haalt nieuwste code via `git pull`
3. Rebuild het Docker image
4. Start de container opnieuw
5. Wacht op healthy status

Voor een droge run (toon veranderingen zonder uitvoeren):

```bash
./scripts/update.sh --dry-run
```

### Handmatig

```bash
# Haal nieuwste code
git pull origin master

# Rebuild en restart Docker
docker compose up -d --build

# Check health
curl http://localhost:8000/health
```

---

## Configuratie

Alle instellingen worden beheerd via omgevingsvariabelen. Zie `.env.example` voor de volledige lijst.

### Belangrijkste variabelen

| Variabele | Standaard | Beschrijving |
|-----------|-----------|-------------|
| `APP_PORT` | `8000` | Poort waarop de app bereikbaar is |
| `APP_ENV` | `production` | Omgeving: `development`, `staging`, `production` |
| `APP_BASE_URL` | `http://localhost:8000` | Basis-URL voor links |
| `APP_ADMIN_USERNAME` | `admin` | Admin gebruikersnaam (eerste start) |
| `APP_ADMIN_PASSWORD` | `verander-dit` | Admin wachtwoord (eerste start) |
| `AI_ENABLED` | `false` | AI-functionaliteit aan/uit |
| `MODEL_URL` | *(leeg)* | URL van het AI-taalmodel |
| `MODEL_NAME` | *(leeg)* | Naam van het AI-model |
| `LOG_LEVEL` | `INFO` | Log level: `DEBUG`, `INFO`, `WARNING`, `ERROR` |
| `LOG_FORMAT` | `json` | Log formaat: `console` of `json` |

### AI Configuratie

Het systeem ondersteunt elk model met een **OpenAI-compatible** `/v1/chat/completions` endpoint:

```bash
# Voorbeeld: LM Studio
MODEL_URL=http://localhost:8033
MODEL_NAME=qwen3.6
AI_ENABLED=true

# Voorbeeld: Ollama
MODEL_URL=http://localhost:11434
MODEL_NAME=llama3
AI_ENABLED=true

# AI uitschakelen
AI_ENABLED=false
```

---

## Docker

### Basis commando's

```bash
# Start
docker compose up -d

# Stop
docker compose stop

# Herstart
docker compose restart

# Logs bekijken
docker compose logs -f

# Status check
docker compose ps

# Volledige cleanup (inclusief data!)
docker compose down -v
```

### Data persistentie

De SQLite database en geüploade bestanden worden opgeslagen in een Docker volume (`innovatiepijplijn-data`). De data blijft bewaard bij herbouw:

```bash
# Volume behouden
docker compose down          # Data blijft
docker compose up -d         # Data is weer beschikbaar

# Database backup vanuit container
docker compose cp innovatiepijplijn:/app/data/innovatiepijplijn.db ./backup.db

# Backups downloaden
docker compose cp innovatiepijplijn:/app/data/backups/ ./backups/
```

### Poort aanpassen

```bash
APP_PORT=9000 docker compose up -d
```

Of pas `APP_PORT` aan in het `.env` bestand.

---

## Ontwikkeling

### Project structuur

```
innovatie_pijplijn/
├── app/                    # Applicatie code
│   ├── main.py            # FastAPI applicatie entry point
│   ├── models.py          # SQLAlchemy data modellen
│   ├── routes/            # API en pagina routes
│   ├── templates/         # Jinja2 HTML templates
│   └── static/            # Static assets (CSS, JS)
├── docker-compose.yml     # Docker Compose configuratie
├── Dockerfile             # Multi-stage Docker build
├── alembic/               # Database migraties (Alembic)
│   └── versions/          # Migratie-bestanden
├── scripts/               # Installatie en onderhoudsscripts
│   ├── install.sh         # Geautomatiseerde installatie
│   ├── update.sh          # Update met backup
│   └── import_excel_v02.py # Import uit Excel inventarisatie
├── tests/                 # Pytest test suite
├── docs/                  # Documentatie
│   └── operations.md      # IT Operations handleiding
├── docker/                # Docker-specific documentatie
│   └── README.md          # Docker gebruiksgids
├── .env.example           # Omgevingsvariabelen template
└── pyproject.toml         # Python dependencies
```

### Tests uitvoeren

```bash
# Met Docker
docker compose exec innovatiepijplijn python -m pytest

# Lokaal
source .venv/bin/activate
pytest
```

---

## API

De applicatie exposeert een REST API en web interface. Enkele belangrijke endpoints:

| Endpoint | Methode | Beschrijving |
|----------|---------|-------------|
| `/health` | GET | Health check |
| `/api/admin/status` | GET | Applicatiestatus en statistieken |
| `/api/admin/config` | GET/PUT | Configuratie (LLM, timeouts) |
| `/api/admin/backup` | POST | Trigger database backup |
| `/api/admin/backup/export/{name}` | GET | Download backup bestand |
| `/api/admin/backup/import` | POST | Upload en importeer backup |
| `/api/initiatieven/filter` | GET | Gefilterde lijst (met sortering) |
| `/api/initiatieven/json` | GET | Alle initiatieven als JSON |
| `/api/initiatieven/create` | POST | Nieuw initiatief aanmaken |
| `/api/initiatieven/{id}` | PUT/DELETE | Bewerken/verwijderen |
| `/api/hypothesen` | GET/POST | Beheer hypothesen |
| `/api/dossier` | GET/POST | Dossier bestanden |
| `/api/export/excel` | GET | Excel export (alle data) |
| `/api/auth/change-password` | POST | Wachtwoord wijzigen |

Volledige API documentatie is beschikbaar op `/docs` na het starten van de applicatie (FastAPI Swagger UI).

---

## Documentatie

| Document | Locatie | Inhoud |
|----------|---------|--------|
| **Deploy gids** | `deploy.md` | Productie-installatie, upgrades, backups, security |
| **Docker gebruik** | `docker/README.md` | Gedetailleerde Docker instructies |
| **IT Operations** | `docs/operations.md` | Monitoring, backups, troubleshooting |
| **.env template** | `.env.example` | Alle configuratie-opties uitgelegd |

---

## Resource-gebruik

| Component | Minimum | Aanbevolen |
|-----------|---------|------------|
| CPU | 1 core | 2 cores |
| RAM | 512 MB | 1 GB |
| Disk (app) | 100 MB | 500 MB |
| Disk (data) | 10 MB | 1 GB (met backups/uploads) |

> **Let op:** Het AI-model draait apart en heeft eigen resources nodig.

---

## Wijzigingen (Changelog)

### v0.2.1 — Bugfix: formulieren en error handling
- Fix: opslaan bewerkt initiatief werkte niet (lege strings → 422 validatiefout)
- Fix: error toast toonde `[Object Object]` in plaats van leesbaar bericht
- Backend: `field_validator` converteert lege strings naar `None` voor alle optionele velden
- Frontend: formulieren filteren lege strings voordat ze naar API gaan
- Error handling: FastAPI validation errors worden nu correct getoond

### v0.2.0 — Beleidsmatrix, Governance & Verbeterde UI
**Nieuwe data-modellen:**
- 12 nieuwe velden per initiatief: cluster, afdeling, team, potentie, risico, capaciteitsvraag, bron_initiatief, externe_partners, betrokkenheid_iv, gerelateerde_initiatieven, volgende_stap, opmerkingen
- Status enum uitgebreid met: onduidelijk, pauze, idee
- Gerelateerde initiatieven als echte koppelingen (zoekbare selector met badges)

**Nieuwe UI-functionaliteit:**
- Beleidsmatrix op detailpagina (potentie/risico/capaciteit altijd zichtbaar)
- Governance sectie met bron, externe partners, betrokkenheid IV
- Card view én list view met sorteerbare kolommen
- Filterpaneel uitgebreid: cluster, potentie, risico filters
- Searchable dropdown voor gerelateerde initiatieven (typ om te zoeken, badges met ×)
- Volgende stap card prominent op detailpagina

**Backend:**
- Alle API endpoints uitgebreid met nieuwe velden
- Excel export bevat nu alle 23 kolommen
- Filter API ondersteunt sorteren op nieuwe velden
- Database migraties via Alembic (automatisch bij startup)
- Excel import script (`scripts/import_excel_v02.py`)

### v0.1.0 — Initiële release
- Initiatiefbeheer met fase, status, horizon tracking
- Hypothese tracking (value/growth/compliance)
- Dossier management (notities en bestanden)
- Centrale vragen koppeling
- Tagging systeem
- AI-assistentie (model-agnostisch)
- Backups en Excel export
- Gebruikersbeheer met rollen
- Profielbeheer (wachtwoord wijzigen)

## Licentie

Intern project — geen externe distributie.
