"""Testes dos coletores (M2) — sem rede, com amostras fixas."""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from crivo.pipeline import collectors

RSS_SAMPLE = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"><channel><title>Teste</title>
<item><title>Governo anuncia reajuste de 15%</title><link>https://exemplo.br/a</link>
<pubDate>Thu, 12 Nov 2026 10:00:00 +0000</pubDate><description>Texto.</description></item>
<item><title>Sem link</title><link></link><pubDate></pubDate><description></description></item>
</channel></rss>"""

CAMARA_SAMPLE = {"dados": [
    {"ementa": "Altera a CLT.", "siglaTipo": "PL", "numero": 123, "ano": 2026,
     "uri": "https://dadosabertos.camara.leg.br/api/v2/proposicoes/1",
     "dataApresentacao": "2026-11-10"},
    {"ementa": "", "siglaTipo": "PL", "numero": 124, "ano": 2026,
     "uri": "", "dataApresentacao": ""},
]}

SENADO_SAMPLE = """<ListaMaterias><Materias><Materia>
<IdentificacaoMateria><CodigoMateria>999</CodigoMateria>
<SiglaSubtipoMateria>PL</SiglaSubtipoMateria><NumeroMateria>45</NumeroMateria>
<AnoMateria>2026</AnoMateria></IdentificacaoMateria>
<DadosBasicosMateria><DataApresentacao>2026-11-09</DataApresentacao>
<EmentaMateria>Dispõe sobre jornada de trabalho.</EmentaMateria></DadosBasicosMateria>
</Materia></Materias></ListaMaterias>"""


class TestCollectors(unittest.TestCase):
    def test_parse_rss(self):
        items = collectors.parse_rss(RSS_SAMPLE.encode())
        self.assertEqual(len(items), 2)
        self.assertEqual(items[0]["title"], "Governo anuncia reajuste de 15%")
        self.assertEqual(items[0]["link"], "https://exemplo.br/a")

    def test_parse_camara(self):
        items = collectors.parse_camara_proposicoes(CAMARA_SAMPLE)
        self.assertEqual(len(items), 2)
        self.assertTrue(items[0]["title"].startswith("PL 123/2026"))
        self.assertEqual(
            items[0]["link"],
            "https://dadosabertos.camara.leg.br/api/v2/proposicoes/1",
        )

    def test_parse_senado(self):
        items = collectors.parse_senado_materias(SENADO_SAMPLE.encode())
        self.assertEqual(len(items), 1)
        self.assertTrue(items[0]["title"].startswith("PL 45/2026"))
        self.assertEqual(items[0]["link"], "")

    def test_collect_unknown_kind(self):
        items, err = collectors.collect_source(
            {"name": "x", "kind": "nunca", "url": "https://x"}
        )
        self.assertEqual(items, [])
        self.assertIn("desconhecido", err)


if __name__ == "__main__":
    unittest.main()
