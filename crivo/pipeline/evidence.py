"""Evidências (etapa 4 do pipeline, M3 + busca primária #47).

Fontes de evidência, nesta ordem:
1. o próprio banco de fatos — boatos reciclados (M3);
2. APIs de dados abertos da Câmara e do Senado ao vivo (ver
   `evidence_search.py`) — fonte primária para alegações sobre
   proposições.

Sem prova, a alegação fica sem_evidencia e a trava do centro segura
o veredito em Inconclusivo. O M3 não inventa evidência.
"""

import hashlib
import re
import unicodedata


def normalize(text):
    """Texto sem caixa, acentos e pontuação — para comparar alegações."""
    norm = unicodedata.normalize("NFKD", (text or "").lower())
    norm = "".join(c for c in norm if not unicodedata.combining(c))
    norm = re.sub(r"[^a-z0-9 ]+", " ", norm)
    return re.sub(r"\s+", " ", norm).strip()


def fingerprint(text):
    """Identificador estável de uma alegação (caixa, acentos e pontuação fora)."""
    return hashlib.sha256(normalize(text).encode("utf-8")).hexdigest()


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
