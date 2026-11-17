"""Experimento: char n-grams melhoram a v1 e a v2 separadamente?

No experimento de mistura (17/11), o modelo unificado com char
foi o melhor modelo único (F1 0,9485 nos artigos, 0,7822 no
misto). Este script testa se o char ajuda cada modelo no seu
próprio terreno:
- v1+char: Fake.Br, avaliada no teste da v1 (v1 pura: 0,9708).
- v2+char: FakenewsBR, avaliada no teste misto (v2 pura: 0,7676)
  e no teste da v1 (v2 pura: 0,8841).

Uso:
    .venv-ml/bin/python scripts/experiment_char.py \\
        --fakenewsbr ~/workspace/crivo/fakenewsbr/FakenewsBR_factchecked.csv \\
        --fakebr ~/workspace/crivo/fakebr-corpus \\
        --out /tmp/char_results.json
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


def main():
    parser = argparse.ArgumentParser(
        description="Mede v1+char e v2+char.")
    parser.add_argument("--fakenewsbr", required=True)
    parser.add_argument("--fakebr", required=True)
    parser.add_argument("--out", default="/tmp/char_results.json")
    args = parser.parse_args()
    clf._require_sklearn()
    results: dict = {}

    fakebr_items = load_fakebr(args.fakebr)
    X_fb_train, y_fb_train, X_v1_test, y_v1_test = clf.split(
        fakebr_items, test_size=0.2, seed=42)
    v1_fps = {fingerprint(t) for t in X_v1_test}
    fn_items = load_fakenewsbr(args.fakenewsbr,
                               exclude_fingerprints=v1_fps)
    fn_train, fn_test = clf.split_items_stratified(
        fn_items, test_size=0.2, seed=42)
    X_fn_train = [it.text for it in fn_train]
    y_fn_train = [it.label for it in fn_train]
    X_fn_test = [it.text for it in fn_test]
    y_fn_test = [it.label for it in fn_test]

    # v1+char
    print("== v1+char (Fake.Br) ==")
    v1c = clf.build_char_pipeline()
    v1c.fit(X_fb_train, y_fb_train)
    results["v1_char_artigos"] = clf.evaluate(v1c, X_v1_test, y_v1_test)
    print(f"  artigos: F1={results['v1_char_artigos']['f1_macro']:.4f} "
          f"(v1 pura: 0,9708)")
    clf.save_model(v1c, results["v1_char_artigos"], "/tmp/char_v1")

    # v2+char
    print("== v2+char (FakenewsBR) ==")
    v2c = clf.build_char_pipeline()
    v2c.fit(X_fn_train, y_fn_train)
    results["v2_char_misto"] = clf.evaluate(v2c, X_fn_test, y_fn_test)
    results["v2_char_artigos"] = clf.evaluate(
        v2c, X_v1_test, y_v1_test)
    print(f"  misto: F1={results['v2_char_misto']['f1_macro']:.4f} "
          f"(v2 pura: 0,7676)")
    print(f"  artigos: F1={results['v2_char_artigos']['f1_macro']:.4f} "
          f"(v2 pura: 0,8841)")
    clf.save_model(v2c, results["v2_char_misto"], "/tmp/char_v2")

    with open(args.out, "w", encoding="utf-8") as fh:
        json.dump(results, fh, ensure_ascii=False, indent=2)
    print(f"resultados salvos em {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
