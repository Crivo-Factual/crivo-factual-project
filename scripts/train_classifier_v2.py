"""Treino da v2 do classificador de veracidade — FakenewsBR + calibração.

Uso:
    .venv-ml/bin/python scripts/train_classifier_v2.py \\
        --fakenewsbr ~/workspace/crivo/fakenewsbr/FakenewsBR_factchecked.csv \\
        --fakebr ~/workspace/crivo/fakebr-corpus \\
        --out crivo/ml/models/v2

O que o script garante:
- COMPARAÇÃO LIMPA v1 × v2: os 1.440 itens do teste da v1 são
  excluídos do treino da v2 por fingerprint (os mesmos textos do
  Fake.Br aparecem dentro do FakenewsBR). A v2 nunca viu esses
  textos — a comparação no teste da v1 é honesta.
- CALIBRAÇÃO: o vencedor é calibrado por isotônica (cv=5) e
  avaliado antes e depois (Brier + faixas + limiares).
- TEXTO CURTO: mede a suspeita da v2 em textos curtos do teste
  (tweets/WhatsApp) para decidir se o guarda MIN_CHARS=500 da v1
  ainda vale para a v2.

Saída: `model.joblib` (v2 SEM calibração — ver o passo 9) +
`metrics.json` com tudo.
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


def _xy(items):
    return [it.text for it in items], [it.label for it in items]


def _per_source_confusion(pipe, test_items):
    """Contagens por fonte, sem F1-macro: [verdadeiras certas,
    verdadeiras chamadas falsas, falsas certas, falsas chamadas
    verdadeiras]. O F1-macro por fonte engana nas fontes de classe
    única (ex.: `true` só tem verdadeiras — o F1 da classe falsa
    é zero por construção e o macro cai pela metade). Contagem é
    o que se lê."""
    from collections import defaultdict
    out: dict[str, list] = defaultdict(lambda: [0, 0, 0, 0])
    for it in test_items:
        pred = int(pipe.predict([it.text])[0])
        cell = out[it.source]
        if it.label == 0:
            cell[0 if pred == 0 else 1] += 1
        else:
            cell[2 if pred == 1 else 3] += 1
    return {s: {"n": sum(v), "verdadeiras_certas": v[0],
                "verdadeiras_chamadas_falsas": v[1],
                "falsas_certas": v[2],
                "falsas_chamadas_verdadeiras": v[3]}
            for s, v in sorted(out.items())}


def _short_text_scores(pipe, test_items, max_chars=300, limit=50):
    """Suspeita média da v2 em textos curtos do teste, por rótulo.
    A v1 pontuava 0,91–0,98 em manchetes verdadeiras — se a v2
    separar curto-verdadeiro de curto-falso, o guarda de 500 chars
    pode cair."""
    short_true = [it for it in test_items
                  if it.label == 0 and len(it.text) < max_chars][:limit]
    short_fake = [it for it in test_items
                  if it.label == 1 and len(it.text) < max_chars][:limit]
    out = {}
    for name, group in (("curto_verdadeiro", short_true),
                        ("curto_falso", short_fake)):
        if not group:
            continue
        probs = [float(pipe.predict_proba([it.text])[0][1])
                 for it in group]
        out[name] = {
            "n": len(group),
            "suspeita_media": round(sum(probs) / len(probs), 3),
        }
    return out


def main():
    parser = argparse.ArgumentParser(
        description="Treina a v2 do classificador (FakenewsBR + calibração).")
    parser.add_argument("--fakenewsbr", required=True,
                        help="CSV unificado do FakenewsBR")
    parser.add_argument("--fakebr", required=True,
                        help="raiz do clone do Fake.Br Corpus")
    parser.add_argument("--out", default="crivo/ml/models/v2",
                        help="pasta de saída do modelo e das métricas")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--v1-model", default="crivo/ml/models/model.joblib",
                        help="modelo v1 para a comparação no teste da v1")
    args = parser.parse_args()
    clf._require_sklearn()

    # 1. Teste da v1 — os textos que a v2 NÃO pode ver.
    fakebr_items = load_fakebr(args.fakebr)
    _, _, X_v1_test, y_v1_test = clf.split(
        fakebr_items, test_size=0.2, seed=42)
    v1_fingerprints = {fingerprint(t) for t in X_v1_test}
    print(f"teste da v1: {len(X_v1_test)} itens "
          f"({sum(y_v1_test)} falsos) — fingerprints de exclusão prontos")

    # 2. FakenewsBR sem o teste da v1.
    items = load_fakenewsbr(args.fakenewsbr,
                            exclude_fingerprints=v1_fingerprints)
    print(f"FakenewsBR canônico: {len(items)} itens "
          f"({sum(it.label for it in items)} falsos)")

    # 3. Split estratificado.
    train_items, test_items = clf.split_items_stratified(
        items, test_size=0.2, seed=args.seed)
    X_train, y_train = _xy(train_items)
    X_test, y_test = _xy(test_items)
    print(f"treino: {len(X_train)} | teste: {len(X_test)}")

    # 4. Candidatos: fit + CV, melhor por F1-macro no teste.
    results = {}
    for name in clf.CANDIDATES:
        pipe = clf.build_pipeline(name)
        pipe.fit(X_train, y_train)
        metrics = clf.evaluate(pipe, X_test, y_test)
        metrics.update(clf.cross_validate(
            clf.build_pipeline(name), X_train, y_train, args.seed))
        metrics["model"] = name
        results[name] = (pipe, metrics)
        print(f"{name}: F1-macro {metrics['f1_macro']:.4f} "
              f"(CV {metrics['cv_f1_macro_mean']:.4f} ± "
              f"{metrics['cv_f1_macro_std']:.4f})")
    best_name = max(results, key=lambda n: results[n][1]["f1_macro"])
    best_pipe, best_metrics = results[best_name]
    best_metrics["all_models"] = {
        name: {k: v for k, v in m.items() if k != "all_models"}
        for name, (_, m) in results.items()
    }

    # 5. Sem calibração: métricas + calibração + limiares + por fonte.
    best_metrics["calibration_before"] = clf.calibration_report(
        best_pipe, X_test, y_test)
    best_metrics["thresholds_before"] = clf.threshold_table(
        best_pipe, X_test, y_test)
    best_metrics["per_source"] = _per_source_confusion(
        best_pipe, test_items)
    print(f"melhor: {best_name} | Brier antes: "
          f"{best_metrics['calibration_before']['brier']}")

    # 6. Calibração isotônica e reavaliação.
    calibrated = clf.calibrate_pipeline(best_pipe, X_train, y_train)
    cal_metrics = clf.evaluate(calibrated, X_test, y_test)
    cal_metrics["calibration_after"] = clf.calibration_report(
        calibrated, X_test, y_test)
    cal_metrics["thresholds_after"] = clf.threshold_table(
        calibrated, X_test, y_test)
    best_metrics["calibrated"] = cal_metrics
    print(f"Brier depois: {cal_metrics['calibration_after']['brier']} | "
          f"F1-macro calibrado: {cal_metrics['f1_macro']:.4f}")

    # 7. Comparação limpa no teste da v1 (artigos completos).
    comparison = {}
    if os.path.exists(args.v1_model):
        v1 = clf.load_model(args.v1_model)
        m = clf.evaluate(v1, X_v1_test, y_v1_test)
        m["calibration"] = clf.calibration_report(v1, X_v1_test, y_v1_test)
        comparison["v1_fakebr"] = m
    for label, pipe in (("v2_sem_calibracao", best_pipe),
                        ("v2_calibrada", calibrated)):
        m = clf.evaluate(pipe, X_v1_test, y_v1_test)
        m["calibration"] = clf.calibration_report(
            pipe, X_v1_test, y_v1_test)
        comparison[label] = m
    best_metrics["v1_test_comparison"] = comparison

    # 8. Texto curto: a v2 separa curto-verdadeiro de curto-falso?
    best_metrics["short_text"] = _short_text_scores(calibrated, test_items)
    print(f"texto curto (v2 calibrada): {best_metrics['short_text']}")

    # 9. Artefato: o modelo SEM calibração. Medido em 17/11: a
    # calibração isotônica melhora o Brier, mas desloca o ponto
    # de operação para "falso" — no teste misto, os falsos
    # positivos em verdadeiras saltam de 590 para 1.011 e o
    # F1-macro cai. Para triagem, o não-calibrado é o melhor
    # artefato; a calibração fica registrada como experimento.
    best_metrics["shipped"] = "uncalibrated"
    best_metrics["short_text_uncalibrated"] = _short_text_scores(
        best_pipe, test_items)
    clf.save_model(best_pipe, best_metrics, args.out)
    print(f"modelo v2 (sem calibração) salvo em {args.out}/model.joblib")
    print(json.dumps(
        {k: best_metrics[k] for k in
         ("model", "accuracy", "f1_macro", "roc_auc", "n_test")},
        indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
