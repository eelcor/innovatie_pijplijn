# Implementatieplan - Innovatiepijplijn

**Status:** Actief
**Versie:** 0.7
**Laatste update:** 2026-05-27

---

## Overzicht

| Stap | Onderdeel | Status | Testdekking |
|------|-----------|--------|-------------|
| 1 | Projectopzet, database, modellen | ✅ Gereed | 10/10 tests |
| 2 | Dashboard (F8) | ✅ Gereed | 16/16 tests |
| 3 | Initiatieven CRUD (F1-F2) | ✅ Gereed | 27/27 tests |
| 4 | Hypothesen & sub-hypothesen (F3) | ✅ Gereed | 23/23 tests |
| 5 | Dossier: notities + uploads (F4) | ✅ Gereed | 15/15 tests |
| 6 | Stoppen met leeruitkomst (F5) | ✅ Gereed | 28/28 tests |
| 7 | Curaties (F6) | ✅ Gereed | 18/18 tests |
| 8 | Zoeken & filteren (F7) | ✅ Gereed | 14/14 tests |
| 9 | Centrale vragen (F9) | ✅ Gereed | 19/19 tests |
| 10 | AI-curatie-assistent (F10) | ✅ Gereed | 18/18 tests |
| H2-4 | Filterpaneel dropdown (F7a) | ✅ Gereed | — (UI, bestaande tests dekken endpoint) |
| **Totaal** | | | **203 tests** ✅ |

---

## Stap 1 - Projectopzet ✅

**Gereed:**
- FastAPI applicatie met lifespan initialisatie
- SQLite database met WAL mode
- SQLAlchemy datamodel: Initiative, Hypothesis (self-referencing), DossierNote, DossierFile, Curation, CurationItem
- Pydantic schemas voor validatie
- FTS5 full-text search (`app/search.py`)
- Jinja2 templates + HTMX + Tailwind CDN
- `render_template()` helper met Starlette 1.0 compatibiliteit
- Jinja2 globale functies: `phaseLabel`, `horizonLabel`, `formatDate`, etc.

**Lessen geleerd:**
- Starlette 1.0 heeft andere API voor `TemplateResponse(request, name, context)`
- SQLAlchemy modellen moeten geïmporteerd worden vóór `create_all()`
- FTS5 tabel moet per connectie aangemaakt worden (SQLite event listener)

---

## Stap 2 - Dashboard (F8) ✅

**Doel:** Werkend dashboard met statistieken en interactieve filters.

**Gereed:**
- [x] Dashboard route (`/`) met statistiek-data (fase, horizon, status tellingen)
- [x] Template: stats cards, fase-verdeling, filter chips, initiatieven tabel
- [x] Tests voor dashboard data-aggregatie (16 tests)
- [x] Client-side zoeken en filteren (JS in template)
- [x] "Recent gestopt met leeruitkomst" sectie prominent
- [x] Lege staat wanneer er geen initiatieven zijn

**Belangrijke fix:** Alle routes omgebouwd van `next(get_db())` naar `Depends(get_db)` zodat FastAPI dependency overrides werken in tests. Hierdoor kunnen tests geïsoleerde databases gebruiken.

---

## Stap 3-8 - CRUD, Stoppen & Zoeken ✅

**Gereed:**
- [x] Hypothesen CRUD met boomstructuur (F3) - 23 tests
- [x] Dossier notities + bestanden (F4) - 15 tests
- [x] Stoppen met leeruitkomst (F5) - 28 tests
- [x] Curaties CRUD + items management (F6) - 18 tests
- [x] Zoeken & filteren op fase, status, horizon, MDS (F7) - 14 tests
- [x] Pydantic `Literal` enums voor alle validatie
- [x] FTS5 indexering voor hypothesen, notities, curaties

