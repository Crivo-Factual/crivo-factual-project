"""CLI de treino do classificador de veracidade.

Uso:
    .venv-ml/bin/python scripts/train_classifier.py \
        --corpus ~/workspace/crivo/fakebr-corpus \
        --out crivo/ml/models

Sem --corpus, procura o clone no caminho padrão do workspace.
O corpus não é versionado (146 MB, licença dos autores) — só o
código, as métricas e o model card vão para o repositório.
"""

from __future__ import annotations

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from crivo.ml.classifier import save_model, train_and_compare  # noqa: E402
from crivo.ml.dataset import load_fakebr  # noqa: E402

DEFAULT_CORPUS = os.path.expanduser("~/workspace/crivo/fakebr-corpus")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Treina o classificador de veracidade (Fake.Br).")
    parser.add_argument("--corpus", default=DEFAULT_CORPUS,
                        help="raiz do clone do Fake.Br Corpus")
    parser.add_argument("--out", default="crivo/ml/models",
                        help="pasta de saída (model.joblib + metrics.json)")
    parser.add_argument("--test-size", type=float, default=0.2)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    items = load_fakebr(args.corpus)
    n_fake = sum(it.label for it in items)
    print(f"corpus: {len(items)} textos "
          f"({n_fake} falsos, {len(items) - n_fake} verdadeiros)")
    pipe, name, metrics = train_and_compare(
        items, test_size=args.test_size, seed=args.seed)
    print(f"melhor modelo: {name}")
    print(f"  accuracy:  {metrics['accuracy']:.4f}")
    print(f"  F1-macro:  {metrics['f1_macro']:.4f}")
    print(f"  F1 falsa:  {metrics['f1_falsa']:.4f} "
          f"(precisão {metrics['precision_falsa']:.4f}, "
          f"recall {metrics['recall_falsa']:.4f})")
    print(f"  ROC-AUC:   {metrics.get('roc_auc', float('nan')):.4f}")
    print(f"  CV 5-fold F1-macro: {metrics['cv_f1_macro_mean']:.4f} "
          f"± {metrics['cv_f1_macro_std']:.4f}")
    print(f"  matriz de confusão: {metrics['confusion_matrix']}")
    save_model(pipe, metrics, args.out)
    print(f"modelo salvo em {args.out}/model.joblib")
    print(json.dumps(metrics, ensure_ascii=False, indent=2)[:400] + " ...")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
