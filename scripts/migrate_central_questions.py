#!/usr/bin/env python3
"""Migratie script — converteer bestaande central_question teksten naar CentralQuestion records."""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import SessionLocal
from app.models import Initiative, CentralQuestion, InitiativeQuestion
from app.database import Base, engine


def migrate():
    """Converteer unieke central_question teksten naar CentralQuestion records."""
    # Maak nieuwe tabellen aan als ze nog niet bestaan
    Base.metadata.create_all(bind=engine)
    print("Tabellen geüpdate met CentralQuestion en InitiativeQuestion")

    db = SessionLocal()
    try:
        # Haal alle initiatieven op met een central_question tekst
        initiatives_with_question = (
            db.query(Initiative)
            .filter(Initiative.central_question.isnot(None))
            .filter(Initiative.central_question != "")
            .all()
        )

        if not initiatives_with_question:
            print("Geen initiatieven gevonden met central_question tekst.")
            return

        # Groepeer op unieke vraagteksten
        unique_questions = {}
        for init in initiatives_with_question:
            q_text = init.central_question.strip()
            if q_text not in unique_questions:
                unique_questions[q_text] = []
            unique_questions[q_text].append(init.id)

        print(f"Gevonden: {len(unique_questions)} unieke centrale vragen")
        print(f"Betrokken initiatieven: {sum(len(ids) for ids in unique_questions.values())}")

        created = 0
        linked = 0

        for q_text, init_ids in unique_questions.items():
            # Check of vraag al bestaat
            existing = db.query(CentralQuestion).filter(
                CentralQuestion.question == q_text,
                CentralQuestion.is_active == True,
            ).first()

            if not existing:
                question = CentralQuestion(question=q_text)
                db.add(question)
                db.flush()  # Haal ID op
                existing = question
                created += 1
                print(f"  Aangemaakt: '{q_text[:60]}...'")

            # Koppel initiatieven
            for init_id in init_ids:
                # Check of koppeling al bestaat
                existing_link = db.query(InitiativeQuestion).filter(
                    InitiativeQuestion.initiative_id == init_id,
                    InitiativeQuestion.central_question_id == existing.id,
                ).first()

                if not existing_link:
                    link = InitiativeQuestion(
                        initiative_id=init_id,
                        central_question_id=existing.id,
                    )
                    db.add(link)
                    linked += 1

        db.commit()
        print(f"\n✅ Migratie voltooid:")
        print(f"   {created} nieuwe centrale vragen aangemaakt")
        print(f"   {linked} koppelingen toegevoegd")

    except Exception as e:
        db.rollback()
        print(f"Fout tijdens migratie: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    migrate()
