"""Triagem determinística (etapa 2 do pipeline).

Proxy v0.1 de viralização: recência + sinais de circulação por
palavras-chave. Não é medição real de viralização (isso exige APIs
pagas de plataformas); só ordena a fila para a extração.

Verificabilidade (M2): só entra no pipeline o que pode ser checado —
tem link para a fonte (o texto completo será extraído depois) ou já
traz no título/resumo algo verificável (número, data, citação).
"""

from datetime import datetime, timezone

from .extraction import extract_candidates

KEYWORDS = [
    "bolsa família", "governo", "lula", "bolsonaro", "congresso", "senado",
    "câmara", "stf", "eleição", "imposto", "salário", "aposentadoria",
    "inss", "pix", "juros", "selic", "combustível", "escala 6x1",
]


def _recency_bonus(published):
    if not published:
        return 0
    for fmt in ("%a, %d %b %Y %H:%M:%S %z", "%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%d"):
        try:
            dt = datetime.strptime(published.strip(), fmt)
            break
        except ValueError:
            continue
    else:
        return 0
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    hours = (datetime.now(timezone.utc) - dt).total_seconds() / 3600
    if hours < 0:
        return 20
    if hours <= 24:
        return 20
    if hours <= 72:
        return 10
    return 0


def score(item, keywords=None):
    text = f"{item.get('title', '')} {item.get('summary', '')}".lower()
    kws = keywords or KEYWORDS
    hits = sum(1 for kw in kws if kw in text)
    return 10 * hits + _recency_bonus(item.get("published", ""))


def triage(items, keywords=None):
    """Devolve os itens ordenados por score, cada um com _score."""
    scored = [dict(item, _score=score(item, keywords)) for item in items]
    scored.sort(key=lambda i: i["_score"], reverse=True)
    return scored


def is_verifiable(item):
    """True quando o item pode ser checado (link ou conteúdo verificável)."""
    if item.get("link"):
        return True
    text = f"{item.get('title', '')} {item.get('summary', '')}"
    return bool(extract_candidates(text))


def triage_and_filter(items, keywords=None):
    """Filtra o não verificável e ordena o resto por score.

    Devolve (mantidos, descartados).
    """
    kept, dropped = [], []
    for item in triage(items, keywords):
        (kept if is_verifiable(item) else dropped).append(item)
    return kept, dropped
