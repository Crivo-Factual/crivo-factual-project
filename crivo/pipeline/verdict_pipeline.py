"""Orquestração do M3: fila -> extração -> evidências -> veredito -> publicação.

Regras de segurança do pipeline:
- A primeira alegação extraída é tratada como central (heurística v0.1).
- Sem evidência, a alegação fica sem_evidencia e a trava do centro
  segura o veredito em Inconclusivo. Nada é publicado como Verdadeiro
  ou Falso sem prova.
- Sem nenhuma alegação extraível, o item sai da fila como fora de
  escopo, sem veredito e sem página.
"""

import os
from datetime import datetime, timezone

from ..factbank import audit, queue as queue_mod, store
from . import evidence, publish, verdict as vmod
from .extraction import extract_candidates
from .llm import extract_with_llm


def process_item(conn, queue_item, llm_client=None, site_dir=None):
    """Processa um item da fila e devolve o resultado do veredito."""
    text = f"{queue_item.get('title', '')} {queue_item.get('summary') or ''}".strip()
    candidates = extract_candidates(text)
    if llm_client is not None:
        candidates = candidates + extract_with_llm(text, llm_client)
    seen = set()
    unique = []
    for cand in candidates:
        if cand["text"] not in seen:
            seen.add(cand["text"])
            unique.append(cand)
    if not unique:
        queue_mod.mark_done(conn, queue_item["id"])
        conn.commit()
        return {
            "item_id": queue_item["id"],
            "verdict": ("Sem índice", None, "sem_alegacoes"),
            "claims": 0,
            "published": False,
        }
    claim_objs = []
    evidences = []
    recycled_from = None
    for i, cand in enumerate(unique):
        prev = evidence.find_previous_verdict(
            conn, evidence.fingerprint(cand["text"])
        )
        if prev:
            status = prev["status"]
            evidences.append(
                {
                    "claim_text": cand["text"],
                    "source_name": f"Verificação anterior ({prev['publication_id']})",
                    "source_url": None,
                    "excerpt": f"Veredito anterior: {prev['label']}",
                }
            )
            recycled_from = prev["publication_id"]
        else:
            status = "sem_evidencia"
        claim_objs.append(
            vmod.Claim(
                text=cand["text"],
                weight=3 if i == 0 else 1,
                central=(i == 0),
                status=status,
            )
        )
    label, index, rule = vmod.verdict(claim_objs)
    pub_id = f"q{queue_item['id']}"
    now = datetime.now(timezone.utc).isoformat()
    version = store.next_version(conn, pub_id)
    store.insert_publication(conn, pub_id, queue_item["title"], queue_item.get("url"), now)
    claim_ids = {}
    for c in claim_objs:
        claim_ids[c.text] = store.insert_claim(
            conn, pub_id, c.text, c.weight, c.central, c.status
        )
    for ev in evidences:
        store.insert_evidence(
            conn, claim_ids[ev["claim_text"]], ev["source_name"],
            ev.get("source_url"), ev.get("excerpt"),
        )
    store.insert_verdict(conn, pub_id, label, index, rule, now, version=version)
    queue_mod.mark_done(conn, queue_item["id"])
    conn.commit()
    audit.log_event(conn, "verdict", pub_id,
                    {"label": label, "index": index, "rule": rule, "version": version})
    published = False
    if site_dir:
        analysis = {
            "id": pub_id,
            "title": queue_item["title"],
            "summary": queue_item.get("summary") or "",
            "claims": [{"text": c.text, "status": c.status} for c in claim_objs],
            "evidences": evidences,
            "version": version,
            "recycled_from": recycled_from,
            "channel_summary": f"Veredito: {label}"
            + (f" ({index:.0f}%)" if index is not None else "")
            + f". {queue_item['title']}",
        }
        page = publish.render_analysis(analysis, label, index, rule)
        os.makedirs(site_dir, exist_ok=True)
        with open(
            os.path.join(site_dir, f"analise-{pub_id}.html"), "w", encoding="utf-8"
        ) as fh:
            fh.write(page)
        published = True
    return {
        "item_id": queue_item["id"],
        "publication_id": pub_id,
        "verdict": (label, index, rule),
        "claims": len(claim_objs),
        "version": version,
        "published": published,
    }


def rebuild_index(conn, site_dir):
    """Regenera o índice com todas as análises publicadas (veredito mais recente)."""
    rows = conn.execute(
        "SELECT p.id, p.title, v.label FROM publications p"
        " JOIN verdicts v ON v.publication_id = p.id"
        " WHERE v.id IN (SELECT MAX(id) FROM verdicts GROUP BY publication_id)"
        " ORDER BY v.id DESC"
    ).fetchall()
    analyses = [{"id": r[0], "title": r[1], "label": r[2]} for r in rows]
    os.makedirs(site_dir, exist_ok=True)
    with open(os.path.join(site_dir, "index.html"), "w", encoding="utf-8") as fh:
        fh.write(publish.render_index(analyses))


def process_queue(conn, limit=10, llm_client=None, site_dir=None):
    """Consome até `limit` itens da fila. Falha num item volta para a
    fila com backoff (não trava o resto)."""
    results = []
    for _ in range(limit):
        item = queue_mod.claim_next(conn)
        if item is None:
            break
        try:
            results.append(process_item(conn, item, llm_client, site_dir))
        except Exception as exc:  # noqa: BLE001 - isola a falha do item
            conn.rollback()
            queue_mod.mark_failed(conn, item["id"])
            results.append({"item_id": item["id"], "error": str(exc)})
    if site_dir and results:
        rebuild_index(conn, site_dir)
    return results
