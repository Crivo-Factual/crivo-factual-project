"""Busca de evidências primárias ao vivo (issue #47).

Cobre alegações sobre proposições (PL/PEC/MPV/...): consulta as APIs
de dados abertos da Câmara e do Senado, gratuitas e sem chave. Só
Confirmada/Contraditada com fonte primária; sem prova, devolve None
(a alegação fica sem_evidencia e a trava do centro segura o veredito).

Regras conservadoras (o motor nunca inventa prova):
- Status ("aprovada", "rejeitada"...) só decide quando a situação
  oficial mapeia com clareza; situação ausente ou não mapeável não
  confirma nada — e nunca confirma só porque a proposição existe.
- Ementa: confirma quando o texto da alegação (sem a referência)
  está contido na ementa oficial. Paráfrase não confirma.
- "Não encontrada": só contradiz quando a alegação afirma um status
  federal ("aprovada na Câmara", "aprovada no Congresso"...); sem a
  casa nomeada, pode ser proposição estadual — sem_evidencia.
- Qualquer erro de rede ou parse devolve None: a falha isola o item,
  nunca o veredito.

Fora do v0.1 (avaliado e adiado, ver DEVELOPMENT.md): DOU (sem API
pública de consulta, só portal web) e IBGE/SIDRA (falta o mapa
alegação → tabela). O Senado não expõe situação descritiva na API —
só existência, ementa e o flag IndicadorTramitando.
"""

import json
import re
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET

from .evidence import normalize

PROPOSITION_RE = re.compile(
    r"\b(PL|PLS|PEC|MPV|PLP|PDC|PDS|RQS|REQ|MSG|VET|MSF|PRS|PLC|RIC|MSC|PAR|EMC|SBT)"
    r"\s*(\d+)/(\d{4})\b"
)

# Tipos numerados por proposição, não por ano: o mesmo "EMC 1/2026"
# existe em centenas de proposições diferentes (132 só na Câmara em
# 12/11/2026). A referência sozinha não identifica o registro — um
# status lido do primeiro registro pode ser de outra proposição. Para
# esses tipos, o status só vale do registro cuja ementa casa com a
# alegação; sem ementa que case, o status não é atribuível.
AMBIGUOUS_TYPES = ("EMC", "PAR", "SBT")

# Páginas de 100 na consulta à Câmara (o teto da API); até 3 páginas
# por referência. EMC 1/2026 tem 132 registros — o certo estava na
# página 2. Sem paginar, a desambiguação por ementa não o alcançaria.
CAMARA_PAGE_SIZE = 100
CAMARA_MAX_PAGES = 3

# Ordem importa: o primeiro radical encontrado decide o status afirmado.
STATUS_WORDS = (
    ("transformad", "transformada em norma"),
    ("sancionad", "sancionada"),
    ("promulgad", "promulgada"),
    ("vetad", "vetada"),
    ("aprovad", "aprovada"),
    ("rejeitad", "rejeitada"),
    ("arquivad", "arquivada"),
    ("tramit", "em tramitação"),
)

FEDERAL_WORDS = ("camara", "senado", "congresso", "federal", "deputados", "senadores")

USER_AGENT = "CrivoFactual/0.1"


def camara_search_url(sigla, numero, ano, pagina=1):
    return (
        "https://dadosabertos.camara.leg.br/api/v2/proposicoes"
        f"?siglaTipo={sigla}&numero={numero}&ano={ano}"
        f"&itens={CAMARA_PAGE_SIZE}&pagina={pagina}"
    )


def senado_search_url(sigla, numero, ano):
    return f"https://legis.senado.leg.br/dadosabertos/materia/{sigla}/{numero}/{ano}"


def _fetch(url, timeout=20):
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read()


