"""Testes do cliente LLM (M3) — contra um servidor local de mentira.

Nenhuma chamada real à Groq: o teste prova o formato da requisição e
o tratamento de respostas (válida, inválida, erro HTTP, sem chave).
"""

import json
import os
import sys
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from crivo.pipeline import llm as llm_mod

CANNED = {
    "choices": [
        {
            "message": {
                "content": json.dumps(
                    {
                        "claims": [
                            {"text": "O Bolsa Família acabou", "kind": "afirmação"}
                        ]
                    }
                )
            }
        }
    ]
}


class Handler(BaseHTTPRequestHandler):
    response_body = json.dumps(CANNED).encode()
    status = 200
    fail_429 = 0
    fail_400_json = 0
    fail_301_self = 0
    redirect_other = 0
    calls = 0

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        self.server.last_body = self.rfile.read(length)
        self.server.last_method = self.command
        Handler.calls += 1
        if Handler.fail_301_self > 0:
            Handler.fail_301_self -= 1
            self.send_response(301)
            self.send_header(
                "Location", f"http://{self.headers.get('Host')}{self.path}"
            )
            self.end_headers()
            return
        if Handler.redirect_other > 0:
            Handler.redirect_other -= 1
            self.send_response(301)
            self.send_header(
                "Location", f"http://{self.headers.get('Host')}/outro-caminho"
            )
            self.end_headers()
            return
        if Handler.fail_429 > 0:
            Handler.fail_429 -= 1
            self.send_response(429)
            self.send_header("Retry-After", "0")
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"error": {"message": "Rate limit reached"}}')
            return
        if Handler.fail_400_json > 0:
            Handler.fail_400_json -= 1
            self.send_response(400)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(
                b'{"error": {"message": "Failed to validate JSON.", '
                b'"code": "json_validate_failed"}}'
            )
            return
        self.send_response(self.status)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(self.response_body)

    def log_message(self, *a):
        pass


