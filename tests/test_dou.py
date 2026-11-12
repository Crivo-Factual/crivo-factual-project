"""Testes da busca no DOU (issue #47)."""

import json
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from crivo.pipeline import dou

SAMPLE_PAGE = """
<html><body>
<script id="_br_com_seatecnologia_in_buscadou_BuscaDouPortlet_params" type="application/json">
{"jsonArray":[
  {"pubName":"DO1","urlTitle":"emenda-constitucional-n-141-1","numberPage":"1",
   "title":"EMENDA CONSTITUCIONAL Nº 141","pubDate":"16/10/2026",
   "editionNumber":"198","content":"...","artType":"Emenda Constitucional",
   "classPK":"1","hierarchyStr":"Congresso Nacional"},
  {"pubName":"DO1","urlTitle":"lei-n-14-973-de-16-de-setembro-de-2024-2","numberPage":"1",
   "title":"LEI Nº <span class='highlight' style='background:#FFA;'>14.973</span>, DE 16 DE SETEMBRO DE 2024",
   "pubDate":"16/09/2024","editionNumber":"179","content":"...","artType":"Lei",
   "classPK":"2","hierarchyStr":"Presidência da República"}
]}
</script>
</body></html>
"""


class TestParseHits(unittest.TestCase):
    def test_extracao_do_json_embutido(self):
        hits = dou.parse_hits(SAMPLE_PAGE)
        self.assertEqual(len(hits), 2)
        self.assertEqual(hits[0]["title"], "EMENDA CONSTITUCIONAL Nº 141")
        self.assertEqual(hits[0]["art_type"], "Emenda Constitucional")
        self.assertEqual(hits[0]["pub_date"], "16/10/2026")
        # O título vem com <span> de destaque da busca: limpo.
        self.assertEqual(
            hits[1]["title"], "LEI Nº 14.973, DE 16 DE SETEMBRO DE 2024"
        )

    def test_sem_json_devolve_lista_vazia(self):
        self.assertEqual(dou.parse_hits("<html></html>"), [])
        self.assertEqual(dou.parse_hits(""), [])


class TestParseActTitle(unittest.TestCase):
    def test_titulos(self):
        cases = [
            ("LEI Nº 14.973, DE 16 DE SETEMBRO DE 2024",
             ("Lei", "14973", 2024)),
            ("EMENDA CONSTITUCIONAL Nº 141",
             ("Emenda Constitucional", "141", None)),
            ("DECRETO Nº 10.954, DE 29 DE JANEIRO DE 2022",
             ("Decreto", "10954", 2022)),
            ("PORTARIA MF Nº 545, DE 2 DE MARÇO DE 2026",
             ("Portaria", "545", 2026)),
        ]
        for title, expected in cases:
            parsed = dou.parse_act_title(title)
            self.assertEqual(
                (parsed["type"], parsed["number"], parsed["year"]),
                expected, title,
            )

    def test_titulo_que_nao_e_ato(self):
        self.assertIsNone(dou.parse_act_title("EDITAL Nº 406, DE 11 DE NOVEMBRO DE 2026"))
        self.assertIsNone(dou.parse_act_title("EXTRATO DE CONTRATO"))


class TestFormatNumber(unittest.TestCase):
    def test_ponto_de_milhar(self):
        self.assertEqual(dou.format_number("14973"), "14.973")
        self.assertEqual(dou.format_number("141"), "141")
        self.assertEqual(dou.format_number("1373"), "1.373")


class TestDouClient(unittest.TestCase):
    def test_find_act_casa_tipo_numero_ano(self):
        calls = []

        def fetch(url):
            calls.append(url)
            return SAMPLE_PAGE.encode("utf-8")

        client = dou.DouClient(fetcher=fetch)
        hit = client.find_act("Lei", "14973", 2024)
        self.assertIsNotNone(hit)
        self.assertIn("14.973", hit["title"])
        self.assertIn("lei", calls[0])
        self.assertIn("14.973", calls[0])

    def test_find_act_ano_divergente_nao_casa(self):
        client = dou.DouClient(fetcher=lambda url: SAMPLE_PAGE.encode("utf-8"))
        self.assertIsNone(client.find_act("Lei", "14973", 2025))

    def test_find_act_numero_inexistente(self):
        client = dou.DouClient(fetcher=lambda url: SAMPLE_PAGE.encode("utf-8"))
        self.assertIsNone(client.find_act("Lei", "99999", 2026))

    def test_cache_evita_repetir_consulta(self):
        calls = []

        def fetch(url):
            calls.append(url)
            return SAMPLE_PAGE.encode("utf-8")

        client = dou.DouClient(fetcher=fetch)
        client.find_act("Emenda Constitucional", "141", 2026)
        client.find_act("Emenda Constitucional", "141", 2026)
        self.assertEqual(len(calls), 1)

    def test_falha_de_rede_devolve_vazio(self):
        def fetch(url):
            raise ConnectionError("sem rede")

        client = dou.DouClient(fetcher=fetch)
        self.assertEqual(client.search("lei"), [])
        self.assertIsNone(client.find_act("Lei", "14973", 2024))


if __name__ == "__main__":
    unittest.main()
