"""Busca no Diário Oficial da União (issue #47).

O DOU não tem API pública de consulta: o portal (in.gov.br) só
oferece a busca web. Os resultados vêm embutidos no HTML como JSON
(script `..._BuscaDouPortlet_params`, campo `jsonArray`) — é dali
que os atos saem. Três armadilhas medidas ao vivo:
- O portal devolve 403 sem o cabeçalho Accept de navegador (só o
  User-Agent não basta).
- A busca sem aspas é OU (milhões de resultados, os mais recentes
  primeiro). Com a frase exata entre aspas + sortType=1 (relevância),
  o próprio ato vem em primeiro (medido: "lei nº 14.973" -> a lei
  em 1º de 646; "emenda constitucional nº 141" -> a EC em 1º de 2).
- O título do ato vem com `<span class='highlight'>` da busca:
  limpar as tags antes de casar tipo+número.

Só biblioteca padrão.
"""

import json
import re
import urllib.error
import urllib.request
import urllib.parse

DOU_SEARCH_URL = "https://www.in.gov.br/consulta/-/buscar/dou"
DOU_ACT_URL = "https://www.in.gov.br/web/dou/-/"

# O portal bloqueia UA de biblioteca e requisição sem Accept de
# navegador (403 medido ao vivo; com esses cabeçalhos, 200).
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

_PARAMS_RE = re.compile(
    r'<script id="[^"]*BuscaDouPortlet_params" type="application/json">'
    r"(.*?)</script>",
    re.S,
)

# "LEI Nº 14.973, DE 16 DE SETEMBRO DE 2024" / "PORTARIA MF Nº 545, ..."
# / "EMENDA CONSTITUCIONAL Nº 141" (sem data no título).
_TITLE_RE = re.compile(
    r"^(EMENDA CONSTITUCIONAL|LEI COMPLEMENTAR|MEDIDA PROVISÓRIA"
    r"|INSTRUÇÃO NORMATIVA|DECRETO-LEI|LEI|DECRETO|PORTARIA|RESOLUÇÃO)"
    r"(?:\s+[A-Z]{1,6})?\s+N[ºO°]?\s*([\d.]+)"
    r"(?:.*?DE\s+(\d{4}))?\s*$",
    re.IGNORECASE,
)

_TYPE_NAMES = {
    "emenda constitucional": "Emenda Constitucional",
    "lei complementar": "Lei Complementar",
    "medida provisória": "Medida Provisória",
    "instrução normativa": "Instrução Normativa",
    "decreto-lei": "Decreto-Lei",
    "lei": "Lei",
    "decreto": "Decreto",
    "portaria": "Portaria",
    "resolução": "Resolução",
    "ec": "Emenda Constitucional",
    "mp": "Medida Provisória",
    "lc": "Lei Complementar",
}


def normalize_type(raw):
    """'EC' -> 'Emenda Constitucional'; 'lei' -> 'Lei'."""
    return _TYPE_NAMES.get((raw or "").strip().lower(), (raw or "").strip())


def format_number(number):
    """'14973' -> '14.973' (o DOU escreve o número com ponto de milhar)."""
    digits = (number or "").replace(".", "")
    if not digits.isdigit():
        return number
    out = []
    while digits:
        out.append(digits[-3:])
        digits = digits[:-3]
    return ".".join(reversed(out))


def search_url(act_type, number):
    phrase = f'"{act_type.lower()} nº {format_number(number)}"'
    return DOU_SEARCH_URL + "?q=" + urllib.parse.quote_plus(phrase) + "&publish=1&sortType=1"


def act_url(hit):
    return DOU_ACT_URL + (hit.get("url_title") or "")


def _strip_tags(text):
    return re.sub(r"<[^>]+>", "", text or "").strip()


def parse_hits(page_html):
    """Extrai a lista de atos do JSON embutido na página de busca."""
    if isinstance(page_html, bytes):
        page_html = page_html.decode("utf-8", errors="replace")
    m = _PARAMS_RE.search(page_html or "")
    if not m:
        return []
    try:
        data = json.loads(m.group(1))
    except (ValueError, TypeError):
        return []
    hits = []
    for h in data.get("jsonArray", []):
        if not isinstance(h, dict):
            continue
        hits.append({
            "title": _strip_tags(h.get("title", "")),
            "art_type": h.get("artType", ""),
            "pub_date": h.get("pubDate", ""),
            "url_title": h.get("urlTitle", ""),
            "section": h.get("pubName", ""),
            "hierarchy": h.get("hierarchyStr", ""),
        })
    return hits


def parse_act_title(title):
    """'LEI Nº 14.973, DE 16 DE SETEMBRO DE 2024' ->
    {'type': 'Lei', 'number': '14973', 'year': 2024}."""
    m = _TITLE_RE.match(_strip_tags(title))
    if not m:
        return None
    return {
        "type": normalize_type(m.group(1)),
        "number": m.group(2).replace(".", ""),
        "year": int(m.group(3)) if m.group(3) else None,
    }


def _year_from_pubdate(pub_date):
    m = re.search(r"(\d{4})\s*$", pub_date or "")
    return int(m.group(1)) if m else None


def _default_fetcher(url):
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=25) as resp:
        return resp.read()


class DouClient:
    """Consulta ao DOU pela busca web do portal (com cache por ato)."""

    def __init__(self, fetcher=None):
        self._fetch = fetcher or _default_fetcher
        self._cache = {}

    def search(self, phrase):
        """Devolve os atos da busca pela frase exata (ou [] se falhar)."""
        url = DOU_SEARCH_URL + "?q=" + urllib.parse.quote_plus(phrase) + "&publish=1&sortType=1"
        try:
            return parse_hits(self._fetch(url))
        except Exception:  # noqa: BLE001 - falha de rede nunca quebra a busca
            return []

    def find_act(self, act_type, number, year=None):
        """O ato (tipo+número+ano) no DOU, ou None. O ano, quando a
        alegação o traz, confere com o ano do título ou da publicação."""
        key = (act_type, number, year)
        if key in self._cache:
            return self._cache[key]
        phrase = f'"{act_type.lower()} nº {format_number(number)}"'
        result = None
        for hit in self.search(phrase):
            parsed = parse_act_title(hit["title"])
            if parsed is None:
                continue
            if parsed["type"] != act_type or parsed["number"] != number:
                continue
            if year is not None:
                hit_year = parsed["year"] or _year_from_pubdate(hit["pub_date"])
                if hit_year is not None and hit_year != year:
                    continue
            result = hit
            break
        self._cache[key] = result
        return result
