#!/usr/bin/env python3
"""Coleta M2: fontes -> triagem -> fila persistente.

Uso:
  python3 scripts/run_collectors.py            # uma passada
  python3 scripts/run_collectors.py --loop 900 # repete a cada 15 min
"""

import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from crivo import config  # noqa: E402
from crivo.factbank import queue as queue_mod, store  # noqa: E402
from crivo.pipeline import collectors, triage  # noqa: E402


def load_sources():
    with open(os.path.join(config.DATA_DIR, "sources.json"), encoding="utf-8") as fh:
        return json.load(fh)["sources"]


def run_once():
    conn = store.init_db(config.DB_PATH, config.SCHEMA_PATH)
    queue_mod.init_queue(conn)
    sources = load_sources()
    items, failures = collectors.collect_all(sources)
    for name, err in failures:
        print(f"fonte {name}: FALHOU ({err})")
    kept, dropped = triage.triage_and_filter(items)
    result = queue_mod.enqueue(conn, kept)
    print(f"coletados: {len(items)} | verificáveis: {len(kept)} | descartados: {len(dropped)}")
    print(
        f"fila: +{result['inserted']} novos, {result['duplicates']} duplicatas,"
        f" {result['dropped_backpressure']} por backpressure"
    )
    print(f"estado da fila: {queue_mod.counts(conn)}")
    for row in queue_mod.peek(conn, limit=5):
        print(f"  [{row['score']}] {row['source']}: {row['title'][:80]}")
    conn.close()
    return result


def main():
    parser = argparse.ArgumentParser(description="Coletores do Crivo Factual (M2)")
    parser.add_argument(
        "--loop", type=int, default=0, metavar="SEGUNDOS",
        help="repete a coleta a cada N segundos (0 = uma passada)",
    )
    args = parser.parse_args()
    while True:
        print(f"--- coleta {datetime.now(timezone.utc).isoformat()} ---")
        run_once()
        if not args.loop:
            break
        try:
            time.sleep(args.loop)
        except KeyboardInterrupt:
            print("interrompido.")
            break


if __name__ == "__main__":
    main()
