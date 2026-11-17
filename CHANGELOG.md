# Changelog

The history on `main` is preserved exactly as it happened: 212 commits
in three working days, mostly one commit per file (the API upload
workflow). This file is the English map of that history, grouped by
workstream. Nothing here rewrites the past — for the branching rules
that apply from now on, see "Branching (GitLab Flow)" in
`DEVELOPMENT.md`.

## 2026-10-30 — Foundation, Wave 0, M1 (36 commits)

- Project documents 01–10 (vision, verdict rules, pipeline, free-tier
  architecture) and repository setup with the GitHub API connection.
- Wave 0 validation demo (v3): stamped verification-card identity,
  4 numbered areas, 9 real images, one 3-part channel message format.
- M1 — repo skeleton: config, SQLite fact bank, 6-module pipeline
  (stdlib-only RSS collectors, triage proxy, rule extraction,
  deterministic verdict engine), static publisher, demo script,
  `tests/test_verdict.py`. Demo verdicts: Bolsa Família **False 20%
  (veto)**, 2027 cuts **Inconclusive 50% (lock)**, end of 6x1
  **True 100%**. CI (unittest + demo on every push to main).

## 2026-11-12 — M2, M3, M4, #47, Wave 1 review (115 commits)

- M2 — collectors and triage: live-verified sources only (g1, Senado
  Notícias, Poder360, Câmara open-data API, Senado open-data API),
  persistent SQLite queue (dedup by content hash, backoff, 5 attempts),
  triage by virality/verifiability.
- M3 — verdict engine: fingerprint-based recycled-verdict lookup,
  Groq free-tier LLM extraction (fails safe to rules only), verdict
  pipeline with versioning, `--llm` / `--limit` runner.
- M4 — distribution and observability: one 3-part message format per
  channel, real Instagram Graph API client (manual outbox without
  credentials), hash-chain audit log, distribution outbox, dashboard,
  weekly newsletter (Resend not wired).
- #47 — live primary-evidence search: Câmara and Senado clients
  (paginated lookup, ambiguous-type disambiguation), DOU search by
  exact-phrase web query with title matching, g1 feed switched to
  politics, full article text, triage fix (reference or political
  keyword in the title), central-statement fix (number/date are never
  central), thousand-separator normalization, coverage probe
  (48 items / 208 claims). Measured: items WITH a reference, 23/26
  with proof (88%); items WITHOUT a reference, 87/87 Inconclusive,
  zero false confirmations.
- Wave 1 review (`docs/revisao-onda-1.md`): 26 verdicts, 100%
  Inconclusive; collection-to-verdict latency 26.1 min average;
  full cycle 17 s. Decision: Wave 1 stays OPEN until primary search
  exists; #47 closed with the reframed acceptance.

## 2026-11-17 — ML adaptation, Hugging Face, English docs (61 commits)

- v1 — Fake.Br article classifier: TF-IDF + Logistic Regression,
  F1-macro **0.9736** (test n=1440), ROC-AUC 0.9960.
- v2 — FakenewsBR mixed-text classifier: F1-macro **0.7754**
  (test n=7319); isotonic calibration measured and rejected.
- Unified model: articles F1 **0.9646** / mixed F1 **0.7924**;
  length router in the demo (>=500 chars -> v1, short -> v2).
- BERTimbau fine-tune (Kaggle T4): articles F1 **0.9868** (beats the
  0.95 target) / mixed F1 **0.8184** — the measured ceiling for mixed
  text; the bottleneck is the data, not the model.
- Hugging Face: linear models published at
  `brenindexdev/crivo-factual-fakebr` (v1, v2, unified + English
  model card). Gradio Space blocked: 402 Payment Required (running
  code needs PRO; account not eligible for free ZeroGPU). BERTimbau
  weights upload in progress from the Kaggle session.
- Experiments tested and rejected: training-data cleaning (mixed
  0.7924 -> 0.7770) and reinforcing short true items (mixed ->
  0.7871). Both data levers fail in opposite directions.
- English docs: ML README, model card, publish guide and the ML
  sections of DEVELOPMENT.md translated (684 numbers verified
  unchanged). Main repo README stays PT-BR — the portal is a
  Brazilian product.
