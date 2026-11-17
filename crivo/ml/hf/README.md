---
language: en
license: mit
library_name: sklearn
tags:
- fake-news
- portuguese
- text-classification
- fact-checking
---

# Crivo Factual — Veracity classifiers (v1 + v2 + unified)

Three classifiers that estimate the probability that a text in
Brazilian Portuguese is fake:

- **v1 — article specialist.** Trained on the
  [Fake.Br Corpus](https://github.com/roneysco/Fake.br-Corpus)
  (Monteiro et al., 2018) — 7,200 news items, 3,600 fake + 3,600
  true, in aligned pairs about the same fact. Only scores texts
  of 500 characters or more.
- **v2 — generalist.** Trained on
  [FakenewsBR](https://github.com/AKCIT-FN/fakenews-data) (Silva
  et al., 2026) — 36,594 canonical items: news, tweets,
  WhatsApp, COVID-19. Scores short text, but with a false-positive
  bias.
- **unified — one model for any length.** Trained on Fake.Br +
  FakenewsBR (35,035 items). Articles F1 0.9646, mixed F1 0.7924
  — the best single model in the project.

Model: TF-IDF (unigrams + bigrams, sublinear, 50k features,
Portuguese stopwords) + TF-IDF of char n-grams (3–5, 30k) +
logistic regression (C=4.0 on the unified model; C=1.0 on v1/v2).
The artifact is the full pipeline (vectorizer + model), saved
with joblib. `model_v1.joblib`, `model_v2.joblib` and
`model_unified.joblib` are the three artifacts; `model.joblib`
(v1) is kept for compatibility.

## Measured results

| Metric | v1 (articles, n=1440) | v2 (mixed, n=7319) | v2 on the v1 articles | unified (articles) | unified (mixed) | BERTimbau (articles) | BERTimbau (mixed) |
|---|---|---|---|---|---|---|---|
| Accuracy | 0.9708 | 0.8086 | 0.8854 | 0.9646 | 0.8386 | 0.9854 | 0.8561 |
| F1-macro | 0.9708 | 0.7676 | 0.8841 | 0.9646 | 0.7924 | 0.9854 | 0.8243 |
| ROC-AUC | 0.9960 | 0.8575 | 0.9888 | — | — | — | — |
| Brier | 0.0418 | 0.1444 | 0.0926 | — | — | — | — |

Real BERTimbau training on 17/11/2026, Kaggle T4 GPU (free
Colab had no GPU available). Same splits (seed 42) and same
tests as the linear models — the numbers are comparable. The
trained model weights are published in this repository, under
`bertimbau/` (configuration, weights, tokenizer and metrics),
uploaded from the Kaggle session on 17/11/2026 (re-run of the
training; first run: articles 0.9868 / mixed 0.8184).

The v2 vs v1 comparison on articles is clean: the 1,440 items
of the v1 test set were excluded from v2 training by
fingerprint. The unified model uses the same splits (seed 42)
and the same tests.

## Usage (router)

```python
import joblib
v1 = joblib.load("model_v1.joblib")
v2 = joblib.load("model_v2.joblib")

def suspicion(text):
    if len(text.strip()) >= 500:
        return float(v1.predict_proba([text])[0][1]), "v1"
    return float(v2.predict_proba([text])[0][1]), "v2"
```

## Usage (unified — one model, any length)

```python
import joblib
uni = joblib.load("model_unified.joblib")

def suspicion(text):
    return float(uni.predict_proba([text])[0][1])
```

## Limits — read before using

- **v2 does not replace v1.** On full articles v1 is still
  better (F1 0.9708 against 0.8841). v2 is worth it for breadth
  (tweets, WhatsApp, COVID) and short text.
- **BERTimbau is the best model on both tests, but mixed
  stays below 0.95.** Articles F1 0.9854 (goal beaten),
  mixed F1 0.8243. Mixed clears the measured linear ceiling
  without the worst sources (0.8183) by 0.6 points, on the full
  set — the bottleneck is the data, not the model. See
  `crivo/ml/README.md`.
- **False positives by source (v2).** The score depends on the
  source: 5% on political news, 9% on Fake.Br articles, 22% on
  WhatsApp, 36% on COVID, 53% on MuMiN tweets, 58% on the true
  Kaggle news. Read it as a weak signal, not as a probability.
- **Short text (v2).** Short true text scores 0.46 and short
  fake 0.72 on average — it separates, but an ordinary true
  sentence can still score 0.80. The 500-character guard on v1
  still applies to articles.
- **Calibration not shipped.** Isotonic calibration improves
  Brier, but shifts the operating point toward "fake" (false
  positives from 590 to 1,011 on the mixed test). The artifact
  is the model without calibration.
- **It is a triage signal, not a verdict.** In the Crivo
  Factual project, this score only prioritizes the checking
  queue. The verdict is still decided by deterministic rules
  over primary sources (Câmara, Senado, Diário Oficial). No
  number from this model declares a news item fake.
- **Corpus bias.** Fake news has strong style markers
  (sensationalism, clickbait); the model learns style as much
  as content. Fake.Br is from 2016–2018; FakenewsBR runs to
  2022.

## Corpus citations

Monteiro R.A., Santos R.L.S., Pardo T.A.S., de Almeida T.A.,
Ruiz E.E.S., Vale O.A. (2018). *Contributions to the Study of
Fake News in Portuguese: New Corpus and Automatic Detection
Results.* PROPOR 2018, LNCS vol. 11122. Springer.

Silva et al. (2026). *FakenewsBR: A Unified Corpus for Fake News
Detection in Portuguese.* DSW 2026.
https://github.com/AKCIT-FN/fakenews-data
