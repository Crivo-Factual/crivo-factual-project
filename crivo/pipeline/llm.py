"""Extração por LLM em tier gratuito (etapa 3 do pipeline, M3).

O modelo só extrai e localiza alegações atômicas; nunca decide. O
veredito continua determinístico (ver crivo/pipeline/verdict.py).

Provedor padrão: Groq free tier (sem cartão), endpoint compatível com
OpenAI. A chave vem de GROQ_API_KEY, do `.env`, ou do Secure Vault
(`via_vault=True`, conexão `custom.groq` — ver
`~/workspace/custom-connectors/custom.groq/CONNECTOR.md`). Sem chave,
sem modelo: a extração segue só com regras e o pipeline avisa.
"""

import json
import os
import sys
import time
import urllib.error
import urllib.request

from .extraction import clean_text

# O texto do artigo (até 8.000 chars) deixa o prompt com ~2.000
# tokens — 8 itens seguidos estouram o teto de tokens/minuto do
# Groq free tier (429 medido ao vivo em 12/11). O lead carrega as
# alegações principais; o resto do artigo continua nas regras.
MAX_INPUT_CHARS = 4000

# Tentativas em erro transitório (429, 400 json_validate_failed,
# queda de conexão); respeita o Retry-After do servidor, com teto
# de 60 s.
MAX_RETRIES = 3
DEFAULT_RETRY_WAIT = 10
MAX_RETRY_WAIT = 60

SYSTEM_PROMPT = (
    "Você extrai alegações atômicas verificáveis de um texto político. "
    "Responda SOMENTE com JSON, neste formato: "
    '{"claims": [{"text": "...", "kind": "..."}]}. '
    "Não julgue veracidade, não adicione comentários. "
    "Responda na mesma língua do texto de origem (em português, se o "
    "texto for em português). Cada alegação deve ser autocontida: inclua "
    "o sujeito, o predicado e o valor ou número — nunca devolva apenas "
    "um número, um percentual ou um valor solto. Quando o texto "
    "mencionar uma proposição (PL, PEC, PLP, MPV, REQ etc.), inclua a "
    "sigla, o número e o ano na alegação (ex.: 'O Senado aprovou o PL "
    "1159/2026'). Nunca devolva URLs ou fragmentos de HTML."
)


