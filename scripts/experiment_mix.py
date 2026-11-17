"""Experimento: a mistura de v1 + v2 é melhor que cada uma?

Três misturas medidas nos MESMOS dois testes (limpos, sem vazamento):
1. ENSEMBLE: média das probabilidades da v1 e da v2 (sem retreino).
2. UNIFICADO: um único modelo treinado com Fake.Br + FakenewsBR juntos.
3. UNIFICADO + CHAR: o unificado com n-grams de caracteres
   (ajuda texto ruidoso de rede social: erros de digitação, gíria).

Também mede: o limiar que maximiza o F1 no teste misto e 3
exemplos de verdadeiras que o modelo chama de falsas na fonte
`true` (Kaggle) — o pior caso da v2 (58% de falso positivo).

Regra de decisão (o uso real é triagem de artigos + texto curto):
o vencedor precisa ser o melhor (ou empatado) no teste de
artigos E não pior no teste misto.

Uso:
    .venv-ml/bin/python scripts/experiment_mix.py \\
        --fakenewsbr ~/workspace/crivo/fakenewsbr/FakenewsBR_factchecked.csv \\
        --fakebr ~/workspace/crivo/fakebr-corpus \\
        --out /tmp/mix_results.json
"""

from __future__ import annotations

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from crivo.ml import classifier as clf
from crivo.ml.dataset import load_fakebr
from crivo.ml.fakenewsbr import fingerprint, load_fakenewsbr


def _metrics_from_proba(proba, y_test):
    """F1-macro, acurácia e Brier a partir das probabilidades
    (limiar 0,5). Evita re-treinar para cada mistura."""
    from sklearn.metrics import (accuracy_score, brier_score_loss,
                                 f1_score)
    pred = [1 if p >= 0.5 else 0 for p in proba]
    return {
        "accuracy": round(float(accuracy_score(y_test, pred)), 4),
        "f1_macro": round(float(f1_score(
            y_test, pred, average="macro")), 4),
        "brier": round(float(brier_score_loss(y_test, proba)), 4),
        "n": len(y_test),
    }


def _best_threshold(proba, y_test):
    """Varre o limiar e devolve o que maximiza o F1-macro."""
    from sklearn.metrics import f1_score
    best = (0.5, 0.0)
    for t in [0.3, 0.35, 0.4, 0.45, 0.5, 0.55, 0.6, 0.65, 0.7]:
        pred = [1 if p >= t else 0 for p in proba]
        f1 = float(f1_score(y_test, pred, average="macro"))
        if f1 > best[1]:
            best = (t, round(f1, 4))
    return {"threshold": best[0], "f1_macro": best[1]}


def _build_char_pipeline():
    """TF-IDF de palavras + TF-IDF de caracteres (char_wb 3-5).
    Caractere ajuda onde palavra falha: texto de rede social com
    erro de digitação, abreviação e gíria."""
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.linear_model import LogisticRegression
    from sklearn.pipeline import FeatureUnion, Pipeline
    from crivo.ml import STOPWORDS_PT
    word = TfidfVectorizer(
        lowercase=True, ngram_range=(1, 2), max_features=50_000,
        min_df=2, sublinear_tf=True, stop_words=sorted(STOPWORDS_PT))
    char = TfidfVectorizer(
        lowercase=True, analyzer="char_wb", ngram_range=(3, 5),
        max_features=30_000, min_df=2, sublinear_tf=True)
    return Pipeline([
        ("features", FeatureUnion([("word", word), ("char", char)])),
        ("clf", LogisticRegression(
            C=1.0, max_iter=1000, class_weight="balanced",
            solver="lbfgs")),
    ])


