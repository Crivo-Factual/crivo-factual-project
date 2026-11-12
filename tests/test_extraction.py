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


if __name__ == "__main__":
    unittest.main()
