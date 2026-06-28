#!/usr/bin/env python3
"""Seed script — voegt 30 realistische initiatieven toe aan de database."""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import datetime, timedelta
import random

from app.database import SessionLocal, get_db
from app.models import Initiative, Hypothesis
from app.search import update_fts_initiative, update_fts_hypothesis


INITIATIEVEN = [
    # --- Verkenning (8) ---
    {
        "title": "AI-gestuurde wachttijdvoorspelling loket",
        "description": "Verkennen of machine learning de wachttijden op het gemeenteloket kan voorspellen en optimaliseren.",
        "phase": "verkenning", "horizon": "h2", "mds": "IT, Klantcontact",
        "owner": "Sandra de Vries", "central_question": "Kan AI wachttijden met 30% reduceren?",
    },
    {
        "title": "Buurthulpenplatform voor ouderen",
        "description": "Digitale match tussen vrijwilligers en alleenstaande ouderen in Leiden Zuid.",
        "phase": "verkenning", "horizon": "h1", "mds": "Maatwerk, IT",
        "owner": "Tom Bakker", "central_question": "Zullen buren elkaar helpen via een platform?",
    },
    {
        "title": "Smart lighting in openbare parken",
        "description": "Sensorgestuurd straatmeubilair dat verlichting aanpast op basis van aanwezigheid en schemering.",
        "phase": "verkenning", "horizon": "h2", "mds": "Openbare Ruimte, IT",
        "owner": "Lisa Jansen", "central_question": "Kan slimme verlichting energiekosten met 40% verlagen?",
    },
    {
        "title": "Gamificatie van afvalscheiding",
        "description": "App die burgers uitdaagt om beter te scheiden via punten en ranglijsten per wijk.",
        "phase": "verkenning", "horizon": "h1", "mds": "Omgeving, Communicatie",
        "owner": "Mark de Groot", "central_question": "Verhoogt gamificatie de scheidingsgraad?",
    },
    {
        "title": "Digitale tweedehandsmarkt voor scholen",
        "description": "Platform waar basisscholen materialen met elkaar kunnen delen en ruilen.",
        "phase": "verkenning", "horizon": "h2", "mds": "Onderwijs, IT",
        "owner": "Femke Visser", "central_question": "Zullen scholen materiaal met elkaar delen?",
    },
    {
        "title": "Chatbot voor vergunningaanvragen",
        "description": "AI-assistent die burgers stap-voor-stap helpt bij het indienen van een omgevingsvergunning.",
        "phase": "verkenning", "horizon": "h1", "mds": "IT, Omgeving",
        "owner": "Kees van Dijk", "central_question": "Kan een chatbot de aanvraagtijd halveren?",
    },
    {
        "title": "Mentorprogramma voor jongeren in Leiden West",
        "description": "Professionals koppelen aan jongeren zonder werkervaring via een gestructureerd mentorprogramma.",
        "phase": "verkenning", "horizon": "h2", "mds": "Maatwerk, Werk & Inkomen",
        "owner": "Amina El Fassi", "central_question": "Levert mentoring tot 6 maanden later een baan op?",
    },
    {
        "title": "Bewegingspaviljoen op schoolpleinen",
        "description": "Pop-up sportfaciliteiten die verspringen tussen scholen met weinig buitenspelmogelijkheden.",
        "phase": "verkenning", "horizon": "h3", "mds": "Onderwijs, Sport & Vitaliteit",
        "owner": "Rob van den Berg", "central_question": "Kan een mobiel paviljoen beweging stimuleren?",
    },

    # --- Experiment (7) ---
    {
        "title": "Pop-up burgerlab voor wijkvragen",
        "description": "PoC: tijdelijke workspace waar bewoners samen oplossingen bedenken voor lokale problemen.",
        "phase": "experiment", "horizon": "h1", "mds": "Participatie, Openbare Ruimte",
        "owner": "Ingrid Postma", "central_question": "Kunnen bewoners zelf wijkvragen oplossen?",
    },
    {
        "title": "Automatische parkeerdetectie met camera's",
        "description": "PoC: slimme camera's die illegaal parkeren signaleren en doorgeven aan handhaving.",
        "phase": "experiment", "horizon": "h2", "mds": "Vervoer, IT, Handhaving",
        "owner": "Pieter de Boer", "central_question": "Werkt automatische detectie in de praktijk?",
    },
    {
        "title": "Bewonerspanel voor beleidsevaluatie",
        "description": "PoC: representatief panel van 100 inwoners dat nieuw beleid beoordeelt vóór implementatie.",
        "phase": "experiment", "horizon": "h1", "mds": "Participatie, Communicatie",
        "owner": "Marieke Smit", "central_question": "Levert een bewonerspanel betere besluiten op?",
    },
    {
        "title": "Digitale klankbordgroep voor MKB",
        "description": "PoC: online platform waar ondernemers elkaar adviseren over regelgeving en subsidies.",
        "phase": "experiment", "horizon": "h2", "mds": "Economie, IT",
        "owner": "Hans Mulder", "central_question": "Helpt peer-to-peer advies MKB met bureaucratie?",
    },
    {
        "title": "Groendag-app voor vrijwilligers",
        "description": "PoC: app die bewoners uitnodigt om op zaterdag mee te helpen bij groenonderhoud.",
        "phase": "experiment", "horizon": "h1", "mds": "Omgeving, Participatie",
        "owner": "Sanne van Leeuwen", "central_question": "Zullen burgers vaker vrijwillig groen onderhouden?",
    },
    {
        "title": "Datakamer Leiden — open data dashboard",
        "description": "PoC: interactief dashboard met open gemeentedata voor journalisten en onderzoekers.",
        "phase": "experiment", "horizon": "h2", "mds": "IT, Communicatie",
        "owner": "Daan Hendriks", "central_question": "Wordt open data meer gebruikt via een dashboard?",
    },
    {
        "title": "Thuiswerkcafé voor starters",
        "description": "PoC: co-working ruimte in bibliotheek voor ZZP'ers die net beginnen.",
        "phase": "experiment", "horizon": "h1", "mds": "Economie, Cultuur",
        "owner": "Nadia El Amrani", "central_question": "Hebben starters een plek nodig om te netwerken?",
    },

    # --- Pilot (7) ---
    {
        "title": "Buurtcoaches voor kwetsbare gezinnen",
        "description": "Pilot in Leiden Zuidwest: 5 coaches ondersteunen 80 gezinnen met praktische vragen.",
        "phase": "pilot", "horizon": "h1", "mds": "Maatwerk, Wijkteams",
        "owner": "Fatima Benali", "central_question": "Reduceren buurtcoaches de uitstroom naar jeugdzorg?",
    },
    {
        "title": "Circulale wijk Leiden Rijnwijk",
        "description": "Pilot: materialenbank + repair café + food sharing in één wijkcentrum.",
        "phase": "pilot", "horizon": "h2", "mds": "Omgeving, Participatie",
        "owner": "Jasper van der Meer", "central_question": "Kan een circulair hub de afvalberg met 20% verlagen?",
    },
    {
        "title": "E-loket voor asielzoekers",
        "description": "Pilot: digitaal loket waar asielzoekers zelf hun status en rechten kunnen inzien.",
        "phase": "pilot", "horizon": "h1", "mds": "IT, Maatwerk",
        "owner": "Youssef Haddad", "central_question": "Vindt dit doelgroep het e-loket toegankelijk?",
    },
    {
        "title": "Bewegingsstraten in Leiden Centrum",
        "description": "Pilot: 3 tijdelijke autovrije straten met beweegoefeningen en groen.",
        "phase": "pilot", "horizon": "h2", "mds": "Openbare Ruimte, Sport & Vitaliteit",
        "owner": "Lotte van der Heijden", "central_question": "Verhoogt een bewegingsstraat de fysieke activiteit?",
    },
    {
        "title": "Wijkbudget 2.0 — digitale participatie",
        "description": "Pilot: bewoners stemmen via app over besteding van wijkbudget, niet meer op papier.",
        "phase": "pilot", "horizon": "h1", "mds": "Participatie, IT",
        "owner": "Bas de Graaf", "central_question": "Levert digitaal stemmen hogere participatie op?",
    },
    {
        "title": "Groene dakbegrazing voor biodiversiteit",
        "description": "Pilot: schapen begrazen daken van gemeentelijke gebouwen voor natuur en onderhoud.",
        "phase": "pilot", "horizon": "h3", "mds": "Omgeving, Facilitair",
        "owner": "Eva de Jong", "central_question": "Is dakkapen technisch haalbaar op gemeentelijke panden?",
    },
    {
        "title": "Peer-to-peer mediation voor burenruzies",
        "description": "Pilot: getrainde buurtbewoners bemiddelen bij kleine conflicten vóór de rechter.",
        "phase": "pilot", "horizon": "h1", "mds": "Veiligheid, Wijkteams",
        "owner": "Rik van den Broek", "central_question": "Kan peer mediation 40% minder zaken naar de rechter brengen?",
    },

    # --- Opschaling (5) ---
    {
        "title": "Digitale wijkapp Leiden",
        "description": "Opschalen naar alle wijken: app met nieuws, agenda, meldingen en buurtcontact.",
        "phase": "opschaling", "horizon": "h1", "mds": "IT, Communicatie, Participatie",
        "owner": "Sandra de Vries", "central_question": "Kan één app alle wijkcommunicatie vervangen?",
    },
    {
        "title": "Energiecoaches voor sociale huur",
        "description": "Opschalen naar 1000 huishoudens: persoonlijke energiebespaaradvies met maatwerkplan.",
        "phase": "opschaling", "horizon": "h1", "mds": "Omgeving, Wijkteams",
        "owner": "Tom Bakker", "central_question": "Levert 1-op-1 coaching structurele besparing op?",
    },
    {
        "title": "Vrijwilligerspool Leiden Online",
        "description": "Opschalen: centraal platform voor alle vrijwilligersinspanningen in de gemeente.",
        "phase": "opschaling", "horizon": "h1", "mds": "Participatie, IT",
        "owner": "Ingrid Postma", "central_question": "Kunnen we 5000 vrijwilligers managen via één platform?",
    },
    {
        "title": "Smart waste sensors in openbare ruimte",
        "description": "Opschalen naar 200 prullenbakken: volksensoren die optimaliseren wanneer afval wordt opgehaald.",
        "phase": "opschaling", "horizon": "h2", "mds": "Omgeving, IT",
        "owner": "Lisa Jansen", "central_question": "Leveren sensors 30% minder ophaalritten op?",
    },
    {
        "title": "Burgerbudget voor innovatie",
        "description": "Opschalen: jaarlijks €50.000 budget dat bewoners zelf toekennen aan initiatieven.",
        "phase": "opschaling", "horizon": "h1", "mds": "Participatie, Financiën",
        "owner": "Marieke Smit", "central_question": "Kan een burgerbudget de betrokkenheid verdubbelen?",
    },

    # --- Gestopt (3) ---
    {
        "title": "QR-codes op gedenkschriften",
        "description": "Gestopt: QR-codes bij begraafplaatsen met biografieën bleken te weinig gebruikt.",
        "phase": "experiment", "horizon": "h2", "mds": "Cultuur, IT",
        "owner": "Daan Hendriks", "central_question": "Willen bezoekers meer weten via QR?",
        "status": "gestopt",
        "stop_reason": "Bezoekers scannen zelden; de doelgroep (ouderen) gebruikt geen smartphones. We hebben geleerd dat laagdrempelige, analoge oplossingen vaak beter werken dan digitale voor deze groep.",
    },
    {
        "title": "Deelfietsen voor ambtenaren",
        "description": "Gestopt: deelsysteem binnen gemeentehuis had te lage opbrengst en hoge onderhoudskosten.",
        "phase": "pilot", "horizon": "h1", "mds": "Facilitair, Omgeving",
        "owner": "Eva de Jong", "central_question": "Rijden ambtenaren meer met de fiets?",
        "status": "gestopt",
        "stop_reason": "Slechts 12% van het personeel gebruikte de fietsen regelmatig. Deelsystemen werken beter op straatniveau dan binnen één gebouw. Les: schaal en context bepalen adoptie.",
    },
    {
        "title": "Voice-assistent voor ouderen",
        "description": "Gestopt: Alexa-achtige assistent voor ouderen had privacybezwaren en te hoge drempel.",
        "phase": "experiment", "horizon": "h2", "mds": "IT, Maatwerk",
        "owner": "Kees van Dijk", "central_question": "Willen ouderen een voice-assistent thuis?",
        "status": "gestopt",
        "stop_reason": "Privacybezwaren en angst voor 'luisterende apparaten' waren te groot. We hebben geleerd dat technologie voor kwetsbare groepen eerst vertrouwen moet opbouwen voordat functionaliteit toegevoegd wordt.",
    },

    # --- Afgerond (2) ---
    {
        "title": "Digitale meldknop voor overlast",
        "description": "Afgerond: app voor het melden van openbare overlast is live en gebruikt door 8000 inwoners.",
        "phase": "opschaling", "horizon": "h1", "mds": "IT, Openbare Ruimte",
        "owner": "Lisa Jansen", "central_question": "Melden burgers meer via app dan via telefoon?",
        "status": "afgerond",
    },
    {
        "title": "Woonwijkfestival Leiden Zuid",
        "description": "Afgerond: jaarlijks terugkerend festival met 5000 bezoekers, volledig bewonersorganisatie.",
        "phase": "opschaling", "horizon": "h1", "mds": "Participatie, Cultuur",
        "owner": "Marieke Smit", "central_question": "Kan een festival de wijkcohesie versterken?",
        "status": "afgerond",
    },
]


