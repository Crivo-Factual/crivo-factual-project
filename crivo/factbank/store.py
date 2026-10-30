"""Acesso ao banco de fatos (SQLite, esqueleto M1)."""

import sqlite3


def init_db(db_path, schema_path):
    with open(schema_path, encoding="utf-8") as fh:
        schema = fh.read()
    conn = sqlite3.connect(db_path)
    conn.executescript(schema)
    conn.commit()
    return conn


def insert_publication(conn, pub_id, title, source_url, captured_at):
    conn.execute(
        "INSERT OR REPLACE INTO publications VALUES (?, ?, ?, ?)",
        (pub_id, title, source_url, captured_at),
    )


def insert_claim(conn, pub_id, text, weight=1, central=False, status="sem_evidencia"):
    cur = conn.execute(
        "INSERT INTO claims (publication_id, text, weight, central, status)"
        " VALUES (?, ?, ?, ?, ?)",
        (pub_id, text, weight, 1 if central else 0, status),
    )
    return cur.lastrowid


def insert_evidence(conn, claim_id, source_name, source_url, excerpt):
    conn.execute(
        "INSERT INTO evidences (claim_id, source_name, source_url, excerpt)"
        " VALUES (?, ?, ?, ?)",
        (claim_id, source_name, source_url, excerpt),
    )


def insert_verdict(conn, pub_id, label, index_value, rule, created_at):
    conn.execute(
        "INSERT INTO verdicts (publication_id, label, index_value, rule, created_at)"
        " VALUES (?, ?, ?, ?, ?)",
        (pub_id, label, index_value, rule, created_at),
    )


def get_verdict(conn, pub_id):
    row = conn.execute(
        "SELECT label, index_value, rule FROM verdicts"
        " WHERE publication_id = ? ORDER BY id DESC LIMIT 1",
        (pub_id,),
    ).fetchone()
    return row
