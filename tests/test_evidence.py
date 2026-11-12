"""Testes das evidências (M3) — fingerprint e boato reciclado."""

import os
import sqlite3
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from crivo import config
from crivo.factbank import store
from crivo.pipeline import evidence


class TestFingerprint(unittest.TestCase):
    def test_ignores_case_accents_punctuation(self):
        a = evidence.fingerprint("O Bolsa Família acabou!")
        b = evidence.fingerprint("o bolsa familia acabou")
        self.assertEqual(a, b)

    def test_different_text_differs(self):
        a = evidence.fingerprint("O Bolsa Família acabou")
        b = evidence.fingerprint("O Bolsa Família continua")
        self.assertNotEqual(a, b)


class TestPreviousVerdict(unittest.TestCase):
    def setUp(self):
        self.conn = store.init_db(":memory:", config.SCHEMA_PATH)
        store.insert_publication(
            self.conn, "p1", "Bolsa Família acabou?", None, "2026-10-27T00:00:00+00:00"
        )
        store.insert_claim(
            self.conn, "p1", "O Bolsa Família acabou", 3, True, "contraditada"
        )
        store.insert_verdict(
            self.conn, "p1", "Falso", 20, "veto", "2026-10-27T00:00:00+00:00", version=1
        )
        store.insert_publication(
            self.conn, "p2", "Lista de cortes?", None, "2026-10-28T00:00:00+00:00"
        )
        store.insert_claim(
            self.conn, "p2", "Existe lista oficial de cortes", 3, True, "sem_evidencia"
        )
        store.insert_verdict(
            self.conn, "p2", "Inconclusivo", 50, "trava_do_centro",
            "2026-10-28T00:00:00+00:00", version=1,
        )
        self.conn.commit()

    def tearDown(self):
        self.conn.close()

    def test_finds_recycled_verdict(self):
        prev = evidence.find_previous_verdict(
            self.conn, evidence.fingerprint("o bolsa familia acabou")
        )
        self.assertEqual(
            prev, {"publication_id": "p1", "status": "contraditada", "label": "Falso"}
        )

    def test_unrelated_claim_returns_none(self):
        prev = evidence.find_previous_verdict(
            self.conn, evidence.fingerprint("A escala 6x1 acabou")
        )
        self.assertIsNone(prev)

    def test_previous_without_evidence_is_not_evidence(self):
        prev = evidence.find_previous_verdict(
            self.conn, evidence.fingerprint("Existe lista oficial de cortes")
        )
        self.assertIsNone(prev)

    def test_next_version_increments(self):
        self.assertEqual(store.next_version(self.conn, "p1"), 2)
        self.assertEqual(store.next_version(self.conn, "p-nova"), 1)


if __name__ == "__main__":
    unittest.main()
