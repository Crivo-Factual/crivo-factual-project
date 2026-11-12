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
import urllib.request

from .extraction import clean_text

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
        with urllib.request.urlopen(req, timeout=self.timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        return data["choices"][0]["message"]["content"]


def extract_with_llm(text, client):
    """Extrai alegações via LLM. Devolve [] em qualquer falha (sem chave,
    erro de rede, resposta inválida): o pipeline segue só com regras."""
    text = clean_text(text)
    if client is None or not text:
        return []
    try:
        raw = client.complete(
            "Extraia as alegações atômicas verificáveis deste texto:\n\n" + text
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