class CamaraClient:
    """Consulta à API de dados abertos da Câmara."""

    def __init__(self, fetcher=None):
        self._fetch = fetcher or _fetch

    @staticmethod
    def _to_record(p, url):
        st = p.get("statusProposicao") or {}
        return {
            "house": "Câmara dos Deputados",
            "source_name": "Câmara dos Deputados — dados abertos",
            "source_url": p.get("uri") or url,
            "ementa": p.get("ementa") or "",
            "situacao": (st.get("descricaoSituacao") or st.get("descricaoTramitacao") or ""),
            "tramitando": None,
            "search_url": url,
        }

    def search_all(self, sigla, numero, ano):
        """Devolve todos os registros oficiais (até CAMARA_MAX_PAGES).

        Tipos ambíguos (EMC/PAR/SBT) devolvem dezenas ou centenas de
        registros com a mesma sigla+número+ano; o primeiro da lista é
        arbitrário. A desambiguação acontece no Searcher, pela ementa.
        """
        records = []
        for pagina in range(1, CAMARA_MAX_PAGES + 1):
            url = camara_search_url(sigla, numero, ano, pagina)
            try:
                data = json.loads(self._fetch(url).decode("utf-8"))
            except urllib.error.HTTPError as exc:
                if exc.code == 404:
                    break
                raise
            records.extend(
                self._to_record(p, url) for p in data.get("dados", [])
            )
            links = {l.get("rel"): l.get("href") for l in data.get("links", [])}
            if "next" not in links:
                break
        return records

    def search(self, sigla, numero, ano):
        """Devolve o primeiro registro oficial ou None (não encontrada)."""
        records = self.search_all(sigla, numero, ano)
        return records[0] if records else None


class SenadoClient:
    """Consulta à API de dados abertos do Senado."""

    def __init__(self, fetcher=None):
        self._fetch = fetcher or _fetch

    def search(self, sigla, numero, ano):
        """Devolve o registro oficial ou None (não encontrada)."""
        url = senado_search_url(sigla, numero, ano)
        try:
            raw = self._fetch(url)
        except urllib.error.HTTPError as exc:
            if exc.code == 404:
                return None
            raise
        root = ET.fromstring(raw)

        def find(tag):
            el = root.find(f".//{tag}")
            return (el.text or "").strip() if el is not None else ""

        codigo = find("CodigoMateria")
        ementa = find("EmentaMateria")
        if not codigo and not ementa:
            return None
        tram = find("IndicadorTramitando").lower()
        return {
            "house": "Senado Federal",
            "source_name": "Senado Federal — dados abertos",
            "source_url": (
                f"https://legis.senado.leg.br/dadosabertos/materia/{codigo}"
                if codigo else url
            ),
            "ementa": ementa,
            "situacao": "",
            "tramitando": tram in ("sim", "s", "true", "1"),
            "search_url": url,
        }


def _detect_status(text):
    low = (text or "").lower()
    for stem, label in STATUS_WORDS:
        if stem in low:
            return label
    return None


def _is_federal(text):
    norm = normalize(text)
    return any(w in norm for w in FEDERAL_WORDS)


def _status_outcome(claim_status, situacao, tramitando):
    """'confirmada', 'contraditada' ou None (não mapeável)."""
    sit = (situacao or "").lower()
    if claim_status == "aprovada":
        if any(k in sit for k in ("aprovad", "transformad", "sancionad", "promulgad")):
            return "confirmada"
        if any(k in sit for k in ("rejeitad", "arquivad")):
            return "contraditada"
    elif claim_status == "rejeitada":
        if any(k in sit for k in ("rejeitad", "arquivad")):
            return "confirmada"
        if any(k in sit for k in ("aprovad", "sancionad", "promulgad")):
            return "contraditada"
    elif claim_status == "arquivada":
        if "arquivad" in sit:
            return "confirmada"
        if tramitando is True:
            return "contraditada"
    elif claim_status == "sancionada":
        if any(k in sit for k in ("sancionad", "promulgad", "transformad em norma")):
            return "confirmada"
        if "vetad" in sit:
            return "contraditada"
    elif claim_status == "vetada":
        if "vetad" in sit:
            return "confirmada"
        if any(k in sit for k in ("sancionad", "promulgad")):
            return "contraditada"
    elif claim_status == "promulgada":
        if "promulgad" in sit:
            return "confirmada"
        if "vetad" in sit:
            return "contraditada"
    elif claim_status == "transformada em norma":
        if any(k in sit for k in ("transformad", "sancionad", "promulgad")):
            return "confirmada"
    elif claim_status == "em tramitação":
        if tramitando is True:
            return "confirmada"
        if any(k in sit for k in ("arquivad", "rejeitad")):
            return "contraditada"
    return None