**Testoverzicht per stap:**
| Stap | Tests | Dekking |
|------|-------|---------|
| 4 - Hypothesen (F3) | 23 | CRUD, sub-hypothesen, boomstructuur, leeruitkomst validatie, alle statussen |
| 5 - Dossier (F4) | 15 | Notities CRUD, bestanden upload/delete, lijst endpoints |
| 6 - Stoppen (F5) | 28 | Stoppen met/zonder leeruitkomst, witruimte-validatie, zichtbaarheid, neutrale UI-taal, hypothesen behouden, per fase |
| 7 - Curaties (F6) | 18 | Curatie CRUD, items toevoegen/verwijderen/herordenen, meerdere curaties per initiatief |
| 8 - Zoeken (F7) | 14 | FTS search, filter op fase/status/horizon/MDS, gecombineerde filters, zoeken in hypothesen en leeruitkomsten |

---

## Stap 4 - Hypothesen & sub-hypothesen (F3) ✅

**Doel:** CRUD voor hypothesen met boomstructuur en leeruitkomst-validatie.

**Gereed:**
- [x] Hypothese CRUD: aanmaken, bewerken, verwijderen
- [x] Sub-hypothese toevoegen onder hoofdhypothese (max 1 niveau)
- [x] Leeruitkomst verplicht bij bevestigd/weerlegd (400 bij ontbreken)
- [x] Leeruitkomst optioneel bij vervallen
- [x] UI: hypothesen tree op detailpagina met sub-hypothesen ingeklapt
- [x] FTS5 indexering voor hypothesen en leeruitkomsten
- [x] 23 tests: CRUD, boomstructuur, validatie, alle statussen

---

## Stap 5 - Dossier (F4) ✅

**Doel:** Notities en bestanden koppelen aan een initiatief.

**Gereed:**
- [x] Notities CRUD: aanmaken, bewerken, verwijderen
- [x] Bestanden uploaden met grootte-validatie (max 25MB)
- [x] Bestanden opslaan in `data/uploads/` met unieke bestandsnamen
- [x] Dossier tab op initiatief detailpagina
- [x] FTS5 indexering voor notities
- [x] 15 tests: notities CRUD, upload/delete, lijst endpoints

---

## Stap 6 - Stoppen met leeruitkomst (F5) ✅

**Doel:** Initiatief stoppen mét verplichte leeruitkomst, neutrale UI-taal.

**Gereed:**
- [x] Backend `/stop` endpoint met validatie: stop_reason verplicht
- [x] Pydantic `field_validator`: witruimte-only strings worden afgewezen
- [x] Modale dialoog in base.html met helptekst (PRD-conform)
- [x] Gestopt initiatief blijft zichtbaar in lijst, dashboard, zoekresultaten
- [x] Neutrale UI-taal: "Gestopt (met leeruitkomst)", "Leeruitkomst" label
- [x] Geen "Stoppen" knop op detailpagina van gestopt initiatief
- [x] "Bewerken" knop blijft wel beschikbaar op gestopt initiatief
- [x] Hypothesen blijven behouden na stoppen van initiatief
- [x] Stoppen mogelijk in elke fase (verkenning, experiment, pilot, opschaling)
- [x] Originele fase blijft behouden na stoppen
- [x] 28 tests: validatie, zichtbaarheid, neutrale taal, edge cases

---

## Stap 7 - Curaties (F6) ✅

**Doel:** Verzamelingen van initiatieven samenstellen met toelichting.

**Gereed:**
- [x] Curatie CRUD: aanmaken, bewerken, verwijderen
- [x] Items toevoegen/verwijderen/herordenen binnen curatie
- [x] Per item toelichting tekstveld
- [x] Initiatief kan in meerdere curaties zitten
- [x] Curatie detailpagina met initiatievenlijst en toelichtingen
- [x] 18 tests: CRUD, items management, meerdere curaties per initiatief

---

## Stap 8 - Zoeken & filteren (F7) ✅

**Doel:** Full-text zoeken en filteren over initiatieven, hypothesen en leeruitkomsten.

