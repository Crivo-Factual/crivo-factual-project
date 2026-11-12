"""Testes do cliente Instagram (M4) — contra um servidor local de mentira."""

import json
import os
import sys
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from crivo.pipeline import instagram as ig_mod


class Handler(BaseHTTPRequestHandler):
    calls = []

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        self.rfile.read(length)
        Handler.calls.append(self.path)
        if self.path.endswith("/media"):
            body = json.dumps({"id": "container-1"}).encode()
        else:
            body = json.dumps({"id": "post-1"}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *a):
        pass


class TestInstagram(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        cls.port = cls.server.server_address[1]
        threading.Thread(target=cls.server.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()

    def setUp(self):
        Handler.calls.clear()

    def _client(self):
        return ig_mod.InstagramClient(
            user_id="123", access_token="tok",
            base_url=f"http://127.0.0.1:{self.port}",
        )

    def test_publish_flow(self):
        post_id = self._client().publish("https://exemplo.br/foto.jpg", "legenda")
        self.assertEqual(post_id, "post-1")
        self.assertEqual(len(Handler.calls), 2)
        self.assertTrue(Handler.calls[0].endswith("/123/media"))
        self.assertTrue(Handler.calls[1].endswith("/123/media_publish"))

    def test_missing_credentials_raises(self):
        with self.assertRaises(ValueError):
            ig_mod.InstagramClient(user_id="", access_token="")

    def test_missing_image_raises(self):
        with self.assertRaises(ValueError):
            self._client().publish("", "legenda")


if __name__ == "__main__":
    unittest.main()
