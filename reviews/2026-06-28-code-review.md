# Code review Innovatiepijplijn

Datum: 2026-06-28  
Scope: veiligheid, robuustheid, modulariteit en gebruikersvriendelijkheid van de huidige FastAPI/SQLite codebase.  
Status: handmatige code review aangevuld met applicatietests; applicatiecode is niet aangepast.

## Managementsamenvatting

De codebase is bruikbaar als lokale MVP/sandbox en heeft een heldere domeinindeling: routes per functioneel gebied, SQLAlchemy-modellen, Pydantic-schema's, server-side templates, tests voor veel basisflows en Docker-support. Voor productie of breder intern gebruik is de applicatie nog niet voldoende gehard.

Belangrijkste advies: behandel de huidige versie als een afgeschermde MVP. Zet eerst een veiligheidsbasis neer met authenticatie, CSRF-bescherming, veilige markdown-rendering, strakkere uploadvalidatie en afgeschermde adminroutes. Daarna loont het om gedeelde infrastructuur voor file handling, database-sessies en AI-aanroepen te centraliseren.

## Risicobeeld

| Thema | Beoordeling | Samenvatting |
| --- | --- | --- |
| Veiligheid | Hoog risico bij netwerktoegang | Geen auth/CSRF, onveilige markdown-rendering, brede admin- en muterende endpoints. |
| Robuustheid | Middel risico | Redelijke validatie en tests, maar sessiebeheer, uploads, AI timeouts en transacties zijn kwetsbaar. |
| Modulariteit | Redelijk, met groeipijn | Routes zijn functioneel gescheiden, maar veel duplicatie en businesslogica zit in routehandlers/templates. |
| Gebruikersvriendelijkheid | Voldoende voor MVP | Duidelijke basisflows, maar foutafhandeling, confirmaties, statusfeedback en toegankelijkheid kunnen sterker. |

## Uitgevoerde applicatietests

Ik heb de bestaande testset uitgevoerd op 2026-06-28.

Gebruikte commando's:

```bash
uv sync --extra dev
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 uv run python -m pytest -p pytest_asyncio.plugin
```

Waarom deze vorm: een normale `uv run pytest` faalde voor testcollectie door een globale pytest-plugin/importconflict buiten het project (`logfire`/`opentelemetry`). Met plugin-autoload uit en `pytest_asyncio.plugin` expliciet aan draait de projecttestset geisoleerd.

Resultaat:

- 272 tests verzameld.
- 268 tests geslaagd.
- 4 tests gefaald.
- Alle failures zitten in `tests/test_admin.py::TestAdminStatus`.

Gefaalde tests:

- `test_status_returns_200`
- `test_status_has_version`
- `test_status_has_counts`
- `test_status_counts_are_correct`

Root cause uit de stacktrace: `/api/admin/status` gebruikt `SessionLocal()` rechtstreeks in `app/admin.py:76`, in plaats van de FastAPI dependency `Depends(get_db)`. Daardoor omzeilt deze route de testdatabase override uit `tests/conftest.py:77` en raakt hij de lokale SQLite-database. Die lokale database heeft een ouder schema zonder kolom `initiatives.trekker`, waardoor SQLAlchemy faalt met `sqlite3.OperationalError: no such column: initiatives.trekker`.

Interpretatie:

- De meeste functionele MVP-flows zijn door tests afgedekt en groen.
- De testfailure bevestigt de reviewbevinding dat database-sessiebeheer inconsistent is.
- Er is ook een migratie-/schema-risico: `Base.metadata.create_all()` voegt ontbrekende kolommen niet toe aan bestaande SQLite databases.
- De testset bevat weinig tot geen regressietests voor security-hardening: auth, CSRF, XSS/markdown sanitizing, upload path traversal, MIME-validatie en admin-afscherming.

## Bevindingen

### 1. Kritiek: geen authenticatie of autorisatie

