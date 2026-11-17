"""Carregamento do Fake.Br Corpus.

Layout esperado (clone de https://github.com/roneysco/Fake.br-Corpus):

    <corpus>/full_texts/fake/*.txt
    <corpus>/full_texts/true/*.txt

Os pares são alinhados: o arquivo `N.txt` falso e o `N.txt`
verdadeiro tratam do mesmo fato. Por isso o split treino/teste é
feito POR PAR (GroupShuffleSplit sobre o nome do arquivo): a falsa
e a verdadeira do mesmo fato nunca caem em lados diferentes do
split. Sem isso o modelo poderia decorar tokens do evento em vez
de aprender o que distingue falso de verdadeiro.
"""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass
class NewsItem:
    text: str
    label: int  # 0 = verdadeira, 1 = falsa
    pair: str  # nome do arquivo (o par alinhado) ou id único da linha
    source: str = ""  # corpus de origem (ex.: "Fake.br", "fakes")


def load_fakebr(corpus_dir: str) -> list[NewsItem]:
    """Lê os textos completos do Fake.Br. Levanta FileNotFoundError
    se o layout não for o esperado."""
    items: list[NewsItem] = []
    for label, folder in ((1, "fake"), (0, "true")):
        path = os.path.join(corpus_dir, "full_texts", folder)
        if not os.path.isdir(path):
            raise FileNotFoundError(
                f"pasta não encontrada: {path}. Clone o corpus de "
                "https://github.com/roneysco/Fake.br-Corpus e passe "
                "--corpus com o caminho da raiz do clone."
            )
        for name in sorted(os.listdir(path)):
            if not name.endswith(".txt"):
                continue
            with open(os.path.join(path, name), encoding="utf-8",
                      errors="replace") as fh:
                text = fh.read().strip()
            if text:
                items.append(NewsItem(text=text, label=label, pair=name))
    if not items:
        raise ValueError(f"nenhum texto encontrado em {corpus_dir}")
    return items
