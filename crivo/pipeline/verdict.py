"""Motor de veredito determinístico do Crivo Factual (doc 02).

Regras implementadas, sem nenhuma decisão probabilística:

- Índice = 50 + 50 x (Pc - Pf) / Pt, onde Pc é o peso das alegações
  confirmadas, Pf o das contraditadas e Pt o peso total das alegações.
  Sem evidência, o índice fica no centro (50), nunca no falso.
- Faixas: 80-100 Verdadeiro, 60-79 Predominantemente verdadeiro,
  40-59 Inconclusivo, 20-39 Predominantemente falso, 0-19 Falso.
- Regra do veto: alegação central contraditada por fonte primária
  trava o veredito em FALSO, qualquer que seja o índice.
- Trava do centro: alegação central sem evidência trava o veredito em
  Inconclusivo com índice 50, mesmo com suportes confirmados.
- Sem nenhuma alegação, não há índice (publicação fora do escopo).
"""

from dataclasses import dataclass

BANDS = [
    (80, "Verdadeiro"),
    (60, "Predominantemente verdadeiro"),
    (40, "Inconclusivo"),
    (20, "Predominantemente falso"),
    (0, "Falso"),
]

VALID_STATUS = ("confirmada", "contraditada", "sem_evidencia")


@dataclass
class Claim:
    text: str
    weight: int = 1
    central: bool = False
    status: str = "sem_evidencia"

    def __post_init__(self):
        if self.status not in VALID_STATUS:
            raise ValueError(f"status inválido: {self.status}")


def compute_index(claims):
    """Índice de sustentação (0-100) ou None quando não há alegações."""
    if not claims:
        return None
    pc = sum(c.weight for c in claims if c.status == "confirmada")
    pf = sum(c.weight for c in claims if c.status == "contraditada")
    pt = sum(c.weight for c in claims)
    if pt == 0:
        return None
    return 50 + 50 * (pc - pf) / pt


def label_for(index):
    """Rótulo da faixa para um índice numérico."""
    for floor, label in BANDS:
        if index >= floor:
            return label
    return "Falso"


def verdict(claims):
    """Devolve (rótulo, índice, regra) para uma lista de alegações."""
    if not claims:
        return ("Sem índice", None, "sem_alegacoes")
    centrals = [c for c in claims if c.central]
    central = centrals[0] if centrals else None
    index = compute_index(claims)
    if central is not None and central.status == "contraditada":
        return ("Falso", index, "veto")
    if central is not None and central.status == "sem_evidencia":
        return ("Inconclusivo", 50, "trava_do_centro")
    return (label_for(index), index, "faixa")
