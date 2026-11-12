"""Evidências (etapa 4 do pipeline, M3).

Fonte de evidência nesta versão: o próprio banco de fatos — boatos
reciclados. Quando uma alegação já foi verificada antes (mesmo texto,
ignorando caixa, acentos e pontuação), o veredito anterior vira
evidência, com link para a análise original.

Busca de fontes primárias externas ao vivo é trabalho futuro. O M3 não
inventa evidência: sem prova, a alegação fica sem_evidencia e a trava
do centro segura o veredito em Inconclusivo.
"""

import hashlib
import re
import unicodedata


def fingerprint(text):
    """Identificador estável de uma alegação (caixa, acentos e pontuação fora)."""
    norm = unicodedata.normalize("NFKD", (text or "").lower())
    norm = "".join(c for c in norm if not unicodedata.combining(c))
    norm = re.sub(r"[^a-z0-9 ]+", " ", norm)
    norm = re.sub(r"\s+", " ", norm).strip()
    return hashlib.sha256(norm.encode("utf-8")).hexdigest()


def find_previous_verdict(conn, fp):
    """Veredito anterior de uma alegação com este fingerprint, ou None.

    Só contam alegações já confirmadas ou contraditadas: um "sem
    evidência" anterior não é evidência.
    """
    row = conn.execute(
        "SELECT c.publication_id, c.status, v.label FROM claims c"
        " JOIN verdicts v ON v.publication_id = c.publication_id"
        " WHERE c.fingerprint = ?"
        " AND c.status IN ('confirmada', 'contraditada')"
        " ORDER BY v.id DESC LIMIT 1",
        (fp,),
    ).fetchone()
    if row is None:
        return None
    return {"publication_id": row[0], "status": row[1], "label": row[2]}
