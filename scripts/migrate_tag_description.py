#!/usr/bin/env python3
"""Migratie — voeg description kolom toe aan tags tabel + seed bestaande tags."""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text
from app.database import engine

# Beschrijvingen voor de 10 seed-tags
TAG_DESCRIPTIONS = {
    "digitaal": "Initiatieven rond digitale transformatie, e-government, online dienstverlening en digitaal werk.",
    "participatie": "Initiatieven die bewonersbetrekking, co-creatie, participatieve begroting of burgerbetrokkenheid bevatten.",
    "duurzaamheid": "Initiatieven op het gebied van klimaat, energie, circulaire economie, groen beleid en duurzaamheid.",
    "ai": "Initiatieven die kunstmatige intelligentie, machine learning, data-analyse of AI-gestuurde besluitvorming inzetten.",
    "zelfbouw": "Initiatieven waarbij gemeentemedewerkers eigen digitale oplossingen bouwen (citizen development, low-code, hackathons).",
    "procesinnovatie": "Initiatieven die interne processen verbeteren, werkstromen optimaliseren of organisatorische innovatie bevatten.",
    "dienstverlening": "Initiatieven gericht op verbetering van de burger- of ondernemersdienstverlening van de gemeente.",
    "veiligheid": "Initiatieven rond openbare veiligheid, preventie, crisisbestrijding of bestuursrechtelijke handhaving.",
    "mobiliteit": "Initiatieven over vervoer, bereikbaarheid, duurzaam vervoer, parkeerbeleid of infrastructuur.",
    "cultuur": "Initiatieven op het gebied van cultuurparticipatie, erfgoed, creatieve industrie of sociale cohesie via cultuur.",
    "circulariteit": "Initiatieven rond circulaire economie, hergebruik, afvalpreventie en duurzaam materiaalbeheer.",
    "data": "Initiatieven die data-analyse, datagedreven besluitvorming, open data of informatievoorziening centraal stellen.",
    "gezondheid": "Initiatieven op het gebied van volksgezondheid, welzijn, preventie, zorginnovatie of vitale wijk.",
    "jongeren": "Initiatieven gericht op jongerenzaken, jeugdbeleid, participatie van jongeren of jeugdwerk.",
    "ondernemerschap": "Initiatieven rond ondernemerssupport, economische ontwikkeling, innovatie-ecosystemen of startup-ontwikkeling.",
    "openbare ruimte": "Initiatieven over inrichting, beheer en gebruik van de openbare ruimte, straatbeleving en publieke pleinen.",
    "sociale samenhang": "Initiatieven die sociale cohesie, inclusie, armoedebestrijding of maatschappelijke participation bevorderen.",
}


def migrate():
    """Voeg description kolom toe en vul bestaande tags in."""
    with engine.connect() as conn:
        # Check of kolom al bestaat
        result = conn.execute(text("PRAGMA table_info(tags)"))
        columns = [row[1] for row in result.fetchall()]

        if "description" not in columns:
            conn.execute(text("ALTER TABLE tags ADD COLUMN description TEXT"))
            print("✅ description kolom toegevoegd aan tags tabel.")
        else:
            print("✅ description kolom bestaat al — geen migratie nodig.")

        # Vul beschrijvingen voor bestaande tags
        tags = conn.execute(text("SELECT id, name FROM tags WHERE is_active = 1")).fetchall()
        for tag_id, tag_name in tags:
            desc = TAG_DESCRIPTIONS.get(tag_name.lower().strip())
            if desc:
                conn.execute(
                    text("UPDATE tags SET description = :desc WHERE id = :id"),
                    {"desc": desc, "id": tag_id},
                )
                print(f"  ✓ Beschrijving toegevoegd voor tag '{tag_name}'")

        conn.commit()
        print("✅ Migratie voltooid.")


if __name__ == "__main__":
    migrate()
