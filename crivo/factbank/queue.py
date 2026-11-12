"""Fila persistente do pipeline (M2, SQLite).

Estados: pending -> processing -> done | failed.
Falha volta para pending com backoff exponencial (60s, 2m, 4m, 8m, 16m,
teto de 1h); após 5 tentativas o item fica failed e não é mais retomado.
Backpressure: a fila não cresce além de MAX_PENDING itens pendentes;
quando cheia, novos itens são descartados e contados.
"""

import hashlib
import sqlite3
from datetime import datetime, timedelta, timezone

MAX_PENDING = 500
MAX_ATTEMPTS = 5
BASE_RETRY_SECONDS = 60
MAX_RETRY_SECONDS = 3600

SCHEMA = """
CREATE TABLE IF NOT EXISTS queue (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  source TEXT NOT NULL,
  url TEXT,
  title TEXT NOT NULL,
  summary TEXT,
  image_url TEXT NOT NULL DEFAULT '',
  published_at TEXT,
  score INTEGER NOT NULL DEFAULT 0,
  content_hash TEXT NOT NULL UNIQUE,
  status TEXT NOT NULL DEFAULT 'pending',
  attempts INTEGER NOT NULL DEFAULT 0,
  next_retry_at TEXT,
  created_at TEXT NOT NULL,
  CHECK (status IN ('pending', 'processing', 'done', 'failed'))
);
"""


def init_queue(conn):
    conn.executescript(SCHEMA)
    cols = [r[1] for r in conn.execute("PRAGMA table_info(queue)").fetchall()]
    if "image_url" not in cols:
        conn.execute("ALTER TABLE queue ADD COLUMN image_url TEXT NOT NULL DEFAULT ''")
    conn.commit()


def content_hash(source, title, link=""):
    raw = f"{source}|{title}|{link or ''}".encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def enqueue(conn, items, now=None, max_pending=MAX_PENDING):
    """Insere itens na fila.

    Devolve {inserted, duplicates, dropped_backpressure}.
    """
    now = now or datetime.now(timezone.utc).isoformat()
    pending = counts(conn).get("pending", 0)
    inserted = duplicates = dropped = 0
    for item in items:
        if pending + inserted >= max_pending:
            dropped += 1
            continue
        try:
            conn.execute(
                "INSERT INTO queue (source, url, title, summary, image_url,"
                " published_at, score, content_hash, created_at)"
                " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    item.get("source", ""),
                    item.get("link") or None,
                    item.get("title", ""),
                    item.get("summary", ""),
                    item.get("image_url", ""),
                    item.get("published", ""),
                    item.get("_score", 0),
                    content_hash(
                        item.get("source", ""),
                        item.get("title", ""),
                        item.get("link") or "",
                    ),
                    now,
                ),
            )
            inserted += 1
        except sqlite3.IntegrityError:
            duplicates += 1
    conn.commit()
    return {
        "inserted": inserted,
        "duplicates": duplicates,
        "dropped_backpressure": dropped,
    }


def claim_next(conn, now=None):
    """Retira o próximo item pendente (maior score, mais antigo).

    Marca como processing e devolve o item, ou None se não há nada pronto.
    """
    now = now or datetime.now(timezone.utc).isoformat()
    row = conn.execute(
        "SELECT id, source, url, title, summary, image_url, published_at, score, attempts"
        " FROM queue WHERE status = 'pending'"
        " AND (next_retry_at IS NULL OR next_retry_at <= ?)"
        " ORDER BY score DESC, created_at ASC LIMIT 1",
        (now,),
    ).fetchone()
    if row is None:
        return None
    conn.execute("UPDATE queue SET status = 'processing' WHERE id = ?", (row[0],))
    conn.commit()
    keys = ("id", "source", "url", "title", "summary", "image_url", "published_at", "score", "attempts")
    return dict(zip(keys, row))


def mark_done(conn, item_id):
    conn.execute("UPDATE queue SET status = 'done' WHERE id = ?", (item_id,))
    conn.commit()


def mark_failed(conn, item_id, now=None, base=BASE_RETRY_SECONDS, cap=MAX_RETRY_SECONDS):
    """Registra falha com backoff. Devolve (tentativas, próximo retry ou None)."""
    now_dt = datetime.fromisoformat(now) if now else datetime.now(timezone.utc)
    row = conn.execute("SELECT attempts FROM queue WHERE id = ?", (item_id,)).fetchone()
    attempts = (row[0] if row else 0) + 1
    if attempts >= MAX_ATTEMPTS:
        conn.execute(
            "UPDATE queue SET status = 'failed', attempts = ? WHERE id = ?",
            (attempts, item_id),
        )
        conn.commit()
        return attempts, None
    delay = min(base * (2 ** (attempts - 1)), cap)
    nxt = (now_dt + timedelta(seconds=delay)).isoformat()
    conn.execute(
        "UPDATE queue SET status = 'pending', attempts = ?, next_retry_at = ?"
        " WHERE id = ?",
        (attempts, nxt, item_id),
    )
    conn.commit()
    return attempts, nxt


def counts(conn):
    rows = conn.execute("SELECT status, COUNT(*) FROM queue GROUP BY status").fetchall()
    return {status: n for status, n in rows}


def peek(conn, limit=10):
    rows = conn.execute(
        "SELECT id, source, title, score FROM queue WHERE status = 'pending'"
        " ORDER BY score DESC, created_at ASC LIMIT ?",
        (limit,),
    ).fetchall()
    return [{"id": r[0], "source": r[1], "title": r[2], "score": r[3]} for r in rows]
