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


def camara_fetch_multi(records):
    """Vários registros para a mesma referência (tipo ambíguo).

    records: lista de (ementa, situacao, uri)."""
    def fetch(url):
        dados = [{
            "id": i + 1,
            "uri": uri,
            "ementa": ementa,
            "statusProposicao": {"descricaoSituacao": situacao, "descricaoTramitacao": None},
        } for i, (ementa, situacao, uri) in enumerate(records)]
        return json.dumps({"dados": dados}).encode()
    return fetch


def camara_fetch_paged(pages):
    """Uma página por chamada: pages é {pagina: [ementas]}.

    Todas as páginas menos a última trazem links.next."""
    def fetch(url):
        import re as _re
        m = _re.search(r"pagina=(\d+)", url)
        pagina = int(m.group(1)) if m else 1
        dados = [{
            "id": i + 1,
            "uri": f"https://dadosabertos.camara.leg.br/api/v2/proposicoes/{pagina}{i}",
            "ementa": ementa,
            "statusProposicao": {"descricaoSituacao": None, "descricaoTramitacao": None},
        } for i, ementa in enumerate(pages.get(pagina, []))]
        links = []
        if pagina < max(pages):
            links = [{"rel": "next", "href": url.replace(f"pagina={pagina}", f"pagina={pagina + 1}")}]
        return json.dumps({"dados": dados, "links": links}).encode()
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

    def test_ementa_do_segundo_registro_confirma(self):
        s = ev.Searcher(camara=ev.CamaraClient(camara_fetch_multi([
            ("Altera a Lei de Aeronáutica", None, "https://x/1"),
            ("Institui tratamento tributário diferenciado para os profissionais de segurança pública",
             None, "https://x/2"),
        ])), senado=ev.SenadoClient(senado_fetch("x", found=False)))
        r = s.search_claim(
            "EMC 1/2026 institui tratamento tributário diferenciado "
            "para os profissionais de segurança pública"
        )
        self.assertEqual(r["status"], "confirmada")
        self.assertEqual(r["source_url"], "https://x/2")

    def test_ambigua_status_sem_ementa_nao_decide(self):
        s = ev.Searcher(camara=ev.CamaraClient(camara_fetch_multi([
            ("Ementa qualquer", "Aprovada", "https://x/1"),
            ("Outra ementa qualquer", None, "https://x/2"),
        ])), senado=ev.SenadoClient(senado_fetch("x", found=False)))
        # O status é da primeira EMC, mas nada liga a alegação a ela.
        self.assertIsNone(s.search_claim("EMC 1/2026 foi aprovada na Câmara"))

    def test_ambigua_status_usa_registro_da_ementa(self):
        s = ev.Searcher(camara=ev.CamaraClient(camara_fetch_multi([
            ("Institui o Programa Primeiro Negócio", "Rejeitada", "https://x/1"),
            ("Institui tratamento tributário diferenciado", "Aprovada", "https://x/2"),
        ])), senado=ev.SenadoClient(senado_fetch("x", found=False)))
        r = s.search_claim(
            "EMC 1/2026, que institui tratamento tributário diferenciado, "
            "foi aprovada na Câmara"
        )
        self.assertEqual(r["status"], "confirmada")
        self.assertEqual(r["source_url"], "https://x/2")

    def test_search_all_pagina_ate_alvo(self):
        client = ev.CamaraClient(camara_fetch_paged({
            1: ["Ementa da página 1"],
            2: ["Institui tratamento tributário diferenciado"],
        }))
        records = client.search_all("EMC", "1", "2026")
        self.assertEqual(len(records), 2)
        self.assertEqual(records[1]["ementa"],
                         "Institui tratamento tributário diferenciado")
        # search() continua devolvendo só o primeiro registro.
        self.assertEqual(client.search("EMC", "1", "2026")["ementa"],
                         "Ementa da página 1")

    def test_artigo_antes_da_referencia_nao_quebra_contencao(self):
        s = ev.Searcher(camara=ev.CamaraClient(camara_fetch("Institui o Programa Primeiro Negócio")),
                        senado=ev.SenadoClient(senado_fetch("x", found=False)))
        r = s.search_claim("O PL 5832/2026 institui o Programa Primeiro Negócio")
        self.assertEqual(r["status"], "confirmada")

    def test_numero_com_ponto_consulta_sem_ponto(self):
        urls = []
        def fetch(url):
            urls.append(url)
            return camara_fetch("Institui o Programa Primeiro Negócio")(url)
        s = ev.Searcher(camara=ev.CamaraClient(fetch),
                        senado=ev.SenadoClient(senado_fetch("x", found=False)))
        r = s.search_claim("O PL 1.454/2021 institui o Programa Primeiro Negócio")
        self.assertEqual(r["status"], "confirmada")
        self.assertTrue(any("numero=1454" in u for u in urls), urls)
        self.assertFalse(any("1.454" in u for u in urls), urls)

    def test_ementa_do_senado_quando_a_da_camara_difere(self):
        # A mesma proposição tem redações diferentes nas duas casas;
        # a confirmação precisa testar as duas.
        s = ev.Searcher(
            camara=ev.CamaraClient(camara_fetch(
                "Institui o Selo-Arte Café, a ser conferido ao produto obtido mediante o emprego de modo artesanal")),
            senado=ev.SenadoClient(senado_fetch(
                "Institui o selo Arte Café, a ser conferido ao café produzido e processado de modo artesanal")))
        r = s.search_claim(
            "PL 1.454/2023 — Institui o selo Arte Café, a ser conferido "
            "ao café produzido e processado de modo artesanal.")
        self.assertEqual(r["status"], "confirmada")
        self.assertIn("Senado", r["source_name"])


if __name__ == "__main__":
    unittest.main()
