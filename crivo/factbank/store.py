"""Acesso ao banco de fatos (SQLite, esqueleto M1)."""

import sqlite3

from ..pipeline.evidence import fingerprint


def init_db(db_path, schema_path):
    with open(schema_path, encoding="utf-8") as fh:
        schema = fh.read()
    conn = sqlite3.connect(db_path)
    conn.executescript(schema)
    # Migração M3: coluna fingerprint em bancos criados antes dela.
    cols = [r[1] for r in conn.execute("PRAGMA table_info(claims)").fetchall()]
    if "fingerprint" not in cols:
        conn.execute("ALTER TABLE claims ADD COLUMN fingerprint TEXT")
    rows = conn.execute(
        "SELECT id, text FROM claims WHERE fingerprint IS NULL"
    ).fetchall()
    for cid, text in rows:
        conn.execute(
            "UPDATE claims SET fingerprint = ? WHERE id = ?",
            (fingerprint(text), cid),
        )
    conn.commit()
    return conn


def insert_publication(conn, pub_id, title, source_url, captured_at):
    conn.execute(
        "INSERT OR REPLACE INTO publications VALUES (?, ?, ?, ?)",
        (pub_id, title, source_url, captured_at),
    )


def insert_claim(conn, pub_id, text, weight=1, central=False, status="sem_evidencia",
                 fp=None):
    cur = conn.execute(
        "INSERT INTO claims (publication_id, text, weight, central, status, fingerprint)"
        " VALUES (?, ?, ?, ?, ?, ?)",
        (pub_id, text, weight, 1 if central else 0, status, fp or fingerprint(text)),
    )
    return cur.lastrowid


def insert_evidence(conn, claim_id, source_name, source_url, excerpt):
    conn.execute(
        "INSERT INTO evidences (claim_id, source_name, source_url, excerpt)"
        " VALUES (?, ?, ?, ?)",
        (claim_id, source_name, source_url, excerpt),
    )


def insert_verdict(conn, pub_id, label, index_value, rule, created_at, version=1):
    conn.execute(
        "INSERT INTO verdicts (publication_id, label, index_value, rule, created_at, version)"
        " VALUES (?, ?, ?, ?, ?, ?)",
        (pub_id, label, index_value, rule, created_at, version),
    )


def next_version(conn, pub_id):
    row = conn.execute(
        "SELECT MAX(version) FROM verdicts WHERE publication_id = ?", (pub_id,)
    ).fetchone()
    return (row[0] or 0) + 1


def get_verdict(conn, pub_id):
    row = conn.execute(
        "SELECT label, index_value, rule FROM verdicts"
        " WHERE publication_id = ? ORDER BY id DESC LIMIT 1",
        (pub_id,),
    ).fetchone()
    return row
