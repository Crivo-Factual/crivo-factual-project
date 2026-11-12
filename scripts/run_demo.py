#!/usr/bin/env python3
"""Demonstração de ponta a ponta do esqueleto M1.

Lê data/examples.json, calcula os vereditos com o motor
determinístico, grava no SQLite e gera páginas estáticas em site/.
Uso: python3 scripts/run_demo.py
"""

import json
import os
import sys
import tempfile
from datetime import datetime, timezone

# A demo usa um banco temporário: nunca apaga a fila ao vivo (crivo.db).
os.environ.setdefault(
    "CRIVO_DB_PATH", os.path.join(tempfile.gettempdir(), "crivo-demo.db")
)

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from crivo import config  # noqa: E402
from crivo.factbank import store  # noqa: E402
from crivo.pipeline import publish, verdict as vmod  # noqa: E402


def main():
    with open(os.path.join(config.DATA_DIR, "examples.json"), encoding="utf-8") as fh:
        analyses = json.load(fh)
    if os.path.exists(config.DB_PATH):
        os.remove(config.DB_PATH)
    conn = store.init_db(config.DB_PATH, config.SCHEMA_PATH)
    os.makedirs(config.SITE_DIR, exist_ok=True)
    now = datetime.now(timezone.utc).isoformat()
    for analysis in analyses:
        claims = [vmod.Claim(**c) for c in analysis["claims"]]
        label, index, rule = vmod.verdict(claims)
        store.insert_publication(
            conn, analysis["id"], analysis["title"], None, now
        )
        claim_ids = {}
        for claim in claims:
            cid = store.insert_claim(
                conn, analysis["id"], claim.text, claim.weight,
                claim.central, claim.status,
            )
            claim_ids[claim.text] = cid
        for ev in analysis.get("evidences", []):
            store.insert_evidence(
                conn, claim_ids[ev["claim_text"]], ev["source_name"],
                ev.get("source_url"), ev.get("excerpt"),
            )
        store.insert_verdict(conn, analysis["id"], label, index, rule, now)
        page = publish.render_analysis(analysis, label, index, rule)
        with open(
            os.path.join(config.SITE_DIR, f"analise-{analysis['id']}.html"),
            "w", encoding="utf-8",
        ) as fh:
            fh.write(page)
        idx = f"{index:.0f}%" if index is not None else "sem índice"
        print(f"{analysis['id']}: {label} ({idx}, regra: {rule})")
    with open(
        os.path.join(config.SITE_DIR, "index.html"), "w", encoding="utf-8"
    ) as fh:
        fh.write(publish.render_index(analyses))
    conn.commit()
    conn.close()
    print(f"Páginas geradas em {config.SITE_DIR}")


if __name__ == "__main__":
    main()
