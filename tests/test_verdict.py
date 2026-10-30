"""Testes do motor de veredito determinístico (doc 02)."""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from crivo.pipeline.verdict import Claim, compute_index, label_for, verdict


def C(text, weight=1, central=False, status="sem_evidencia"):
    return Claim(text=text, weight=weight, central=central, status=status)


class TestIndex(unittest.TestCase):
    def test_all_confirmed(self):
        claims = [C("central", 3, True, "confirmada"),
                  C("apoio", 1, False, "confirmada")]
        self.assertEqual(compute_index(claims), 100)

    def test_doc_example_veto_index(self):
        # Exemplo do doc 02: central contraditada (3) + 2 suportes (1+1).
        claims = [C("central", 3, True, "contraditada"),
                  C("apoio 1", 1, False, "confirmada"),
                  C("apoio 2", 1, False, "confirmada")]
        self.assertEqual(compute_index(claims), 40)

    def test_no_claims(self):
        self.assertIsNone(compute_index([]))

    def test_all_no_evidence(self):
        claims = [C("a", 1, False), C("b", 1, False)]
        self.assertEqual(compute_index(claims), 50)


class TestVerdict(unittest.TestCase):
    def test_veto_overrides_index(self):
        claims = [C("central", 3, True, "contraditada"),
                  C("apoio 1", 1, False, "confirmada"),
                  C("apoio 2", 1, False, "confirmada")]
        label, index, rule = verdict(claims)
        self.assertEqual((label, rule), ("Falso", "veto"))
        self.assertEqual(index, 40)

    def test_center_lock(self):
        claims = [C("central", 3, True, "sem_evidencia"),
                  C("apoio", 1, False, "confirmada")]
        self.assertEqual(verdict(claims), ("Inconclusivo", 50, "trava_do_centro"))

    def test_no_claims(self):
        self.assertEqual(verdict([]), ("Sem índice", None, "sem_alegacoes"))

    def test_mixed_75(self):
        claims = [C("central", 3, True, "confirmada"),
                  C("apoio", 1, False, "contraditada")]
        label, index, rule = verdict(claims)
        self.assertEqual(index, 75)
        self.assertEqual(label, "Predominantemente verdadeiro")

    def test_bolsa_demo_values(self):
        claims = [C("O Bolsa Família acabou", 3, True, "contraditada"),
                  C("Os pagamentos foram suspensos", 1, False, "contraditada"),
                  C("Houve reajuste", 1, False, "confirmada")]
        label, index, rule = verdict(claims)
        self.assertEqual((label, index, rule), ("Falso", 20, "veto"))


class TestBands(unittest.TestCase):
    def test_boundaries(self):
        cases = [
            (100, "Verdadeiro"), (80, "Verdadeiro"),
            (79.9, "Predominantemente verdadeiro"), (60, "Predominantemente verdadeiro"),
            (59.9, "Inconclusivo"), (40, "Inconclusivo"),
            (39.9, "Predominantemente falso"), (20, "Predominantemente falso"),
            (19.9, "Falso"), (0, "Falso"),
        ]
        for index, expected in cases:
            with self.subTest(index=index):
                self.assertEqual(label_for(index), expected)


if __name__ == "__main__":
    unittest.main()
