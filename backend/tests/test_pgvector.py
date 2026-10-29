"""The v2 knowledge base depends on pgvector; prove it works in every environment CI covers."""

from sqlalchemy import text


def test_pgvector_nearest_neighbour_search_with_an_hnsw_index(db):
    db.execute(text("CREATE TEMP TABLE vec_probe (id int, embedding vector(3))"))
    db.execute(text("CREATE INDEX ON vec_probe USING hnsw (embedding vector_cosine_ops)"))
    db.execute(
        text("INSERT INTO vec_probe VALUES (1, '[1,0,0]'), (2, '[0,1,0]'), (3, '[0.9,0.1,0]')")
    )
    rows = db.execute(
        text(
            "SELECT id, round((1 - (embedding <=> '[1,0,0]'))::numeric, 3) AS similarity "
            "FROM vec_probe ORDER BY embedding <=> '[1,0,0]' LIMIT 2"
        )
    ).all()
    assert [r.id for r in rows] == [1, 3]
    assert float(rows[0].similarity) == 1.0
