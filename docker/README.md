# Docker Gebruik

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

## Poorten configureren

### Via omgevingsvariabele (aanbevolen)

```bash
# Start op poort 9000 in plaats van 8000
APP_PORT=9000 docker compose up -d
```

### Via .env bestand

1. Kopieer het voorbeeld: `cp .env.example .env`
2. Pas de waarden aan:
   ```
   APP_PORT=9000
   APP_HOST=0.0.0.0
   ```
3. Start: `docker compose up -d`

### Direct in docker-compose.yml

Wijzig de `ports` sectie:
```yaml
ports:
  - "9000:8000"
```

## Data persistentie

De SQLite database en geüploade bestanden worden opgeslagen in een Docker volume:
- `innovatiepijplijn-data` → `/app/data/` binnen de container

Om data te behouden bij herbouw:
```bash
# Volume blijft bestaan na docker compose down
docker compose down  # Data blijft bewaard
docker compose up -d # Data is weer beschikbaar
```

Om alle data te verwijderen:
```bash
docker compose down -v
```

## Handige commando's

```bash
# Bouw opnieuw (na code-wijzigingen)
docker compose build --no-cache

# Stop de service
docker compose stop

# Start de service weer
docker compose start

# Complete cleanup (inclusief data!)
docker compose down -v

# Voer commando in container uit
docker compose exec innovatiepijplijn python -c "print('hello')"
```

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
```
