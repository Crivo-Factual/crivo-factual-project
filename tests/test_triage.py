"""Testes da triagem (M2 + correção 12/11/2026)."""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from crivo.pipeline import triage


class TestTriage(unittest.TestCase):
    def test_link_is_verifiable(self):
        self.assertTrue(
            triage.is_verifiable(
                {"title": "Lula discursa", "link": "https://x", "summary": ""}
            )
        )

    def test_link_sozinho_nao_basta(self):
        # Link sem nada checável no título/resumo: o pipeline não lê o
        # artigo, então o item sempre sairia como Sem índice.
        self.assertFalse(
            triage.is_verifiable(
                {"title": "Chuva forte atinge Teresina", "link": "https://x", "summary": ""}
            )
        )

    def test_sem_nada_nao_e_verificavel(self):
        self.assertFalse(
            triage.is_verifiable({"title": "Chuva forte atinge Teresina", "link": "", "summary": ""})
        )

    def test_number_in_title_is_verifiable(self):
        self.assertTrue(
            triage.is_verifiable(
                {"title": "Reajuste de 15% anunciado", "link": "", "summary": ""}
            )
        )

    def test_proposition_reference_is_verifiable(self):
        # Matéria do Senado sem link: a referência "PL 45/2026" é
        # conferível no registro oficial, então é verificável.
        self.assertTrue(
            triage.is_verifiable(
                {
                    "title": "PL 45/2026 — Dispõe sobre jornada de trabalho",
                    "link": "",
                    "summary": "Matéria 999: Dispõe sobre jornada de trabalho.",
                }
            )
        )
        # Outros subtipos do Senado também contam (VET, MSG, PDS).
        self.assertTrue(
            triage.is_verifiable(
                {"title": "VET 00010/2002", "link": "", "summary": ""}
            )
        )

    def test_filter_drops_and_sorts(self):
        items = [
            {"title": "Sem nada", "link": "", "summary": "", "published": ""},
            {"title": "Reajuste de 15%", "link": "", "summary": "", "published": ""},
            {"title": "Governo anuncia medida", "link": "https://x/1", "summary": "", "published": ""},
        ]
        kept, dropped = triage.triage_and_filter(items)
        self.assertEqual(len(kept), 2)
        self.assertEqual(len(dropped), 1)
        self.assertEqual(dropped[0]["title"], "Sem nada")

    def test_noticia_com_referencia_passa_na_frente(self):
        news = {"title": "Aprovado o PL 1159/2026", "summary": "",
                "source": "g1", "published": ""}
        listing = {"title": "PL 05827/2026", "summary": "",
                   "source": "senado_tramitando", "published": ""}
        self.assertGreater(triage.score(news), triage.score(listing))
        self.assertEqual(triage.score(news), 40)

    def test_listagem_nua_tem_score_baixo(self):
        bare = {"title": "PL 05827/2026", "summary": "",
                "source": "senado_tramitando", "published": ""}
        with_ementa = {"title": "PL 05827/2026 — Dispõe sobre jornada",
                       "summary": "", "source": "senado_tramitando", "published": ""}
        self.assertEqual(triage.score(bare), 5)
        self.assertEqual(triage.score(with_ementa), 15)

    def test_palavra_chave_so_no_resumo_nao_infla(self):
        # Menção de passagem no resumo não é o assunto do item.
        crime = {"title": "Troca de tiros deixa dois feridos", "summary": "o governador lamentou",
                 "source": "g1", "published": ""}
        self.assertEqual(triage.score(crime), 0)
        self.assertFalse(triage.is_verifiable(crime))
        politics = {"title": "Governador anuncia pacote", "summary": "",
                    "source": "g1", "published": ""}
        self.assertEqual(triage.score(politics), 10)
        self.assertTrue(triage.is_verifiable(politics))


if __name__ == "__main__":
    unittest.main()
