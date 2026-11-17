"""Fine-tuning do BERTimbau para o classificador de veracidade.

Por que transformer: o melhor modelo linear (TF-IDF + LogReg +
char) chega a F1 0,9485 nos artigos e 0,7822 no misto — e o alvo
é >= 0,95 nos dois. O linear esbarrou no teto: texto curto de
rede social, perguntas de checagem e ironia não se separam por
contagem de palavras. O BERTimbau (BERT pré-treinado em
português) lê contexto — é o único caminho plausível para o
salto no misto. A literatura no Fake.Br aponta o BERTimbau
como o mais forte do corpus.

Onde roda: GPU — Google Colab gratuito (T4). Na CPU desta VM
não é viável (horas por época). O notebook
`crivo/ml/hf/bertimbau-colab.ipynb` roda este script.

O script é AUTOCONTIDO (não importa o pacote crivo): baixa os
corpora, reproduz os MESMOS splits dos experimentos lineares
(seed 42, exclusão do teste da v1 por fingerprint) e avalia nos
dois testes, para os números serem comparáveis.

Uso (Colab):
    !python train_bertimbau.py --fakebr fakebr-corpus \\
        --fakenewsbr FakenewsBR_factchecked.csv --out ./bertimbau-v1

Uso (smoke test na CPU, 64 exemplos, verifica que o código roda):
    python train_bertimbau.py --smoke --fakebr ... --fakenewsbr ...
"""

from __future__ import annotations

import argparse
import json
import os
import re
import unicodedata


def fingerprint(text: str, chars: int = 300) -> str:
    """Igual a crivo.ml.fakenewsbr.fingerprint — imprime o início
    do texto normalizado para excluir o teste da v1 do treino."""
    norm = unicodedata.normalize("NFKD", text or "")
    norm = "".join(c for c in norm if not unicodedata.combining(c))
    norm = norm.lower()
    norm = re.sub(r"[^a-z0-9 ]+", " ", norm)
    norm = re.sub(r"\s+", " ", norm).strip()
    return norm[:chars]


def load_fakebr(corpus_dir: str):
    """(texto, rótulo, par) do Fake.Br — 0 = verdadeira, 1 = falsa."""
    items = []
    for label, folder in ((1, "fake"), (0, "true")):
        path = os.path.join(corpus_dir, "full_texts", folder)
        for name in sorted(os.listdir(path)):
            if not name.endswith(".txt"):
                continue
            with open(os.path.join(path, name), encoding="utf-8",
                      errors="replace") as fh:
                text = fh.read().strip()
            if text:
                items.append((text, label, name))
    return items


def load_fakenewsbr(csv_path: str, exclude_fps: set):
    """(texto, rótulo, fonte) canônicos do FakenewsBR."""
    import pandas as pd
    df = pd.read_csv(csv_path, low_memory=False)
    items = []
    for row in df.itertuples(index=False):
        name = str(row.dataset_name)
        if name.endswith("_raw"):
            continue
        label = {"fake": 1, "true": 0}.get(str(row.label).strip().lower())
        if label is None:
            continue
        text = str(row.text).strip() if row.text is not None else ""
        if len(text) < 50:
            continue
        if fingerprint(text) in exclude_fps:
            continue
        items.append((text, label, name))
    return items


def build_splits(fakebr_dir: str, fakenewsbr_csv: str, seed: int = 42):
    """Reproduz os splits dos experimentos lineares. Devolve
    (train, v1_test, mixed_test) como listas de (texto, rótulo)."""
    from sklearn.model_selection import GroupShuffleSplit, train_test_split
    fb = load_fakebr(fakebr_dir)
    groups = [it[2] for it in fb]
    labels = [it[1] for it in fb]
    splitter = GroupShuffleSplit(
        n_splits=1, test_size=0.2, random_state=seed)
    tr_idx, te_idx = next(splitter.split(fb, labels, groups))
    fb_train = [fb[i] for i in tr_idx]
    v1_test = [(fb[i][0], fb[i][1]) for i in te_idx]
    v1_fps = {fingerprint(t) for t, _ in v1_test}
    fn = load_fakenewsbr(fakenewsbr_csv, v1_fps)
    fn_labels = [it[1] for it in fn]
    fn_train, fn_test = train_test_split(
        fn, test_size=0.2, random_state=seed, stratify=fn_labels)
    train = ([(t, l) for t, l, _ in fb_train]
             + [(t, l) for t, l, _ in fn_train])
    mixed_test = [(t, l) for t, l, _ in fn_test]
    return train, v1_test, mixed_test


