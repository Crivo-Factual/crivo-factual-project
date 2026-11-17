"""Treino, avaliação e inferência do classificador de veracidade.

Modelo: TF-IDF (unigramas + bigramas, sublinear) + classificador
linear. Dois candidatos são comparados e o melhor por F1-macro no
teste é o escolhido:
- regressão logística (tem predict_proba nativo — vira o
  `suspicion_score`, a probabilidade de o texto ser falso);
- Multinomial Naive Bayes (baseline clássico do corpus).

O pipeline inteiro (vetorizador + modelo) é um único objeto
scikit-learn, salvo com joblib — é o artefato que vai para o
Hugging Face Hub.
"""

from __future__ import annotations

import json
import os

try:
    import joblib
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.linear_model import LogisticRegression
    from sklearn.metrics import (accuracy_score, classification_report,
                                 confusion_matrix, f1_score, roc_auc_score)
    from sklearn.model_selection import GroupShuffleSplit, cross_val_score
    from sklearn.naive_bayes import MultinomialNB
    from sklearn.pipeline import Pipeline
    SKLEARN_AVAILABLE = True
except ImportError:  # o repo é só biblioteca padrão; o ML é opcional
    joblib = None
    Pipeline = None
    SKLEARN_AVAILABLE = False


def _require_sklearn():
    if not SKLEARN_AVAILABLE:
        raise ImportError(
            "scikit-learn não instalado. Crie o venv de ML "
            "(`python3 -m venv .venv-ml && .venv-ml/bin/pip install "
            "scikit-learn pandas`) e rode com ele."
        )


# Mínimo de texto para o modelo opinar. Medido em 16/11: manchetes e
# resumos curtos (~200 chars) pontuam 0,91–0,98 MESMO sendo verdadeiros
# — o modelo só viu artigos completos no treino e não sabe o que
# fazer com texto curto. Abaixo disso, sem score (None), nunca um
# número enganoso.
MIN_CHARS = 500

from . import STOPWORDS_PT  # noqa: E402
from .dataset import NewsItem  # noqa: E402

CANDIDATES = {
    "logreg": lambda: LogisticRegression(
        C=1.0, max_iter=1000, class_weight="balanced", solver="lbfgs"
    ),
    "nb": lambda: MultinomialNB(alpha=0.1),
}


def build_pipeline(model_name: str) -> Pipeline:
    _require_sklearn()
    if model_name not in CANDIDATES:
        raise ValueError(
            f"modelo desconhecido: {model_name}. Use: {sorted(CANDIDATES)}"
        )
    return Pipeline([
        ("tfidf", TfidfVectorizer(
            lowercase=True,
            ngram_range=(1, 2),
            max_features=50_000,
            min_df=2,
            sublinear_tf=True,
            stop_words=sorted(STOPWORDS_PT),
        )),
        ("clf", CANDIDATES[model_name]()),
    ])


def split(items: list[NewsItem], test_size: float = 0.2,
          seed: int = 42):
    """Split estratificado POR PAR (ver dataset.py). Devolve
    (X_train, y_train, X_test, y_test)."""
    _require_sklearn()
    groups = [it.pair for it in items]
    labels = [it.label for it in items]
    splitter = GroupShuffleSplit(
        n_splits=1, test_size=test_size, random_state=seed
    )
    train_idx, test_idx = next(splitter.split(items, labels, groups))
    return (
        [items[i].text for i in train_idx],
        [items[i].label for i in train_idx],
        [items[i].text for i in test_idx],
        [items[i].label for i in test_idx],
    )


def evaluate(pipe: Pipeline, X_test, y_test) -> dict:
    _require_sklearn()
    pred = pipe.predict(X_test)
    proba = pipe.predict_proba(X_test)[:, 1] if hasattr(
        pipe, "predict_proba") else None
    report = classification_report(
        y_test, pred, target_names=["verdadeira", "falsa"],
        output_dict=True, zero_division=0,
    )
    metrics = {
        "accuracy": accuracy_score(y_test, pred),
        "f1_macro": f1_score(y_test, pred, average="macro"),
        "f1_falsa": report["falsa"]["f1-score"],
        "precision_falsa": report["falsa"]["precision"],
        "recall_falsa": report["falsa"]["recall"],
        "f1_verdadeira": report["verdadeira"]["f1-score"],
        "confusion_matrix": confusion_matrix(y_test, pred).tolist(),
        "n_test": len(y_test),
    }
    if proba is not None:
        metrics["roc_auc"] = roc_auc_score(y_test, proba)
    return metrics


def cross_validate(pipe: Pipeline, X_train, y_train,
                   seed: int = 42) -> dict:
    _require_sklearn()
    scores = cross_val_score(
        pipe, X_train, y_train, cv=5, scoring="f1_macro",
        n_jobs=-1,
    )
    return {
        "cv_f1_macro_mean": float(scores.mean()),
        "cv_f1_macro_std": float(scores.std()),
        "cv_folds": [float(s) for s in scores],
    }


def train_and_compare(items: list[NewsItem], test_size: float = 0.2,
                      seed: int = 42) -> tuple[Pipeline, str, dict]:
    """Treina os candidatos, avalia no teste e devolve
    (melhor_pipeline, nome_do_modelo, métricas). O pipeline
    devolvido já está ajustado no treino completo."""
    X_train, y_train, X_test, y_test = split(items, test_size, seed)
    results = {}
    for name in CANDIDATES:
        pipe = build_pipeline(name)
        pipe.fit(X_train, y_train)
        metrics = evaluate(pipe, X_test, y_test)
        metrics.update(cross_validate(
            build_pipeline(name), X_train, y_train, seed))
        metrics["model"] = name
        results[name] = (pipe, metrics)
    best_name = max(results, key=lambda n: results[n][1]["f1_macro"])
    best_pipe, best_metrics = results[best_name]
    best_metrics["all_models"] = {
        name: {k: v for k, v in m.items() if k != "all_models"}
        for name, (_, m) in results.items()
    }
    return best_pipe, best_name, best_metrics


def suspicion_score(pipe, text: str) -> float | None:
    """Probabilidade de o texto ser notícia falsa, 0.0–1.0, ou None
    quando o texto é curto demais para o modelo opinar (ver
    MIN_CHARS). É um SINAL DE TRIAGEM, nunca um veredito."""
    if not text or len(text.strip()) < MIN_CHARS:
        return None
    return float(pipe.predict_proba([text])[0][1])


def save_model(pipe: Pipeline, metrics: dict, out_dir: str) -> None:
    _require_sklearn()
    os.makedirs(out_dir, exist_ok=True)
    joblib.dump(pipe, os.path.join(out_dir, "model.joblib"))
    with open(os.path.join(out_dir, "metrics.json"), "w",
              encoding="utf-8") as fh:
        json.dump(metrics, fh, ensure_ascii=False, indent=2)


def load_model(path: str) -> Pipeline:
    _require_sklearn()
    return joblib.load(path)
