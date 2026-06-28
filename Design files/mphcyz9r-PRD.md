# PRD — Innovatiepijplijn-tool (werktitel)

**Versie:** 0.1 — concept voor coding agent
**Domein:** Ondersteuning van de innovatie-aanpak van de gemeente Leiden, zoals beschreven in de notitie *Effectief innoveren in de gemeente Leiden* (v0.5).
**Status:** persoonlijke sandbox; potentieel later uit te bouwen tot inter-gemeentelijke samenwerking.

---

## 1. Overzicht en doel

### Probleem
Initiatieven binnen de gemeente (rondom AI, zelfbouw, procesinnovatie, dienstverlening, etc.) ontstaan op veel plekken tegelijk. Ze hangen ergens tussen "verkenning" en "opschaling" zonder dat er een gedeelde plek is waar ze geregistreerd, doordacht en met elkaar in verband gebracht worden. Daardoor:

- weet niemand goed wat er loopt;
- worden hypothesen impliciet getoetst (of helemaal niet);
- gaan geleerde lessen verloren bij personeelswisselingen of gestopte initiatieven;
- ontstaat dubbel werk;
- is curatie — het actief *selecteren* en *arrangeren* van initiatieven voor een doel — onmogelijk omdat het overzicht ontbreekt.

### Doel
Een eenvoudig toegankelijke webapplicatie waarmee medewerkers initiatieven kunnen registreren, hypothesen kunnen vastleggen, leeruitkomsten kunnen behouden (ook bij stoppen), en waarmee curatie- en stuurinformatie kan worden gegenereerd.

### Niet-doel
Dit is **geen** Jira/Notion/Azure DevOps-vervanging. Het is geen projectmanagementtool en geen taakvolger. Het is een **registratie- en analysetool voor de fase vóór een initiatief regulier project wordt**.

### Succescriteria
- Een initiatief invoeren kost minder dan twee minuten.
- De drempel om hypothesen en sub-hypothesen te koppelen is laag genoeg om het ook bij verkenningen te doen.
- Stoppen met een leeruitkomst voelt evenwaardig aan opschalen (geen "afvoeren").
- De programmamanager kan binnen één scherm een curatie (selectie + arrangement van initiatieven) samenstellen voor bijvoorbeeld een show & tell of een directievoordracht.
- Zoeken levert binnen seconden relevante resultaten over initiatieven, hypothesen en dossier-inhoud.

---

## 2. Doelgroep en personas

### P1 — De **invoerder** (medewerker met een idee)
Iemand die een initiatief wil registreren of een bestaand initiatief wil bijwerken. Heeft weinig tijd en weinig zin in bureaucratie. Wil snel kunnen invoeren en later eenvoudig terug kunnen vinden.

**Belangrijkste handelingen:** initiatief aanmaken, status updaten, hypothesen formuleren, leeruitkomsten noteren, bestand uploaden.

### P2 — De **MDS-trekker / lokale curator**
Iemand die overzicht houdt over een set initiatieven (binnen een MDS, programma of thema). Cureert: selecteert welke initiatieven aandacht verdienen, arrangeert combinaties voor specifieke doelen.

**Belangrijkste handelingen:** filteren en doorzoeken, collecties samenstellen, voortgang per fase volgen, leeruitkomsten van gestopte initiatieven raadplegen.

### P3 — De **programmamanager / stuurder** (eerste primaire gebruiker)
De rol die jij als persoon vervult. Heeft analyse-behoefte over alle MDS heen, wil curatie kunnen doen op organisatieniveau, en wil stuurinformatie kunnen extraheren (verdeling over fasen, over horizonten, over MDS, doorlooptijden, hypothese-uitkomsten).

**Belangrijkste handelingen:** analyses, dashboards, curaties, narratieven samenstellen.

### Rolverdeling in MVP
Voor de MVP-sandbox is er **geen authenticatie en geen rolbeperking** — alle personas zijn dezelfde gebruiker (jij). Rollen worden vanaf v2 ingevoerd.

---

## 3. Kernconcepten (domeintaal)

