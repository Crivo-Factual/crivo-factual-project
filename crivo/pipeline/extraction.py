"""Extração por regras (etapa 3 do pipeline, camada gratuita).

Encontra candidatos a alegações verificáveis sem modelo de linguagem:
números, valores em reais, percentuais, datas, trechos entre aspas e
referências a proposições (PL, PEC, MPV etc.). Uma referência a
proposição é verificável: ela pode ser conferida no registro oficial.
Os candidatos ainda precisam de evidência (etapas 4 e 5); extração
não é veredito.
"""

import re

MONEY = re.compile(r"R\$\s?[\d\.\,]+(?:\s?(?:mil|milhões|bilhões))?")
PERCENT = re.compile(r"\d+(?:[,\.]\d+)?\s?%")
DATE = re.compile(r"\d{1,2}/\d{1,2}/\d{4}")
QUOTE = re.compile(r'"([^"]{10,200})"')
PROPOSITION = re.compile(
    r"\b(?:PL|PLS|PEC|MPV|PLP|PDC|PDS|RQS|REQ|MSG|VET|MSF|PRS|PLC|RIC|MSC|PAR|EMC|SBT)\s*\d+/\d{4}\b"
)


def extract_candidates(text):
    """Devolve candidatos [{text, kind}] sem duplicar pelo texto.

    Ordem: a proposição vem primeiro — é a alegação mais verificável
    (tem registro oficial) e vira a central no pipeline (#47). Um
    número solto ("50%") sem contexto quase nunca é verificável
    sozinho e não deve ser a central quando há uma proposição.
    """
    found = []
    seen = set()

    def add(kind, value):
        value = value.strip()
        if value and value not in seen:
            seen.add(value)
            found.append({"text": value, "kind": kind})

    for m in PROPOSITION.finditer(text or ""):
        add("proposição", m.group(0))
    for m in MONEY.finditer(text or ""):
        add("valor", m.group(0))
    for m in PERCENT.finditer(text or ""):
        add("percentual", m.group(0))
    for m in DATE.finditer(text or ""):
        add("data", m.group(0))
    for m in QUOTE.finditer(text or ""):
        add("citação", m.group(1))
    return found
