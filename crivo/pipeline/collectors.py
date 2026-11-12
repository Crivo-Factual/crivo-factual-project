"""Coletores de fontes gratuitas (etapa 1 do pipeline, M2).

Fontes registradas em data/sources.json, verificadas ao vivo em
12/11/2026. Nenhuma fonte exige chave. Falha de uma fonte nunca derruba
a coleta das demais: o erro é registrado e a fonte é pulada.
"""

import json
import urllib.request
import xml.etree.ElementTree as ET

USER_AGENT = "CrivoFactual/0.1"
MAX_ITEMS_PER_SOURCE = 50


def _get(url, timeout=20):
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read()


def _text(parent, tag):
    child = parent.find(tag)
    return (child.text or "").strip() if child is not None else ""


def parse_rss(raw):
    """Extrai itens de um feed RSS ou Atom."""
    root = ET.fromstring(raw)
    items = []
    for el in root.iter("item"):  # RSS
        items.append(
            {
                "title": _text(el, "title"),
                "link": _text(el, "link"),
                "published": _text(el, "pubDate"),
                "summary": _text(el, "description"),
                "image_url": _media_url(el),
            }
        )
    for el in root.iter("{http://www.w3.org/2005/Atom}entry"):  # Atom
        link = ""
        for ln in el.findall("{http://www.w3.org/2005/Atom}link"):
            if ln.get("rel", "alternate") == "alternate":
                link = ln.get("href", "")
        items.append(
            {
                "title": _text(el, "{http://www.w3.org/2005/Atom}title"),
                "link": link,
                "published": _text(el, "{http://www.w3.org/2005/Atom}updated"),
                "summary": _text(el, "{http://www.w3.org/2005/Atom}summary"),
                "image_url": _media_url(el),
            }
        )
    return items


def _media_url(el):
    """URL da imagem do item, quando o feed a traz (media:content,
    media:thumbnail ou enclosure de imagem). Senão, string vazia."""
    for tag in (
        "{http://search.yahoo.com/mrss/}content",
        "{http://search.yahoo.com/mrss/}thumbnail",
    ):
        child = el.find(tag)
        if child is not None and child.get("url"):
            return child.get("url")
    enc = el.find("enclosure")
    if enc is not None and (enc.get("type") or "").startswith("image"):
        return enc.get("url") or ""
    for ln in el.findall("{http://www.w3.org/2005/Atom}link"):
        if ln.get("rel") == "enclosure" and (ln.get("type") or "").startswith("image"):
            return ln.get("href") or ""
    return ""


def fetch_rss(url, timeout=20):
    """Baixa um feed RSS/Atom e devolve itens {title, link, published, summary}."""
    return parse_rss(_get(url, timeout))


def parse_camara_proposicoes(data):
    """Adapta a resposta JSON da API de dados abertos da Câmara."""
    items = []
    for prop in data.get("dados", []):
        ementa = (prop.get("ementa") or "").strip()
        sigla = prop.get("siglaTipo", "")
        numero = prop.get("numero", "")
        ano = prop.get("ano", "")
        title = f"{sigla} {numero}/{ano} — {ementa[:120]}".strip(" —")
        items.append(
            {
                "title": title,
                "link": prop.get("uri") or "",
                "published": prop.get("dataApresentacao", ""),
                "summary": ementa,
                "image_url": "",
            }
        )
    # Mais recentes primeiro (datas ISO ordenam como texto).
    items.sort(key=lambda i: (bool(i["published"]), i["published"]), reverse=True)
    return items


def parse_senado_materias(raw):
    """Adapta a resposta XML da API de dados abertos do Senado.

    O link público não vem na resposta, então fica vazio: a matéria é
    identificada pelo código no resumo e a dedup é por hash de conteúdo.
    """
    root = ET.fromstring(raw)
    items = []
    for mat in root.iter("Materia"):
        def find(tag):
            el = mat.find(f".//{tag}")
            return (el.text or "").strip() if el is not None else ""

        sigla = find("SiglaSubtipoMateria")
        numero = find("NumeroMateria")
        ano = find("AnoMateria")
        ementa = find("EmentaMateria")
        codigo = find("CodigoMateria")
        title = f"{sigla} {numero}/{ano} — {ementa[:120]}".strip(" —")
        if not title:
            continue
        items.append(
            {
                "title": title,
                "link": "",
                "published": find("DataApresentacao"),
                "summary": f"Matéria {codigo}: {ementa}" if codigo else ementa,
                "image_url": "",
            }
        )
    # Mais recentes primeiro (datas ISO ordenam como texto).
    items.sort(key=lambda i: (bool(i["published"]), i["published"]), reverse=True)
    return items


def collect_source(source):
    """Coleta uma fonte do registro. Devolve (itens, erro ou None)."""
    kind = source.get("kind")
    url = source.get("url", "")
    try:
        if kind == "rss":
            items = fetch_rss(url)
        elif kind == "camara_api":
            items = parse_camara_proposicoes(json.loads(_get(url).decode("utf-8")))
        elif kind == "senado_api":
            items = parse_senado_materias(_get(url))
        else:
            return [], f"tipo desconhecido: {kind}"
    except Exception as exc:  # noqa: BLE001 - falha isolada por fonte
        return [], f"{type(exc).__name__}: {exc}"
    for item in items:
        item["source"] = source.get("name", "")
    return items[:MAX_ITEMS_PER_SOURCE], None


def collect_all(sources):
    """Coleta todas as fontes. Devolve (itens, falhas[(nome, erro)])."""
    items, failures = [], []
    for source in sources:
        got, err = collect_source(source)
        if err:
            failures.append((source.get("name", "?"), err))
        else:
            items.extend(got)
    return items, failures
