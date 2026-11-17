"""Afinação extra do unificado — rodada 2.

A rodada 1 (tune_unified.py) deixou duas perguntas:
1. C=2,0 bateu C=1,0 nos dois testes e a tendência ainda subia
   (0,5 → 0,7769; 1,0 → 0,7822; 2,0 → 0,7894 no misto).
   C=4,0 continua a subir ou já vira?
2. O voto majoritário foi o melhor no misto (0,7914) e o
   oversample foi o melhor nos artigos (0,9625). A combinação
   (voto + oversample ×2) ganha nos dois?

Anexa os resultados a /tmp/tune_results.json (mesmo arquivo da
rodada 1), para a comparação final ficar num só lugar.

Uso:
    .venv-ml/bin/python scripts/tune_unified_extra.py \\
        --fakenewsbr ~/workspace/crivo/fakenewsbr/FakenewsBR_factchecked.csv \\
        --fakebr ~/workspace/crivo/fakebr-corpus
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
from scripts.tune_unified import _char_pipeline_c, _word_pipeline


def main():
    parser = argparse.ArgumentParser(
        description="Afinação extra do unificado (rodada 2).")
    parser.add_argument("--fakenewsbr", required=True)
    parser.add_argument("--fakebr", required=True)
    parser.add_argument("--out", default="/tmp/tune_results.json")
    args = parser.parse_args()
    clf._require_sklearn()
    results = {}
    if os.path.exists(args.out):
        with open(args.out, encoding="utf-8") as fh:
            results = json.load(fh)

    fakebr_items = load_fakebr(args.fakebr)
    X_fb_train, y_fb_train, X_v1_test, y_v1_test = clf.split(
        fakebr_items, test_size=0.2, seed=42)
    v1_fps = {fingerprint(t) for t in X_v1_test}
    fn_items = load_fakenewsbr(args.fakenewsbr,
                               exclude_fingerprints=v1_fps)
    fn_train, fn_test = clf.split_items_stratified(
        fn_items, test_size=0.2, seed=42)
    X_train = X_fb_train + [it.text for it in fn_train]
    y_train = y_fb_train + [it.label for it in fn_train]
    X_fn_test = [it.text for it in fn_test]
    y_fn_test = [it.label for it in fn_test]
    print(f"treino unificado: {len(X_train)} itens", flush=True)

    def _eval_both(name, pipe):
        m_art = clf.evaluate(pipe, X_v1_test, y_v1_test)
        m_mix = clf.evaluate(pipe, X_fn_test, y_fn_test)
        results[name] = {
            "artigos_f1": round(m_art["f1_macro"], 4),
            "artigos_acc": round(m_art["accuracy"], 4),
            "misto_f1": round(m_mix["f1_macro"], 4),
            "misto_acc": round(m_mix["accuracy"], 4),
        }
        print(f"  {name}: artigos F1={m_art['f1_macro']:.4f} | "
              f"misto F1={m_mix['f1_macro']:.4f}", flush=True)
        with open(args.out, "w", encoding="utf-8") as fh:
            json.dump(results, fh, ensure_ascii=False, indent=2)
        return pipe

    # 1. C=4,0 continua a subir?
    char_c4 = _char_pipeline_c(4.0)
    char_c4.fit(X_train, y_train)
    _eval_both("char_C4.0", char_c4)

    # 2. Voto majoritário + oversample ×2 dos artigos.
    from sklearn.ensemble import VotingClassifier
    from sklearn.naive_bayes import ComplementNB
    from sklearn.svm import LinearSVC
    X_over = X_train + X_fb_train
    y_over = y_train + y_fb_train
    vote_over = VotingClassifier(
        estimators=[("char", _char_pipeline_c(2.0)),
                    ("svc", _word_pipeline(LinearSVC(
                        C=1.0, class_weight="balanced",
                        max_iter=2000))),
                    ("cnb", _word_pipeline(ComplementNB(alpha=0.1)))],
        voting="hard")
    vote_over.fit(X_over, y_over)
    _eval_both("vote_C2.0_over2", vote_over)

    print(f"resultados salvos em {args.out}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
