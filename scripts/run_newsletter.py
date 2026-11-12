#!/usr/bin/env python3
"""Boletim semanal M4: gera o resumo da semana no outbox.

Uso: python3 scripts/run_newsletter.py [--days N]
O envio por e-mail (Resend free tier) ainda não está ligado: o boletim
é gerado como arquivo, pronto para envio (ver DEVELOPMENT.md).
"""

import argparse
import os
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from crivo import config  # noqa: E402
from crivo.factbank import audit, distribution as dist, queue as queue_mod, store  # noqa: E402
from crivo.pipeline import newsletter  # noqa: E402


def main():
    parser = argparse.ArgumentParser(description="Boletim semanal do Crivo Factual (M4)")
    parser.add_argument("--days", type=int, default=7)
    args = parser.parse_args()
    conn = store.init_db(config.DB_PATH, config.SCHEMA_PATH)
    queue_mod.init_queue(conn)
    audit.init_audit(conn)
    dist.init_distribution(conn)
    digest = newsletter.build_weekly_digest(conn, days=args.days)
    outbox = os.path.join(config.ROOT, "outbox")
    os.makedirs(outbox, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    md_path = os.path.join(outbox, f"boletim-{stamp}.md")
    html_path = os.path.join(outbox, f"boletim-{stamp}.html")
    with open(md_path, "w", encoding="utf-8") as fh:
        fh.write(digest["body_md"])
    with open(html_path, "w", encoding="utf-8") as fh:
        fh.write(digest["body_html"])
    audit.log_event(conn, "newsletter_built", None, {"count": digest["count"], "days": args.days})
    conn.close()
    print(f"{digest['subject']}\nArquivos: {md_path} | {html_path}")


if __name__ == "__main__":
    main()