def main():
    parser = argparse.ArgumentParser(
        description="Fine-tuning do BERTimbau (veracidade).")
    parser.add_argument("--fakebr", required=True)
    parser.add_argument("--fakenewsbr", required=True)
    parser.add_argument("--out", default="./bertimbau-v1")
    parser.add_argument("--model", default="neuralmind/bert-base-portuguese-cased")
    parser.add_argument("--epochs", type=float, default=3.0)
    parser.add_argument("--batch", type=int, default=32)
    parser.add_argument("--max-len", type=int, default=256)
    parser.add_argument("--lr", type=float, default=2e-5)
    parser.add_argument("--smoke", action="store_true",
                        help="64 exemplos, 1 época curta — só "
                        "verifica que o código roda (CPU).")
    args = parser.parse_args()

    import numpy as np
    import torch
    from datasets import Dataset
    from sklearn.metrics import accuracy_score, f1_score
    from transformers import (AutoModelForSequenceClassification,
                              AutoTokenizer,
                              DataCollatorWithPadding, Trainer,
                              TrainingArguments)

    print("montando os splits (seed 42, iguais aos lineares)...")
    train, v1_test, mixed_test = build_splits(
        args.fakebr, args.fakenewsbr)
    if args.smoke:
        # Amostra ESTRATIFICADA: o treino é fake-then-true na
        # ordem de carga, e train[:64] era só falso (peso inf).
        def _strat(pairs, per_class):
            out = []
            for label in (0, 1):
                pool = [p for p in pairs if p[1] == label]
                out.extend(pool[:per_class])
            return out
        train, v1_test, mixed_test = (
            _strat(train, 32), _strat(v1_test, 16),
            _strat(mixed_test, 16))
        args.epochs = 1.0
        args.batch = 8
    print(f"treino: {len(train)} | teste artigos: {len(v1_test)} | "
          f"teste misto: {len(mixed_test)}")

    tokenizer = AutoTokenizer.from_pretrained(args.model)

    def _tok(batch):
        return tokenizer(batch["text"], truncation=True,
                         max_length=args.max_len)

    def _to_ds(pairs):
        ds = Dataset.from_dict({
            "text": [t for t, _ in pairs],
            "label": [l for _, l in pairs]})
        return ds.map(_tok, batched=True, remove_columns=["text"])

    train_ds = _to_ds(train)
    v1_ds = _to_ds(v1_test)
    mixed_ds = _to_ds(mixed_test)

    # Peso por classe: o treino é 73% falso — sem peso o modelo
    # aprende o prior e inunda de falso positivo (o mesmo viés
    # que a v2 linear mostrou). Guarda: classe ausente (só
    # acontece no smoke) pesa 1,0, nunca inf.
    counts = np.bincount([l for _, l in train], minlength=2)
    weights = torch.tensor(
        [len(train) / (2 * counts[0]) if counts[0] else 1.0,
         len(train) / (2 * counts[1]) if counts[1] else 1.0],
        dtype=torch.float)
    print(f"pesos de classe (verdadeira/falsa): {weights.tolist()}")

    model = AutoModelForSequenceClassification.from_pretrained(
        args.model, num_labels=2)

    class WeightedTrainer(Trainer):
        def compute_loss(self, model, inputs, return_outputs=False,
                         **kwargs):
            labels = inputs.pop("labels")
            outputs = model(**inputs)
            loss = torch.nn.functional.cross_entropy(
                outputs.logits, labels, weight=weights.to(
                    outputs.logits.device))
            return (loss, outputs) if return_outputs else loss

    def _metrics(eval_pred):
        logits, labels = eval_pred
        pred = np.argmax(logits, axis=1)
        return {
            "accuracy": accuracy_score(labels, pred),
            "f1_macro": f1_score(labels, pred, average="macro"),
        }

    # transformers 5.x não tem mais `warmup_ratio` — só
    # `warmup_steps`. Calcula 10% dos passos totais, que era a
    # intenção original.
    import math
    total_steps = (math.ceil(len(train) / args.batch)
                   * math.ceil(args.epochs))
    training_args = TrainingArguments(
        output_dir=args.out,
        num_train_epochs=args.epochs,
        per_device_train_batch_size=args.batch,
        per_device_eval_batch_size=64,
        learning_rate=args.lr,
        warmup_steps=max(1, int(0.1 * total_steps)),
        weight_decay=0.01,
        logging_steps=50,
        eval_strategy="no",
        save_strategy="no",
        report_to=[],
        seed=42,
    )
    trainer = WeightedTrainer(
        model=model, args=training_args, train_dataset=train_ds,
        # Sem padding dinâmico o collator padrão quebra: os
        # textos têm comprimentos diferentes e o batch exige
        # tensores retangulares.
        data_collator=DataCollatorWithPadding(tokenizer),
        compute_metrics=_metrics)
    trainer.train()

    results = {}
    for name, ds in (("artigos_v1", v1_ds), ("misto", mixed_ds)):
        out = trainer.predict(ds)
        pred = np.argmax(out.predictions, axis=1)
        labels = out.label_ids
        results[name] = {
            "accuracy": round(float(accuracy_score(labels, pred)), 4),
            "f1_macro": round(float(f1_score(
                labels, pred, average="macro")), 4),
            "n": len(labels),
        }
        print(f"{name}: {results[name]}")

    trainer.save_model(args.out)
    tokenizer.save_pretrained(args.out)
    with open(os.path.join(args.out, "metrics.json"), "w",
              encoding="utf-8") as fh:
        json.dump(results, fh, ensure_ascii=False, indent=2)
    print(f"modelo salvo em {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
