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


class FakeDou:
    """DOU de mentira: atos conhecidos por (tipo, número, ano)."""

    def __init__(self, acts=None):
        self.acts = acts or {}
        self.calls = []

    def find_act(self, act_type, number, year=None):
        self.calls.append((act_type, number, year))
        return self.acts.get((act_type, number, year))


def _dou_searcher(acts=None):
    return ev.Searcher(
        camara=ev.CamaraClient(failing_fetch),
        senado=ev.SenadoClient(failing_fetch),
        dou=FakeDou(acts),
    )


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

    def test_dou_confirma_ec_promulgada(self):
        hit = {"title": "EMENDA CONSTITUCIONAL Nº 141",
               "pub_date": "16/10/2026", "url_title": "emenda-constitucional-n-141-1"}
        s = _dou_searcher({("Emenda Constitucional", "141", 2026): hit})
        r = s.search_claim("A Emenda Constitucional nº 141, de 2026, foi promulgada")
        self.assertEqual(r["status"], "confirmada")
        self.assertIn("Diário Oficial", r["source_name"])

    def test_dou_confirma_lei_sancionada(self):
        hit = {"title": "LEI Nº 14.973, DE 16 DE SETEMBRO DE 2024",
               "pub_date": "16/09/2024", "url_title": "lei-n-14-973-2"}
        s = _dou_searcher({("Lei", "14973", 2024): hit})
        r = s.search_claim("A Lei nº 14.973, de 2024, foi sancionada")
        self.assertEqual(r["status"], "confirmada")

    def test_dou_ato_inexistente_com_status_federal_contradiz(self):
        s = _dou_searcher({})
        r = s.search_claim(
            "A Lei nº 99.999, de 2026, foi sancionada pelo Congresso Nacional")
        self.assertEqual(r["status"], "contraditada")
        self.assertIn("Diário Oficial", r["source_name"])

    def test_dou_ato_inexistente_sem_status_nao_decide(self):
        s = _dou_searcher({})
        self.assertIsNone(s.search_claim("Lei nº 99.999, de 2026"))

    def test_dou_status_nao_implicado_nao_confirma(self):
        hit = {"title": "DECRETO Nº 10.954, DE 29 DE JANEIRO DE 2022",
               "pub_date": "29/01/2022", "url_title": "decreto-n-10-954-3"}
        s = _dou_searcher({("Decreto", "10954", 2022): hit})
        # Decreto não é "aprovado" pelo Congresso: o ato existe, mas
        # o status afirmado não é implicado por ele.
        self.assertIsNone(s.search_claim("O Decreto nº 10.954, de 2022, foi aprovado"))

    def test_proposicao_nao_cai_no_dou(self):
        # A alegação tem ref de proposição: o caminho é o das APIs de
        # dados abertos, mesmo que ela cite uma lei — o DOU nem é
        # consultado.
        fake_dou = FakeDou({("Lei", "8629", 1993): {
            "title": "LEI Nº 8.629, DE 25 DE FEVEREIRO DE 1993",
            "pub_date": "26/02/1993", "url_title": "lei-n-8-629-4"}})
        s = ev.Searcher(
            camara=ev.CamaraClient(camara_fetch("Ementa qualquer que não casa")),
            senado=ev.SenadoClient(senado_fetch("x", found=False)),
            dou=fake_dou)
        r = s.search_claim("O PL 810/2020 altera a Lei nº 8.629, de 1993")
        self.assertIsNone(r)
        self.assertEqual(fake_dou.calls, [])


if __name__ == "__main__":
    unittest.main()
