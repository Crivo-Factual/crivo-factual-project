"""Testes do log de auditoria (M4)."""

import os
import sqlite3
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from crivo.factbank import audit


class TestAudit(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        audit.init_audit(self.conn)

    def tearDown(self):
        self.conn.close()

    def test_chain_verifies(self):
        audit.log_event(self.conn, "collect", None, {"n": 10})
        audit.log_event(self.conn, "verdict", "q1", {"label": "Falso"})
        audit.log_event(self.conn, "message_prepared", "q1", {"channel": "x"})
        self.assertTrue(audit.verify_chain(self.conn))
        self.assertEqual(
            self.conn.execute("SELECT COUNT(*) FROM audit_log").fetchone()[0], 3
        )

    def test_tamper_breaks_chain(self):
        audit.log_event(self.conn, "collect", None, {"n": 10})
        audit.log_event(self.conn, "verdict", "q1", {"label": "Falso"})
        self.conn.execute(
            "UPDATE audit_log SET details = ? WHERE id = 1",
            ('{"n": 999}',),
        )
        self.conn.commit()
        self.assertFalse(audit.verify_chain(self.conn))


if __name__ == "__main__":
    unittest.main()
