#!/usr/bin/env python3
"""Sonda de cobertura das fontes candidatas (issue #47).

Mede, sobre as alegações já extraídas (tabela claims) e, como proxy,
sobre os títulos dos itens pendentes, quantos itens/alegações cada
fonte candidata conseguiria responder. Padrões conservadores: a
alegação só conta como coberta se carregar informação suficiente para
formar uma consulta determinística naquela fonte.

Uso: python3 /tmp/probe_coverage.py
"""

import json
import re
import sqlite3
import unicodedata

DB = "/home/hatch/workspace/crivo/crivo-skeleton/crivo.db"

REF = re.compile(
    r"\b(PL|PLP|PEC|REQ|RQS|RIC|MSC|PAR|EMC|SBT)\s*\d{1,5}(?:/\d{4})?\b", re.I
)
NUM = re.compile(r"\d+(?:[.,]\d+)?\s*(?:%|milhões|bilhões|mil\b|R\$)?")


def norm(text):
    text = unicodedata.normalize("NFKD", text or "").encode("ascii", "ignore").decode()
    return text.lower()


def has(text, *words):
    t = norm(text)
    return any(re.search(r"\b" + re.escape(w) + r"\b", t) for w in words)


def classify(text):
    """Devolve o conjunto de fontes que poderiam responder a alegação."""
    t = norm(text)
    out = set()
    if REF.search(text):
        out.add("proposicao")  # Câmara/Senado — já existe
    if has(text, "sancionad", "promulgad", "decreto", "diario oficial",
           "entrou em vigor", "lei nº", "lei n.", "lei federal"):
        out.add("dou")
    if has(text, "ipca", "selic", "dolar", "pib", "desemprego", "inflacao",
           "taxa de juros", "taxa basica", "cambio", "igp-m", "pnad") and NUM.search(text):
        out.add("indicador")  # BCB SGS / IBGE SIDRA
    if has(text, "votou", "votaram", "votacao", "voto favoravel", "voto contrario"):
        out.add("votacao")
    if has(text, "eleicao", "eleicoes", "eleito", "eleita", "urna",
           "votos validos", "tse", "segundo turno", "primeiro turno"):
        out.add("tse")
    # Índice local de ementas: verbo de status + assunto, sem nº da proposição
    if (has(text, "aprovou", "aprovada", "aprovado", "rejeitou", "rejeitada",
            "rejeitado", "sancionou") and not REF.search(text) and len(t) > 20):
        out.add("ementa")
    return out


def is_residual(text):
    """Alegação sem consulta possível em fonte estruturada."""
    t = norm(text).strip()
    if re.fullmatch(r"[r$\s\d.,%]+", t) and NUM.search(t):
        return "numero_solto"
    if has(text, "disse", "afirmou", "declarou", "segundo ", "de acordo com"):
        return "citacao"
    if has(text, "anunciou", "apresentou", "lancou", "propos", "defendeu"):
        return "anuncio_sem_ref"
    return None


def main():
    conn = sqlite3.connect(DB)
    rows = conn.execute(
        "SELECT publication_id, text, status FROM claims"
    ).fetchall()
    verdicts = dict(conn.execute(
        "SELECT publication_id, label FROM verdicts"
    ).fetchall())
    pending = conn.execute(
        "SELECT title FROM queue WHERE status='pending'"
    ).fetchall()

    sources = ["proposicao", "dou", "indicador", "votacao", "tse", "ementa"]
    claim_hits = {s: 0 for s in sources}
    item_hits = {s: set() for s in sources}
    residual = {}
    items = {}
    for pub, text, _status in rows:
        hits = classify(text)
        for s in hits:
            claim_hits[s] += 1
            item_hits[s].add(pub)
        items.setdefault(pub, []).append((text, hits))
        r = is_residual(text)
        if r:
            residual[r] = residual.get(r, 0) + 1

    n_items = len(items)
    n_claims = len(rows)
    new_sources = ["dou", "indicador", "votacao", "tse", "ementa"]
    coverable_any_new = set().union(*(item_hits[s] for s in new_sources))
    coverable_proposicao = item_hits["proposicao"]
    coverable_all = coverable_any_new | coverable_proposicao
    inconclusivo = {p for p, v in verdicts.items() if v == "Inconclusivo"}
    inconclusivo_coverable = inconclusivo & coverable_all

    # Proxy: mesmos padrões sobre os títulos pendentes
    title_hits = {s: 0 for s in sources}
    for (title,) in pending:
        for s in classify(title):
            title_hits[s] += 1
    n_pending = len(pending)

    result = {
        "amostra": {
            "alegacoes": n_claims,
            "itens_com_alegacoes": n_items,
            "vereditos_inconclusivos": len(inconclusivo),
            "itens_pendentes_titulos": n_pending,
        },
        "por_fonte_alegacoes": claim_hits,
        "por_fonte_itens": {s: len(item_hits[s]) for s in sources},
        "por_fonte_itens_pct": {
            s: round(100 * len(item_hits[s]) / n_items, 1) for s in sources
        },
        "itens_cobertos_nova_fonte": len(coverable_any_new),
        "itens_cobertos_qualquer_fonte": len(coverable_all),
        "itens_cobertos_qualquer_fonte_pct": round(100 * len(coverable_all) / n_items, 1),
        "inconclusivos_que_virariam_cobertos": len(inconclusivo_coverable),
        "inconclusivos_pct": round(100 * len(inconclusivo_coverable) / max(len(inconclusivo), 1), 1),
        "residuo_alegacoes": residual,
        "proxy_titulos_pendentes": title_hits,
        "proxy_titulos_pendentes_pct": {
            s: round(100 * title_hits[s] / max(n_pending, 1), 1) for s in sources
        },
    }
    print(json.dumps(result, indent=2, ensure_ascii=False))
    with open("/tmp/coverage_result.json", "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)


if __name__ == "__main__":
    main()
