"""Crivo Factual — veracity classifier demo (Streamlit).

Paste a text in Portuguese and see the estimated probability
that it is false.

Models:
- BERTimbau (default, via the Hugging Face Inference API):
  the published weights run on Hugging Face's servers, so the
  app stays light — no torch, no 440 MB download. Needs an
  HF_TOKEN with inference permission in the app's Secrets
  (Streamlit dashboard -> Settings -> Secrets). If the API is
  unavailable, the demo falls back to the unified model and
  says so.
- Unified (Fake.Br + FakenewsBR): one local model for any
  length, downloaded from the Hub on first run.
- Router: v1 (Fake.Br, full articles, only 500+ chars) or v2
  (FakenewsBR, short text) by length.

Triage signal, not a verdict: in Crivo Factual, the verdict is
decided by deterministic rules over primary sources, never by
this model.

Measured limits (current-politics test set, Nov 2026, n=20):
articles 100% correct for every model (n=8); short claims
75% (n=12) — every model over-flags short true claims as
false. Short-text scores are a weak signal.
"""

import time

import joblib
import streamlit as st
from huggingface_hub import InferenceClient, hf_hub_download

HF_MODEL_REPO = "brenindexdev/crivo-factual-fakebr"

# Minimum text length for v1 to score (see crivo/ml/classifier.py).
MIN_CHARS_V1 = 500
# Short text: every model over-flags short true claims (measured).
SHORT_TEXT_CHARS = 500

EXAMPLE_ARTICLE = (
    "A Câmara dos Deputados aprovou nesta terça-feira o projeto "
    "que trata da renegociação de dívidas rurais. A votação "
    "contou com ampla maioria dos parlamentares presentes, e o "
    "texto segue agora para análise do Senado Federal, onde deve "
    "ser votado ainda nesta semana, segundo a liderança do "
    "governo na Casa."
)

EXAMPLE_CLICKBAIT = (
    "URGENTE: você não vai acreditar no que o governo escondeu! "
    "Compartilhe antes que apaguem!"
)


@st.cache_resource
def load(name):
    path = hf_hub_download(repo_id=HF_MODEL_REPO, filename=name)
    return joblib.load(path)


def _bertimbau_score(text, token):
    """P(fake) from the Inference API. Raises on any failure;
    the caller decides the fallback. Retries once while the
    model is loading on the server (503)."""
    client = InferenceClient(model=HF_MODEL_REPO, token=token, timeout=120)
    last_error = None
    for attempt in range(3):
        try:
            out = client.text_classification(text)
            break
        except Exception as exc:  # noqa: BLE001 - surfaced as fallback
            last_error = exc
            if "loading" in str(exc).lower() and attempt < 2:
                time.sleep(15)
                continue
            raise
    else:
        raise last_error
    for entry in out:
        if entry["label"] in ("LABEL_1", "fake", "FAKE"):
            return float(entry["score"])
    # Single-label response: the top label is the answer.
    top = max(out, key=lambda e: e["score"])
    return float(top["score"]) if top["label"] in ("LABEL_1", "fake", "FAKE") else 1.0 - float(top["score"])


def reading(proba):
    if proba >= 0.8:
        return "likely false"
    if proba >= 0.6:
        return "suspicious"
    return "likely true"


