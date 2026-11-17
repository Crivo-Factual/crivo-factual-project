"""Testes do classificador de ML (crivo/ml) e da integração com a triagem.

Os testes que treinam de verdade pulam quando o scikit-learn não
está instalado (o repo é só biblioteca padrão; o ML vive num venv
separado). Os testes de integração usam um modelo falso — não
precisam do sklearn.
"""

import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from crivo import config
from crivo.factbank import queue as queue_mod, store
from crivo.ml import classifier as clf_mod
from crivo.ml.dataset import NewsItem, load_fakebr
from crivo.pipeline import triage as triage_mod
from crivo.pipeline import verdict_pipeline

ML_AVAILABLE = clf_mod.SKLEARN_AVAILABLE

FAKE_TEMPLATES = [
    "URGENTE: {assunto} — você não vai acreditar no que aconteceu! "
    "Compartilhe antes que apaguem! {enchimento}",
    "EXCLUSIVO: {assunto} escondido da população! A mídia não mostra! "
    "Clique e veja a verdade! {enchimento}",
]
TRUE_TEMPLATES = [
    "A Câmara dos Deputados aprovou nesta terça-feira o projeto sobre "
    "{assunto}. A votação contou com ampla maioria. {enchimento}",
    "O Senado Federal publicou nesta semana o relatório sobre {assunto}. "
    "O documento traz dados oficiais do governo. {enchimento}",
]
ENCHIMENTO = ("O texto segue com detalhes apurados pela redação, "
              "com declarações de autoridades e números oficiais. " * 6)


def _synthetic_items(n_per_class=20):
    items = []
    for i in range(n_per_class):
        assunto = f"tema {i}"
        items.append(NewsItem(
            text=FAKE_TEMPLATES[i % 2].format(
                assunto=assunto, enchimento=ENCHIMENTO),
            label=1, pair=f"par-{i}",
        ))
        items.append(NewsItem(
            text=TRUE_TEMPLATES[i % 2].format(
                assunto=assunto, enchimento=ENCHIMENTO),
            label=0, pair=f"par-{i}",
        ))
    return items


class FakeModel:
    """Modelo falso: devolve probabilidade fixa de falso."""

    def __init__(self, proba_falsa=0.9):
        self._proba = proba_falsa

    def predict_proba(self, texts):
        return [[1 - self._proba, self._proba] for _ in texts]


class TestDataset(unittest.TestCase):
    def test_load_fakebr_missing_dir(self):
        with self.assertRaises(FileNotFoundError):
            load_fakebr("/caminho/que/nao/existe")

    @unittest.skipUnless(ML_AVAILABLE, "scikit-learn não instalado")
    def test_split_is_pair_aware(self):
        items = _synthetic_items()
        X_train, _, X_test, _ = clf_mod.split(items, test_size=0.25, seed=42)
        train_texts = set(X_train)
        test_texts = set(X_test)
        # Nenhum par (mesmo tema, falsa e verdadeira) nos dois lados:
        # os textos de treino e teste não se sobrepõem.
        self.assertEqual(train_texts & test_texts, set())
        self.assertEqual(len(X_train) + len(X_test), len(items))


@unittest.skipUnless(ML_AVAILABLE, "scikit-learn não instalado")
class TestClassifier(unittest.TestCase):
    def test_pipeline_trains_and_predicts(self):
        items = _synthetic_items()
        X_train, y_train, X_test, y_test = clf_mod.split(
            items, test_size=0.25, seed=42)
        pipe = clf_mod.build_pipeline("logreg")
        pipe.fit(X_train, y_train)
        metrics = clf_mod.evaluate(pipe, X_test, y_test)
        self.assertGreaterEqual(metrics["accuracy"], 0.8)
        self.assertIn("roc_auc", metrics)
        self.assertEqual(len(metrics["confusion_matrix"]), 2)

    def test_train_and_compare_picks_a_model(self):
        items = _synthetic_items()
        pipe, name, metrics = clf_mod.train_and_compare(
            items, test_size=0.25, seed=42)
        self.assertIn(name, ("logreg", "nb"))
        self.assertGreaterEqual(metrics["f1_macro"], 0.8)
        self.assertIn("cv_f1_macro_mean", metrics)

    def test_unknown_model(self):
        with self.assertRaises(ValueError):
            clf_mod.build_pipeline("transformer")


