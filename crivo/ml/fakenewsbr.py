"""Carregamento do FakenewsBR — corpus unificado de notícias falsas em
português (Silva et al., 2026, DSW).

Fonte: espelho público do corpus unificado no Hugging Face Hub
(`kauandivino/FakenewsBR`, arquivo `FakenewsBR_factchecked.csv`,
95 MB, 51.205 linhas). O arquivo é o produto do pipeline do
repositório https://github.com/AKCIT-FN/fakenews-data — não vem no
repo do Crivo (95 MB); baixe com:

    curl -sL -o FakenewsBR_factchecked.csv \\
      https://huggingface.co/datasets/kauandivino/FakenewsBR/resolve/main/FakenewsBR_factchecked.csv

O que o loader faz (e por quê):
- Só linhas canônicas: as variantes `*_raw` (ex.: `Fake.br_raw`)
  são as mesmas instâncias antes da limpeza — usá-las junto seria
  contar cada item duas vezes e vazar quase-duplicatas entre
  treino e teste.
- Só textos com 50+ caracteres: abaixo disso é ruído (2.602 linhas
  têm menos de 50 chars). O limite é documentado, não escondido.
- Exclusão por fingerprint: recebe um conjunto de fingerprints de
  textos que NÃO podem entrar no treino — no caso da v2, os 1.440
  itens do teste da v1, para a comparação v1 × v2 ser limpa (os
  mesmos textos do Fake.Br aparecem aqui dentro).
- Usa a coluna `text` (crua): a limpeza é do nosso pipeline
  (TF-IDF), não a do corpus — o método fica autocontido.

Composição canônica (40.278 linhas): fakes 20.364 (Kaggle, só
falsas), Fake.br 7.160, FakeWhatsApp.BR_2018 6.383, true 2.717
(Kaggle, só verdadeiras), COVID19.BR 1.952, MuMiN-PT 1.403,
LLM4BR_300 299. O corpus é majoritariamente texto curto (tweets,
WhatsApp): mediana de 156 chars — bem diferente do Fake.Br, que
só tem artigos completos. Isso muda o comportamento do modelo
com texto curto (ver o treino da v2).
"""

from __future__ import annotations

import re
import unicodedata

from .dataset import NewsItem

MIN_TEXT_CHARS = 50
LABEL_MAP = {"fake": 1, "true": 0}


def fingerprint(text: str, chars: int = 300) -> str:
    """Impressão do início do texto normalizado: minúsculas, sem
    acento, só alfanuméricos e espaços, colapsados. Serve para
    excluir textos que já estão no teste de outro modelo mesmo
    quando a cópia difere em espaço ou pontuação no fim."""
    norm = unicodedata.normalize("NFKD", text or "")
    norm = "".join(c for c in norm if not unicodedata.combining(c))
    norm = norm.lower()
    norm = re.sub(r"[^a-z0-9 ]+", " ", norm)
    norm = re.sub(r"\s+", " ", norm).strip()
    return norm[:chars]


def load_fakenewsbr(csv_path: str,
                    exclude_fingerprints: set[str] | None = None,
                    min_chars: int = MIN_TEXT_CHARS) -> list[NewsItem]:
    """Lê o CSV unificado e devolve os itens canônicos. Levanta
    FileNotFoundError se o arquivo não existir e ImportError se o
    pandas não estiver instalado."""
    try:
        import pandas as pd
    except ImportError as exc:
        raise ImportError(
            "pandas não instalado — instale no venv de ML "
            "(`.venv-ml/bin/pip install pandas`)."
        ) from exc
    df = pd.read_csv(csv_path, low_memory=False)
    items: list[NewsItem] = []
    excluded = 0
    for row in df.itertuples(index=False):
        name = str(row.dataset_name)
        if name.endswith("_raw"):
            continue
        label = LABEL_MAP.get(str(row.label).strip().lower())
        if label is None:
            continue
        text = str(row.text) if row.text is not None else ""
        text = text.strip()
        if len(text) < min_chars:
            continue
        if exclude_fingerprints and fingerprint(text) in exclude_fingerprints:
            excluded += 1
            continue
        items.append(NewsItem(
            text=text,
            label=label,
            pair=f"fakenewsbr-{row.rid}",
            source=name,
        ))
    if not items:
        raise ValueError(f"nenhum item canônico em {csv_path}")
    return items
