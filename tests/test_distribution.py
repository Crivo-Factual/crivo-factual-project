"""Testes do outbox de distribuição (M4)."""

import os
import sqlite3
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from crivo.factbank import distribution as dist


class TestDistribution(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        dist.init_distribution(self.conn)

    def tearDown(self):
        self.conn.close()

    def test_prepare_is_idempotent(self):
        id1, created1 = dist.prepare(self.conn, "q1", "x", "texto", cost_usd=0.20)
        id2, created2 = dist.prepare(self.conn, "q1", "x", "texto", cost_usd=0.20)
        self.assertTrue(created1)
        self.assertFalse(created2)
        self.assertEqual(id1, id2)
        self.assertEqual(len(dist.list_pending(self.conn)), 1)

    def test_mark_sent(self):
        dist_id, _ = dist.prepare(self.conn, "q1", "whatsapp", "texto")
        self.assertTrue(dist.mark_sent(self.conn, dist_id))
        self.assertFalse(dist.mark_sent(self.conn, dist_id))
        self.assertEqual(dist.list_pending(self.conn), [])

    def test_prepared_on_counts_by_day(self):
        dist.prepare(self.conn, "q1", "x", "a", now="2026-11-12T10:00:00+00:00")
        dist.prepare(self.conn, "q2", "x", "b", now="2026-11-12T11:00:00+00:00")
        dist.prepare(self.conn, "q3", "x", "c", now="2026-11-11T10:00:00+00:00")
        self.assertEqual(dist.prepared_on(self.conn, "x", "2026-11-12"), 2)
        self.assertEqual(dist.prepared_on(self.conn, "x", "2026-11-11"), 1)


if __name__ == "__main__":
    unittest.main()