def main():
    parser = argparse.ArgumentParser(
        description="Mede as misturas de v1 + v2.")
    parser.add_argument("--fakenewsbr", required=True)
    parser.add_argument("--fakebr", required=True)
    parser.add_argument("--v1-model",
                        default="crivo/ml/models/model.joblib")
    parser.add_argument("--v2-model",
                        default="crivo/ml/models/v2/model.joblib")
    parser.add_argument("--out", default="/tmp/mix_results.json")
    args = parser.parse_args()
    clf._require_sklearn()
    results: dict = {}

    # --- Testes limpos (os mesmos da v2) ---
    fakebr_items = load_fakebr(args.fakebr)
    _, _, X_v1_test, y_v1_test = clf.split(
        fakebr_items, test_size=0.2, seed=42)
    v1_fps = {fingerprint(t) for t in X_v1_test}
    fn_items = load_fakenewsbr(args.fakenewsbr,
                               exclude_fingerprints=v1_fps)
    fn_train, fn_test = clf.split_items_stratified(
        fn_items, test_size=0.2, seed=42)
    X_fn_test = [it.text for it in fn_test]
    y_fn_test = [it.label for it in fn_test]
    X_fn_test_long = [it.text for it in fn_test
                      if len(it.text) >= 500]
    y_fn_test_long = [it.label for it in fn_test
                      if len(it.text) >= 500]
    print(f"teste v1: {len(X_v1_test)} artigos | teste misto: "
          f"{len(X_fn_test)} ({len(X_fn_test_long)} longos)")

    v1 = clf.load_model(args.v1_model)
    v2 = clf.load_model(args.v2_model)

    # --- 1. Ensemble: média das probabilidades ---
    print("== ensemble (média v1+v2) ==")
    for name, X, y in (("artigos_v1", X_v1_test, y_v1_test),
                       ("misto", X_fn_test, y_fn_test),
                       ("misto_longo", X_fn_test_long, y_fn_test_long)):
        p1 = v1.predict_proba(X)[:, 1]
        p2 = v2.predict_proba(X)[:, 1]
        ens = [(a + b) / 2 for a, b in zip(p1, p2)]
        results[f"ensemble_{name}"] = _metrics_from_proba(ens, y)
        print(f"  {name}: {results[f'ensemble_{name}']}")

    # --- 2. Unificado: Fake.Br (treino) + FakenewsBR (treino) ---
    # split por par do Fake.Br: reusa a mesma semente da v1.
    X_fb_train, y_fb_train, _, _ = clf.split(
        fakebr_items, test_size=0.2, seed=42)
    X_uni_train = X_fb_train + [it.text for it in fn_train]
    y_uni_train = y_fb_train + [it.label for it in fn_train]
    print(f"treino unificado: {len(X_uni_train)} itens")
    uni = clf.build_pipeline("logreg")
    uni.fit(X_uni_train, y_uni_train)
    print("== unificado ==")
    for name, X, y in (("artigos_v1", X_v1_test, y_v1_test),
                       ("misto", X_fn_test, y_fn_test)):
        results[f"unificado_{name}"] = clf.evaluate(uni, X, y)
        print(f"  {name}: F1={results[f'unificado_{name}']['f1_macro']:.4f} "
              f"acc={results[f'unificado_{name}']['accuracy']:.4f}")

    # --- 3. Unificado + char n-grams ---
    uni_char = _build_char_pipeline()
    uni_char.fit(X_uni_train, y_uni_train)
    print("== unificado + char ==")
    for name, X, y in (("artigos_v1", X_v1_test, y_v1_test),
                       ("misto", X_fn_test, y_fn_test)):
        results[f"unificado_char_{name}"] = clf.evaluate(uni_char, X, y)
        print(f"  {name}: F1={results[f'unificado_char_{name}']['f1_macro']:.4f} "
              f"acc={results[f'unificado_char_{name}']['accuracy']:.4f}")

    # --- Limiar ótimo do unificado no teste misto ---
    proba_uni = uni.predict_proba(X_fn_test)[:, 1]
    results["unificado_best_threshold_misto"] = _best_threshold(
        proba_uni, y_fn_test)
    print(f"limiar ótimo (unificado, misto): "
          f"{results['unificado_best_threshold_misto']}")

    # --- Erros: verdadeiras chamadas falsas na fonte `true` ---
    pred_uni = uni.predict(X_fn_test)
    examples = []
    for it, p in zip(fn_test, pred_uni):
        if it.source == "true" and it.label == 0 and p == 1:
            examples.append(it.text[:200].replace("\n", " "))
        if len(examples) >= 3:
            break
    results["erros_true_kaggle"] = examples
    print("exemplos de verdadeiras (Kaggle) chamadas falsas:")
    for ex in examples:
        print("  -", ex)

    with open(args.out, "w", encoding="utf-8") as fh:
        json.dump(results, fh, ensure_ascii=False, indent=2)
    print(f"resultados salvos em {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
