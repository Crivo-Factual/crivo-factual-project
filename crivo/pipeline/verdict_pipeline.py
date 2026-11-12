"""Orquestração do M3: fila -> extração -> evidências -> veredito -> publicação.

Regras de segurança do pipeline:
- A alegação central é a mais verificável, não a primeira do texto
  (heurística v0.1 era "a primeira é a central"): proposição, ato do
  DOU, afirmação do LLM ou citação — número, valor e data soltos
  nunca são central (caso real: "12/11/2026" virou central e travou
  o veredito em Inconclusivo). Ver choose_central_index.
- Sem evidência, a alegação fica sem_evidencia e a trava do centro
  segura o veredito em Inconclusivo. Nada é publicado como Verdadeiro
  ou Falso sem prova.
- Sem nenhuma alegação extraível, o item sai da fila como fora de
  escopo, sem veredito e sem página.
- Sem veredito anterior, a busca primária ao vivo (#47) tenta a prova
  nas APIs de dados abertos da Câmara e do Senado (ver
  `evidence_search.py`). Sem prova, sem_evidencia.
"""

import os
from datetime import datetime, timezone

from ..factbank import audit, queue as queue_mod, store
from . import article as article_mod
from . import evidence, evidence_search, publish, verdict as vmod
from .extraction import extract_candidates
from .llm import extract_with_llm


def choose_central_index(unique, rules_texts):
    """Índice da alegação central.

    Ordem: (1) proposição ou ato do DOU — têm registro oficial;
    (2) a primeira afirmação do LLM — o prompt exige sujeito,
    predicado e valor, então é uma alegação de verdade (o `kind` que
    o modelo devolve não é confiável, por isso a origem é o texto:
    tudo que não veio das regras veio do LLM); (3) citação; (4) o
    primeiro candidato, só quando não há mais nada — valor,
    percentual e data soltos nunca são central se houver alternativa.
    """
    for i, cand in enumerate(unique):
        if cand.get("kind") in ("proposição", "ato"):
            return i
    for i, cand in enumerate(unique):
        if cand["text"] not in rules_texts:
            return i
    for i, cand in enumerate(unique):
        if cand.get("kind") == "citação":
            return i
    return 0


def process_item(conn, queue_item, llm_client=None, site_dir=None,
                 searcher=None, evidence_enabled=True, article_fetcher=None):
    """Processa um item da fila e devolve o resultado do veredito."""
    text = article_mod.get_item_text(queue_item, fetcher=article_fetcher)
    rules = extract_candidates(text)
    llm_claims = (
        extract_with_llm(text, llm_client) if llm_client is not None else []
    )
    candidates = rules + llm_claims
    rules_texts = {cand["text"] for cand in rules}
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
    central_idx = choose_central_index(unique, rules_texts)
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
            if evidence_enabled:
                ev = (searcher or evidence_search.Searcher()).search_claim(cand["text"])
                if ev:
                    status = ev["status"]
                    evidences.append(
                        {
                            "claim_text": cand["text"],
                            "source_name": ev["source_name"],
                            "source_url": ev.get("source_url"),
                            "excerpt": ev.get("excerpt"),
                        }
                    )
        claim_objs.append(
            vmod.Claim(
                text=cand["text"],
                weight=3 if i == central_idx else 1,
                central=(i == central_idx),
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


def process_queue(conn, limit=10, llm_client=None, site_dir=None,
                  evidence_enabled=True, searcher=None, article_fetcher=None):
    """Consome até `limit` itens da fila. Falha num item volta para a
    fila com backoff (não trava o resto)."""
    if evidence_enabled and searcher is None:
        searcher = evidence_search.Searcher()
    results = []
    for _ in range(limit):
        item = queue_mod.claim_next(conn)
        if item is None:
            break
        try:
            results.append(process_item(conn, item, llm_client, site_dir,
                                        searcher=searcher,
                                        evidence_enabled=evidence_enabled,
                                        article_fetcher=article_fetcher))
        except Exception as exc:  # noqa: BLE001 - isola a falha do item
            conn.rollback()
            queue_mod.mark_failed(conn, item["id"])
            results.append({"item_id": item["id"], "error": str(exc)})
    if site_dir and results:
        rebuild_index(conn, site_dir)
    return results
