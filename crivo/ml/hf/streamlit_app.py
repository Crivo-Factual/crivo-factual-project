"""Crivo Factual — veracity classifier demo (Streamlit).

Paste a text in Portuguese and see the estimated probability
that it is false. Same models and thresholds as the Gradio demo
(`crivo/ml/hf/app.py`), rewritten for Streamlit Community Cloud.

Models (downloaded from the Hub on first run):
- v1 (Fake.Br, full articles): only scores texts of 500+ chars.
- v2 (FakenewsBR, news + tweets + WhatsApp): scores short text,
  but with a false-positive bias — a weak signal.
- unified (Fake.Br + FakenewsBR): one model for any length.

Triage signal, not a verdict: in Crivo Factual, the verdict is
decided by deterministic rules over primary sources, never by
this model.

BERTimbau is intentionally NOT loaded here: Streamlit Community
Cloud gives a free app 1 GB of RAM, and torch + a 440 MB BERT
model does not fit in it. The weights are published in the same
Hub repository, under `bertimbau/`.
"""

import joblib
import streamlit as st
from huggingface_hub import hf_hub_download

HF_MODEL_REPO = "brenindexdev/crivo-factual-fakebr"

# Minimum text length for v1 to score (see crivo/ml/classifier.py).
MIN_CHARS_V1 = 500

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
    "Three models: v1 trained on the Fake.Br Corpus (7,200 articles) "
    "for long texts, v2 trained on FakenewsBR (36,594 items: news, "
    "tweets, WhatsApp) for short texts, and the unified model "
    "(Fake.Br + FakenewsBR) for any length. The score is a triage "
    "signal, not a verdict."
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
    ["Unified (one model)", "Router (v1/v2 by length)"],
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
        st.info(
            "This is a triage signal, not a verdict: in Crivo Factual, "
            "the conclusion comes from primary sources (Chamber of "
            "Deputies, Senate, Official Gazette)."
        )

with st.expander("How it works"):
    st.write(
        "The suspicion score orders the human verification queue and "
        "is recorded in the audit trail; it never decides the "
        "published verdict. Measured results (fixed tests, seed 42):"
    )
    st.table(
        {
            "Model": ["v1 (articles)", "v2 (mixed)", "Unified (articles)", "Unified (mixed)", "BERTimbau (articles)", "BERTimbau (mixed)"],
            "Macro-F1": ["0.9736", "0.7754", "0.9646", "0.7924", "0.9854", "0.8243"],
        }
    )
    st.write(
        "BERTimbau is the best model on both test sets, but the mixed "
        "regime has a measured ceiling of ~0.82: the bottleneck is the "
        "data, not the model. Models and weights: "
        "[brenindexdev/crivo-factual-fakebr](https://huggingface.co/brenindexdev/crivo-factual-fakebr). "
        "Source code: [Crivo-Factual/crivo-factual-project](https://github.com/Crivo-Factual/crivo-factual-project)."
    )
