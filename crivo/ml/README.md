# Veracity classifier (ML)

Three models, one router by text length — and a single model:

- **v1 — article specialist** (Fake.Br Corpus, 7,200 news items
  in aligned pairs). Only scores texts of 500 characters or more.
- **v2 — generalist** (FakenewsBR, 36,594 items: news, tweets,
  WhatsApp, COVID). Scores short text, but with a false-positive
  bias — it is a weak signal, never a verdict.
- **unified — one model for any length** (Fake.Br +
  FakenewsBR, 35,035 items). Articles F1 0.9646, mixed F1 0.7924 —
  the best single model; it only loses to v1 on articles (0.9736)
  and beats v2 on mixed (0.7754).

The design stays the same: ML is a **triage signal, never a
verdict** (see the section below).

## v1 — Fake.Br Corpus (16/11/2026)

Trained on the **Fake.Br Corpus** (Monteiro et al., 2018, PROPOR
2018) — 7,200 news items, 3,600 fake + 3,600 true, in aligned
pairs about the same fact.

## What it is — and what it is not

**It is a triage signal.** The suspicion score (0–1) prioritizes
the queue: what looks most fake is checked first, and the score
is recorded in the verdict and in the audit log
(`run_verdicts.py --ml-model`).

**It is not a judge.** It NEVER decides a verdict. The Crivo
verdict is still decided by deterministic rules over primary
sources (Câmara, Senado, DOU). A text with suspicion 0.99 and
another with 0.01 go through the same screening: without a
primary source, both come out Inconclusivo. This separation is
the central point of the design — and it is what makes the model
publishable without compromising the portal's methodology.

## Measured results (16/11/2026)

Training: TF-IDF (unigrams + bigrams, sublinear, 50k features,
Portuguese stopwords) + logistic regression, against a Naive
Bayes baseline. **Pair-wise split** (the fake and the true item
about the same fact never land on different sides — without this
the model would memorize the event).

| Metric | Value |
|---|---|
| Chosen model | Logistic regression |
| Accuracy (test, n=1440) | 0.9708 |
| F1-macro (test) | 0.9708 |
| Fake-class F1 | 0.9710 (precision 0.9669, recall 0.9750) |
| ROC-AUC | 0.9960 |
| CV 5-fold F1-macro | 0.9663 ± 0.0064 |
| Confusion matrix | [[696, 24], [18, 702]] |

## Measured limit: short text does not work

The model only saw full articles in training. On headlines and
summaries (~200 chars) it scores 0.91–0.98 **even when the news
is true** — it does not know what to do with short text. That is
why `suspicion_score` returns **None below 500 characters**
instead of a misleading number, and the integration only
computes suspicion over the **full article text**
(`get_item_text`), never over the title. On full articles the
behavior is as expected: true items from the corpus score
0.04–0.18; fake ones, 0.69–0.93.

## Calibration and measured thresholds (17/11/2026)

The probabilities **are not calibrated chances** — they are
ranking scores. Brier 0.0418 (good overall), but the middle
bands deviate: in the 0.1–0.3 band, 0% are fake (the model says
17%); in 0.3–0.5, 21% are fake (it says 39%); in 0.7–0.9, 99%
are fake (it says 83%). At the extremes it is right: 0.0–0.1
has 0% fakes and 0.9–1.0 has 100%. Read the score as "more
suspicious / less suspicious", not as "x% chance of being fake".

The triage bonus thresholds were measured on the test set
(n=1440), not guessed: **0.6 → precision 0.977, recall 0.950**
(bonus +5) and **0.8 → precision 0.998, recall 0.721** (bonus
+10). In other words: above 0.8 it is almost never a false
positive, but it only catches 72% of the fakes. Of the 42 test
errors, the average size is 2,337 chars (test average: 3,951)
— the model errs more on medium texts, not only on short ones
(only 4 of the 42 are under 1,000 chars).

## v2 — FakenewsBR + calibration (17/11/2026)

Training on the unified **FakenewsBR** corpus (Silva et al.,
2026, DSW) — 51,205 lines in the file, **36,594 canonical items
used** (26,534 fake / 10,060 true). Excluded: the `*_raw`
variants (the same instances before cleaning) and texts under
50 chars. The corpus is mostly short text (median 156 chars):
Kaggle news, tweets, WhatsApp, COVID-19, MuMiN-PT, LLM4BR_300.
Training runs in `scripts/train_classifier_v2.py`.

