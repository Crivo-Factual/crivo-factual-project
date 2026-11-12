"""Testes da triagem (M2)."""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from crivo.pipeline import triage


class TestTriage(unittest.TestCase):
    def test_link_is_verifiable(self):
        self.assertTrue(
            triage.is_verifiable(
                {"title": "Lula discursa", "link": "https://x", "summary": ""}
            )
        )

    def test_no_link_no_claim_is_not_verifiable(self):
        self.assertFalse(
            triage.is_verifiable({"title": "Lula discursa", "link": "", "summary": ""})
        )

    def test_number_in_title_is_verifiable(self):
        self.assertTrue(
            triage.is_verifiable(
                {"title": "Reajuste de 15% anunciado", "link": "", "summary": ""}
            )
        )

    def test_proposition_reference_is_verifiable(self):
        # Matéria do Senado sem link: a referência "PL 45/2026" é
        # conferível no registro oficial, então é verificável.
        self.assertTrue(
            triage.is_verifiable(
                {
                    "title": "PL 45/2026 — Dispõe sobre jornada de trabalho",
                    "link": "",
                    "summary": "Matéria 999: Dispõe sobre jornada de trabalho.",
                }
            )
        )
        # Outros subtipos do Senado também contam (VET, MSG, PDS).
        self.assertTrue(
            triage.is_verifiable(
                {"title": "VET 00010/2002", "link": "", "summary": ""}
            )
        )

    def test_filter_drops_and_sorts(self):
        items = [
            {"title": "Sem nada", "link": "", "summary": "", "published": ""},
            {"title": "Reajuste de 15%", "link": "", "summary": "", "published": ""},
            {"title": "Governo anuncia medida", "link": "https://x/1", "summary": "", "published": ""},
        ]
        kept, dropped = triage.triage_and_filter(items)
        self.assertEqual(len(kept), 2)
        self.assertEqual(len(dropped), 1)
        self.assertEqual(dropped[0]["title"], "Sem nada")


if __name__ == "__main__":
    unittest.main()