De applicatie registreert alle routers direct zonder auth dependency in `app/main.py` en bevat muterende endpoints voor aanmaken, wijzigen, verwijderen, uploads, AI-acties en backups. De PRD noemt dit expliciet als MVP-keuze, maar zodra de app op een gedeelde host draait kan iedereen met netwerktoegang data lezen, wijzigen, verwijderen en backups starten.

Voorbeelden:

- `app/main.py:71` t/m `app/main.py:80`: alle routers worden publiek geregistreerd.
- `app/routes/initiatives.py:136`, `app/routes/initiatives.py:197`, `app/routes/initiatives.py:309`: create/update/delete zonder autorisatie.
- `app/admin.py:70`, `app/admin.py:106`, `app/admin.py:136`, `app/admin.py:216`: adminstatus, configuratie, backup en backup-delete zonder autorisatie.

Aanbeveling:

- Voeg een centrale auth dependency toe en hang die minimaal aan alle `/api/*` mutaties en `/api/admin/*`.
- Kies voor MVP-productie een eenvoudige reverse-proxy/M365-auth of API-key/session-auth met allowlist.
- Scheid publieke healthcheck (`/health`) van gevoelige admininformatie.

### 2. Kritiek: geen CSRF-bescherming op muterende endpoints

De frontend doet veel `fetch` calls naar POST/PUT/DELETE endpoints. Zonder CSRF-token of SameSite-strategie kan een browsergebruiker, zodra auth later wordt toegevoegd via cookies, onbedoeld mutaties uitvoeren via een externe pagina.

Voorbeelden:

- `app/templates/base.html:1260`: generieke `fetch` helper voegt JSON headers toe, maar geen CSRF-token.
- `app/routes/hypotheses.py:14`, `app/routes/dossier.py:26`, `app/routes/dossier.py:75`, `app/routes/dossier.py:115`: muterende endpoints zonder CSRF-controle.
- `app/admin.py:136` en `app/admin.py:216`: backup create/delete zonder CSRF-controle.

Aanbeveling:

- Voeg CSRF-middleware of een dependency toe voor alle browser-callable mutaties.
- Gebruik `SameSite=Lax/Strict`, `Secure`, `HttpOnly` cookies zodra sessie-auth wordt toegevoegd.
- Voeg tests toe die mutaties zonder token weigeren.

### 3. Kritiek: XSS-risico door eigen markdown-rendering zonder escaping

De server-side markdown renderer zegt expliciet dat HTML niet wordt geescaped en wordt vervolgens met `| safe` in templates gebruikt. Daarmee kan user-generated content of AI-output script/HTML injecteren in detailpagina's. De client-side markdown renderer heeft hetzelfde patroon: hij bouwt HTML via regex en plaatst output met `innerHTML`.

Voorbeelden:

- `app/helpers.py:111` t/m `app/helpers.py:170`: markdown naar HTML via regex, zonder HTML escaping.
- `app/helpers.py:115`: commentaar bevestigt dat input veilig wordt verondersteld.
- `app/templates/initiative_detail.html:50`, `app/templates/initiative_detail.html:204`, `app/templates/mds_detail.html:18`, `app/templates/curation_detail.html:42`: `renderMarkdown(...) | safe`.
- `app/templates/base.html:1269` t/m `app/templates/base.html:1297`: client-side markdown naar HTML zonder escaping.
- `app/templates/initiative_detail.html:1627` t/m `app/templates/initiative_detail.html:1632`: AI one-pager wordt als HTML gerenderd.

Aanbeveling:

- Vervang de eigen renderer door een bewezen markdown-library met sanitizing, bijvoorbeeld Markdown + Bleach, of render alleen plain text.
- Sta alleen een kleine allowlist toe (`p`, `strong`, `em`, `ul`, `li`, `code`, veilige `a[href]`).
- Voeg XSS-regressietests toe met payloads zoals `<script>`, `javascript:` links en event handlers.

### 4. Hoog: uploadvalidatie en path-hardening zijn inconsistent

