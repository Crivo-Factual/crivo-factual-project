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

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        self.rfile.read(length)  # consome o corpo (formato validado pelo mock)
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

    def test_missing_key_raises(self):
        with mock.patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(ValueError):
                llm_mod.GroqClient(api_key=None)


if __name__ == "__main__":
    unittest.main()