Deze begrippen komen rechtstreeks uit de notitie en moeten in de UI, de code en de database consistent worden gebruikt — niet vervangen door generieke equivalenten zoals "project" of "task".

- **Initiatief** — het centrale data-object. Een idee, verkenning, experiment of pilot dat door de fasen heen kan bewegen.
- **Fase** — een van vier: *verkenning*, *experiment* (PoC), *pilot*, *opschaling*. Plus de eindstatus *gestopt* (in elke fase mogelijk) en *afgerond* (na opschaling).
- **Horizon** — een van drie: *H1 (vandaag)*, *H2 (morgen)*, *H3 (overmorgen)*. Optioneel per initiatief.
- **Hypothese** — een claim over een initiatief, in een van drie hoofdtypen: *value*, *growth*, *compliance*. Per initiatief kunnen meerdere hypothesen.
- **Sub-hypothese** — een verfijning van een hoofdhypothese (bijv. onder *value*: probleem-, gebruiker-, oplossing-, adoptie-hypothese).
- **Status van een hypothese** — *open* (nog niet getoetst), *bevestigd*, *weerlegd*, *vervallen*.
- **Leeruitkomst** — wat we hebben geleerd. Verplicht veld bij het stopzetten van een initiatief of bij een weerlegde hypothese.
- **Dossier** — het verzamelpunt per initiatief voor notities en bestanden.
- **Curatie** — een door een gebruiker samengestelde verzameling van initiatieven voor een specifiek doel (show & tell, directievoordracht, leerlijn, regionaal verhaal). De curatie heeft een naam, een doel, een geordende selectie van initiatieven en een korte beschrijving per item over waarom dat initiatief deel uitmaakt van deze curatie.
- **MDS** — Multidisciplinaire Samenwerking. Een groepering waar een initiatief bij hoort. Voor MVP een vrij veld; vanaf v2 een aparte entiteit.
- **Centrale vraag** — de "raketpunt" per MDS waaraan initiatieven hangen. Voor MVP een tekstveld per initiatief; vanaf v2 een aparte entiteit.

---

## 4. MVP-scope

### In scope (MVP)
1. **Initiatieven** — CRUD met titel, omschrijving, fase, status, horizon, MDS (vrij tekstveld), centrale vraag (vrij tekstveld), eigenaar (vrij tekstveld), aanmaakdatum, laatste wijziging.
2. **Hypothesen** — CRUD onder initiatieven, met type (value/growth/compliance), omschrijving, status, en bij niet-open statussen een verplicht leeruitkomst-veld.
3. **Sub-hypothesen** — CRUD onder hypothesen; zelfde structuur als hypothesen.
4. **Dossier per initiatief** — notities (markdown-tekstvelden met datum) en bestandsuploads (afbeeldingen, PDF, docx, xlsx — voor MVP geen voorbeeld-rendering vereist, alleen download).
5. **Stoppen met leeruitkomst** — een initiatief op status "gestopt" zetten kan alleen met een ingevuld leeruitkomst-veld. Dit moet visueel niet als afval voelen — gebruik bewuste, neutrale UI-taal.
6. **Curaties** — collecties van initiatieven met naam, doel, vrije beschrijving, en een geordende lijst van initiatieven (drag-and-drop herordening). Per item in de curatie een korte toelichting (één tot drie zinnen) over waarom dit initiatief erbij hoort.
7. **Zoeken** — volledige tekstzoekopdracht over titels, omschrijvingen, hypothesen, leeruitkomsten en dossiernotities. Filteren op fase, status, horizon en MDS.
8. **Eenvoudig dashboard** — één scherm met: aantal initiatieven per fase, per horizon, per status; recent gewijzigde initiatieven; recent gestopte initiatieven met hun leeruitkomst.