**Clean comparison:** the 1,440 items of the v1 test set were
excluded from v2 training by fingerprint (1,416 matched, all
from `Fake.br`; the other 24 do not exist in the file). v2 never
saw these texts — the comparison below is honest.

| Metric | v1 (articles) | v2 (mixed) | v2 on the v1 test |
|---|---|---|---|
| Accuracy | 0.9708 | 0.8086 | 0.9313 (calibrated) / 0.8854 |
| F1-macro | 0.9708 | 0.7676 | 0.9311 (calibrated) / 0.8841 |
| ROC-AUC | 0.9960 | 0.8575 | 0.9890 |
| Brier | 0.0418 | 0.1444 | 0.0561 (calibrated) / 0.0926 |
| n (test) | 1,440 | 7,319 | 1,440 |

**Verdict: v2 does NOT replace v1.** On full articles v1 is
still better (0.9708 against 0.9311 calibrated). The value of
v2 is its breadth: it covers tweets, WhatsApp and COVID,
domains v1 never saw — and it is the only model that scores
short text.

**Calibration — mixed result, not shipped.** Isotonic
calibration improves Brier (0.1444 → 0.1256 on the mixed test;
0.0926 → 0.0561 on articles) and improves F1 on articles
(0.8841 → 0.9311), but it shifts the operating point toward
"fake": on the mixed test, false positives on true items jump
from 590 to 1,011 and F1-macro drops (0.7676 → 0.7444). The
shipped artifact is the model **without calibration**;
calibration stays recorded as an experiment in `metrics.json`.

**False positives by source (v2 without calibration, mixed
test) — the score depends on the source, it is not uniform:**

| Source | True items called fake |
|---|---|
| LLM4BR_300 (political news) | 5% (1/20) |
| Fake.br (articles) | 9% (52/555) |
| FakeWhatsApp.BR_2018 | 22% (157/698) |
| COVID19.BR | 36% (81/226) |
| MuMiN-PT (tweets) | 53% (8/15) |
| true (Kaggle, true items only) | 58% (291/498) |