def _ementa_matches(text, ref_match, ementa):
    """A alegação (sem a referência) está contida na ementa oficial?"""
    rest = normalize(text[:ref_match.start()] + " " + text[ref_match.end():])
    # O artigo que acompanhava a referência ("O PL ... institui") é
    # cola gramatical, não conteúdo: sem tirá-lo, a contenção falha
    # mesmo quando o resto é verbatim da ementa (caso real q271).
    while True:
        stripped = re.sub(r"^(o|a|os|as|que|e)\s+", "", rest)
        if stripped == rest:
            break
        rest = stripped
    if len(rest) < 20 and not _detect_status(text):
        return True  # a alegação é basicamente a referência
    return rest in normalize(ementa)


class Searcher:
    """Busca com cache por referência (evita repetir a mesma consulta)."""

    def __init__(self, camara=None, senado=None):
        self.camara = camara or CamaraClient()
        self.senado = senado or SenadoClient()
        self._cache = {}

    def _lookup(self, sigla, numero, ano):
        """Devolve (registros, casas consultadas). A Câmara pode devolver
        vários registros para a mesma referência (tipos ambíguos); o
        Senado devolve no máximo um. O cache é por referência."""
        key = (sigla, numero, ano)
        if key in self._cache:
            return self._cache[key]
        records = []
        consulted = 0
        for client in (self.camara, self.senado):
            try:
                if isinstance(client, CamaraClient):
                    found = client.search_all(sigla, numero, ano)
                else:
                    rec = client.search(sigla, numero, ano)
                    found = [rec] if rec else []
                consulted += 1
            except Exception:  # noqa: BLE001 - casa indisponível, tenta a outra
                continue
            records.extend(found)
            if records:
                break
        result = (records, consulted)
        self._cache[key] = result
        return result

    def _match_by_ementa(self, text, ref, records):
        """Primeiro registro cuja ementa casa com a alegação (ou None)."""
        for record in records:
            if _ementa_matches(text, ref, record["ementa"]):
                return record
        return None

    def _identify_record(self, text, records):
        """Registro cuja ementa aparece na alegação (ou None).

        Usado só para identificar QUAL registro de um tipo ambíguo a
        alegação trata, antes de ler o status dele: a alegação cita a
        ementa e afirma um status, então a contenção é reversa (a
        ementa está na alegação, não o contrário). Ementa curta demais
        não identifica nada.
        """
        tx = normalize(text)
        for record in records:
            em = normalize(record["ementa"])
            if len(em) >= 20 and (em in tx or em[:80] in tx):
                return record
        return None

    def search_claim(self, text):
        """Busca evidência primária para a alegação. Devolve a evidência
        {status, source_name, source_url, excerpt} ou None."""
        ref = PROPOSITION_RE.search(text or "")
        if not ref:
            return None
        sigla, numero, ano = ref.group(1), ref.group(2), ref.group(3)
        claim_status = _detect_status(text)
        records, consulted = self._lookup(sigla, numero, ano)
        if not records:
            if consulted == 2 and claim_status and _is_federal(text):
                return {
                    "status": "contraditada",
                    "source_name": "Câmara dos Deputados + Senado Federal — dados abertos",
                    "source_url": camara_search_url(sigla, numero, ano),
                    "excerpt": (
                        f"{sigla} {numero}/{ano} não encontrada nas bases "
                        "oficiais da Câmara e do Senado."
                    ),
                }
            return None
        if claim_status:
            # Tipo ambíguo: o status só vale do registro cuja ementa a
            # alegação cita — o primeiro da lista pode ser outra
            # proposição. Tipo único: o registro é o da referência.
            if sigla in AMBIGUOUS_TYPES:
                record = self._identify_record(text, records)
                if record is None:
                    return None  # status sem registro identificável
            else:
                record = records[0]
            outcome = _status_outcome(
                claim_status, record.get("situacao", ""), record.get("tramitando")
            )
            if outcome:
                return {
                    "status": outcome,
                    "source_name": record["source_name"],
                    "source_url": record["source_url"],
                    "excerpt": (
                        "Situação oficial: "
                        f"{record.get('situacao') or 'em tramitação'}."
                    ),
                }
            return None  # status não mapeável: nunca confirma só por existir
        record = self._match_by_ementa(text, ref, records)
        if record is not None:
            return {
                "status": "confirmada",
                "source_name": record["source_name"],
                "source_url": record["source_url"],
                "excerpt": f"Ementa oficial: {record['ementa'][:200]}",
            }
        return None


def search_claim(text, searcher=None):
    """Atalho: busca com um Searcher padrão."""
    return (searcher or Searcher()).search_claim(text)