### Buiten scope (MVP, expliciet voor agent)
- Authenticatie / multi-user / rollen
- AI-functionaliteit (narratief-generatie, semantische zoek, samenvatting)
- Mobile-first / responsive perfectie (desktop-first; werk op mobiel mag matig zijn)
- Notificaties, e-mail, agenda-integratie
- Comments / discussie per initiatief
- Events (show & tells, hackathons) als aparte entiteiten
- Communities of practice als aparte entiteit
- Versiebeheer van velden / history-tracking (afgezien van laatst-gewijzigd)
- Export naar Word/PDF van curaties (wel een nice-to-have)
- Integraties (SharePoint, Teams, Outlook)
- Inter-municipale multi-tenant ondersteuning

---

## 5. Functionele requirements (MVP, in detail)

### F1 — Initiatief aanmaken
- Eén knop "Nieuw initiatief" op het hoofdscherm.
- Verplicht: titel, fase (default: verkenning).
- Optioneel: omschrijving (markdown), horizon, MDS, centrale vraag, eigenaar.
- Aanmaken moet binnen 30 seconden kunnen (zonder optionele velden).
- Direct na opslaan landt de gebruiker op de detailpagina van het initiatief.

### F2 — Initiatief bewerken
- Alle velden inline of via een edit-modus aanpasbaar.
- Fase- en statuswijzigingen worden in een lichte log bijgehouden (datum + oude/nieuwe waarde — voor MVP alleen geheugen, geen aparte history-tabel nodig).

### F3 — Hypothesen en sub-hypothesen koppelen
- Onder een initiatief: knop "Hypothese toevoegen".
- Verplicht: type (value/growth/compliance), omschrijving.
- Optioneel: status (default: open).
- Onder een hypothese: knop "Sub-hypothese toevoegen", zelfde structuur.
- Bij statuswijziging naar *weerlegd* of *bevestigd*: leeruitkomst-veld verplicht.

### F4 — Dossier per initiatief
- Tab of paneel "Dossier" op de detailpagina.
- Notities: markdown-input, lijst van notities chronologisch, elk met datum en korte titel.
- Bestanden: upload-knop, lijst van bestanden met naam, type-icoon, grootte, datum. Klikken downloadt.
- Maximum bestandsgrootte: 25 MB per bestand (voor MVP).

### F5 — Stoppen met leeruitkomst
- Status "gestopt" kan alleen worden gezet via een modale dialoog die om de leeruitkomst vraagt.
- Helptekst in de dialoog: "Wat we hier leren is brandstof voor wat erna komt. Schrijf in een paar zinnen wat dit initiatief heeft opgeleverd."
- Een gestopt initiatief blijft volledig zichtbaar en doorzoekbaar; het wordt niet gearchiveerd of verstopt.

### F6 — Curaties
- Apart scherm "Curaties" in de hoofdnavigatie.
- Lijst van bestaande curaties; knop "Nieuwe curatie".
- Bij aanmaken: naam, doel (bijv. "Show & tell juli", "Directievoordracht AI"), beschrijving.
- In een curatie: initiatieven toevoegen via zoek-/selectie-interface; geordend met drag-and-drop; per item een toelichting in een tekstveld.
- Een initiatief kan in meerdere curaties zitten.

### F7 — Zoeken en filteren
- Vrije-tekst zoekbalk altijd zichtbaar bovenaan.
- Resultaten gegroepeerd op: initiatieven, hypothesen, dossiernotities, curaties.
- Filterpaneel: fase, status, horizon, MDS, periode (laatst gewijzigd).
- Implementatie: SQLite FTS5 of equivalent — eenvoudige full-text zoek, geen geavanceerde semantische zoek voor MVP.

### F8 — Dashboard
- Hoofdscherm na inloggen toont:
  - Aantal initiatieven per fase (visualisatie: gestapelde balk of kaarten)
  - Aantal per horizon (kleine grafiek)
  - Aantal per status (incl. gestopt)
  - Lijst "Recent gewijzigd" (top 10)
  - Lijst "Recent gestopt met leeruitkomst" (top 5) — bewust prominent, om stoppen normaal te maken
- Klikken op een lijst-item gaat naar het initiatief.

---

## 6. Datamodel

Voorgestelde entiteiten en relaties (relationeel, normalisatie waar zinvol):