**Gereed:**
- [x] FTS5 full-text search voor titels, omschrijvingen, hypothesen, notities, leeruitkomsten
- [x] Filteren op fase, status, horizon, MDS
- [x] Gecombineerde filters (fase + status, fase + horizon)
- [x] Client-side zoeken in dashboard en initiatievenlijst
- [x] 14 tests: FTS search, filter per attribuut, gecombineerde filters, zoek in hypothesen/leeruitkomsten

---

## Stap 9 - Centrale vragen (F9) ✅

**Doel:** Centraal beheerde vraagstellingen die gekoppeld worden aan initiatieven.

**Datamodel:**
- Tabel `central_questions`: id, question (text), description (markdown), is_active (bool), created_at, updated_at
- Tabel `central_question_files`: id, central_question_id, filename, mime_type, file_size, storage_path, uploaded_at
- Nieuwe join-tabel `initiative_questions`: initiative_id + central_question_id (many-to-many)
- Bestaand veld `Initiative.central_question` blijft als nullable fallback voor migratie

**Gereed:**
- [x] SQLAlchemy modellen: `CentralQuestion`, `CentralQuestionFile`, `InitiativeQuestion` join tabel
- [x] Pydantic schemas: `CentralQuestionCreate`, `CentralQuestionUpdate`
- [x] Routes: CRUD voor centrale vragen (`/api/vragen/...`)
- [x] Routes: bestanden upload/download/delete bij centrale vragen
- [x] Routes: koppeling initiatief ↔ vraag (toevoegen/verwijderen/set)
- [x] Template: overzichtspagina `/api/vragen/lijst` met teller + toelichting preview
- [x] Template: detailpagina per vraag met tabs: initiatieven + bestanden
- [x] Sidebar navigatie: link "Centrale vragen" onder "Overzicht"
- [x] Initiatief detail: centrale vragen tonen + toevoegen/verwijderen modal
- [x] Dashboard: stat "initiatieven zonder centrale vraag"
- [x] FTS5 indexering voor centrale vragen (vraagtekst + toelichting)
- [x] Migratie: 10 brede centrale vragen + koppeling aan initiatieven
- [x] Tests: CRUD, many-to-many koppeling, soft delete, zichtbaarheid inactieve vragen (19 tests)

**Acceptatiecriteria:**
- ✅ Een initiatief kan 0, 1 of meerdere centrale vragen hebben
- ✅ Bestaande vragen zijn te selecteren bij aanmaken/bewerken
- ✅ Nieuwe vraag kan inline worden toegevoegd
- ✅ Inactieve vragen niet zichtbaar in selectie/overzicht
- ✅ Overzicht toont hoeveel initiatieven per vraag
- ✅ Initiatieven zonder centrale vraag zijn prominent zichtbaar
- ✅ Centrale vraag heeft optionele toelichting (markdown)
- ✅ Bestanden kunnen worden geüpload bij een centrale vraag

---

## Horizon 2 - Te implementeren

### H2-1: Tags op initiatieven en centrale vragen ✅
**Doel:** Thema-tags die zowel op initiatieven als op centrale vragen toegepast kunnen worden, voor betere grouping en filtering.

**Datamodel:**
- Tabel `tags`: id (uuid), name (text, uniek), is_active (bool, default=True), created_at
- Join-tabel `initiative_tags`: initiative_id + tag_id
- Join-tabel `question_tags`: central_question_id + tag_id