class _PreservePostRedirectHandler(urllib.request.HTTPRedirectHandler):
    """A Groq devolve 301 para a mesma URL de tempos em tempos; o
    urllib converte o POST em GET ao seguir o redirect e a API
    responde 404 "Unknown request URL: GET ..." (medido ao vivo em
    12/11, q149/q311/q313). Preserva o método e o corpo no redirect;
    redirect para a mesma URL não é seguido — vira 301, que o retry
    trata como transitório."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if newurl == req.full_url:
            return None
        new_req = super().redirect_request(req, fp, code, msg, headers, newurl)
        if new_req is not None and req.get_method() == "POST":
            new_req.method = "POST"
            new_req.data = req.data
            new_req.add_header("Content-Type", "application/json")
        return new_req


class GroqClient:
    """Cliente mínimo da API da Groq (endpoint compatível com OpenAI)."""

    def __init__(self, api_key=None, model=None,
                 base_url="https://api.groq.com/openai/v1", timeout=30,
                 via_vault=False):
        self.via_vault = via_vault
        self.api_key = api_key or os.environ.get("GROQ_API_KEY", "")
        if not self.api_key and not via_vault:
            raise ValueError(
                "GROQ_API_KEY não configurada. Defina a variável de ambiente, "
                "copie .env.example para .env com a chave do Groq free tier, "
                "ou use via_vault=True (conexão custom.groq no Secure Vault)."
            )
        self.model = model or os.environ.get("GROQ_MODEL", "openai/gpt-oss-20b")
        self.base_url = base_url
        self.timeout = timeout
        self._opener = urllib.request.build_opener(_PreservePostRedirectHandler())

    def complete(self, prompt):
        body = json.dumps(
            {
                "model": self.model,
                "messages": [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": prompt},
                ],
                "temperature": 0,
                "response_format": {"type": "json_object"},
            }
        ).encode("utf-8")
        req = urllib.request.Request(
            self.base_url + "/chat/completions",
            data=body,
            method="POST",
            headers={
                "Content-Type": "application/json",
                # Sem User-Agent próprio, o Cloudflare (error 1010)
                # barra o Python-urllib. Mesmo padrão dos coletores.
                "User-Agent": "CrivoFactual/0.1",
            },
        )
        if self.via_vault:
            # A chave real nunca passa por aqui: o runtime troca o
            # surrogate pela credencial do Secure Vault (custom.groq).
            sys.path.insert(0, "/opt/muse/skills/custom-connector-setup/bin")
            from dynamic_credentials import add_surrogate_to_request

            add_surrogate_to_request(
                req, "custom.groq", allowed_hosts=["api.groq.com"]
            )
        else:
            req.add_header("Authorization", f"Bearer {self.api_key}")
        last_error = None
        for attempt in range(MAX_RETRIES):
            try:
                with self._opener.open(req, timeout=self.timeout) as resp:
                    data = json.loads(resp.read().decode("utf-8"))
                return data["choices"][0]["message"]["content"]
            except urllib.error.HTTPError as exc:
                last_error = exc
                # Transitório: 429 (rate limit do tier gratuito), 301
                # (redirect para a mesma URL, ver o handler acima) e
                # 400 json_validate_failed (o modelo falhou em gerar
                # JSON válido — medido ao vivo em 12/11, q149). Outro
                # erro HTTP não é transitório — propaga.
                retryable = exc.code in (429, 301) or (
                    exc.code == 400 and "json_validate_failed" in _error_body(exc)
                )
                if not retryable or attempt == MAX_RETRIES - 1:
                    raise
                # Espera crescente: a janela ruim do servidor pode
                # durar mais que uma tentativa.
                wait = min(max(_retry_after(exc), 0), MAX_RETRY_WAIT) * (attempt + 1)
                time.sleep(wait)
            except (urllib.error.URLError, ConnectionError, TimeoutError) as exc:
                # Queda de conexão / timeout: transitório (medido ao
                # vivo em 12/11, q313 — RemoteDisconnected).
                last_error = exc
                if attempt == MAX_RETRIES - 1:
                    raise
                time.sleep(DEFAULT_RETRY_WAIT * (attempt + 1))
        raise last_error  # inalcançável, mas deixa o fluxo explícito


def _error_body(exc):
    try:
        return exc.read().decode("utf-8", errors="replace")
    except Exception:  # noqa: BLE001 - sem corpo legível, não é retryable
        return ""


def _retry_after(exc):
    try:
        return int(exc.headers.get("Retry-After", DEFAULT_RETRY_WAIT))
    except (TypeError, ValueError):
        return DEFAULT_RETRY_WAIT


def extract_with_llm(text, client):
    """Extrai alegações via LLM. Devolve [] em qualquer falha (sem chave,
    erro de rede, resposta inválida): o pipeline segue só com regras."""
    text = clean_text(text)
    if client is None or not text:
        return []
    # Corta no fim de palavra: o corte no meio de uma palavra deixa o
    # prompt truncado e o modelo falha em gerar JSON (400 medido).
    window = text[:MAX_INPUT_CHARS]
    if len(text) > MAX_INPUT_CHARS and " " in window:
        window = window.rsplit(" ", 1)[0]
    try:
        raw = client.complete(
            "Extraia as alegações atômicas verificáveis deste texto:\n\n"
            + window
        )
        data = json.loads(raw)
        claims = []
        for item in data.get("claims", []):
            if isinstance(item, dict) and item.get("text"):
                claim = str(item["text"]).strip()
                # Defesa em profundidade: o modelo pode devolver URL ou
                # fragmento de HTML mesmo com o prompt proibindo.
                if claim and "http" not in claim and "<" not in claim and ">" not in claim:
                    claims.append(
                        {"text": claim, "kind": str(item.get("kind", ""))}
                    )
        return claims
    except Exception:  # noqa: BLE001 - qualquer falha vira "só regras"
        return []