### `initiatives`
| veld | type | opmerking |
|---|---|---|
| id | uuid | primary key |
| title | text | verplicht |
| description | text | markdown |
| phase | enum | `verkenning`, `experiment`, `pilot`, `opschaling` |
| status | enum | `actief`, `gestopt`, `afgerond` |
| horizon | enum nullable | `h1`, `h2`, `h3` |
| mds | text nullable | vrij tekstveld in MVP |
| central_question | text nullable | vrij tekstveld in MVP |
| owner | text nullable | vrij tekstveld |
| stop_reason | text nullable | verplicht als status = gestopt |
| created_at | timestamp | |
| updated_at | timestamp | |

### `hypotheses`
| veld | type | opmerking |
|---|---|---|
| id | uuid | primary key |
| initiative_id | uuid fk | → initiatives |
| parent_hypothesis_id | uuid fk nullable | → hypotheses (voor sub-hypothesen) |
| type | enum | `value`, `growth`, `compliance` |
| description | text | verplicht |
| status | enum | `open`, `bevestigd`, `weerlegd`, `vervallen` |
| learning | text nullable | verplicht als status ≠ open |
| created_at | timestamp | |
| updated_at | timestamp | |

> **Modelopmerking:** sub-hypothesen kunnen via een self-referencing `parent_hypothesis_id` of via een aparte tabel. Self-referencing is eenvoudiger en past bij de gewenste flexibiliteit (een sub-hypothese is gewoon een hypothese met een ouder).

### `dossier_notes`
| veld | type | opmerking |
|---|---|---|
| id | uuid | primary key |
| initiative_id | uuid fk | → initiatives |
| title | text nullable | |
| body | text | markdown |
| created_at | timestamp | |

### `dossier_files`
| veld | type | opmerking |
|---|---|---|
| id | uuid | primary key |
| initiative_id | uuid fk | → initiatives |
| filename | text | |
| mime_type | text | |
| file_size | int | bytes |
| storage_path | text | relatief pad in lokale opslag |
| uploaded_at | timestamp | |

### `curations`
| veld | type | opmerking |
|---|---|---|
| id | uuid | primary key |
| name | text | verplicht |
| purpose | text nullable | bijv. "Show & tell juli" |
| description | text nullable | markdown |
| created_at | timestamp | |
| updated_at | timestamp | |

### `curation_items`
| veld | type | opmerking |
|---|---|---|
| id | uuid | primary key |
| curation_id | uuid fk | → curations |
| initiative_id | uuid fk | → initiatives |
| position | int | volgorde binnen curatie |
| note | text nullable | toelichting waarom dit item in deze curatie zit |

### Indexering
- Full-text index over `initiatives.title`, `initiatives.description`, `hypotheses.description`, `hypotheses.learning`, `dossier_notes.body`, `curations.description`, `curation_items.note`.
- Aanbevolen voor SQLite: FTS5 virtuele tabel die deze velden bij elkaar brengt.

---

## 7. Niet-functionele requirements

### Toegankelijkheid en ergonomie
- Het invoeren van een initiatief moet voelen als een mail schrijven, niet als een formulier invullen. Inline-velden, geen pop-ups voor het hoofd-aanmaakproces.
- Tastbaar verschil tussen "actief", "gestopt" en "afgerond" — gestopt mag niet als afval voelen. Gebruik neutrale kleuren (geen rood), bijvoorbeeld grijs-met-lichtpaarse-rand of een "leeruitkomst"-icoon.
- Toetsenbordbediening voor alle hoofd-acties (toevoegen, zoeken, openen).
- WCAG 2.1 AA als doelstelling (kleur-contrast, focus-states); volledige certificering is geen MVP-eis.

### Performance
- Zoekresultaten binnen 500 ms bij datasets tot ~10.000 initiatieven en ~30.000 hypothesen (ruim boven verwachte werkelijke schaal voor de sandbox).
- Pagina-laad onder 1 seconde lokaal.

### Data en backup
- Single-file SQLite database (voor MVP). Backup = `cp` van dat bestand.
- Bestandsuploads in een lokale map (`/data/uploads/<initiative_id>/<file_id>__<filename>`).

