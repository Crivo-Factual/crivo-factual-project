"""Texto completo do artigo (M3, #47).

O pipeline só lia título+resumo, e a referência da proposição muitas
vezes está no corpo da matéria ("Congresso aprova projeto que autoriza
governo a usar R$ 26 bilhões...") — sem ela, a alegação central fica
sem evidência. A busca do artigo só acontece na hora do veredito (não
na coleta, para não martelar os portais): só para fontes de notícia
com link. Falha de rede nunca quebra o item — volta para
título+resumo. Só biblioteca padrão.

A extração usa HTMLParser, não regex: o g1 embute um JSON enorme num
atributo data-props, e o JSON contém `>` dentro de strings — um
regex de remoção de tags cortava a tag no meio e despejava o JSON
como texto (caso real q294: alegações "recommendationSummary",
"cropOptions", UUIDs). O parser respeita aspas nos atributos e o
JSON do atributo nunca vira texto.
"""

import html
import re
import urllib.error
import urllib.request
from html.parser import HTMLParser

NEWS_SOURCES = {"g1", "senado_noticias", "poder360"}

USER_AGENT = "CrivoFactual/0.1"
TIMEOUT_SECONDS = 15
MAX_HTML_BYTES = 500_000
MAX_CHARS = 8000

# Tags cujo conteúdo nunca é corpo de matéria.
_BLOCKED = {"script", "style", "nav", "header", "footer", "aside",
            "noscript", "svg", "form", "iframe", "template", "button"}

# Blocos que fecham um parágrafo no texto extraído.
_BLOCK_END = {"p", "div", "article", "section", "li", "h1", "h2", "h3",
              "h4", "h5", "h6", "tr", "blockquote", "figcaption"}

# Elementos vazios: não empilham (não têm fechamento).
_VOID = {"br", "img", "hr", "meta", "link", "input", "area", "base",
         "col", "embed", "source", "track", "wbr"}

# Classes/ids de widgets de cotação (o ticker de mercado do g1 vira
# alegação de número solto se entrar no texto). Token exato, não
# substring — "bolsa-família" não pode cair aqui.
_MARKET_TOKENS = {"ticker", "cotacao", "cambio", "ibovespa", "dolar",
                  "euro", "quotes", "market"}


class _TextExtractor(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts = []
        # Pilha: True no nível que deve ser ignorado (tag bloqueada ou
        # widget de mercado). O `any` diz se o texto atual é lixo.
        self._stack = []

    def _skipping(self):
        return any(self._stack)

    def _is_market(self, attrs):
        for key, value in attrs:
            if key in ("class", "id") and value:
                tokens = re.split(r"[^a-z0-9]+", value.lower())
                if _MARKET_TOKENS.intersection(tokens):
                    return True
        return False

    def handle_starttag(self, tag, attrs):
        tag = tag.lower()
        if tag in _VOID:
            if tag == "br" and not self._skipping():
                self.parts.append("\n")
            return
        self._stack.append(tag in _BLOCKED or self._is_market(attrs))

    def handle_endtag(self, tag):
        tag = tag.lower()
        if self._stack:
            self._stack.pop()
        if not self._skipping() and tag in _BLOCK_END:
            self.parts.append("\n")

    def handle_data(self, data):
        if self._skipping():
            return
        text = data.strip()
        if text:
            self.parts.append(text + " ")

    def handle_startendtag(self, tag, attrs):
        if tag.lower() == "br" and not self._skipping():
            self.parts.append("\n")


def html_to_text(page_html):
    """Extrai o texto legível de uma página HTML (sem dependências)."""
    parser = _TextExtractor()
    try:
        parser.feed(page_html or "")
        parser.close()
    except Exception:  # noqa: BLE001 - HTML malformado não quebra a extração
        pass
    text = "".join(parser.parts)
    text = html.unescape(text)
    lines = [re.sub(r"\s+", " ", line).strip() for line in text.splitlines()]
    return "\n".join(line for line in lines if line)


def _default_fetcher(url):
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=TIMEOUT_SECONDS) as resp:
        return resp.read(MAX_HTML_BYTES + 1)


def fetch_article_text(url, fetcher=None, max_chars=MAX_CHARS):
    """Devolve o texto do artigo (no máximo `max_chars` caracteres).
    Qualquer falha (rede, 403, página vazia) devolve '' — o pipeline
    segue só com título+resumo."""
    if not url:
        return ""
    try:
        raw = (fetcher or _default_fetcher)(url)
        if isinstance(raw, bytes):
            raw = raw.decode("utf-8", errors="replace")
        text = html_to_text(raw)
    except Exception:  # noqa: BLE001 - falha de rede nunca quebra o item
        return ""
    return text[:max_chars].strip()


def get_item_text(queue_item, fetcher=None):
    """Texto que o pipeline extrai alegações: título + resumo + corpo
    do artigo (só para fonte de notícia com link). O título vem
    primeiro para a ref dele continuar sendo a central (heurística
    v0.1)."""
    base = f"{queue_item.get('title', '')} {queue_item.get('summary') or ''}".strip()
    if queue_item.get("source") not in NEWS_SOURCES:
        return base
    article = fetch_article_text(queue_item.get("url") or "", fetcher=fetcher)
    if not article:
        return base
    return f"{base}\n{article}"
