"""Testes das mensagens de canal (M4)."""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from crivo.pipeline import channels

BASE = {
    "id": "q1",
    "title": "Bolsa Família acabou?",
    "label": "Falso",
    "index": 20,
    "summary": "O boato voltou a circular. Passamos pelo crivo: o programa continua.",
    "image_url": "https://exemplo.br/foto.jpg",
}


class TestChannels(unittest.TestCase):
    def test_all_three_formats(self):
        msgs = channels.build_messages(BASE)
        self.assertIn("Link na bio", msgs["instagram"]["text"])
        self.assertIn("Análise completa", msgs["whatsapp"]["text"])
        self.assertIn("crivofactual.com.br/analise/q1", msgs["x"]["text"])

    def test_x_fits_280_chars(self):
        long_summary = "x" * 500
        msgs = channels.build_messages({**BASE, "summary": long_summary})
        self.assertLessEqual(len(msgs["x"]["text"]), 280)

    def test_x_cost_with_link(self):
        msgs = channels.build_messages(BASE)
        self.assertEqual(msgs["x"]["cost_usd"], 0.20)

    def test_image_url_passes_through(self):
        msgs = channels.build_messages(BASE)
        for channel in msgs.values():
            self.assertEqual(channel["image_url"], "https://exemplo.br/foto.jpg")

    def test_missing_summary_still_builds(self):
        msgs = channels.build_messages({**BASE, "summary": "", "image_url": ""})
        self.assertIn("Bolsa Família acabou?", msgs["whatsapp"]["text"])
        self.assertEqual(msgs["instagram"]["image_url"], "")


if __name__ == "__main__":
    unittest.main()