**Gereed:**
- [x] SQLAlchemy modellen: `Tag` (met `is_active`), `InitiativeTag`, `QuestionTag`
- [x] Tag CRUD API: `POST /api/tags/create`, `PUT /api/tags/{id}`, `DELETE /api/tags/{id}` (soft delete), `GET /api/tags/json`
- [x] Initiatief routes: `tag_ids` in create/update schemas
- [x] JSON endpoint: `tag_ids` veld in response + single initiative JSON (`GET /api/initiatieven/{id}`)
- [x] Tags op centrale vragen: `tag_ids` in CentralQuestionCreate/Update schemas; koppeling via `question_tags`
- [x] Tag-selectie UI: multi-select bij initiatief aanmaken/bewerken (base.html + initiative_detail.html)
- [x] Tag-selectie UI: multi-select bij vraag aanmaken/bewerken (central_questions_list.html + central_question_detail.html)
- [x] Tag-toevoegen modal op initiatief detailpagina (inline nieuwe tag mogelijk)
- [x] Tags tonen op initiatief detailpagina met link naar tag-detail
- [x] Tags tonen op centrale vraag detailpagina met link naar tag-detail
- [x] Tags tonen op centrale vragen overzichtspagina
- [x] Tag-overzichtspagina (`/api/tags/lijst`) met tellers per type koppeling
- [x] Tag-detailpagina (`/api/tags/{id}`) met gekoppelde initiatieven én vragen + hernoemen/inactief-zetten
- [x] Navigatielink "Tags" in sidebar
- [x] Filteren op tags: tag-filter row in initiatievenlijst (client-side)
- [x] Tag ID filter in server-side filter endpoint (`/api/initiatieven/filter?tag_id=...`)
- [x] Tag in FTS5: tag-namen opnemen in full-text search index
- [x] 10 voorbeeld tags aangemaakt (digitaal, participatie, duurzaamheid, AI, zelfbouw, procesinnovatie, dienstverlening, veiligheid, mobiliteit, cultuur)
- [x] Migratie: `is_active` kolom toegevoegd aan bestaande tags tabel
- [x] Tests: 17 tests (tag CRUD, koppeling initiatieven/vragen, filtering, detail pagina)

**Acceptatiecriteria:**
- ✅ Een initiatief kan 0 of meer tags hebben; een centrale vraag ook
- ✅ Tags zijn beherbaar via eigen CRUD API
- ✅ Tag-selectie bij aanmaken/bewerken van initiatieven en vragen
- ✅ Nieuwe tag kan inline worden toegevoegd (als die nog niet bestaat)
- ✅ Overzichtspagina toont alle tags met tellers per type koppeling
- ✅ Filteren op tags werkt in dashboard en zoekresultaten
- ✅ Tag-naam is uniek; dubbele aanmaak wordt afgewezen

### H2-2: MDS als entiteit ✅
**Doel:** MDS (Multidisciplinaire Samenwerking) als aparte tabel i.p.v. vrij tekstveld, per MDS een dashboard.

**Datamodel:**
- Tabel `mds`: id, name (text), description (markdown), is_active, created_at, updated_at
- Veld `Initiative.mds_id` → FK naar `mds.id`
- Migratie: unieke MDS-waarden → aparte records

**Gereed:**
- [x] SQLAlchemy model: `MDS` + FK in `Initiative`
- [x] Routes: CRUD MDS (`/api/mds/...`)
- [x] UI: MDS-overzichtspagina, MDS-detailpagina per team
- [x] Initiatief routes: `mds_id` in create/update schemas
- [x] Sidebar navigatie: "MDS teams" link
- [x] Migratie: 7 echte teams (Publiekszaken/Veiligheid, Stedelijk Beheer, etc.)
- [x] 33 initiatieven gekoppeld aan MDS teams
- [x] Tests

### H2-4: Filterpaneel als dropdown (F7a)
**Doel:** Vervang de huidige filterchips door een strak opklapbaar filterpaneel onder "Filter resultaten", zoals beschreven in PRD sectie F7a.

**Motivatie:** De huidige filterchips nemen 4 rijen verticale ruimte in beslag, ook wanneer er geen filters actief zijn. Een dropdown-paneel houdt het scherm strak en geeft de filters meer structuur.

**UI-ontwerp (zie PRD F7a voor ASCII-art en gedetailleerde specificatie):**
- Één knop "Filter resultaten" met optionele badge (`(3)` = aantal actieve filters)
- Opklapbaar paneel met 5 filtergroepen: Fase, Status, Horizon, MDS team, Tags
- Radio-knoppen voor enkel-selectie groepen (fase, status, horizon)
- `<select>` dropdown voor MDS team
- Checkboxes voor tags (meervoudig), max 6 zichtbaar + "meer..." opvouwbaar
- "Alles wissen" knop verschijnt bij ≥1 actief filter
- Paneel sluit bij klik buiten of Escape