Initiatiefuploads krijgen een UUID-bestandsnaam, maar centrale-vraag-uploads nemen de originele bestandsnaam op in het opslagpad. Daarnaast wordt bestandstype vooral op extensie of client-provided content type gebaseerd, de hele upload wordt in geheugen gelezen, en er is geen allowlist op type/extensie.

Voorbeelden:

- `app/routes/dossier.py:118`: volledige upload wordt in geheugen gelezen.
- `app/routes/dossier.py:126` t/m `app/routes/dossier.py:137`: extensie en MIME worden uit originele bestandsnaam afgeleid.
- `app/routes/central_questions.py:495`: volledige upload wordt in geheugen gelezen.
- `app/routes/central_questions.py:505` t/m `app/routes/central_questions.py:507`: originele `file.filename` wordt onderdeel van `safe_filename` en `full_path`.
- `app/routes/dossier.py:206` t/m `app/routes/dossier.py:230`: inline serving van image/pdf op basis van opgeslagen MIME.

Aanbeveling:

- Centraliseer uploadverwerking in een service/helper.
- Gebruik uitsluitend server-generated storage names en bewaar originele namen alleen als metadata.
- Valideer extensie, MIME en waar mogelijk magic bytes.
- Stream uploads naar disk met limieten in plaats van volledige `read()` in geheugen.
- Normaliseer downloadheaders veilig; vertrouw niet op client-provided bestandsnamen of content types.

### 5. Hoog: adminroutes lekken operationele informatie en voeren beheeracties uit

Admin endpoints tonen databasepaden, model-URL's, counts en configuratie. De backup endpoint kan op afstand disk I/O en opslaggroei veroorzaken. Backup delete gebruikt een string-prefix check die kwetsbaar is voor padnormalisatieproblemen.

Voorbeelden:

- `app/admin.py:95` t/m `app/admin.py:103`: databasepad, omgeving, counts en AI-model publiek zichtbaar.
- `app/admin.py:112` t/m `app/admin.py:132`: host, poort, databasepad, model URL en API-key-aanwezigheid publiek zichtbaar.
- `app/admin.py:136` t/m `app/admin.py:193`: backup trigger publiek beschikbaar.
- `app/admin.py:222` t/m `app/admin.py:231`: `backup_dir / backup_name` plus string-prefix check in plaats van `resolve()` en parent-check.

Aanbeveling:

- Zet `/api/admin/*` achter beheer-auth en eventueel IP allowlisting.
- Geef in productie alleen minimale healthinformatie vrij.
- Gebruik `Path.resolve()` en controleer dat het doelbestand echt onder `backup_dir.resolve()` ligt.
- Rate-limit of verplaats backupacties naar CLI/cron.

### 6. Middel: database-sessies worden handmatig gesloten in routehandlers

FastAPI dependencies sluiten de sessie al in `get_db()`. Veel handlers sluiten `db` daarnaast zelf in `finally`. In sommige AI-routes wordt de sessie gesloten en daarna nog gebruikt. Dat maakt gedrag afhankelijk van SQLAlchemy-hergebruik van een gesloten session en maakt tests/bugs lastiger te interpreteren.

Voorbeelden:

- `app/database.py:26` t/m `app/database.py:32`: dependency beheert sessie lifecycle.
- `app/routes/dossier.py:48`, `app/routes/initiatives.py:193`, `app/routes/dashboard.py:206`: routehandlers sluiten de injected sessie zelf.
- `app/routes/ai.py:420` t/m `app/routes/435`: sessie wordt in `finally` gesloten en daarna gebruikt.
- `app/routes/ai.py:532` t/m `app/routes/617`: sessie wordt gesloten voordat de gegenereerde one-pager wordt opgeslagen.
- `app/admin.py:76` t/m `app/admin.py:93`: adminstatus gebruikt `SessionLocal()` rechtstreeks en omzeilt daarmee dependency overrides; dit veroorzaakt 4 falende tests in `tests/test_admin.py`.