def seed():
    """Voeg initiatieven toe aan de database."""
    db = SessionLocal()
    try:
        existing = db.query(Initiative).count()
        print(f"Bestaande initiatieven: {existing}")

        created = 0
        stopped_with_learning = 0

        for item in INITIATIEVEN:
            initiative = Initiative(
                title=item["title"],
                description=item["description"],
                phase=item["phase"],
                horizon=item.get("horizon"),
                mds=item.get("mds"),
                owner=item.get("owner"),
                central_question=item.get("central_question"),
                status=item.get("status", "actief"),
                stop_reason=item.get("stop_reason"),
            )

            # Simuleer verschillende creatie-dates (laatste 6 maanden)
            days_ago = random.randint(1, 180)
            initiative.created_at = datetime.now() - timedelta(days=days_ago)
            initiative.updated_at = datetime.now() - timedelta(days=random.randint(0, days_ago))

            db.add(initiative)
            created += 1

            # FTS indexeren
            update_fts_initiative(db, None, initiative.title, initiative.description or "")

            # Voeg hypothesen toe voor actieve initiatieven
            if initiative.status == "actief":
                num_hypotheses = random.randint(1, 4)
                for h_idx in range(num_hypotheses):
                    hyp_type = random.choice(["value", "growth", "compliance"])
                    hyp_status = random.choice(["open", "bevestigd", "weerlegd"])

                    learning = None
                    if hyp_status == "bevestigd":
                        learning = random.choice([
                            "Test bevestigt dat burgers wel bereid zijn tot participatie.",
                            "Resultaten tonen duidelijke verbetering ten opzichte van baseline.",
                            "Met 78% adoptie is de hypothese bevestigd.",
                        ])
                    elif hyp_status == "weerlegd":
                        learning = random.choice([
                            "Aannemer bleek te optimistisch; realiteit is complexer.",
                            "Doelgroep reageert anders dan verwacht; aanpassing nodig.",
                            "Data toont geen significant effect na 3 maanden.",
                        ])

                    hypothesis = Hypothesis(
                        initiative_id=initiative.id,
                        type=hyp_type,
                        description=f"Hypothese {h_idx + 1} voor '{item['title']}'",
                        status=hyp_status,
                        learning=learning,
                    )
                    db.add(hypothesis)
                    update_fts_hypothesis(db, None, hypothesis.description, hypothesis.learning or "")

            # Voeg sub-hypothese toe bij sommige
            if random.random() < 0.3 and initiative.status == "actief":
                parent = db.query(Hypothesis).filter(
                    Hypothesis.initiative_id == initiative.id
                ).first()
                if parent:
                    sub = Hypothesis(
                        initiative_id=initiative.id,
                        parent_hypothesis_id=parent.id,
                        type="value",
                        description=f"Sub-hypothese van '{parent.description}'",
                        status=random.choice(["open", "bevestigd"]),
                        learning="Sub-resultaat bevestigt hoofdverwachting." if random.random() > 0.5 else None,
                    )
                    db.add(sub)

        # Commit alles
        db.commit()
        print(f"✅ {created} initiatieven toegevoegd")

        # Statistieken
        total = db.query(Initiative).count()
        per_phase = {}
        for phase in ["verkenning", "experiment", "pilot", "opschaling"]:
            count = db.query(Initiative).filter(Initiative.phase == phase, Initiative.status == "actief").count()
            per_phase[phase] = count

        per_status = {}
        for status in ["actief", "gestopt", "afgerond"]:
            count = db.query(Initiative).filter(Initiative.status == status).count()
            per_status[status] = count

        total_hyp = db.query(Hypothesis).count()

        print(f"\n📊 Overzicht ({total} totaal):")
        print(f"   Per fase: {per_phase}")
        print(f"   Per status: {per_status}")
        print(f"   Totaal hypothesen: {total_hyp}")

    finally:
        db.close()


if __name__ == "__main__":
    seed()
