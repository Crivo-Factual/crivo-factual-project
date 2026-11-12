#!/usr/bin/env python3
"""Distribuição M4: prepara mensagens no outbox (e publica no Instagram com --live).

Uso:
  python3 scripts/run_distribute.py [--limit N] [--list] [--mark-sent ID] [--live]
  --live publica no Instagram (precisa de IG_USER_ID e IG_ACCESS_TOKEN).
  Sem --live, nada é postado: as mensagens ficam pendentes no outbox.
"""

import argparse
import os
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from crivo import config  # noqa: E402
from crivo.factbank import audit, distribution as dist, store  # noqa: E402
from crivo.pipeline import channels, instagram as ig_mod  # noqa: E402

PRIORITY = {
    "Falso": 0,
    "Verdadeiro": 1,
    "Predominantemente verdadeiro": 2,
    "Predominantemente falso": 2,
    "Inconclusivo": 3,
}


def _x_daily_cap():
    try:
        return int(os.environ.get("X_DAILY_CAP", "3"))
    except ValueError:
        return 3


def _analysis_for(conn, pub_id, title, label, index):
    summary = ""
    image_url = ""
    if pub_id.startswith("q") and pub_id[1:].isdigit():
        row = conn.execute(
            "SELECT summary, image_url FROM queue WHERE id = ?",
            (int(pub_id[1:]),),
        ).fetchone()
        if row:
            summary, image_url = row[0] or "", row[1] or ""
    return {
        "id": pub_id, "title": title, "label": label, "index": index,
        "summary": summary, "image_url": image_url,
    }


def prepare_all(conn, limit=20):
    """Prepara mensagens dos vereditos ainda não distribuídos."""
    rows = conn.execute(
        "SELECT v.publication_id, p.title, v.label, v.index_value FROM verdicts v"
        " JOIN publications p ON p.id = v.publication_id"
        " WHERE v.id IN (SELECT MAX(id) FROM verdicts GROUP BY publication_id)"
        " ORDER BY v.id DESC"
    ).fetchall()
    rows.sort(key=lambda r: (PRIORITY.get(r[2], 3), -0))
    today = datetime.now(timezone.utc).date().isoformat()
    prepared = {"instagram": 0, "x": 0, "whatsapp": 0}
    skipped_x = 0
    for pub_id, title, label, index in rows[:limit]:
        analysis = _analysis_for(conn, pub_id, title, label, index)
        messages = channels.build_messages(analysis)
        for channel in ("instagram", "x", "whatsapp"):
            if channel == "x" and dist.prepared_on(conn, "x", today) >= _x_daily_cap():
                skipped_x += 1
                continue
            msg = messages[channel]
            _, created = dist.prepare(
                conn, pub_id, channel, msg["text"],
                cost_usd=msg.get("cost_usd", 0.0),
            )
            if created:
                prepared[channel] += 1
                audit.log_event(
                    conn, "message_prepared", pub_id,
                    {"channel": channel, "cost_usd": msg.get("cost_usd", 0.0)},
                )
    return prepared, skipped_x


def main():
    parser = argparse.ArgumentParser(description="Distribuição do Crivo Factual (M4)")
    parser.add_argument("--limit", type=int, default=20)
    parser.add_argument("--list", action="store_true", help="lista mensagens pendentes")
    parser.add_argument("--mark-sent", type=int, default=0, metavar="ID",
                        help="marca a mensagem do outbox como enviada")
    parser.add_argument("--live", action="store_true",
                        help="publica de verdade no Instagram (padrão: simulação)")
    args = parser.parse_args()
    conn = store.init_db(config.DB_PATH, config.SCHEMA_PATH)
    audit.init_audit(conn)
    dist.init_distribution(conn)
    if args.list:
        for row in dist.list_pending(conn):
            print(f"#{row['id']} [{row['channel']}] {row['publication_id']}: "
                  f"{row['message'][:80]}")
        conn.close()
        return
    if args.mark_sent:
        ok = dist.mark_sent(conn, args.mark_sent)
        if ok:
            audit.log_event(conn, "message_sent", None, {"distribution_id": args.mark_sent})
        print("marcada como enviada." if ok else "mensagem não encontrada ou já enviada.")
        conn.close()
        return
    prepared, skipped_x = prepare_all(conn, limit=args.limit)
    print(f"preparadas: {prepared} | X puladas pelo teto diário: {skipped_x}")
    if args.live:
        try:
            client = ig_mod.InstagramClient()
        except ValueError as exc:
            print(f"Instagram ao vivo indisponível ({exc})")
            conn.close()
            return
        for row in dist.list_pending(conn, channel="instagram"):
            pub_id = row["publication_id"]
            v = conn.execute(
                "SELECT p.title, v.label, v.index_value FROM verdicts v"
                " JOIN publications p ON p.id = v.publication_id"
                " WHERE v.publication_id = ? ORDER BY v.id DESC LIMIT 1",
                (pub_id,),
            ).fetchone()
            if not v:
                print(f"Instagram --live #{row['id']}: sem veredito, pulado.")
                continue
            analysis = _analysis_for(conn, pub_id, v[0], v[1], v[2])
            if not analysis["image_url"]:
                print(f"Instagram --live #{row['id']}: sem imagem pública, pulado (manual).")
                continue
            try:
                post_id = client.publish(analysis["image_url"], row["message"])
                dist.mark_sent(conn, row["id"])
                audit.log_event(conn, "message_sent", pub_id,
                                {"channel": "instagram", "post_id": post_id})
                print(f"Instagram --live #{row['id']}: publicado ({post_id}).")
            except Exception as exc:  # noqa: BLE001
                print(f"Instagram --live #{row['id']}: FALHOU ({exc})")
    conn.close()


if __name__ == "__main__":
    main()
