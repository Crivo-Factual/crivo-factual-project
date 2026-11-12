"""Testes do boletim semanal (M4)."""

import os
import sqlite3
import sys
import unittest
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from crivo import config
from crivo.factbank import store
from crivo.pipeline import newsletter


class TestNewsletter(unittest.TestCase):
    def setUp(self):
        self.conn = store.init_db(":memory:", config.SCHEMA_PATH)
        now = datetime(2026, 11, 12, 12, 0, tzinfo=timezone.utc)
        self.now = now
        store.insert_publication(self.conn, "q1", "Recente", None, "2026-11-11T10:00:00+00:00")
        store.insert_verdict(self.conn, "q1", "Falso", 20, "veto", "2026-11-11T10:00:00+00:00", version=1)
        store.insert_publication(self.conn, "q2", "Antiga", None, "2026-11-01T10:00:00+00:00")
        store.insert_verdict(self.conn, "q2", "Verdadeiro", 100, "faixa", "2026-11-01T10:00:00+00:00", version=1)
        self.conn.commit()

    def tearDown(self):
        self.conn.close()

    def test_digest_only_recent(self):
        digest = newsletter.build_weekly_digest(self.conn, days=7, now=self.now)
        self.assertEqual(digest["count"], 1)
        self.assertIn("Recente", digest["body_md"])
        self.assertNotIn("Antiga", digest["body_md"])
        self.assertIn("1 verificações", digest["subject"])

    def test_empty_week(self):
        digest = newsletter.build_weekly_digest(self.conn, days=1, now=self.now)
        self.assertEqual(digest["count"], 0)
        self.assertIn("Nenhuma verificação nova", digest["body_md"])


if __name__ == "__main__":
    unittest.main()