Aanbeveling:

- Laat alleen de dependency de sessie sluiten.
- Verwijder route-level `finally: db.close()` waar `Depends(get_db)` wordt gebruikt.
- Introduceer transacties per use case, bijvoorbeeld `with session.begin()`, voor acties met meerdere commits.
- Maak adminstatus consistent met de rest van de app: gebruik `db: Session = Depends(get_db)`.

### 6b. Middel: bestaande databases worden niet gemigreerd

De testfailure op `/api/admin/status` maakt een tweede robuustheidsrisico zichtbaar. De applicatie gebruikt `Base.metadata.create_all()` bij startup, maar dat migreert bestaande tabellen niet wanneer modellen nieuwe kolommen krijgen. De lokale database mistte `initiatives.trekker`, terwijl het model die kolom wel verwacht.

Voorbeelden:

- `app/database.py:35` t/m `app/database.py:39`: `init_db()` gebruikt `create_all`.
- `app/models.py:50` t/m `app/models.py:51`: `trekker` en `owner` bestaan in het model.
- `scripts/migrate_db.py` en losse migratiescripts bestaan, maar worden niet automatisch of centraal afgedwongen.

Aanbeveling:

- Voeg een formele migratiestrategie toe, bijvoorbeeld Alembic of een centrale versiegestuurde migratierunner.
- Laat startup expliciet falen met een duidelijke melding als de schema-versie niet klopt.
- Voeg een test toe die `/api/admin/status` tegen de dependency-overridden testdatabase draait.

### 7. Middel: transacties en side effects zijn niet atomair

Sommige flows doen meerdere commits en side effects zonder rollbackstrategie. Daardoor kunnen gedeeltelijke updates ontstaan, bijvoorbeeld initiatief aangemaakt maar tags/vragen/FTS/logging niet volledig bijgewerkt, of bestand op disk geschreven maar databasecommit mislukt.

Voorbeelden:

- `app/routes/initiatives.py:152` t/m `app/routes/185`: meerdere commits voor initiatief, koppelingen, FTS en changelog.
- `app/routes/dossier.py:134` t/m `app/routes/dossier.py:148`: file write gevolgd door DB commit zonder cleanup bij DB-fout.
- `app/routes/central_questions.py:509` t/m `app/routes/central_questions.py:522`: zelfde patroon voor centrale-vraag-bestanden.
- `app/search.py:65` t/m `app/search.py:137`: FTS-updates committen zelfstandig.

Aanbeveling:

- Groepeer databasewijzigingen per user action in een transactie.
- Maak file writes idempotent en ruim opgeslagen bestanden op bij DB-fouten.
- Overweeg FTS te herleiden uit brontabellen of via consistente event/update service.

### 8. Middel: inputvalidatie is ongelijk verdeeld

Pydantic-schema's beschermen enumwaarden en enkele verplichte velden, maar diverse endpoints accepteren ruwe `dict` payloads of onbeperkte strings. Relationele IDs worden vaak pas via database constraints of niet expliciet gevalideerd.

Voorbeelden:

- `app/schemas.py:27` t/m `app/schemas.py:61`: goede basisvalidatie voor initiatieven.
- `app/routes/tags.py:145` en `app/routes/mds.py:102`: ruwe `dict` in plaats van schemas.
- `app/routes/ai.py:519` en `app/routes/ai.py:670`: ruwe payloads voor one-pager genereren/bewerken.
- `app/schemas.py:27` t/m `app/schemas.py:128`: weinig maximumlengtes op user-controlled tekstvelden.

Aanbeveling:

- Maak Pydantic-schema's voor MDS, tags, AI one-pagers en adminacties.
- Voeg maximumlengtes en normalisatie toe voor titels, namen, descriptions en AI-input.
- Valideer gekoppelde IDs expliciet en geef consistente 400/404 responses.

### 9. Middel: AI-integratie mist guardrails voor kosten, latency en prompt-injectie