class TestSuspicionScore(unittest.TestCase):
    def test_short_text_returns_none(self):
        self.assertIsNone(clf_mod.suspicion_score(FakeModel(), "curto"))
        self.assertIsNone(clf_mod.suspicion_score(FakeModel(), ""))
        self.assertIsNone(
            clf_mod.suspicion_score(FakeModel(), "x" * 499))

    def test_long_text_returns_probability(self):
        score = clf_mod.suspicion_score(FakeModel(0.9), "x " * 300)
        self.assertAlmostEqual(score, 0.9)


class TestTriageBonus(unittest.TestCase):
    def _item(self, source="g1", title="Título político"):
        return {"source": source, "title": title, "summary": "",
                "published": ""}

    def test_suspicion_bonus(self):
        base = triage_mod.score(self._item())
        self.assertEqual(
            triage_mod.score(self._item(), suspicion=0.9), base + 10)
        self.assertEqual(
            triage_mod.score(self._item(), suspicion=0.7), base + 5)
        self.assertEqual(
            triage_mod.score(self._item(), suspicion=0.3), base)
        self.assertEqual(
            triage_mod.score(self._item(), suspicion=None), base)

    def test_suspicion_never_beats_reference(self):
        with_ref = triage_mod.score(
            self._item(title="Senado aprova PL 1159/2026"))
        without_ref_high_suspicion = triage_mod.score(
            self._item(title="Título político sem ref"), suspicion=0.99)
        self.assertGreater(with_ref, without_ref_high_suspicion)

    def test_triage_accepts_suspicion_callable(self):
        items = [self._item(title="A"), self._item(title="B")]
        ranked = triage_mod.triage(
            items, suspicion_for=lambda it: 0.9 if it["title"] == "B" else 0.1)
        self.assertEqual(ranked[0]["title"], "B")


class NoEvidenceSearcher:
    """Busca falsa: nunca encontra evidência (sem rede no teste)."""

    def search_claim(self, text):
        return None


class TestProcessItemSuspicion(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = os.path.join(self.tmp.name, "test.db")
        self.site = os.path.join(self.tmp.name, "site")
        self.conn = store.init_db(self.db, config.SCHEMA_PATH)
        queue_mod.init_queue(self.conn)

    def tearDown(self):
        self.conn.close()
        self.tmp.cleanup()

    def test_suspicion_recorded_and_verdict_unchanged(self):
        queue_mod.enqueue(self.conn, [{
            "source": "g1",
            "title": "Senado aprova PL 1159/2026",
            "link": "https://x/1", "summary": "", "published": "",
            "_score": 40,
        }])
        long_article = b"conteudo do artigo " * 100
        results = verdict_pipeline.process_queue(
            self.conn, limit=5, site_dir=self.site,
            article_fetcher=lambda url: long_article,
            searcher=NoEvidenceSearcher(),
            ml_model=FakeModel(0.9),
        )
        self.assertEqual(len(results), 1)
        r = results[0]
        # A suspeita é registrada...
        self.assertAlmostEqual(r["suspicion"], 0.9)
        # ...mas o veredito continua decidido só por regras. Sem
        # evidência primária, Inconclusivo — o mesmo com e sem modelo.
        queue_mod.enqueue(self.conn, [{
            "source": "g1",
            "title": "Senado aprova PL 1159/2026",
            "link": "https://x/2", "summary": "", "published": "",
            "_score": 40,
        }])
        results_no_ml = verdict_pipeline.process_queue(
            self.conn, limit=5, site_dir=self.site,
            article_fetcher=lambda url: long_article,
            searcher=NoEvidenceSearcher(),
        )
        self.assertEqual(
            r["verdict"][0], results_no_ml[0]["verdict"][0])
        self.assertIsNone(results_no_ml[0]["suspicion"])


if __name__ == "__main__":
    unittest.main()
