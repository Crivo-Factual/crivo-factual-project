"""Testes da busca de evidências primárias (#47) — com clientes de mentira."""

import json
import os
import sys
import unittest
import urllib.error

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from crivo.pipeline import evidence_search as ev


def camara_fetch(ementa, situacao=None, tramitacao=None, found=True):
    def fetch(url):
        dados = []
        if found:
            dados = [{
                "id": 1,
                "uri": "https://dadosabertos.camara.leg.br/api/v2/proposicoes/1",
                "ementa": ementa,
                "statusProposicao": {
                    "descricaoSituacao": situacao,
                    "descricaoTramitacao": tramitacao,
                },
            }]
        return json.dumps({"dados": dados}).encode()
    return fetch


def senado_fetch(ementa, tramitando="Sim", found=True):
    def fetch(url):
        if not found:
            raise urllib.error.HTTPError(url, 404, "Not Found", None, None)
        xml = (
            "<Materia><CodigoMateria>123</CodigoMateria>"
            f"<EmentaMateria>{ementa}</EmentaMateria>"
            f"<IndicadorTramitando>{tramitando}</IndicadorTramitando></Materia>"
        )
        return xml.encode()
    return fetch


def failing_fetch(url):
    raise urllib.error.URLError("sem rede")


class TestEvidenceSearch(unittest.TestCase):
    def test_ementa_match_confirma(self):
        s = ev.Searcher(camara=ev.CamaraClient(camara_fetch("Institui o Programa Primeiro Negócio")),
                        senado=ev.SenadoClient(senado_fetch("x", found=False)))
        r = s.search_claim("PL 5832/2026 — Institui o Programa Primeiro Negócio")
        self.assertEqual(r["status"], "confirmada")
        self.assertIn("Câmara", r["source_name"])

    def test_status_aprovada_confirma(self):
        s = ev.Searcher(camara=ev.CamaraClient(camara_fetch("Ementa qualquer", situacao="Aprovada")),
                        senado=ev.SenadoClient(senado_fetch("x", found=False)))
        r = s.search_claim("PL 1/2026 foi aprovada na Câmara")
        self.assertEqual(r["status"], "confirmada")

    def test_status_aprovada_contra_rejeitada(self):
        s = ev.Searcher(camara=ev.CamaraClient(camara_fetch("Ementa qualquer", situacao="Rejeitada")),
                        senado=ev.SenadoClient(senado_fetch("x", found=False)))
        r = s.search_claim("PL 1/2026 foi aprovada na Câmara")
        self.assertEqual(r["status"], "contraditada")

    def test_status_sem_mapeamento_nao_decide(self):
        s = ev.Searcher(camara=ev.CamaraClient(camara_fetch("Ementa qualquer", tramitacao="Apresentação de Proposição")),
                        senado=ev.SenadoClient(senado_fetch("x", found=False)))
        self.assertIsNone(s.search_claim("PL 1/2026 foi aprovada na Câmara"))

    def test_senado_fallback(self):
        s = ev.Searcher(camara=ev.CamaraClient(camara_fetch("x", found=False)),
                        senado=ev.SenadoClient(senado_fetch("Altera o Código de Trânsito Brasileiro")))
        r = s.search_claim("PL 5833/2026 — Altera o Código de Trânsito Brasileiro")
        self.assertEqual(r["status"], "confirmada")
        self.assertIn("Senado", r["source_name"])

    def test_nao_encontrada_com_status_federal_contradiz(self):
        s = ev.Searcher(camara=ev.CamaraClient(camara_fetch("x", found=False)),
                        senado=ev.SenadoClient(senado_fetch("x", found=False)))
        r = s.search_claim("PL 99999/2024 foi aprovada no Congresso")
        self.assertEqual(r["status"], "contraditada")

    def test_nao_encontrada_sem_casa_nao_decide(self):
        s = ev.Searcher(camara=ev.CamaraClient(camara_fetch("x", found=False)),
                        senado=ev.SenadoClient(senado_fetch("x", found=False)))
        self.assertIsNone(s.search_claim("PL 99999/2024 foi aprovada"))

    def test_sem_referencia_nao_busca(self):
        s = ev.Searcher(camara=ev.CamaraClient(camara_fetch("x")),
                        senado=ev.SenadoClient(senado_fetch("x")))
        self.assertIsNone(s.search_claim("Bolsa Família acabou"))

    def test_parafrase_nao_confirma(self):
        s = ev.Searcher(camara=ev.CamaraClient(camara_fetch("Institui o Programa Primeiro Negócio")),
                        senado=ev.SenadoClient(senado_fetch("x", found=False)))
        self.assertIsNone(s.search_claim("PL 5832/2026 acaba com o Bolsa Família"))

    def test_erro_de_rede_nao_quebra(self):
        s = ev.Searcher(camara=ev.CamaraClient(failing_fetch),
                        senado=ev.SenadoClient(failing_fetch))
        self.assertIsNone(s.search_claim("PL 1/2026 — Ementa qualquer"))

    def test_arquivada_contra_tramitando(self):
        s = ev.Searcher(camara=ev.CamaraClient(camara_fetch("x", found=False)),
                        senado=ev.SenadoClient(senado_fetch("Ementa qualquer", tramitando="Sim")))
        r = s.search_claim("PL 1/2026 foi arquivada no Senado")
        self.assertEqual(r["status"], "contraditada")

    def test_cache_evita_repetir_consulta(self):
        calls = []
        def counting(url):
            calls.append(url)
            return camara_fetch("Institui o Programa Primeiro Negócio")(url)
        s = ev.Searcher(camara=ev.CamaraClient(counting),
                        senado=ev.SenadoClient(senado_fetch("x", found=False)))
        s.search_claim("PL 5832/2026 — Institui o Programa Primeiro Negócio")
        s.search_claim("PL 5832/2026 — Institui o Programa Primeiro Negócio")
        self.assertEqual(len(calls), 1)


if __name__ == "__main__":
    unittest.main()
