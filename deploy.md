# Innovatiepijplijn — Deploy Gids

Gedetailleerde instructies voor het inrichten, updaten en onderhouden van de applicatie op een productie-omgeving.

## Inhoud

- [Systeemvereisten](#systeemvereisten)
- [Eerste installatie](#eerste-installatie)
- [Configuratie](#configuratie)
- [Upgrades](#upgrades)
- [Backups & Restore](#backups--restore)
- [Monitoring & Onderhoud](#monitoring--onderhoud)
- [Troubleshooting](#troubleshooting)

---

## Systeemvereisten

| Component | Minimum | Aanbevolen |
|-----------|---------|------------|
| CPU | 1 core | 2 cores |
| RAM | 512 MB | 1 GB |
| Disk (app) | 100 MB | 500 MB |
| Disk (data + backups) | 50 MB | 1 GB |
| Docker | v20.10+ | v24.x |
| Docker Compose | v2.0+ | v2.x |

> **Let op:** Het AI-taalmodel draait in een aparte container/server en heeft eigen resources nodig.

---

## Eerste installatie

### Optie 1: Geautomatiseerd (aanbevolen)

```bash
# Clone de repository
git clone https://github.com/eelcor/innovatie_pijplijn.git
cd innovatie_pijplijn

# Voer installatiescript uit
chmod +x scripts/install.sh
./scripts/install.sh
```

Het script:
1. Controleert Docker en Compose versies
2. Kopieert `.env.example` naar `.env`
3. Vraagt admin credentials (of gebruikt defaults in non-interactive mode)
4. Bouwt het Docker image
5. Start de applicatie
6. Wacht op healthy status

**Non-interactive mode:**
```bash
./scripts/install.sh --non-interactive
```

### Optie 2: Handmatig

```bash
# 1. Clone en configureer
git clone https://github.com/eelcor/innovatie_pijplijn.git
cd innovatie_pijplijn
cp .env.example .env
# Pas .env aan (zie Configuratie hieronder)

# 2. Bouw en start
docker compose up -d --build

# 3. Controleer
docker compose ps
curl http://localhost:8000/health
```

---

## Configuratie

Alle instellingen via `.env`. Zie `.env.example` voor volledige lijst.

### Minimale configuratie

```bash
APP_PORT=8000
APP_SECRET_KEY=willekeurige-string-minimaal-32-karakters
APP_ADMIN_USERNAME=admin
APP_ADMIN_PASSWORD=veilig-wachtwoord-hier
```

### AI / LLM configuratie (optioneel)

```bash
AI_ENABLED=true
MODEL_URL=http://taalmodel.local:8033
MODEL_NAME=qwen3.6
AI_REQUEST_TIMEOUT=120
AI_TEMPERATURE=0.7
AI_MAX_TOKENS=8192
```

> De admin kan AI-instellingen live aanpassen via het beheerpaneel (`/admin` → "Model Configuratie"). Waarden in `.env` fungeren als defaults.

### Belangrijkste variabelen

| Variabele | Standaard | Beschrijving |
|-----------|-----------|-------------|
| `APP_PORT` | `8000` | Poort waarop de app bereikbaar is |
| `APP_SECRET_KEY` | *(verplicht)* | Secret voor sessie signing |
| `APP_ADMIN_USERNAME` | `admin` | Admin gebruikersnaam (eerste start) |
| `APP_ADMIN_PASSWORD` | `verander-dit` | Admin wachtwoord (eerste start) |
| `AI_ENABLED` | `false` | AI-functionaliteit aan/uit |
| `MODEL_URL` | *(leeg)* | URL van het AI-taalmodel |
| `MODEL_NAME` | *(leeg)* | Naam van het AI-model |
| `LOG_LEVEL` | `INFO` | Log level: DEBUG, INFO, WARNING, ERROR |
| `LOG_FORMAT` | `json` | Log formaat: console of json |
| `BACKUP_DIR` | `/app/data/backups` | Backup opslaglocatie |

---

## Upgrades

### Met updatescript (aanbevolen)

```bash
./scripts/update.sh
```

Het script:
1. Controleert git status en haalt nieuwste code (`git pull`)
2. Maakt een automatische backup van de database
3. Rebuild het Docker image
4. Start de container opnieuw met zero-downtime restart
5. Wacht op healthy status en rapporteert resultaat

**Dry-run (toon veranderingen zonder uitvoeren):**
```bash
./scripts/update.sh --dry-run
```

### Handmatig

```bash
# 1. Backup maken (altijd eerst!)
docker compose exec innovatiepijplijn sh -c 'cp /app/data/innovatiepijplijn.db /tmp/backup_$(date +%Y%m%d).db'

# 2. Code ophalen
git pull origin master

# 3. Rebuild en restart
docker compose up -d --build

# 4. Controleer
curl http://localhost:8000/health
```

### Versieschema

| Versie | Wijzigingen | Migratie nodig? |
|--------|-------------|-----------------|
| v0.2.0 | Beleidsmatrix, governance, gerelateerde initiatieven | Nee (auto bij rebuild) |
| v0.1.0 | Initiële release | — |

---

## Backups & Restore

### Automatische backups

De applicatie maakt automatisch backups in `/app/data/backups/` (Docker volume).

### Handmatige backup via API

```bash
# Login en haal CSRF token
curl -c cookies.txt -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"wachtwoord"}'

# Trigger backup
curl -b cookies.txt -X POST http://localhost:8000/api/admin/backup \
  -H "X-CSRF-Token: $(curl -s -b cookies.txt http://localhost:8000/api/auth/csrf-token | python3 -c 'import sys,json; print(json.load(sys.stdin)["csrf_token"])')"
```

### Backup downloaden via admin UI

1. Ga naar `/admin` → "Backup & Restore" tab
2. Klik op de download-knop naast een backup
3. Het `.db` bestand wordt gedownload

### Backup van databasebestand (direct)

```bash
# Vanuit container naar host kopieren
docker compose cp innovatiepijplijn:/app/data/innovatiepijplijn.db ./backup.db

# Alle backups downloaden
docker compose cp innovatiepijplijn:/app/data/backups/ ./backups/
```

### Restore

Via de admin UI:
1. Ga naar `/admin` → "Backup & Restore" tab
2. Klik op "Importeer backup"
3. Selecteer een `.db` bestand
4. Bevestig — er wordt eerst een pre-restore backup gemaakt

### Wat zit er in de backup?

| Onderdeel | In backup? | Opmerking |
|-----------|------------|-----------|
| Initiatieven (met alle velden) | ✅ | Inclusief v0.2: cluster, potentie, risico, etc. |
| Hypothesen | ✅ | Met status en leeruitkomsten |
| Centrale vragen | ✅ | Met tags en koppelingen |
| Curaties | ✅ | Met initiatieven-lijsten |
| Tags | ✅ | Alle actieve tags |
| Dossier bestanden | ✅ | Aparte `.zip` backup |
| MDS teams | ✅ | Multidisciplinaire samenwerking |
| **Gebruikersaccounts** | ❌ | Worden niet meegenomen (veiligheid) |
| AI-configuratie | ⚠️ | Alleen als `admin_config.json` in data-dir staat |

> **Gebruikersaccounts:** Accounts worden bewust niet opgenomen in backups omdat ze gevoelige gegevens bevatten (bcrypt hashes). Bij een restore op een nieuw systeem moet je admin account handmatig aanmaken of de `.env` variabelen `APP_ADMIN_USERNAME` en `APP_ADMIN_PASSWORD` instellen — het account wordt automatisch aangemaakt bij startup.

---

## Monitoring & Onderhoud

### Health checks

```bash
# Snelle check
curl http://localhost:8000/health

# Gedetailleerd
curl http://localhost:8000/api/admin/status
```

### Logs bekijken

```bash
# Live logs
docker compose logs -f innovatiepijplijn

# Laatste 100 regels
docker compose logs --tail=100 innovatiepijplijn

# Alleen errors
docker compose logs innovatiepijplijn 2>&1 | grep -i error
```

### Database grootte

```bash
docker compose exec innovatiepijplijn sh -c 'ls -lh /app/data/innovatiepijplijn.db'
```

### Volume opschonen

```bash
# Waarschuwing: verwijdert ALLE data!
docker compose down -v

# Specifiek volume verwijderen
docker volume rm innovatiepijplijn-innovatiepijplijn-data
```

---

## Troubleshooting

### Container start niet

```bash
# Check logs voor foutmeldingen
docker compose logs innovatiepijplijn

# Vaakste oorzaak: .env ontbreekt of APP_SECRET_KEY is te kort
ls -la .env
grep APP_SECRET_KEY .env
```

### "Database is locked" error

SQLite kan conflicten krijgen bij gelijktijdige schrijfacties:

```bash
# Herstart de container
docker compose restart innovatiepijplijn

# Controleer of er geen andere processen op de DB draaien
docker compose exec innovatiepijplijn lsof /app/data/innovatiepijplijn.db 2>/dev/null || echo "Geen conflicten"
```

### Port al in gebruik

```bash
# Check welke processen op poort 8000 luisteren
lsof -i :8000

# Pas APP_PORT aan in .env
APP_PORT=9000
docker compose up -d
```

### AI-functionaliteit werkt niet

1. Controleer of `AI_ENABLED=true` in `.env` of admin config
2. Test model endpoint direct:
   ```bash
   curl $MODEL_URL/v1/chat/completions \
     -H "Content-Type: application/json" \
     -d '{"model":"'$MODEL_NAME'","messages":[{"role":"user","content":"hi"}]}'
   ```
3. Check logs voor time-out of connectie errors

### Data herstellen na corruptie

```bash
# 1. Stop de applicatie
docker compose stop

# 2. Vervang database met backup
docker compose cp ./backup.db innovatiepijplijn:/app/data/innovatiepijplijn.db

# 3. Start opnieuw
docker compose start
```

### Upgrade problemen

Bij upgrade van v0.1 naar v0.2:
- De database migratie (nieuwe kolommen) wordt automatisch uitgevoerd bij container rebuild
- Handmatige migratie indien nodig:
  ```bash
  docker compose exec innovatiepijplijn python3 /app/scripts/migrate_v02.py
  ```

---

## Veiligheid

### Aanbevelingen voor productie

1. **Sterke `APP_SECRET_KEY`** — minimaal 32 karakters, willekeurig gegenereerd
   ```bash
   python3 -c "import secrets; print(secrets.token_urlsafe(32))"
   ```

2. **Admin wachtwoord wijzigen** — verander het default wachtwoord direct na installatie

3. **Firewall** — beperk toegang tot poort 8000 tot vertrouwde netwerken

4. **HTTPS** — gebruik een reverse proxy (nginx, traefik) voor TLS encryptie

5. **Regelmatige backups** — plan automatische backups via cron of de backup API

6. **Log monitoring** — configureer log rotatie en alerting op errors

### Reverse proxy configuratie (nginx voorbeeld)

```nginx
server {
    listen 443 ssl;
    server_name innovatiepijplijn.example.com;

    ssl_certificate     /etc/ssl/certs/cert.pem;
    ssl_certificate_key /etc/ssl/private/key.pem;

    location / {
        proxy_pass http://localhost:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

Vergeet niet `APP_BASE_URL=https://innovatiepijplijn.example.com` te zetten in `.env`.
