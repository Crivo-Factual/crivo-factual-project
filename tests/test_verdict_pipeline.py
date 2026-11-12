"""Teste de ponta a ponta do M3: fila -> veredito -> página."""

import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from crivo import config
from crivo.factbank import queue as queue_mod, store
from crivo.pipeline import verdict_pipeline


class FakeLLM:
    """Cliente falso: devolve alegações fixas, sem rede."""

    def __init__(self, claims):
        self._claims = claims

    def complete(self, prompt):
        return json.dumps({"claims": self._claims})


class TestVerdictPipeline(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = os.path.join(self.tmp.name, "test.db")
        self.site = os.path.join(self.tmp.name, "site")
        self.conn = store.init_db(self.db, config.SCHEMA_PATH)
        queue_mod.init_queue(self.conn)
        # Veredito anterior no banco de fatos (boato reciclado).
        store.insert_publication(
            self.conn, "p-antiga", "Bolsa Família acabou?", None,
            "2026-10-27T00:00:00+00:00",
        )
        store.insert_claim(
            self.conn, "p-antiga", "O Bolsa Família acabou", 3, True, "contraditada"
        )
        store.insert_verdict(
            self.conn, "p-antiga", "Falso", 20, "veto",
            "2026-10-27T00:00:00+00:00", version=1,
        )
        self.conn.commit()

    def tearDown(self):
        self.conn.close()
        self.tmp.cleanup()

    def _enqueue(self, title, link="https://x/1", score=30):
        queue_mod.enqueue(
            self.conn,
            [{"source": "g1", "title": title, "link": link, "summary": "",
              "published": "", "_score": score}],
        )

    def test_recycled_claim_gets_veto(self):
        self._enqueue("O Bolsa Família acabou, diz vídeo")
        fake = FakeLLM([{"text": "O Bolsa Família acabou", "kind": "afirmação"}])
        results = verdict_pipeline.process_queue(
            self.conn, limit=5, llm_client=fake, site_dir=self.site
        )
        self.assertEqual(len(results), 1)
        r = results[0]
        # Só a central contraditada: Pc=0, Pf=3, Pt=3 -> índice 0, veto -> Falso.
        self.assertEqual(r["verdict"], ("Falso", 0, "veto"))
        self.assertTrue(r["published"])
        self.assertTrue(os.path.exists(os.path.join(self.site, "analise-q1.html")))
        index_html = open(os.path.join(self.site, "index.html"), encoding="utf-8").read()
        self.assertIn("analise-q1.html", index_html)
        self.assertIn("Falso", index_html)
        self.assertEqual(queue_mod.counts(self.conn), {"done": 1})
        self.assertEqual(store.get_verdict(self.conn, "q1")[0], "Falso")

    def test_no_evidence_is_inconclusive(self):
        self._enqueue("Governo anuncia medida inédita")
        fake = FakeLLM(
            [{"text": "O governo anunciou uma medida inédita", "kind": "afirmação"}]
        )
        results = verdict_pipeline.process_queue(
            self.conn, limit=5, llm_client=fake, site_dir=self.site
        )
        self.assertEqual(
            results[0]["verdict"], ("Inconclusivo", 50, "trava_do_centro")
        )

    def test_no_claims_is_out_of_scope(self):
        self._enqueue("Bom dia", link="https://x/3", score=0)
        # Sem LLM e sem candidatos nas regras -> sem alegações.
        results = verdict_pipeline.process_queue(
            self.conn, limit=5, llm_client=None, site_dir=self.site
        )
        self.assertEqual(results[0]["verdict"], ("Sem índice", None, "sem_alegacoes"))
        self.assertFalse(results[0]["published"])


if __name__ == "__main__":
    unittest.main()
