"""Log imutável com encadeamento por hash (M4).

Cada evento registra o hash do anterior: qualquer alteração num
registro antigo quebra a cadeia e é detectada por verify_chain.
"""

import hashlib
import json
from datetime import datetime, timezone

SCHEMA = """
CREATE TABLE IF NOT EXISTS audit_log (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  ts TEXT NOT NULL,
  event TEXT NOT NULL,
  publication_id TEXT,
  details TEXT,
  prev_hash TEXT NOT NULL DEFAULT '',
  hash TEXT NOT NULL
);
"""


def init_audit(conn):
    conn.executescript(SCHEMA)
    conn.commit()


def log_event(conn, event, publication_id=None, details=None, ts=None):
    """Registra um evento e devolve o hash do registro."""
    init_audit(conn)  # garante a tabela (vereditos rodam sem init explícito)
    prev = conn.execute(
        "SELECT hash FROM audit_log ORDER BY id DESC LIMIT 1"
    ).fetchone()
    prev_hash = prev[0] if prev else ""
    ts = ts or datetime.now(timezone.utc).isoformat()
    details = details or {}
    payload = json.dumps(
        {
            "ts": ts,
            "event": event,
            "publication_id": publication_id,
            "details": details,
            "prev_hash": prev_hash,
        },
        sort_keys=True,
        ensure_ascii=False,
    )
    h = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    conn.execute(
        "INSERT INTO audit_log (ts, event, publication_id, details, prev_hash, hash)"
        " VALUES (?, ?, ?, ?, ?, ?)",
        (ts, event, publication_id, json.dumps(details, ensure_ascii=False),
         prev_hash, h),
    )
    conn.commit()
    return h


def verify_chain(conn):
    """True quando nenhum registro foi alterado desde o registro."""
    row = conn.execute(
        "SELECT COUNT(*) FROM sqlite_master WHERE type = 'table' AND name = 'audit_log'"
    ).fetchone()
    if not row[0]:
        return True  # sem tabela, sem eventos: cadeia vazia é válida
    rows = conn.execute(
        "SELECT ts, event, publication_id, details, prev_hash, hash"
        " FROM audit_log ORDER BY id"
    ).fetchall()
    prev = ""
    for ts, event, pub, details, prev_hash, h in rows:
        if prev_hash != prev:
            return False
        payload = json.dumps(
            {
                "ts": ts,
                "event": event,
                "publication_id": pub,
                "details": json.loads(details),
                "prev_hash": prev_hash,
            },
            sort_keys=True,
            ensure_ascii=False,
        )
        if hashlib.sha256(payload.encode("utf-8")).hexdigest() != h:
            return False
        prev = h
    return True
