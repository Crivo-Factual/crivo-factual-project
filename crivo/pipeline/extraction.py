"""Extração por regras (etapa 3 do pipeline, camada gratuita).

Encontra candidatos a alegações verificáveis sem modelo de linguagem:
números, valores em reais, percentuais, datas, trechos entre aspas e
referências a proposições (PL, PEC, MPV etc.). Uma referência a
proposição é verificável: ela pode ser conferida no registro oficial.
Os candidatos ainda precisam de evidência (etapas 4 e 5); extração
não é veredito.
"""

import html
import re

MONEY = re.compile(r"R\$\s?[\d\.\,]+(?:\s?(?:mil|milhões|bilhões))?")
PERCENT = re.compile(r"\d+(?:[,\.]\d+)?\s?%")
DATE = re.compile(r"\d{1,2}/\d{1,2}/\d{4}")
QUOTE = re.compile(r'"([^"]{10,200})"')
PROPOSITION = re.compile(
    r"\b(?:PL|PLS|PEC|MPV|PLP|PDC|PDS|RQS|REQ|MSG|VET|MSF|PRS|PLC|RIC|MSC|PAR|EMC|SBT)"
    r"\s*(?:\d{1,3}(?:\.\d{3})+|\d+)/\d{4}\b"
)
# Número com ponto de milhar ("PL 1.454/2021") ou sem ("PL 1454/2021").
# O padrão antigo (\d+) não casava o ponto e a referência sumia: a
# alegação ficava sem busca e sem evidência (caso real q70).


def clean_text(text):
    """Tira markup do texto (resumos de RSS trazem HTML) antes de extrair.

    Sem isso, o padrão de citação casa o valor de atributos
    (`src="https://..."`) e URLs de imagem viram "alegação" — 12% das
    alegações do banco em 12/11. O texto limpo é só p/ extração; o
    resumo original continua guardado na fila.
    """
    if not text:
        return ""
    text = re.sub(r"<[^>]+>", " ", text)
    text = html.unescape(text)
    return re.sub(r"\s+", " ", text).strip()


def extract_candidates(text):
    """Devolve candidatos [{text, kind}] sem duplicar pelo texto.

    Ordem: a proposição vem primeiro — é a alegação mais verificável
    (tem registro oficial) e vira a central no pipeline (#47). Um
    número solto ("50%") sem contexto quase nunca é verificável
    sozinho e não deve ser a central quando há uma proposição.
    """
    found = []
    seen = set()
    text = clean_text(text)

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
