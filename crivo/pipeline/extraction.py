"""Extração por regras (etapa 3 do pipeline, camada gratuita).

Encontra candidatos a alegações verificáveis sem modelo de linguagem:
números, valores em reais, percentuais, datas e trechos entre aspas.
Os candidatos ainda precisam de evidência (etapas 4 e 5); extração
não é veredito.
"""

import re

MONEY = re.compile(r"R\$\s?[\d\.\,]+(?:\s?(?:mil|milhões|bilhões))?")
PERCENT = re.compile(r"\d+(?:[,\.]\d+)?\s?%")
DATE = re.compile(r"\d{1,2}/\d{1,2}/\d{4}")
QUOTE = re.compile(r'"([^"]{10,200})"')


def extract_candidates(text):
    """Devolve candidatos [{text, kind}] sem duplicar pelo texto."""
    found = []
    seen = set()

    def add(kind, value):
        value = value.strip()
        if value and value not in seen:
            seen.add(value)
            found.append({"text": value, "kind": kind})

    for m in MONEY.finditer(text or ""):
        add("valor", m.group(0))
    for m in PERCENT.finditer(text or ""):
        add("percentual", m.group(0))
    for m in DATE.finditer(text or ""):
        add("data", m.group(0))
    for m in QUOTE.finditer(text or ""):
        add("citação", m.group(1))
    return found
