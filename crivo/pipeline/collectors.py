"""Coletor RSS via biblioteca padrão (sem dependências externas).

Etapa 1 do pipeline: captura. Só lê feeds públicos (RSS/Atom).
"""

import urllib.request
import xml.etree.ElementTree as ET


def fetch_rss(url, timeout=20):
    """Baixa um feed RSS/Atom e devolve itens {title, link, published, summary}."""
    req = urllib.request.Request(url, headers={"User-Agent": "CrivoFactual/0.1"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        raw = resp.read()
    root = ET.fromstring(raw)
    items = []
    for el in root.iter("item"):  # RSS
        items.append(
            {
                "title": _text(el, "title"),
                "link": _text(el, "link"),
                "published": _text(el, "pubDate"),
                "summary": _text(el, "description"),
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
            }
        )
    return items


def _text(parent, tag):
    child = parent.find(tag)
    return (child.text or "").strip() if child is not None else ""