AI-aanroepen gebruiken database-inhoud als promptcontext en hebben standaard een timeout van 600 seconden. Resultaten worden opgeslagen en opnieuw als markdown gerenderd. Er zijn instructies tegen hallucinaties, maar geen duidelijke output-sanitizing, requestbudget, rate limiting of audittrail.

Voorbeelden:

- `app/ai_client.py:24`: AI staat standaard aan tenzij `AI_ENABLED` anders is gezet.
- `app/ai_client.py:27`: standaard timeout is 600 seconden.
- `app/routes/ai.py:282` t/m `app/routes/ai.py:318`, `app/routes/ai.py:541` t/m `app/routes/ai.py:597`: user content gaat direct promptcontext in.
- `app/routes/ai.py:609` t/m `app/routes/ai.py:620`: AI-output wordt opgeslagen.

Aanbeveling:

- Zet AI standaard uit in code en expliciet aan per omgeving.
- Voeg requestlimieten, timeouts per endpoint en duidelijke foutmeldingen toe.
- Sanitize AI-output voordat deze in HTML wordt gerenderd.
- Log minimale auditmetadata: endpoint, initiatief/curatie, duur, model, success/failure.

### 10. Laag tot middel: performance en schaalbaarheid zijn MVP-niveau

Voor een kleine dataset is dit acceptabel, maar meerdere routes laden alle records in geheugen en rekenen counts of filters in Python uit. Bij groei naar honderden/duizenden initiatieven wordt dit merkbaar.

Voorbeelden:

- `app/routes/dashboard.py:18` t/m `app/routes/dashboard.py:63`: alle initiatieven en hypothesen worden geladen voor dashboardstatistieken.
- `app/routes/central_questions.py:27` t/m `app/routes/central_questions.py:73`: N+1 counts en tagmapping in Python.
- `app/routes/ai.py:429` t/m `app/routes/457`: alle initiatieven laden en lokaal filteren voor AI-suggesties.

Aanbeveling:

- Verplaats tellingen naar SQL aggregaties.
- Voeg paginering toe aan lijsten die onbeperkt groeien.
- Gebruik selectinload/joinedload waar relaties nodig zijn.

### 11. Laag: deploymentconfiguratie is deels goed, maar health en datahygiëne kunnen beter

De Dockerfile draait non-root en gebruikt een volume voor data. Tegelijk staat de projectmap vol met lokale databasebestanden, backups, uploads en `__pycache__`-bestanden. Zonder Git-context is niet vast te stellen of deze worden meegeleverd, maar dit is een duidelijk risico voor repositoryhygiëne en gevoelige data.

Voorbeelden:

- `Dockerfile:17` t/m `Dockerfile:34`: non-root runtime is positief.
- `Dockerfile:42` en `docker-compose.yml:35`: healthchecks gebruiken verschillende URLs (`/` versus `/health`).
- Projectboom bevat `data/innovatiepijplijn.db`, `data/backups/*`, `data/uploads/*` en `__pycache__`.

Aanbeveling:

- Voeg of controleer `.gitignore`/deployment excludes voor `data/`, `*.db`, backups, uploads, `__pycache__`.
- Gebruik overal dezelfde healthcheck (`/health`) en beperk details in productie.
- Documenteer minimale veilige reverse-proxy instellingen.

## Positieve punten

- De functionele indeling in routers (`initiatives`, `hypotheses`, `dossier`, `curations`, `central_questions`, `mds`, `tags`, `ai`) is begrijpelijk.
- SQLAlchemy-relaties en cascades geven een goede basis voor het domeinmodel.
- Pydantic-schema's worden op belangrijke CRUD-flows al gebruikt.
- SQLite WAL en foreign keys worden aangezet.
- Docker runtime draait als non-root gebruiker.
- Er is redelijke testdekking voor basis-CRUD, dashboardfilters, admin-health en AI-flow mocking.

## Modulariteitsadvies

