"""Extração por LLM em tier gratuito (etapa 3 do pipeline, M3).

O modelo só extrai e localiza alegações atômicas; nunca decide. O
veredito continua determinístico (ver crivo/pipeline/verdict.py).

Provedor padrão: Groq free tier (sem cartão), endpoint compatível com
OpenAI. A chave vem de GROQ_API_KEY; o modelo, de GROQ_MODEL. Sem
chave, sem modelo: a extração segue só com regras e o pipeline avisa.
"""

import json
import os
import urllib.request

SYSTEM_PROMPT = (
    "Você extrai alegações atômicas verificáveis de um texto político. "
    "Responda SOMENTE com JSON, neste formato: "
    '{"claims": [{"text": "...", "kind": "..."}]}. '
    "Não julgue veracidade, não adicione comentários. Cada alegação deve "
    "ser uma afirmação única e checável."
)


class GroqClient:
    """Cliente mínimo da API da Groq (endpoint compatível com OpenAI)."""

    def __init__(self, api_key=None, model=None,
                 base_url="https://api.groq.com/openai/v1", timeout=30):
        self.api_key = api_key or os.environ.get("GROQ_API_KEY", "")
        if not self.api_key:
            raise ValueError(
                "GROQ_API_KEY não configurada. Defina a variável de ambiente "
                "ou copie .env.example para .env com a chave do Groq free tier."
            )
        self.model = model or os.environ.get("GROQ_MODEL", "llama-3.1-8b-instant")
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
                "Authorization": f"Bearer {self.api_key}",
            },
        )
        with urllib.request.urlopen(req, timeout=self.timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        return data["choices"][0]["message"]["content"]


def extract_with_llm(text, client):
    """Extrai alegações via LLM. Devolve [] em qualquer falha (sem chave,
    erro de rede, resposta inválida): o pipeline segue só com regras."""
    if client is None or not (text or "").strip():
        return []
    try:
        raw = client.complete(
            "Extraia as alegações atômicas verificáveis deste texto:\n\n" + text
        )
        data = json.loads(raw)
        claims = []
        for item in data.get("claims", []):
            if isinstance(item, dict) and item.get("text"):
                claims.append(
                    {"text": str(item["text"]).strip(), "kind": str(item.get("kind", ""))}
                )
        return claims
    except Exception:  # noqa: BLE001 - qualquer falha vira "só regras"
        return []
