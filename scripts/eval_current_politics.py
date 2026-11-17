"""Score all four models on the current-politics test set.

Models: v1, v2, unified (local joblib) and BERTimbau (published
weights from the Hub, run locally with torch). Also scores the
demo router (v1 if >=500 chars else v2).

Usage (needs torch + sklearn in the venv):
    .venv-bert/bin/python scripts/eval_current_politics.py

Writes crivo/ml/data/current_politics_results.json and prints
a per-item table plus per-model accuracy, split by kind
(article/short) and by label (false-positive rate on true
items, recall on false items). Threshold 0.5.
"""
import json
import joblib
import torch
from transformers import AutoModelForSequenceClassification, AutoTokenizer

BASE = "crivo/ml/models"
TEST_PATH = "crivo/ml/data/current_politics_test.json"
OUT_PATH = "crivo/ml/data/current_politics_results.json"
MIN_CHARS_V1 = 500


def main():
    data = json.load(open(TEST_PATH))
    items = data["items"]

    v1 = joblib.load(f"{BASE}/model.joblib")
    v2 = joblib.load(f"{BASE}/v2/model.joblib")
    uni = joblib.load(f"{BASE}/unified/model.joblib")
    tok = AutoTokenizer.from_pretrained(
        "brenindexdev/crivo-factual-fakebr", subfolder="bertimbau")
    bert = AutoModelForSequenceClassification.from_pretrained(
        "brenindexdev/crivo-factual-fakebr", subfolder="bertimbau")
    bert.eval()

    def bert_score(text):
        enc = tok(text, return_tensors="pt", truncation=True, max_length=256)
        with torch.no_grad():
            probs = torch.softmax(bert(**enc).logits, dim=-1)[0]
        return float(probs[1])

    rows = []
    for it in items:
        t = it["text"]
        row = {
            "id": it["id"], "label": it["label"], "kind": it["kind"],
            "chars": len(t),
            "v1": float(v1.predict_proba([t])[0][1]),
            "v2": float(v2.predict_proba([t])[0][1]),
            "unified": float(uni.predict_proba([t])[0][1]),
            "bertimbau": bert_score(t),
        }
        row["router"] = row["v1"] if len(t) >= MIN_CHARS_V1 else row["v2"]
        rows.append(row)

    print(f"{'id':28} {'lbl':3} {'kind':7} {'v1':>6} {'v2':>6} {'uni':>6} {'bert':>6} {'rout':>6}")
    for r in rows:
        print(f"{r['id']:28} {r['label']:3} {r['kind']:7} "
              f"{r['v1']:6.2f} {r['v2']:6.2f} {r['unified']:6.2f} "
              f"{r['bertimbau']:6.2f} {r['router']:6.2f}")

    def report(name, key):
        def acc(sub):
            if not sub:
                return float("nan")
            return sum(1 for r in sub if (r[key] >= 0.5) == bool(r["label"])) / len(sub)
        all_r = rows
        art = [r for r in rows if r["kind"] == "article"]
        short = [r for r in rows if r["kind"] == "short"]
        true = [r for r in rows if r["label"] == 0]
        false = [r for r in rows if r["label"] == 1]
        fp = sum(1 for r in true if r[key] >= 0.5) / len(true)
        rec = sum(1 for r in false if r[key] >= 0.5) / len(false)
        print(f"{name:10} acc={acc(all_r):.2f} (n={len(all_r)}) "
              f"articles={acc(art):.2f} short={acc(short):.2f} "
              f"FP-on-true={fp:.2f} recall-false={rec:.2f}")
        return {"acc": acc(all_r), "acc_articles": acc(art),
                "acc_short": acc(short), "fp_on_true": fp,
                "recall_false": rec}

    print()
    summary = {name: report(name, key) for name, key in
               [("v1", "v1"), ("v2", "v2"), ("unified", "unified"),
                ("bertimbau", "bertimbau"), ("router", "router")]}
    json.dump({"n": len(rows), "rows": rows, "summary": summary},
              open(OUT_PATH, "w"), ensure_ascii=False, indent=2)
    print("saved", OUT_PATH)


if __name__ == "__main__":
    main()
