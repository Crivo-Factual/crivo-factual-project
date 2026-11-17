#!/usr/bin/env python3
"""Vereditos M3: consome a fila e publica análises.

Uso:
  python3 scripts/run_verdicts.py [--limit N] [--llm] [--loop SEGUNDOS]
  --llm usa o Groq free tier (precisa de GROQ_API_KEY); sem ele, só regras.
  --loop repete a cada N segundos (0 = uma passada).
"""

import argparse
import os
import sys
import time
from collections import Counter
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from crivo import config  # noqa: E402
from crivo.factbank import queue as queue_mod, store  # noqa: E402
from crivo.pipeline import llm as llm_mod, verdict_pipeline  # noqa: E402


def main():
    parser = argparse.ArgumentParser(description="Vereditos do Crivo Factual (M3)")
    parser.add_argument("--limit", type=int, default=10, help="itens da fila a processar")
    parser.add_argument("--llm", action="store_true",
                        help="usa o Groq free tier para extrair alegações")
    parser.add_argument(
        "--loop", type=int, default=0, metavar="SEGUNDOS",
        help="repete a cada N segundos (0 = uma passada)",
    )
    parser.add_argument(
        "--no-evidence", action="store_true",
        help="desliga a busca primária ao vivo (#47); só banco de fatos",
    )
    parser.add_argument(
        "--ml-model", default=None, metavar="PATH",
        help="modelo de ML (model.joblib) p/ suspeita de triagem; "
             "o score vai p/ o resultado e p/ a auditoria, nunca p/ o "
             "veredito. Sem ele, sem score.",
    )
    args = parser.parse_args()
    client = None
    if args.llm:
        try:
            client = llm_mod.GroqClient()
            print(f"LLM ativo: {client.model} (Groq free tier)")
        except ValueError:
            try:
                client = llm_mod.GroqClient(via_vault=True)
                print(f"LLM ativo via cofre: {client.model} (Groq free tier)")
            except ValueError as exc:
                print(f"LLM indisponível ({exc}); seguindo só com regras.")
    ml_model = None
    if args.ml_model:
        try:
            from crivo.ml.classifier import load_model
            ml_model = load_model(args.ml_model)
            print(f"ML ativo: {args.ml_model} "
                  "(suspeita de triagem, nunca veredito)")
        except ImportError as exc:
            print(f"ML indisponível ({exc}); seguindo sem score.")
        except (OSError, ValueError) as exc:
            print(f"ML indisponível ({exc}); seguindo sem score.")
    conn = store.init_db(config.DB_PATH, config.SCHEMA_PATH)
    queue_mod.init_queue(conn)
    while True:
        print(f"--- vereditos {datetime.now(timezone.utc).isoformat()} ---")
        results = verdict_pipeline.process_queue(
            conn, limit=args.limit, llm_client=client, site_dir=config.SITE_DIR,
            evidence_enabled=not args.no_evidence, ml_model=ml_model,
        )
        labels = Counter(r["verdict"][0] for r in results if "verdict" in r)
        print(f"processados: {len(results)} | vereditos: {dict(labels)}")
        for r in results:
            if "verdict" in r:
                label, index, rule = r["verdict"]
                detail = f" ({index:.0f}%, {rule})" if index is not None else f" ({rule})"
                suspicion = r.get("suspicion")
                sus_txt = (f" [suspeita {suspicion:.2f}]"
                           if suspicion is not None else "")
                print(f"  q{r['item_id']}: {label}{detail}{sus_txt}"
                      + ("" if r["published"] else " [sem página]"))
            else:
                print(f"  q{r['item_id']}: ERRO {r.get('error')}")
        if not args.loop:
            break
        try:
            time.sleep(args.loop)
        except KeyboardInterrupt:
            print("interrompido.")
            break
    conn.close()


if __name__ == "__main__":
    main()
