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

    def test_ato_do_dou(self):
        for text, expected in (
            ("Lei nº 14.973, de 2024", "Lei nº 14.973, de 2024"),
            ("EC 141/2026", "EC 141/2026"),
            ("MP 1373", "MP 1373"),
            ("Portaria MF Nº 545, de 2026", "Portaria MF Nº 545, de 2026"),
            ("Decreto-Lei nº 2.848, de 1940", "Decreto-Lei nº 2.848, de 1940"),
        ):
            cands = extract_candidates(text)
            self.assertEqual(len(cands), 1, text)
            self.assertEqual(cands[0]["kind"], "ato", text)
            self.assertEqual(cands[0]["text"], expected, text)

    def test_ato_vem_depois_da_proposicao_e_antes_do_numero(self):
        cands = extract_candidates("50% — PLP 230/2025 e Lei nº 14.973, de 2024")
        self.assertEqual(
            [c["kind"] for c in cands], ["proposição", "ato", "percentual"]
        )

    def test_mp3_nao_vira_ato(self):
        self.assertEqual(extract_candidates("O arquivo MP3 toca no rádio"), [])

    def test_lei_de_ano_nao_vira_ato(self):
        self.assertEqual(extract_candidates("Lei de 2024"), [])

    def test_fragmento_entre_aspas_nao_vira_citacao(self):
        # O padrão de citação casa o texto entre o fechamento de uma
        # aspa e a abertura da próxima: ", disse o secretário." não é
        # citação (caso real q313).
        cands = extract_candidates(
            '"O governo vai cortar gastos", disse o secretário. "Vamos em frente."'
        )
        texts = [c["text"] for c in cands]
        self.assertNotIn(", disse o secretário.", texts)
        self.assertIn("O governo vai cortar gastos", texts)
        self.assertIn("Vamos em frente.", texts)


if __name__ == "__main__":
    unittest.main()