### Veiligheid (sandbox)
- Geen authenticatie in MVP. App draait lokaal of op een afgeschermde host.
- Geen externe netwerk-calls behalve naar standaard CDN's voor frontend-assets.
- Geen PII-vereisten in MVP (sandbox-gebruik); aandacht voor PII komt bij v2.

---

## 8. Tech stack-advies

> **Let op:** dit is een aanbeveling, geen mandaat. De keuze mag worden aangepast als de coding agent of de gebruiker een sterk alternatief verkiest. De redenering staat erbij zodat afwijken een geïnformeerde keuze blijft.

### Aanbevolen stack
- **Backend:** Python met FastAPI. Modern, async-vriendelijk, uitstekende OpenAPI-documentatie, en past goed bij latere AI-uitbreiding (Anthropic-client beschikbaar).
- **Database:** SQLite met FTS5 voor full-text search. Zero-config, één bestand om te backuppen, voldoende voor sandbox-schaal en zelfs een eerste multi-gemeente uitrol. Migratie naar PostgreSQL later is bewerkelijk maar mogelijk.
- **Frontend:** **HTMX + Jinja2-templates** voor MVP. Reden: minimale build-stappen, snel ontwikkelen, en de UI is voornamelijk formulieren en lijsten — geen rich client-side state. Past bij "personal sandbox". Alternatief als de agent of gebruiker dat verkiest: React/Vite met Tailwind.
- **Styling:** Tailwind CSS via CDN voor MVP (later eventueel via build).
- **Bestandsopslag:** lokale filesystem onder `/data/uploads/`. Eenvoudige abstractie zodat een blob-storage backend (Azure Blob, S3) later kan worden geplugd.
- **Deployment:** Docker-container of pure `uvicorn`-process op localhost. Geen complexe infrastructuur in MVP.

### Waarom deze stack
1. Lage cognitieve overhead — een coding agent kan in één pull request iets bruikbaars opleveren.
2. Schaalbaar in twee dimensies: schaal van data (SQLite → Postgres) en schaal van interactiviteit (HTMX → React).
3. Volledig open source, geen vendor lock-in.
4. AI-narratief-features later toevoegen is een kwestie van een API-client aanroepen vanuit FastAPI — geen architectuurherziening.

---

## 9. UX-uitgangspunten

1. **Drempel is alles.** Initiatief toevoegen mag nooit afhankelijk zijn van compleet ingevulde velden. Alleen titel en fase verplicht; de rest kan later.
2. **Stoppen is een eerste-rangs handeling.** Visueel evenwaardig aan opschalen. Een gestopt initiatief met heldere leeruitkomst is een succes, geen falen.
3. **Curatie is zichtbaar werk.** Een curatie samenstellen mag *plezierig* zijn — drag-and-drop, vrije toelichting per item, voorbeeldweergave van hoe de curatie als verhaal leest.
4. **Geen verplichte taxonomie waar het niet nodig is.** MDS en centrale vraag zijn vrije velden in MVP. Strakke taxonomie pas wanneer we ervaring hebben met wat mensen er werkelijk invullen.
5. **Domeintaal trouw blijven.** Geen "tasks", "tickets", "projects" — wel "initiatieven", "verkenningen", "hypothesen".
6. **Markdown waar tekst meer dan twee regels kan zijn.** Lichte preview, geen WYSIWYG.

---

## 10. Roadmap na MVP (volgordelijk advies)

Niet exhaustief, en niet bindend — bedoeld om de richting van het ontwerp te bepalen zodat MVP-keuzes uitbreiding niet blokkeren.

