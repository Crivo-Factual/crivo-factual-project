"""Testes do loader do FakenewsBR, da calibração e do split
estratificado (v2 do classificador).

Os testes que treinam de verdade pulam quando o scikit-learn não
está instalado; os do loader pulam sem o pandas. O repo é só
biblioteca padrão — o ML vive num venv separado.
"""

import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from crivo.ml import classifier as clf_mod
from crivo.ml.dataset import NewsItem

try:
    import pandas as pd
    PANDAS_AVAILABLE = True
except ImportError:
    PANDAS_AVAILABLE = False

ML_AVAILABLE = clf_mod.SKLEARN_AVAILABLE


def _synthetic_csv(path):
    """CSV mínimo no esquema do FakenewsBR: canônico + _raw
    (duplicata que deve cair fora) + texto curto + rótulo
    inválido."""
    rows = [
        # rid, dataset_name, source_type, source_description, label,
        # date_iso, url_review, text, text_clean, text_no_url,
        # extracted_urls, is_duplicated, is_null, too_short,
        # factcheck_rating, factcheck_claimant, factcheck_url
        [1, "Fake.br", "news", "", "fake", "", "", "Texto falso longo o suficiente para passar no filtro de tamanho minimo do loader.", "", "", "", 0, 0, 0, "", "", ""],
        [2, "Fake.br", "news", "", "true", "", "", "Texto verdadeiro longo o suficiente para passar no filtro de tamanho minimo do loader.", "", "", "", 0, 0, 0, "", "", ""],
        [3, "Fake.br_raw", "news", "", "fake", "", "", "Texto falso longo o suficiente para passar no filtro de tamanho minimo do loader.", "", "", "", 0, 0, 0, "", "", ""],
        [4, "fakes", "news", "", "fake", "", "", "curto", "", "", "", 0, 0, 0, "", "", ""],
        [5, "fakes", "news", "", "duvidoso", "", "", "Texto com rotulo invalido longo o suficiente para passar no filtro de tamanho.", "", "", "", 0, 0, 0, "", "", ""],
    ]
    cols = ["rid", "dataset_name", "source_type", "source_description",
            "label", "date_iso", "url_review", "text", "text_clean",
            "text_no_url", "extracted_urls", "is_duplicated", "is_null",
            "too_short", "factcheck_rating", "factcheck_claimant",
            "factcheck_url"]
    pd.DataFrame(rows, columns=cols).to_csv(path, index=False)


@unittest.skipUnless(PANDAS_AVAILABLE, "pandas não instalado")
class TestLoadFakenewsbr(unittest.TestCase):
    def test_canonical_only(self):
        from crivo.ml.fakenewsbr import fingerprint, load_fakenewsbr
        with tempfile.NamedTemporaryFile(
                suffix=".csv", delete=False, mode="w") as fh:
            path = fh.name
        try:
            _synthetic_csv(path)
            items = load_fakenewsbr(path)
            # 1 fake + 1 true canônicos; _raw, curto e rótulo
            # inválido caem fora.
            self.assertEqual(len(items), 2)
            self.assertEqual({it.label for it in items}, {0, 1})
            self.assertEqual({it.source for it in items}, {"Fake.br"})
            self.assertTrue(all(it.pair.startswith("fakenewsbr-")
                                for it in items))
            # Exclusão por fingerprint: o texto falso sai.
            items2 = load_fakenewsbr(
                path,
                exclude_fingerprints={fingerprint(items[0].text)})
            self.assertEqual(len(items2), 1)
            self.assertNotEqual(items2[0].text, items[0].text)
        finally:
            os.unlink(path)

    def test_fingerprint_ignores_case_and_punctuation(self):
        from crivo.ml.fakenewsbr import fingerprint
        a = fingerprint("O Presidente anunciou, hoje, a medida!")
        b = fingerprint("o presidente anunciou hoje a medida")
        self.assertEqual(a, b)


@unittest.skipUnless(ML_AVAILABLE, "scikit-learn não instalado")
class TestCalibration(unittest.TestCase):
    def _docs(self, n=120):
        fake = ("URGENTE compartilhe antes que apaguem "
                "voce nao vai acreditar no segredo escondido "
                "exclusivo bomba " * 3)
        true = ("o ministerio anunciou nesta terca feira a "
                "publicacao da portaria que regulamenta o "
                "procedimento administrativo ordinario " * 3)
        items = ([NewsItem(text=fake, label=1, pair=f"f{i}")
                  for i in range(n // 2)]
                 + [NewsItem(text=true, label=0, pair=f"t{i}")
                    for i in range(n // 2)])
        return items

    def test_calibrate_keeps_proba_valid(self):
        items = self._docs()
        X_train, y_train, X_test, y_test = clf_mod.split_stratified(
            items, test_size=0.25, seed=7)
        pipe = clf_mod.build_pipeline("logreg")
        pipe.fit(X_train, y_train)
        calibrated = clf_mod.calibrate_pipeline(
            pipe, X_train, y_train, cv=3)
        proba = calibrated.predict_proba(X_test)
        for row in proba:
            self.assertAlmostEqual(sum(row), 1.0, places=5)
        report = clf_mod.calibration_report(calibrated, X_test, y_test)
        self.assertIn("brier", report)
        self.assertTrue(0 <= report["brier"] <= 1)
        self.assertTrue(len(report["bands"]) >= 1)
        table = clf_mod.threshold_table(calibrated, X_test, y_test)
        self.assertEqual([r["threshold"] for r in table], [0.5, 0.6, 0.8])

    def test_split_stratified_preserves_proportions(self):
        items = self._docs(n=100)
        train, test = clf_mod.split_items_stratified(
            items, test_size=0.2, seed=7)
        self.assertEqual(len(test), 20)
        self.assertEqual(sum(it.label for it in test), 10)
        self.assertEqual(len({it.pair for it in train}
                             & {it.pair for it in test}), 0)

    def test_metrics_json_serializable(self):
        """Regressão (17/11): calibration_report devolvia np.int64
        em 'n', e save_model quebrava no json.dump no fim do
        treino da v2 — com o modelo salvo e as métricas perdidas."""
        import json
        items = self._docs()
        X_train, y_train, X_test, y_test = clf_mod.split_stratified(
            items, test_size=0.25, seed=7)
        pipe = clf_mod.build_pipeline("logreg")
        pipe.fit(X_train, y_train)
        metrics = clf_mod.evaluate(pipe, X_test, y_test)
        metrics["calibration"] = clf_mod.calibration_report(
            pipe, X_test, y_test)
        metrics["thresholds"] = clf_mod.threshold_table(
            pipe, X_test, y_test)
        # json.dumps puro, sem default: tem que passar.
        json.dumps(metrics)
        with tempfile.TemporaryDirectory() as tmp:
            clf_mod.save_model(pipe, metrics, tmp)
            with open(os.path.join(tmp, "metrics.json"),
                      encoding="utf-8") as fh:
                json.load(fh)


if __name__ == "__main__":
    unittest.main()