class TestLLM(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        cls.port = cls.server.server_address[1]
        threading.Thread(target=cls.server.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()

    def _client(self):
        return llm_mod.GroqClient(
            api_key="test-key", base_url=f"http://127.0.0.1:{self.port}"
        )

    def test_extract_with_mock(self):
        claims = llm_mod.extract_with_llm(
            "O Bolsa Família acabou, dizem por aí.", self._client()
        )
        self.assertEqual(
            claims, [{"text": "O Bolsa Família acabou", "kind": "afirmação"}]
        )

    def test_bad_json_returns_empty(self):
        Handler.response_body = b"not json"
        try:
            self.assertEqual(
                llm_mod.extract_with_llm("texto", self._client()), []
            )
        finally:
            Handler.response_body = json.dumps(CANNED).encode()

    def test_http_error_returns_empty(self):
        Handler.status = 500
        try:
            self.assertEqual(
                llm_mod.extract_with_llm("texto", self._client()), []
            )
        finally:
            Handler.status = 200

    def test_429_tenta_de_novo_e_recupera(self):
        # O tier gratuito limita tokens/minuto: 2x 429 e depois 200.
        Handler.fail_429 = 2
        try:
            claims = llm_mod.extract_with_llm(
                "O Bolsa Família acabou, dizem por aí.", self._client()
            )
        finally:
            Handler.fail_429 = 0
        self.assertEqual(
            claims, [{"text": "O Bolsa Família acabou", "kind": "afirmação"}]
        )

    def test_429_persistente_devolve_vazio(self):
        Handler.fail_429 = 10
        try:
            self.assertEqual(
                llm_mod.extract_with_llm("texto", self._client()), []
            )
        finally:
            Handler.fail_429 = 0

    def test_400_json_validate_failed_tenta_de_novo(self):
        # O modelo falhou em gerar JSON válido (400 medido ao vivo,
        # q149): 1x 400 e depois 200.
        Handler.fail_400_json = 1
        try:
            claims = llm_mod.extract_with_llm(
                "O Bolsa Família acabou, dizem por aí.", self._client()
            )
        finally:
            Handler.fail_400_json = 0
        self.assertEqual(
            claims, [{"text": "O Bolsa Família acabou", "kind": "afirmação"}]
        )

    def test_400_outro_erro_nao_tenta(self):
        Handler.status = 400
        Handler.calls = 0
        try:
            self.assertEqual(
                llm_mod.extract_with_llm("texto", self._client()), []
            )
        finally:
            Handler.status = 200
        self.assertEqual(Handler.calls, 1)

    def test_301_para_mesma_url_tenta_de_novo(self):
        # A Groq devolve 301 para a mesma URL de tempos em tempos; sem
        # o handler, o urllib vira GET e a API responde 404.
        Handler.fail_301_self = 1
        try:
            claims = llm_mod.extract_with_llm(
                "O Bolsa Família acabou, dizem por aí.", self._client()
            )
        finally:
            Handler.fail_301_self = 0
        self.assertEqual(
            claims, [{"text": "O Bolsa Família acabou", "kind": "afirmação"}]
        )

    def test_redirect_para_outra_url_preserva_post(self):
        Handler.redirect_other = 1
        try:
            claims = llm_mod.extract_with_llm(
                "O Bolsa Família acabou, dizem por aí.", self._client()
            )
        finally:
            Handler.redirect_other = 0
        self.assertEqual(
            claims, [{"text": "O Bolsa Família acabou", "kind": "afirmação"}]
        )
        self.assertEqual(self.server.last_method, "POST")
        self.assertIn("gpt-oss-20b", self.server.last_body.decode("utf-8"))

    def test_texto_longo_e_cortado_antes_de_enviar(self):
        texto = "O Senado aprovou o PL 1159/2026. " + "x" * 5000 + " MARCADOR_FINAL"
        llm_mod.extract_with_llm(texto, self._client())
        body = json.loads(self.server.last_body.decode("utf-8"))
        user_msg = body["messages"][1]["content"]
        self.assertIn("PL 1159/2026", user_msg)
        self.assertNotIn("MARCADOR_FINAL", user_msg)
        self.assertLessEqual(
            len(user_msg), len("Extraia as alegações atômicas verificáveis deste texto:\n\n")
            + llm_mod.MAX_INPUT_CHARS
        )

    def test_missing_key_raises(self):
        with mock.patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(ValueError):
                llm_mod.GroqClient(api_key=None)

    def test_prompt_pede_lingua_e_referencia(self):
        self.assertIn("mesma língua do texto de origem", llm_mod.SYSTEM_PROMPT)
        self.assertIn("sigla, o número e o ano", llm_mod.SYSTEM_PROMPT)
        self.assertIn("Nunca devolva URLs ou fragmentos de HTML", llm_mod.SYSTEM_PROMPT)

    def test_input_e_limpo_de_html_antes_de_enviar(self):
        llm_mod.extract_with_llm(
            '<p>Senado aprova o PL 1159/2026</p> <img src="https://x.com/f.jpg">',
            self._client(),
        )
        body = json.loads(self.server.last_body.decode("utf-8"))
        user_msg = body["messages"][1]["content"]
        self.assertNotIn("<", user_msg)
        self.assertNotIn("http", user_msg)
        self.assertIn("PL 1159/2026", user_msg)

    def test_url_e_html_da_resposta_sao_filtrados(self):
        Handler.response_body = json.dumps(
            {
                "choices": [
                    {
                        "message": {
                            "content": json.dumps(
                                {
                                    "claims": [
                                        {
                                            "text": "O Senado aprovou o PL 1159/2026",
                                            "kind": "fact",
                                        },
                                        {
                                            "text": "https://s2-g1.glbimg.com/abc",
                                            "kind": "fact",
                                        },
                                        {
                                            "text": "trecho <br /> quebrado",
                                            "kind": "fact",
                                        },
                                    ]
                                }
                            )
                        }
                    }
                ]
            }
        ).encode()
        try:
            claims = llm_mod.extract_with_llm("texto", self._client())
            self.assertEqual(
                claims,
                [{"text": "O Senado aprovou o PL 1159/2026", "kind": "fact"}],
            )
        finally:
            Handler.response_body = json.dumps(CANNED).encode()


if __name__ == "__main__":
    unittest.main()