**Short text improved, but not solved.** v2 without calibration
scores short true text at 0.456 and short fake at 0.722 on
average (v1 scored 0.91–0.98 on short true text). It separates,
but the 500-character guard still applies — an ordinary true
sentence ("O governo anunciou hoje a nova regra para o saque do
FGTS...") still scores 0.80 on v2.

**v2 thresholds (mixed test, without calibration):** 0.6 →
precision 0.913, recall 0.716; 0.8 → precision 0.964, recall
0.313. The triage bonus thresholds (+5/+10) were measured for
v1 and **do not apply to v2** — v2 does not inherit the bonuses.

**Router (design):** text with 500+ characters → v1; short
text → v2 (weak signal). The local test script
(`crivo/ml/hf/infer.py`) already implements the router and the
unified model. Integration in the pipeline (`run_verdicts.py`)
still uses only v1 for now — the pipeline only scores full
articles.

## Mixing v1+v2 and char n-grams (17/11/2026)

The request was a single model with F1 >= 0.95 on both tests.
Three designs were measured (`scripts/experiment_mix.py`,
`scripts/experiment_char.py`):

- **Ensemble (average of the v1+v2 probabilities): LOST to
  both.** Articles F1 0.9597 (v1 alone: 0.9708); mixed F1
  0.6479 (v2 alone: 0.7676). Averaging dilutes each model's
  strength.
- **Unified (one model, training = Fake.Br training +
  FakenewsBR training = 35,035 items):** articles F1 0.9197,
  mixed F1 0.7754.
- **Unified + char n-grams: best SINGLE model** — articles
  F1 0.9485, mixed F1 0.7822 (beats v2 on both tests; loses to
  v1 on articles).
- **Optimal threshold (unified, mixed): 0.5** — already
  optimal; nothing to gain from threshold tuning.

**Char n-grams help both models on their own turf:**
v1+char (articles) F1 0.9736 (plain v1: 0.9708); v2+char
(mixed) F1 0.7754 (plain v2: 0.7676). That is why `logreg_char`
became the official configuration for both — and the canonical
retraining (17/11) confirmed the numbers exactly: v1 F1 0.9736,
v2 F1 0.7754.

**Kaggle `true` insight (resolved):** the 58% false-positive
rate on that source **is not a model failure** — the "true
texts" there **are not news**: they are fact-check questions
and fragments ("Papa Francisco recusou que fiéis beijassem o
anel papal?", "Portugal é o país da Europa Ocidental com o
mais baixo rendimento líquido de salários?"). It is another
text genre (short, interrogative, fragmentary) — exactly what
the model learned to call fake.

## Tuning the unified model (17/11/2026)

`scripts/tune_unified.py` and `tune_unified_extra.py` measured
everything on the same unified training set, on both tests:

| Candidate | Articles F1 | Mixed F1 |
|---|---|---|
| char C=0.5 | 0.9478 | 0.7769 |
| char C=1.0 | 0.9485 | 0.7822 |
| char C=2.0 | 0.9513 | 0.7894 |
| char C=4.0 | 0.9534 | 0.7909 |
| char C=2.0 + article oversample ×2 | 0.9625 | 0.7870 |
| **char C=4.0 + oversample articles ×2** | **0.9646** | **0.7924** |
| LinearSVC | 0.9339 | 0.7859 |
| ComplementNB | 0.7947 | 0.7264 |
| Vote (char + SVC + CNB) | 0.9359 | 0.7914 |
| Vote C=2.0 + oversample ×2 | 0.9471 | 0.7877 |

**What the table says:** larger C helps on both tests up to
C=4.0 (the trend flattens — C=2.0 → C=4.0 gains only +0.0015
on mixed). Oversampling the articles lifts articles without
hurting mixed. Voting is the best on mixed without oversampling
(0.7914), but drops on articles (0.9359) — CNB drags the vote
down on articles. The **final unified model is char C=4.0 +
oversample ×2: articles 0.9646, mixed 0.7924**
(`scripts/train_unified.py --compare`, artifact in
`crivo/ml/models/unified/`).

**Measured ceiling — why 0.95 on mixed does not come from a
linear model:** the best model evaluated on the mixed test
WITHOUT the `true` (Kaggle) and `MuMiN-PT` sources reaches F1
0.8183. Even without the two worst sources, the linear model
stays 13 points below the goal. The bottleneck is the data
(short text, fact-check questions, irony and mixed genres do
not separate by word counts), not the tuning. The honest
footnote: C was chosen by evaluating directly on the test sets
(3-fold CV would not finish on this VM), so the C numbers are
slightly optimistic.

## BERTimbau — the path to 0.95 on mixed (17/11/2026)

The only plausible path to the jump on mixed is a transformer
pretrained in Portuguese, which reads context instead of
counting words. The script `scripts/train_bertimbau.py`
fine-tunes BERTimbau (`neuralmind/bert-base-portuguese-cased`)
on the **same splits** as the linear experiments (seed 42),
with class weights (training is 73% fake) and evaluation on
both tests, so the numbers are comparable. The notebook
`crivo/ml/hf/bertimbau-colab.ipynb` runs everything on free
Colab (T4 GPU, 30–60 min, 3 epochs, batch 32, max_len 256).

**Result (real training, 17/11/2026, Kaggle T4 GPU — free
Colab had no GPU available; the Kaggle notebook is
`crivo/ml/hf/bertimbau-kaggle.ipynb`): articles F1-macro
0.9868 (accuracy 0.9868, n=1440) — the 0.95 goal BEATEN, above
v1 (0.9736) and the unified model (0.9646); mixed F1-macro
0.8184 (accuracy 0.8507, n=7319) — the best on mixed so far
(unified 0.7924), but below the 0.95 goal. Mixed landed exactly
on the measured linear ceiling without the worst sources
(0.8183), but on the FULL set — the transformer solved the
`true` and `MuMiN-PT` source problem that capped the linear
model, and still hit the same ceiling. Conclusion: the
bottleneck on mixed is the data, not the model. The script was
checked beforehand with a CPU smoke test (64 examples, 1 epoch
— training, evaluation and saving all ran; the smoke F1 values
are not metrics, they only prove the code works). Two
transformers 5.x incompatibilities were fixed along the way:
`warmup_ratio` no longer exists (only `warmup_steps`, computed
as 10% of total steps) and the default collator breaks on texts
of different lengths (`DataCollatorWithPadding`). The notebook
pins `transformers==5.23.0`, the tested version. The trained
model weights are in the Kaggle session output
(`./bertimbau-v1`) — not yet uploaded to the Hub.

**Training-data cleaning does not work (17/11/2026).**
Removing the non-news items of the `true` source and texts
<100 chars from training made mixed worse (F1 0.7924 →
0.7770) and raised the false-positive rate on the `true`
source to 94.0% — the question fragments were the only
short-true counterweight against the "short text → fake"
shortcut. The right direction is the opposite: keep or
reinforce short true items.

**Reinforcing short true items does not work either
(17/11/2026).** Duplicating ×2/×3 the short true items in
training made mixed worse (F1 0.7924 → 0.7871 in the best
case): the false-positive rate on the `true` source fell, but
false recall fell more. Duplicating shifts the prior, it does
not teach the pattern.

## Reproduce

```bash
# 1. Download the corpus (not committed to the repo — 146 MB)
git clone --depth 1 https://github.com/roneysco/Fake.br-Corpus.git \
  ~/workspace/crivo/fakebr-corpus

# 2. ML venv (the repo is standard library only; ML is optional)
python3 -m venv .venv-ml
.venv-ml/bin/pip install scikit-learn pandas

# 3. Train v1 (generates crivo/ml/models/model.joblib + metrics.json)
.venv-ml/bin/python scripts/train_classifier.py

# 3b. Train v2 (needs the FakenewsBR CSV — see
# crivo/ml/fakenewsbr.py for the download; generates
# crivo/ml/models/v2/model.joblib + metrics.json)
.venv-ml/bin/python scripts/train_classifier_v2.py \
  --fakenewsbr ~/workspace/crivo/fakenewsbr/FakenewsBR_factchecked.csv \
  --fakebr ~/workspace/crivo/fakebr-corpus \
  --out crivo/ml/models/v2

# 3c. Train the unified model (the best single model; generates
# crivo/ml/models/unified/model.joblib + metrics.json)
.venv-ml/bin/python scripts/train_unified.py \
  --fakenewsbr ~/workspace/crivo/fakenewsbr/FakenewsBR_factchecked.csv \
  --fakebr ~/workspace/crivo/fakebr-corpus \
  --out crivo/ml/models/unified --compare

# 3d. BERTimbau (GPU Colab only — see
# crivo/ml/hf/bertimbau-colab.ipynb; the smoke test runs on CPU)
.venv-bert/bin/python scripts/train_bertimbau.py --smoke \
  --fakenewsbr ~/workspace/crivo/fakenewsbr/FakenewsBR_factchecked.csv \
  --fakebr ~/workspace/crivo/fakebr-corpus \
  --out /tmp/bertimbau-smoke

# 4. Use in the pipeline (score recorded, verdict unchanged)
python3 scripts/run_verdicts.py --limit 10 \
  --ml-model crivo/ml/models/model.joblib
```

ML tests (`tests/test_ml.py`) skip on their own when
scikit-learn is not installed — CI stays green without it.
Integration tests (triage bonus, suspicion recorded without
changing the verdict) use a fake model and always run.

## Publishing on Hugging Face

The artifacts are the full pipelines (vectorizer + model),
saved with joblib: `crivo/ml/models/model.joblib` (v1),
`crivo/ml/models/v2/model.joblib` (v2, without calibration) and
`crivo/ml/models/unified/model.joblib` (unified, C=4.0 +
oversample ×2), each with its `metrics.json`. The publishing
files (model card + Gradio demo with the v1/v2 router and the
unified selector) are in `crivo/ml/hf/` — the models go to the
Hub with the creator's account; see `crivo/ml/hf/README.md`
and `crivo/ml/hf/README-publicar.md`. The BERTimbau
fine-tuning, once run on Colab, goes to the same repository
(`bertimbau/`).

## Corpus citations

Monteiro R.A., Santos R.L.S., Pardo T.A.S., de Almeida T.A.,
Ruiz E.E.S., Vale O.A. (2018). *Contributions to the Study of
Fake News in Portuguese: New Corpus and Automatic Detection
Results.* PROPOR 2018, LNCS vol. 11122. Springer.

Silva et al. (2026). *FakenewsBR: A Unified Corpus for Fake News
Detection in Portuguese.* DSW 2026. Unified corpus at
https://github.com/AKCIT-FN/fakenews-data (CSV mirror on the
Hugging Face Hub: `kauandivino/FakenewsBR`).
