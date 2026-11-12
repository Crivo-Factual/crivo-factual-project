"""Testes da busca do texto completo do artigo (M3, #47)."""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from crivo.pipeline import article


class TestHtmlToText(unittest.TestCase):
    def test_tira_script_style_nav_e_mantem_corpo(self):
        page = """
        <html><head><style>.x{color:red}</style>
        <script>var a = 1;</script></head>
        <body><nav>Menu Home Política</nav>
        <article><h1>Congresso aprova projeto</h1>
        <p>O Congresso aprovou o PL 5832/2026, que institui o
        Programa Primeiro Negócio.</p></article>
        <footer>Rodapé 2026</footer></body></html>
        """
        text = article.html_to_text(page)
        self.assertIn("Congresso aprova projeto", text)
        self.assertIn("PL 5832/2026", text)
        self.assertNotIn("var a", text)
        self.assertNotIn("color:red", text)
        self.assertNotIn("Menu Home", text)
        self.assertNotIn("Rodapé", text)

    def test_desentidades_e_colapsa_espacos(self):
        text = article.html_to_text("<p>A &amp; B &nbsp;  C</p><p>D</p>")
        self.assertEqual(text, "A & B C\nD")

    def test_json_em_data_props_nao_vaza(self):
        # Caso real q294: o g1 embute um JSON enorme num atributo
        # data-props; o JSON contém `>` dentro de strings e um regex
        # de remoção de tags despejava o JSON como texto.
        page = (
            "<html><body>"
            "<section class='mini-home' data-props='{\"channel\":\"desktop\","
            "\"content\":{\"category\":\"85027f2d-fa94-468c\","
            "\"recommendationSummary\":\"Fenômeno deve atingir o pico\","
            "\"image\":{\"cropOptions\":{},\"convert_url\":\"\"}}}'>"
            "</section>"
            "<article><p>O Congresso aprovou o PL 5832/2026.</p></article>"
            "</body></html>"
        )
        text = article.html_to_text(page)
        self.assertIn("PL 5832/2026", text)
        self.assertNotIn("recommendationSummary", text)
        self.assertNotIn("cropOptions", text)
        self.assertNotIn("85027f2d", text)

    def test_widget_de_cotacao_nao_vira_texto(self):
        page = (
            "<html><body>"
            "<div class='ticker'>Ibovespa 170.708 pts -0,79% "
            "Dólar Comercial R$ 5,652</div>"
            "<article><p>O Congresso aprovou o PL 5832/2026.</p></article>"
            "</body></html>"
        )
        text = article.html_to_text(page)
        self.assertIn("PL 5832/2026", text)
        self.assertNotIn("Ibovespa", text)
        self.assertNotIn("5,652", text)


class TestFetchArticle(unittest.TestCase):
    def test_fetcher_falso_devolve_texto_limitado(self):
        def fetch(url):
            return b"<p>" + b"x" * 100 + b" PL 5832/2026</p>"
        text = article.fetch_article_text("https://x/1", fetcher=fetch, max_chars=20)
        self.assertTrue(text.startswith("x" * 20) or len(text) <= 20)

    def test_falha_de_rede_devolve_vazio(self):
        def fetch(url):
            raise ConnectionError("sem rede")
        self.assertEqual(article.fetch_article_text("https://x/1", fetcher=fetch), "")

    def test_sem_url_devolve_vazio(self):
        self.assertEqual(article.fetch_article_text(""), "")


class TestGetItemText(unittest.TestCase):
    def test_noticia_com_link_busca_artigo(self):
        def fetch(url):
            self.assertEqual(url, "https://x/1")
            return b"<p>Corpo com PL 5832/2026.</p>"
        item = {"source": "g1", "title": "Congresso aprova projeto",
                "summary": "", "url": "https://x/1"}
        text = article.get_item_text(item, fetcher=fetch)
        self.assertIn("Congresso aprova projeto", text)
        self.assertIn("PL 5832/2026", text)

    def test_listagem_nao_busca_artigo(self):
        calls = []
        item = {"source": "senado_tramitando", "title": "PL 05827/2026",
                "summary": "", "url": "https://x/1"}
        text = article.get_item_text(item, fetcher=lambda u: calls.append(u) or b"")
        self.assertEqual(calls, [])
        self.assertEqual(text, "PL 05827/2026")

    def test_falha_no_artigo_volta_para_titulo_resumo(self):
        def fetch(url):
            raise ConnectionError("403")
        item = {"source": "g1", "title": "Congresso aprova projeto",
                "summary": "Resumo curto.", "url": "https://x/1"}
        self.assertEqual(article.get_item_text(item, fetcher=fetch),
                         "Congresso aprova projeto Resumo curto.")


if __name__ == "__main__":
    unittest.main()
