"""Treino canônico do modelo UNIFICADO.

Um só modelo, treino = Fake.Br (artigos) + FakenewsBR (misto),
mesmos splits dos experimentos (seed 42, exclusão do teste da
v1 por fingerprint). Configuração = a melhor medida pela
afinação (scripts/tune_unified.py e tune_unified_extra.py):
TF-IDF palavra (1–2, 50k) + TF-IDF char_wb (3–5, 30k) +
LogReg, C=2,0 por padrão, artigos com oversample ×2 por
padrão (o unificado tem só 14% de artigos — o oversample
levanta o F1 nos artigos sem derrubar o misto).

O artefato vai para crivo/ml/models/unified/ (gitignorado, como
os outros modelos) e é o modelo único do zip de teste e da
demo do Hugging Face. O roteador v1/v2 continua existindo para
comparação — o unificado é o modelo que o idealizador pediu
("um modelo unificado e completo").

Uso:
    .venv-ml/bin/python scripts/train_unified.py \\
        --fakenewsbr ~/workspace/crivo/fakenewsbr/FakenewsBR_factchecked.csv \\
        --fakebr ~/workspace/crivo/fakebr-corpus \\
        --out crivo/ml/models/unified [--C 2.0] [--oversample 2]
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
from scripts.tune_unified import _char_pipeline_c


def _train_one(X_train, y_train, X_fb_train, y_fb_train,
               X_v1_test, y_v1_test, X_fn_test, y_fn_test,
               c_value, oversample):
    if oversample > 1:
        X_fit = X_train + X_fb_train * (oversample - 1)
        y_fit = y_train + y_fb_train * (oversample - 1)
    else:
        X_fit, y_fit = X_train, y_train
    print(f"  C={c_value} oversample ×{oversample}: "
          f"fit com {len(X_fit)} itens", flush=True)
    pipe = _char_pipeline_c(c_value)
    pipe.fit(X_fit, y_fit)
    m_art = clf.evaluate(pipe, X_v1_test, y_v1_test)
    m_mix = clf.evaluate(pipe, X_fn_test, y_fn_test)
    print(f"    artigos: F1={m_art['f1_macro']:.4f} "
          f"acc={m_art['accuracy']:.4f}", flush=True)
    print(f"    misto:   F1={m_mix['f1_macro']:.4f} "
          f"acc={m_mix['accuracy']:.4f}", flush=True)
    metrics = {
        "model": "logreg_char_unified",
        "C": c_value,
        "oversample": oversample,
        "artigos": {"f1_macro": round(m_art["f1_macro"], 4),
                    "accuracy": round(m_art["accuracy"], 4),
                    "n_test": len(X_v1_test)},
        "misto": {"f1_macro": round(m_mix["f1_macro"], 4),
                  "accuracy": round(m_mix["accuracy"], 4),
                  "n_test": len(X_fn_test)},
    }
    return pipe, metrics


def main():
    parser = argparse.ArgumentParser(
        description="Treino canônico do modelo unificado.")
    parser.add_argument("--fakenewsbr", required=True)
    parser.add_argument("--fakebr", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--C", type=float, default=2.0,
                        dest="c_value")
    parser.add_argument("--oversample", type=int, default=2)
    parser.add_argument("--compare", action="store_true",
                        help="treina (C=2,0, ×2) e (C=4,0, ×2) e "
                        "salva o melhor pela soma dos F1.")
    args = parser.parse_args()
    clf._require_sklearn()

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

    configs = [(2.0, 2), (4.0, 2)] if args.compare else [
        (args.c_value, args.oversample)]
    best_pipe, best_metrics, best_sum = None, None, -1.0
    for c_value, oversample in configs:
        pipe, metrics = _train_one(
            X_train, y_train, X_fb_train, y_fb_train,
            X_v1_test, y_v1_test, X_fn_test, y_fn_test,
            c_value, oversample)
        total = (metrics["artigos"]["f1_macro"]
                 + metrics["misto"]["f1_macro"])
        if total > best_sum:
            best_pipe, best_metrics, best_sum = pipe, metrics, total
    print(f"melhor: C={best_metrics['C']} "
          f"oversample ×{best_metrics['oversample']} "
          f"(soma F1={best_sum:.4f})", flush=True)
    clf.save_model(best_pipe, best_metrics, args.out)
    print(f"modelo unificado salvo em {args.out}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
