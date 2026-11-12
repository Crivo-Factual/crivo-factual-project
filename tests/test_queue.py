"""Testes da fila persistente (M2)."""

import os
import sqlite3
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from crivo.factbank import queue as q


def item(title, score=0, source="g1", link=""):
    return {
        "source": source, "title": title, "link": link, "summary": "",
        "published": "", "_score": score,
    }


class TestQueue(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        q.init_queue(self.conn)

    def tearDown(self):
        self.conn.close()

    def test_enqueue_dedup(self):
        r1 = q.enqueue(self.conn, [item("A", 10, link="https://x/1")])
        r2 = q.enqueue(self.conn, [item("A", 10, link="https://x/1")])
        self.assertEqual((r1["inserted"], r1["duplicates"]), (1, 0))
        self.assertEqual((r2["inserted"], r2["duplicates"]), (0, 1))

    def test_claim_highest_score_first(self):
        q.enqueue(self.conn, [item("baixo", 1), item("alto", 50), item("medio", 10)])
        nxt = q.claim_next(self.conn)
        self.assertEqual(nxt["title"], "alto")
        self.assertEqual(q.counts(self.conn).get("processing"), 1)

    def test_mark_done(self):
        q.enqueue(self.conn, [item("A")])
        nxt = q.claim_next(self.conn)
        q.mark_done(self.conn, nxt["id"])
        self.assertEqual(q.counts(self.conn), {"done": 1})

    def test_retry_backoff_and_give_up(self):
        q.enqueue(self.conn, [item("A")])
        nxt = q.claim_next(self.conn)
        attempts, nxt_retry = q.mark_failed(
            self.conn, nxt["id"], now="2026-11-12T10:00:00+00:00"
        )
        self.assertEqual(attempts, 1)
        self.assertTrue(nxt_retry.startswith("2026-11-12T10:01:00"))
        # Falhas 2 a 5, com o relógio avançando para respeitar o backoff.
        for hour in ("13", "14", "15", "16"):
            nxt = q.claim_next(self.conn, now=f"2026-11-12T{hour}:00:00+00:00")
            self.assertIsNotNone(nxt)
            attempts, nxt_retry = q.mark_failed(
                self.conn, nxt["id"], now=f"2026-11-12T{hour}:00:00+00:00"
            )
        self.assertEqual(attempts, 5)
        self.assertIsNone(nxt_retry)
        self.assertEqual(q.counts(self.conn), {"failed": 1})

    def test_backpressure(self):
        items = [item(f"n{i}", 1) for i in range(5)]
        r = q.enqueue(self.conn, items, max_pending=3)
        self.assertEqual((r["inserted"], r["dropped_backpressure"]), (3, 2))


if __name__ == "__main__":
    unittest.main()
