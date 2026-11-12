"""Outbox de distribuição (M4).

Cada mensagem preparada vira uma linha: pending (aguardando postagem),
sent (postada) ou skipped. A preparação é idempotente: preparar a
mesma publicação no mesmo canal duas vezes devolve a linha existente.
"""

SCHEMA = """
CREATE TABLE IF NOT EXISTS distribution (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  publication_id TEXT NOT NULL,
  channel TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'pending',
  cost_usd REAL NOT NULL DEFAULT 0,
  message TEXT NOT NULL,
  created_at TEXT NOT NULL,
  sent_at TEXT,
  CHECK (status IN ('pending', 'sent', 'skipped'))
);
"""


def init_distribution(conn):
    conn.executescript(SCHEMA)
    conn.commit()


def prepare(conn, publication_id, channel, message, cost_usd=0.0, now=None):
    """Prepara (ou reutiliza) uma mensagem. Devolve (id, criada_agora)."""
    from datetime import datetime, timezone

    row = conn.execute(
        "SELECT id FROM distribution WHERE publication_id = ? AND channel = ?"
        " AND status = 'pending'",
        (publication_id, channel),
    ).fetchone()
    if row:
        return row[0], False
    now = now or datetime.now(timezone.utc).isoformat()
    cur = conn.execute(
        "INSERT INTO distribution (publication_id, channel, cost_usd, message, created_at)"
        " VALUES (?, ?, ?, ?, ?)",
        (publication_id, channel, cost_usd, message, now),
    )
    conn.commit()
    return cur.lastrowid, True


def list_pending(conn, channel=None):
    query = (
        "SELECT id, publication_id, channel, message, created_at FROM distribution"
        " WHERE status = 'pending'"
    )
    params = []
    if channel:
        query += " AND channel = ?"
        params.append(channel)
    query += " ORDER BY id"
    rows = conn.execute(query, params).fetchall()
    return [
        {"id": r[0], "publication_id": r[1], "channel": r[2],
         "message": r[3], "created_at": r[4]}
        for r in rows
    ]


def mark_sent(conn, dist_id, now=None):
    """Marca como enviada. Devolve True se a linha existia e estava pendente."""
    from datetime import datetime, timezone

    now = now or datetime.now(timezone.utc).isoformat()
    cur = conn.execute(
        "UPDATE distribution SET status = 'sent', sent_at = ?"
        " WHERE id = ? AND status = 'pending'",
        (now, dist_id),
    )
    conn.commit()
    return cur.rowcount > 0


def prepared_on(conn, channel, date_str):
    """Quantas mensagens do canal foram preparadas nesta data (AAAA-MM-DD)."""
    row = conn.execute(
        "SELECT COUNT(*) FROM distribution WHERE channel = ?"
        " AND substr(created_at, 1, 10) = ?",
        (channel, date_str),
    ).fetchone()
    return row[0] if row else 0
