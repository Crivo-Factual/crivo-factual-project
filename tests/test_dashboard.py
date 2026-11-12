"""Testes do dashboard (M4)."""

import os
import sqlite3
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from crivo import config
from crivo.factbank import audit, distribution as dist, queue as queue_mod, store
from crivo.pipeline import dashboard


class TestDashboard(unittest.TestCase):
    def setUp(self):
        self.conn = store.init_db(":memory:", config.SCHEMA_PATH)
        queue_mod.init_queue(self.conn)
        audit.init_audit(self.conn)
        dist.init_distribution(self.conn)
        store.insert_publication(self.conn, "q1", "A", None, "2026-11-12T10:00:00+00:00")
        store.insert_publication(self.conn, "q2", "B", None, "2026-11-12T10:00:00+00:00")
        store.insert_verdict(self.conn, "q1", "Falso", 20, "veto", "2026-11-12T10:05:00+00:00", version=1)
        store.insert_verdict(self.conn, "q2", "Inconclusivo", 50, "trava_do_centro", "2026-11-12T10:06:00+00:00", version=1)
        queue_mod.enqueue(self.conn, [{"source": "g1", "title": "C", "link": "https://x", "summary": "", "published": "", "_score": 1}])
        dist.prepare(self.conn, "q1", "x", "texto", cost_usd=0.20)
        audit.log_event(self.conn, "verdict", "q1", {"label": "Falso"})
        self.conn.commit()

    def tearDown(self):
        self.conn.close()

    def test_dashboard_contains_counts(self):
        html = dashboard.build_dashboard(self.conn)
        self.assertIn("Falso", html)
        self.assertIn("Inconclusivo", html)
        self.assertIn("pending", html)
        self.assertIn("x / pending", html)
        self.assertIn("Cadeia íntegra: sim", html)


if __name__ == "__main__":
    unittest.main()