De eerstvolgende modulariteitswinst zit niet in nieuwe architectuurlagen, maar in het centraliseren van herhaalde risicovolle patronen:

1. `security.py`: auth dependency, CSRF-validatie, security headers.
2. `files.py` of `services/uploads.py`: uploadvalidatie, storage paths, downloadheaders, cleanup.
3. `services/markdown.py`: markdown-rendering en sanitizing.
4. `services/fts.py`: consistente FTS-updates zonder losse commits in routes.
5. `services/ai.py`: promptbouw, timeouts, logging, outputvalidatie.
6. Pydantic schemas voor alle ruwe `dict` endpoints.

## Gebruikersvriendelijkheid

Sterke punten:

- De app heeft duidelijke domeinschermen en modals voor veelvoorkomende acties.
- Dashboard, filters, tags, MDS en centrale vragen sluiten aan op het werkproces.
- AI-functies zijn zichtbaar geïntegreerd in initiatief- en curatieflows.

Verbeterpunten:

- Toon consistente loading/error states bij alle mutaties, uploads en AI-acties.
- Maak destructieve acties explicieter: bestandsdelete, hypothese-delete, initiatief-delete en backup-delete verdienen uniforme confirmaties.
- Geef uploadfouten specifieker terug: bestandstype, grootte, netwerkfout, serverfout.
- Voeg lege-staatteksten en herstelroutes toe waar gebruikers vast kunnen lopen.
- Verbeter toegankelijkheid: keyboard focus, aria-labels voor icon-only knoppen, formulierfoutmeldingen gekoppeld aan inputs.

## Aanbevolen roadmap

### Fase 1: Veiligheidsbasis

Prioriteit: hoog, voor elke gedeelde omgeving.

- Voeg auth toe voor alle `/api/*` en `/api/admin/*` routes.
- Voeg CSRF-bescherming toe voor browsergestuurde POST/PUT/DELETE.
- Vervang markdown-rendering door gesanitized rendering.
- Scherm adminroutes af en beperk healthcheck-output.
- Harden uploads met allowlists, UUID-only storage paths en veilige headers.

### Fase 2: Robuustheid

Prioriteit: hoog na veiligheidsbasis.

- Laat database-sessies uitsluitend door `get_db()` beheren.
- Voeg formele schema-migraties toe voor bestaande SQLite databases.
- Maak transacties atomair per user action.
- Voeg cleanup toe bij mislukte file/database-combinaties.
- Voeg Pydantic-schema's toe voor tags, MDS, admin en AI-payloads.
- Voeg regressietests toe voor XSS, uploadpath, auth/CSRF en admin-afscherming.

### Fase 3: Onderhoudbaarheid

Prioriteit: middel.

- Centraliseer uploads, markdown, FTS en AI in services.
- Verminder routehandlers tot requestvalidatie, service-aanroep en response.
- Verplaats grote inline JavaScript-blokken naar statische modules.
- Voeg consistente error response modellen toe.

### Fase 4: Schaal en UX

Prioriteit: middel tot laag, afhankelijk van gebruik.

- Optimaliseer dashboardcounts met SQL aggregaties.
- Voeg paginering toe aan grote lijsten.
- Verbeter accessibility en uniforme interactiepatronen.
- Voeg operationele documentatie toe voor backup/restore, auth en reverse proxy.

## Conclusie

De applicatie is een degelijke MVP voor lokaal of strikt afgeschermd gebruik, maar niet productieklaar zodra meerdere gebruikers of netwerktoegang in beeld komen. De grootste risico's zitten in ontbrekende toegangscontrole, onveilige markdown/HTML rendering, upload-hardening en publieke adminacties. Mijn advies is om eerst een korte hardening-sprint te doen voordat nieuwe functionaliteit wordt toegevoegd. Daarna kan de codebase met beperkte refactoring goed doorgroeien: de domeinstructuur is al herkenbaar en de bestaande tests geven een bruikbare basis.