**Gewijzigde bestanden:**

| Bestand | Wijziging |
|---------|----------|
| `app/templates/base.html` | ✅ CSS toegevoegd voor `.filter-toggle`, `.filter-panel`, `.filter-group`, badge styling |
| `app/templates/partials/filter_panel.html` | ✅ **Nieuw** — herbruikbaar filterpaneel partial template met JS |
| `app/templates/initiatives_list.html` | ✅ Vervang 4x `.filters-row` chips door `include "partials/filter_panel.html"` |
| `app/routes/dashboard.py` | ✅ `/api/initiatieven/filter` uitgebreid: `mds_id` + meervoudige `tag_ids=uuid1,uuid2` |

**Acceptatiecriteria:**
- [x] Filterknop "Filters" altijd zichtbaar boven initiatievenlijst
- [x] Klikken opent/klapt het paneel naar beneden (geen page reload)
- [x] Alle 5 filtergroepen aanwezig: Fase, Status, Horizon, MDS team, Tags
- [x] Badge toont correct aantal actieve filters
- [x] "Alles wissen" reset alle filters en laadt volledige lijst
- [x] Tags ondersteunen meerdere selecties (checkboxes)
- [x] MDS team filter werkt met dropdown van alle actieve teams (23 teams)
- [x] Paneel sluit bij klik buiten
- [x] Initiatievenlijst gebruikt nieuw paneel ✅
- [x] Server-side filter endpoint (`/api/initiatieven/filter`) uitgebreid en werkend
- [ ] Dashboard: filterpaneel toevoegen (nog te doen — dashboard heeft nu geen filters)
- [ ] Tests: nieuwe tests voor `mds_id` en meervoudige `tag_ids` parameters

### H2-3 / F10: AI-curatie-assistent ✅
**Doel:** AI helpt bij het samenstellen van curaties, het formuleren van hypothesen en het genereren van narratieven.

**Model-agnostisch ontwerp:**
- Configuratie via environment variabelen: `MODEL_URL`, `MODEL_NAME`, `MODEL_API_KEY` (optioneel), `AI_ENABLED`
- Werkt met elk model dat een OpenAI-compatible chat completions endpoint ondersteunt (Ollama, vLLM, LM Studio, etc.)
- Prompt templates centraal beheerd in `app/routes/ai.py`
- Graceful degradation: bij uitgeschakeld AI of onbereikbaar model toont UI duidelijke foutmelding

**Gereed:**
- [x] `app/ai_client.py` - model-agnostische async client met httpx, configurable via env vars
- [x] Hypothese-suggesties (`POST /api/ai/initiatieven/{id}/suggest-hypotheses`)
- [x] Hypothese accepteren (`POST /api/ai/initiatieven/{id}/accept-hypothesis`)
- [x] Narratief-generatie (`POST /api/ai/curaties/{id}/narratief`)
- [x] One-pager generatie (`POST /api/ai/initiatieven/{id}/one-pager`)
- [x] UI: "AI-assistent" tab op initiatief detailpagina
- [x] UI: "Narratief genereren" knop op curatie detailpagina
- [x] Data-helpers: `_get_initiative_with_details()`, `_get_curation_with_details()`
- [x] `.env.example` met AI configuratie voorbeelden
- [x] 18 tests: configuratie, prompts, API endpoints, error handling

---

## Open beslissingen

1. **Naamgeving:** "Innovatiepijplijn-tool" is werktitel
2. **Bestandstype-restricties:** Nu alle types toegestaan, alleen grootte-cap
3. **Sub-hypothesen diepte:** Max één laag (geen sub-sub)
4. **Filterdiepte zoeken:** Basis filters voor nu; hypothese-type filter later