def classify(text, mode):
    """Return (suspicion, model_label, warning). Suspicion is the
    estimated probability that the text is false (0–1)."""
    text = (text or "").strip()
    if not text:
        return None, "", "Paste a text to classify."
    if mode.startswith("BERTimbau"):
        try:
            token = st.secrets.get("HF_TOKEN")
        except Exception:  # noqa: BLE001 - no secrets file configured
            token = None
        if token:
            try:
                proba = _bertimbau_score(text, token)
                return proba, "BERTimbau (via Inference API)", ""
            except Exception:  # noqa: BLE001 - fallback is the point
                pass
            fallback_note = (
                "BERTimbau API unavailable (no answer from the "
                "Inference API), scored with the unified model "
                "instead."
            )
        else:
            fallback_note = (
                "BERTimbau API needs an HF_TOKEN in the app Secrets, "
                "scored with the unified model instead."
            )
        proba = float(load("model_unified.joblib").predict_proba([text])[0][1])
        return proba, "unified (fallback)", fallback_note
    if mode.startswith("Unified"):
        proba = float(load("model_unified.joblib").predict_proba([text])[0][1])
        return proba, "unified", ""
    if len(text) >= MIN_CHARS_V1:
        proba = float(load("model_v1.joblib").predict_proba([text])[0][1])
        return proba, "v1 (full article)", ""
    proba = float(load("model_v2.joblib").predict_proba([text])[0][1])
    warning = (
        "v2 scores short text, but with a bias: short true text "
        "scores 0.46 on average — read it as a weak signal."
    )
    return proba, "v2 (short text)", warning


st.set_page_config(page_title="Crivo Factual — Veracity classifier", layout="centered")
st.title("Crivo Factual — Veracity classifier")
st.write(
    "BERTimbau (best model, served by the Hugging Face Inference "
    "API), the unified linear model, and the v1/v2 router. The "
    "score is a triage signal, not a verdict."
)

if "text" not in st.session_state:
    st.session_state.text = ""

col1, col2 = st.columns(2)
with col1:
    if st.button("Try a real article"):
        st.session_state.text = EXAMPLE_ARTICLE
with col2:
    if st.button("Try clickbait"):
        st.session_state.text = EXAMPLE_CLICKBAIT

text = st.text_area(
    "Text in Portuguese (article or short text)",
    value=st.session_state.text,
    height=200,
    placeholder="Paste the text here...",
)
mode = st.radio(
    "Model",
    ["BERTimbau (via Inference API)", "Unified (one model)", "Router (v1/v2 by length)"],
    index=0,
)

if st.button("Classify", type="primary"):
    proba, model, warning = classify(text, mode)
    if proba is None:
        st.warning(warning)
    else:
        st.metric("Suspicion score (probability the text is false)", f"{proba:.2f}")
        st.progress(proba)
        st.write(f"**Model:** {model}. **Reading:** {reading(proba)}.")
        if warning:
            st.warning(warning)
        if len(text.strip()) < SHORT_TEXT_CHARS:
            st.warning(
                "Short text: on the current-politics test set "
                "(Nov 2026, 12 short items) every model over-flags "
                "short true claims as false (false-positive rate "
                "20–30%). Read short-text scores as a weak signal."
            )
        st.info(
            "This is a triage signal, not a verdict: in Crivo Factual, "
            "the conclusion comes from primary sources (Chamber of "
            "Deputies, Senate, Official Gazette)."
        )

with st.expander("How it works"):
    st.write(
        "The suspicion score orders the human verification queue and "
        "is recorded in the audit trail; it never decides the "
        "published verdict. Measured results on the fixed test sets "
        "(seed 42):"
    )
    st.table(
        {
            "Model": ["v1 (articles)", "v2 (mixed)", "Unified (articles)", "Unified (mixed)", "BERTimbau (articles)", "BERTimbau (mixed)"],
            "Macro-F1": ["0.9736", "0.7754", "0.9646", "0.7924", "0.9854", "0.8243"],
        }
    )
    st.write(
        "Current-politics test set (Nov 2026, n=20: 10 true, 10 "
        "false — real g1 articles and claims debunked by Lupa / "
        "Aos Fatos): accuracy 0.85 for v2, unified, BERTimbau and "
        "the router (v1: 0.75). Articles: 1.00 for every model "
        "(n=8). Short claims: 0.75 (n=12) — every model over-flags "
        "short true claims. The bottleneck is the data, not the "
        "model. Models and weights: "
        "[brenindexdev/crivo-factual-fakebr](https://huggingface.co/brenindexdev/crivo-factual-fakebr). "
        "Source code and test set: [Crivo-Factual/crivo-factual-project](https://github.com/Crivo-Factual/crivo-factual-project)."
    )
