"""Triagem determinística (etapa 2 do pipeline).

Proxy v0.1 de viralização: recência + sinais de circulação por
palavras-chave. Não é medição real de viralização (isso exige APIs
pagas de plataformas); só ordena a fila para a extração.

Verificabilidade (M2, corrigida em 12/11/2026): só entra no
pipeline o que traz referência a proposição (título ou resumo) ou
palavra-chave política NO TÍTULO. Número, data ou citação sozinhos
NÃO bastam: a rodada de notícias de 12/11 mostrou que eles admitem
notícia de crime e local ("roubou R$ 12 mil", "70% de desconto") —
10 de 10 inconclusivos, sem fonte primária possível. Ter link
também NÃO basta: o pipeline só lê título+resumo (nunca busca o
texto completo do artigo), então um item sem conteúdo extraível no
título/resumo sempre sairia como Sem índice. A regra antiga ("link
basta") deixava entrar notícia geral sem nada checável — 100 dos
110 itens pendentes do g1 em 12/11 não tinham ref nem palavra-chave.

Prioridade (corrigida em 12/11/2026): a evidência ao vivo só prova
alegações com referência, então notícia com referência passa na
frente. Listagens cruas de proposições (fontes camara_proposicoes
e senado_tramitando) são registros de referência, não notícia: ficam
no fim da fila e só são processadas sem notícia pendente.
"""

import re
from datetime import datetime, timezone

from .extraction import PROPOSITION

KEYWORDS = [
    "bolsa família", "governo", "lula", "bolsonaro", "congresso", "senado",
    "câmara", "stf", "eleição", "imposto", "salário", "aposentadoria",
    "inss", "pix", "juros", "selic", "combustível", "escala 6x1",
    "deputado", "senador", "ministro", "plenário", "prefeito",
    "governador", "vereador", "partido", "reajuste", "orçamento",
    "fiscal", "votação", "sanção", "veto", "decreto", "polícia federal",
    "previdência",
]

# Fontes que listam proposições (título = referência ou referência +
# ementa), não notícia. São verificáveis, mas de baixo valor como
# checagem — vão para o fim da fila.
LISTING_SOURCES = {"camara_proposicoes", "senado_tramitando"}

# Título que é só a referência ("PL 05827/2026", "PL 1.454/2021") ou quase só ela.
BARE_REF = re.compile(
    r"^\s*(?:PL|PLS|PEC|MPV|PLP|PDC|PDS|RQS|REQ|MSG|VET|MSF|PRS|PLC|RIC|MSC|PAR|EMC|SBT)"
    r"\s*(?:\d{1,3}(?:\.\d{3})+|\d+)/\d{4}\s*[-–—:.]?\s*$",
    re.IGNORECASE,
)


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


def _has_ref(text):
    return bool(PROPOSITION.search(text or ""))


def _keyword_hits(text, keywords=None):
    text = (text or "").lower()
    return sum(1 for kw in (keywords or KEYWORDS) if kw in text)


def score(item, keywords=None, suspicion=None):
    """Prioridade: notícia com referência (40) > notícia política
    (10 por palavra-chave NO TÍTULO) > listagem com ementa (15) >
    ref solta (5). Soma o bônus de recência (20 <24h, 10 <72h).

    Palavras-chave contam só no título: no resumo, uma menção de
    passagem ("o governo federal informou...") inflava notícia de
    crime e local para o topo da fila.

    `suspicion` é o score do classificador de ML (0–1, probabilidade
    de o texto ser falso; ver crivo/ml). Bônus: +10 se >= 0,8, +5 se
    >= 0,6. Ele NUNCA passa na frente de um item com referência
    (40): só reordena dentro da mesma classe. None (sem modelo ou
    texto curto demais) não muda nada."""
    title = item.get("title", "") or ""
    text = f"{title} {item.get('summary', '') or ''}"
    total = 0
    if item.get("source") in LISTING_SOURCES:
        total += 5 if BARE_REF.match(title) else 15
    elif _has_ref(text):
        total += 40
    total += 10 * _keyword_hits(title, keywords)
    total += _recency_bonus(item.get("published", ""))
    if suspicion is not None:
        if suspicion >= 0.8:
            total += 10
        elif suspicion >= 0.6:
            total += 5
    return total


def triage(items, keywords=None, suspicion_for=None):
    """Devolve os itens ordenados por score, cada um com _score.
    `suspicion_for` é um callable item -> float | None (o score do
    classificador de ML); sem ele, o comportamento é o de sempre."""
    scored = []
    for item in items:
        suspicion = suspicion_for(item) if suspicion_for else None
        scored.append(dict(item, _score=score(item, keywords, suspicion)))
    scored.sort(key=lambda i: i["_score"], reverse=True)
    return scored


def is_verifiable(item):
    """True quando o título/resumo traz algo checável: referência a
    proposição ou palavra-chave política NO TÍTULO. Link sozinho não
    basta (o pipeline não lê o artigo). Número, data ou citação
    sozinhos também não: sem palavra-chave política, são notícia de
    crime ou local ("roubou R$ 12 mil", "70% de desconto") — sem
    fonte primária possível. Palavra-chave só no resumo não conta:
    é menção de passagem ("o governador lamentou...") numa notícia
    de crime ou acidente, não o assunto do item."""
    title = item.get("title", "") or ""
    text = f"{title} {item.get('summary', '') or ''}"
    if _has_ref(text):
        return True
    return _keyword_hits(title) > 0


def triage_and_filter(items, keywords=None):
    """Filtra o não verificável e ordena o resto por score.

    Devolve (mantidos, descartados).
    """
    kept, dropped = [], []
    for item in triage(items, keywords):
        (kept if is_verifiable(item) else dropped).append(item)
    return kept, dropped
