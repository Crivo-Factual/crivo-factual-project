"""Testes da extração por regras (padrão de proposição, #47)."""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from crivo.pipeline.extraction import extract_candidates


class TestExtraction(unittest.TestCase):
    def test_proposition_siglas(self):
        for text in ("PL 123/2024", "PEC 45/2023", "MPV 12/2026", "RIC 7/2025",
                     "MSC 3/2024", "EMC 1/2026", "SBT 2/2025"):
            cands = extract_candidates(text)
            self.assertEqual(len(cands), 1, text)
            self.assertEqual(cands[0]["kind"], "proposição")

    def test_proposition_sem_numero_nao_casa(self):
        self.assertEqual(extract_candidates("o PL foi aprovado"), [])

    def test_proposicao_vem_primeiro(self):
        cands = extract_candidates("Senado aprova regras: 50% dos recursos — PLP 230/2025")
        self.assertEqual(cands[0]["kind"], "proposição")
        self.assertEqual(cands[0]["text"], "PLP 230/2025")

    def test_numero_com_ponto_de_milhar(self):
        for text, expected in (("PL 1.454/2021", "PL 1.454/2021"),
                               ("PL 12.345/2026", "PL 12.345/2026"),
                               ("PL 1454/2021", "PL 1454/2021")):
            cands = extract_candidates(f"Aprovado o {text}")
            self.assertEqual(cands[0]["text"], expected, text)
            self.assertEqual(cands[0]["kind"], "proposição")

    def test_html_e_removido_antes_de_extrair(self):
        cands = extract_candidates("<p>Senado aprova PLP 230/2025</p> com 50% dos votos")
        texts = [c["text"] for c in cands]
        self.assertIn("PLP 230/2025", texts)
        self.assertTrue(all("<" not in t and ">" not in t for t in texts))

    def test_url_de_imagem_nao_vira_alegacao(self):
        cands = extract_candidates(
            'Notícia <img src="https://s2-g1.glbimg.com/abc123"> sobre o PL 1159/2026'
        )
        texts = [c["text"] for c in cands]
        self.assertTrue(all("http" not in t for t in texts))
        self.assertIn("PL 1159/2026", texts)

    def test_atributo_src_nao_vira_citacao(self):
        cands = extract_candidates(
            '<img src="https://exemplo.com/foto.jpg" alt="texto da foto"> 70% aprovam'
        )
        texts = [c["text"] for c in cands]
        self.assertNotIn("https://exemplo.com/foto.jpg", texts)
        self.assertIn("70%", texts)


if __name__ == "__main__":
    unittest.main()
