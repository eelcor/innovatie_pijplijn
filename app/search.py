"""Full-text search met SQLite FTS5."""

from sqlalchemy import text


def _ensure_fts_table(db):
    """Zorg dat de FTS5 tabel bestaat."""
    try:
        db.execute(text("""
            CREATE VIRTUAL TABLE IF NOT EXISTS search_index USING fts5(
                content,
                content_rowid
            )
        """))
        db.commit()
    except Exception:
        pass


def create_fts_table(db):
    """Maak de FTS5 virtuele tabel aan en bevolk deze."""
    _ensure_fts_table(db)


def rebuild_fts_index(db):
    """Herbouw de volledige FTS index vanuit alle relevante tabellen."""
    # Verwijder en herbouw
    db.execute(text("DROP TABLE IF EXISTS search_index"))
    db.execute(text("""
        CREATE VIRTUAL TABLE search_index USING fts5(
            content,
            content_rowid
        )
    """))

    # Voeg alle doorzoekbare inhoud toe
    db.execute(text("""
        INSERT INTO search_index(content, content_rowid)
        SELECT title || ' ' || COALESCE(description, ''), id FROM initiatives
    """))
    db.execute(text("""
        INSERT INTO search_index(content, content_rowid)
        SELECT description || ' ' || COALESCE(learning, ''), id FROM hypotheses
    """))
    db.execute(text("""
        INSERT INTO search_index(content, content_rowid)
        SELECT body || ' ' || COALESCE(title, ''), id FROM dossier_notes
    """))
    db.execute(text("""
        INSERT INTO search_index(content, content_rowid)
        SELECT name || ' ' || COALESCE(description, ''), id FROM curations
    """))
    db.execute(text("""
        INSERT INTO search_index(content, content_rowid)
        SELECT question, id FROM central_questions WHERE is_active = 1
    """))
    # Tags: tag-namen opnemen in FTS index
    db.execute(text("""
        INSERT INTO search_index(content, content_rowid)
        SELECT name, id FROM tags WHERE is_active = 1
    """))


def update_fts_initiative(db, initiative_id: str, title: str, description: str = ""):
    """Update FTS index voor een initiatief.

    Let op: deze functie commit NIET. De aanroepende code is verantwoordelijk
    voor het committen van de transactie. Dit zorgt voor atomaire updates
    waarbij FTS en brongegevens samen worden gecommittet.
    """
    _ensure_fts_table(db)
    content = f"{title} {description}".strip()
    db.execute(
        text("DELETE FROM search_index WHERE content_rowid = :rid"),
        {"rid": initiative_id},
    )
    db.execute(
        text("INSERT INTO search_index(content, content_rowid) VALUES(:content, :rid)"),
        {"content": content, "rid": initiative_id},
    )


def update_fts_hypothesis(db, hypothesis_id: str, description: str, learning: str = ""):
    """Update FTS index voor een hypothese."""
    _ensure_fts_table(db)
    content = f"{description} {learning}".strip()
    db.execute(
        text("DELETE FROM search_index WHERE content_rowid = :rid"),
        {"rid": hypothesis_id},
    )
    db.execute(
        text("INSERT INTO search_index(content, content_rowid) VALUES(:content, :rid)"),
        {"content": content, "rid": hypothesis_id},
    )


def update_fts_note(db, note_id: str, body: str, title: str = ""):
    """Update FTS index voor een dossiernotitie."""
    _ensure_fts_table(db)
    content = f"{body} {title}".strip()
    db.execute(
        text("DELETE FROM search_index WHERE content_rowid = :rid"),
        {"rid": note_id},
    )
    db.execute(
        text("INSERT INTO search_index(content, content_rowid) VALUES(:content, :rid)"),
        {"content": content, "rid": note_id},
    )


def update_fts_curation(db, curation_id: str, name: str, description: str = ""):
    """Update FTS index voor een curatie."""
    _ensure_fts_table(db)
    content = f"{name} {description}".strip()
    db.execute(
        text("DELETE FROM search_index WHERE content_rowid = :rid"),
        {"rid": curation_id},
    )
    db.execute(
        text("INSERT INTO search_index(content, content_rowid) VALUES(:content, :rid)"),
        {"content": content, "rid": curation_id},
    )


def update_fts_central_question(db, question_id: str, question: str, description: str = ""):
    """Update FTS index voor een centrale vraag."""
    _ensure_fts_table(db)
    content = f"{question} {description}".strip()
    db.execute(
        text("DELETE FROM search_index WHERE content_rowid = :rid"),
        {"rid": question_id},
    )
    db.execute(
        text("INSERT INTO search_index(content, content_rowid) VALUES(:content, :rid)"),
        {"content": content, "rid": question_id},
    )


def search(db, query: str, limit: int = 50):
    """Zoek in de FTS index. Retourneert lijst van (rowid, rank)."""
    if not query or not query.strip():
        return []

    result = db.execute(
        text("""
            SELECT content_rowid, rank FROM search_index
            WHERE search_index MATCH :query
            ORDER BY rank
            LIMIT :limit
        """),
        {"query": query, "limit": limit},
    )
    return [(row.content_rowid, row.rank) for row in result.fetchall()]
