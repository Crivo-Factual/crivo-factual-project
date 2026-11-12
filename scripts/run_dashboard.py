#!/usr/bin/env python3
"""Dashboard M4: gera site/dashboard.html a partir do banco.

Uso: python3 scripts/run_dashboard.py
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from crivo import config  # noqa: E402
from crivo.factbank import audit, distribution as dist, queue as queue_mod, store  # noqa: E402
from crivo.pipeline import dashboard  # noqa: E402


def main():
    conn = store.init_db(config.DB_PATH, config.SCHEMA_PATH)
    queue_mod.init_queue(conn)
    audit.init_audit(conn)
    dist.init_distribution(conn)
    html = dashboard.build_dashboard(conn)
    os.makedirs(config.SITE_DIR, exist_ok=True)
    path = os.path.join(config.SITE_DIR, "dashboard.html")
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(html)
    conn.close()
    print(f"Dashboard gerado em {path}")


if __name__ == "__main__":
    main()