### Horizon 2 (de eerste paar maanden na MVP)
1. **AI-narratief-generatie.** Eerste use-case: gegeven een curatie, genereer een verhaalparagraaf die de initiatieven aan elkaar verbindt. Tweede: gegeven een initiatief met dossier en hypothesen, genereer een one-pager voor de directie. Implementatie: Anthropic Claude API (model nader te bepalen via gemeente-keuze). Prompt-engineering als aparte werkstroom.
2. **Semantische zoek.** Naast full-text. Embeddings genereren bij opslag, vector search bij query. Bij SQLite kan dit met `sqlite-vec` of vergelijkbare extensie; bij Postgres met `pgvector`.
3. **Lichtgewicht auth.** Magic-link of M365-SSO. Begin van multi-user.
4. **MDS en centrale vraag als entiteiten.** In plaats van vrije tekstvelden. Per MDS een dashboard.
5. **Events.** Show & tell, hackathon, maker faire als aparte entiteiten, gekoppeld aan initiatieven en aan curaties.
6. **Export.** Een curatie als Word- of PDF-document downloaden (gebruik de docx-skill, of `python-docx` server-side).

### Horizon 3 (denk-aan-eerder, doe-pas-later)
- Multi-tenant voor inter-municipale samenwerking.
- Rollen en toegangsrechten (zien vs. bewerken vs. cureren).
- Comments / discussie per initiatief.
- Communities of practice als entiteit (incl. ledenlijst, kern, perifere participatie).
- Integraties met SharePoint, Teams, Outlook-agenda.
- API voor externe gebruik (bijv. een dashboard in Power BI dat zich voedt vanuit de tool).
- AVG-conform productiegebruik (DPIA, archivering, retentiebeleid).

---

## 11. Open vragen en beslispunten

Punten waarop ik aannames heb gedaan; graag bevestigen of bijsturen:

1. **Eigenaar als vrij tekstveld.** Geen koppeling aan een gebruikers-entiteit in MVP. Akkoord?
2. **Eén gebruiker, geen audit-trail.** Voor sandbox aanvaardbaar; in v2 introduceren we wie wat heeft gewijzigd.
3. **Sub-hypothesen tot één laag diep.** Onder een hoofdhypothese kunnen sub-hypothesen, maar geen sub-sub-hypothesen. Conform de notitie. Akkoord?
4. **Aanvankelijke filterdiepte op de zoekfunctie.** Voorgesteld: fase, status, horizon, MDS, periode. Wil je ook kunnen filteren op *type hoofdhypothese* (alleen value, alleen compliance) of *hypothese-status* (alleen weerlegd, om geleerde lessen te oogsten)?
5. **Visualisatie van curatie als verhaal.** Voorstel: een "leesweergave" van een curatie die opeenvolgend toont: doel — beschrijving — initiatief 1 (met toelichting) — initiatief 2 (met toelichting) — enzovoort. Akkoord?
6. **Bestandstype-restricties.** Voorgesteld: alle types, geen restrictie, alleen grootte-cap. Akkoord, of liever whitelist (PDF, docx, xlsx, png, jpg)?
7. **Naamgeving.** "Innovatiepijplijn-tool" is een werktitel. Een goede definitieve naam (kort, herkenbaar, niet te ambtelijk) helpt bij draagvlak — denk aan iets als *Brandstof*, *Raket*, *Combustie*, *Cureerder*, of iets specifieks voor Leiden. Zelf bedenken of meedenken?

---

## 12. Referentie voor de coding agent

Voor domeinbegrip is de bijbehorende notitie *Effectief innoveren in de gemeente Leiden* (werkversie 0.5) leidend. Wanneer er twijfel ontstaat tussen technische optimalisatie en domein-trouw, kiest de agent voor domein-trouw en signaleert ze de spanning expliciet in een commit-bericht of een open vraag.

Concreet vraagt dit van de agent:

- **Geen herinterpretatie van domeintaal.** "Initiatief" wordt geen "project", "verkenning" wordt geen "draft", "hypothese" wordt geen "criterion".
- **Verklaarbare UX-keuzes.** Elke afwijking van de hier opgenomen UX-uitgangspunten wordt expliciet onderbouwd.
- **Conservatief met dependencies.** Liever een eenvoudige inhouse-oplossing dan een zware library.
- **Werkbaar in incrementen.** Een pull request mag klein zijn. Een werkende "initiatief aanmaken + lijst zien" is al een waardevolle eerste tussenstand.

---

*Einde PRD v0.1.*
