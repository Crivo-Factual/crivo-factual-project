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


class FakeSearcher:
    """Busca falsa: confirma qualquer alegação sobre PL 5832/2026."""

    def search_claim(self, text):
        if "PL 5832/2026" in text:
            return {
                "status": "confirmada",
                "source_name": "Câmara dos Deputados — dados abertos",
                "source_url": "https://dadosabertos.camara.leg.br/api/v2/proposicoes/2653123",
                "excerpt": "Ementa oficial: Institui o Programa Primeiro Negócio",
            }
        return None


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
            self.conn, limit=5, llm_client=fake, site_dir=self.site,
            article_fetcher=lambda url: b"",
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
            self.conn, limit=5, llm_client=fake, site_dir=self.site,
            article_fetcher=lambda url: b"",
        )
        self.assertEqual(
            results[0]["verdict"], ("Inconclusivo", 50, "trava_do_centro")
        )

    def test_live_evidence_confirms_proposition(self):
        self._enqueue("PL 5832/2026 — Institui o Programa Primeiro Negócio")
        results = verdict_pipeline.process_queue(
            self.conn, limit=5, site_dir=self.site, searcher=FakeSearcher(),
            article_fetcher=lambda url: b"",
        )
        self.assertEqual(results[0]["verdict"], ("Verdadeiro", 100, "faixa"))
        self.assertTrue(results[0]["published"])

    def test_no_claims_is_out_of_scope(self):
        self._enqueue("Bom dia", link="https://x/3", score=0)
        # Sem LLM e sem candidatos nas regras -> sem alegações.
        results = verdict_pipeline.process_queue(
            self.conn, limit=5, llm_client=None, site_dir=self.site,
            article_fetcher=lambda url: b"",
        )
        self.assertEqual(results[0]["verdict"], ("Sem índice", None, "sem_alegacoes"))
        self.assertFalse(results[0]["published"])

    def test_article_body_provides_reference(self):
        # Título/resumo sem ref; o corpo do artigo traz PL 5832/2026.
        self._enqueue("Congresso aprova projeto de incentivo")

        def fetch(url):
            return (
                "<p>O Congresso aprovou o PL 5832/2026, que institui "
                "o Programa Primeiro Negócio.</p>"
            ).encode("utf-8")

        results = verdict_pipeline.process_queue(
            self.conn, limit=5, llm_client=FakeLLM([]), site_dir=self.site,
            searcher=FakeSearcher(), article_fetcher=fetch,
        )
        self.assertEqual(results[0]["verdict"], ("Verdadeiro", 100, "faixa"))
        self.assertTrue(results[0]["published"])

    def _central_claim(self, publication_id):
        row = self.conn.execute(
            "SELECT text FROM claims WHERE publication_id=? AND central=1",
            (publication_id,),
        ).fetchone()
        return row[0] if row else None

    def test_central_is_llm_assertion_not_bare_date(self):
        # Caso real (rodada 12/11): "12/11/2026" virava a central e
        # travava o veredito. Agora a central é a afirmação do LLM.
        self._enqueue("Congresso aprova pacote de R$ 50 bilhões 12/11/2026")
        fake = FakeLLM(
            [{"text": "O Congresso aprovou um pacote de R$ 50 bilhões",
              "kind": "afirmação"}]
        )
        results = verdict_pipeline.process_queue(
            self.conn, limit=5, llm_client=fake, site_dir=self.site,
            searcher=FakeSearcher(), article_fetcher=lambda url: b"",
        )
        self.assertEqual(
            results[0]["verdict"], ("Inconclusivo", 50, "trava_do_centro")
        )
        self.assertEqual(
            self._central_claim("q1"),
            "O Congresso aprovou um pacote de R$ 50 bilhões",
        )

    def test_central_is_proposition_when_present(self):
        self._enqueue("PL 5832/2026 — R$ 50 bilhões em 12/11/2026")
        results = verdict_pipeline.process_queue(
            self.conn, limit=5, site_dir=self.site, searcher=FakeSearcher(),
            article_fetcher=lambda url: b"",
        )
        self.assertEqual(results[0]["verdict"], ("Verdadeiro", 80, "faixa"))
        self.assertEqual(self._central_claim("q1"), "PL 5832/2026")

    def test_central_is_ato_when_no_proposition(self):
        class FakeDouSearcher:
            def search_claim(self, text):
                if "Lei nº 14.973" in text:
                    return {
                        "status": "confirmada",
                        "source_name": "Diário Oficial da União — Imprensa Nacional",
                        "source_url": "https://www.in.gov.br/web/dou/-/lei-n-14-973-2",
                        "excerpt": "LEI Nº 14.973, DE 16 DE SETEMBRO DE 2024 — Publicado em 16/09/2024.",
                    }
                return None

        self._enqueue("Lei nº 14.973, de 2024, foi sancionada")
        results = verdict_pipeline.process_queue(
            self.conn, limit=5, site_dir=self.site, searcher=FakeDouSearcher(),
            article_fetcher=lambda url: b"",
        )
        self.assertEqual(results[0]["verdict"], ("Verdadeiro", 100, "faixa"))
        self.assertEqual(self._central_claim("q1"), "Lei nº 14.973, de 2024")

    def test_only_bare_numbers_central_is_first(self):
        # Só número e data: não há alternativa — a central cai no
        # primeiro candidato (sem quebrar) e o veredito trava.
        self._enqueue("Bolsa Família de R$ 691 em 12/11/2026")
        results = verdict_pipeline.process_queue(
            self.conn, limit=5, llm_client=None, site_dir=self.site,
            article_fetcher=lambda url: b"",
        )
        self.assertEqual(
            results[0]["verdict"], ("Inconclusivo", 50, "trava_do_centro")
        )
        self.assertEqual(self._central_claim("q1"), "R$ 691")


if __name__ == "__main__":
    unittest.main()
