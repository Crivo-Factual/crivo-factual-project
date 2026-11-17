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

import json
import time

import joblib
import streamlit as st
from huggingface_hub import hf_hub_download

HF_MODEL_REPO = "brenindexdev/crivo-factual-fakebr"
# BERTimbau has its own repo: the Inference API can only serve a
# model whose transformers files are at the repo root, and the
# main repo holds the BERTimbau files under bertimbau/ (plus the
# sklearn joblibs, which is why the router answered HTTP 400).
HF_BERTIMBAU_REPO = "brenindexdev/crivo-factual-bertimbau"

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


class _InferenceApiError(Exception):
    """An Inference API failure, carrying the HTTP status so the
    on-screen fallback note can say what actually went wrong."""

    def __init__(self, status, detail):
        super().__init__(f"HTTP {status}: {detail}" if status else detail)
        self.status = status
        self.detail = detail


def _bertimbau_score(text, token):
    """P(fake) from the Inference API via a plain HTTPS POST.
    (InferenceClient swallows the real error as a bare
    StopIteration, so the app calls the router directly and
    keeps the HTTP status.) Raises _InferenceApiError on any
    failure; retries twice while the model is loading (503)."""
    import urllib.error
    import urllib.request

    body = json.dumps({"inputs": text}).encode()
    url = f"https://router.huggingface.co/hf-inference/models/{HF_BERTIMBAU_REPO}"
    for attempt in range(3):
        req = urllib.request.Request(url, data=body, method="POST")
        req.add_header("Authorization", f"Bearer {token}")
        req.add_header("Content-Type", "application/json")
        try:
            with urllib.request.urlopen(req, timeout=120) as resp:
                out = json.loads(resp.read().decode())
            break
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode()[:200]
            if exc.code == 503 and "loading" in detail.lower() and attempt < 2:
                time.sleep(15)
                continue
            raise _InferenceApiError(exc.code, detail)
        except Exception as exc:  # noqa: BLE001 - wrapped below
            raise _InferenceApiError(None, str(exc)[:200])
    for entry in out:
        if entry["label"] in ("LABEL_1", "fake", "FAKE"):
            return float(entry["score"])
    # Single-label response: the top label is the answer.
    top = max(out, key=lambda e: e["score"])
    return float(top["score"]) if top["label"] in ("LABEL_1", "fake", "FAKE") else 1.0 - float(top["score"])


def _short_detail(detail):
    """The router's error message, if any (its JSON body is
    {"error": "..."}). Never includes the token."""
    if not detail:
        return ""
    try:
        parsed = json.loads(detail)
        if isinstance(parsed, dict) and parsed.get("error"):
            return str(parsed["error"])[:150]
    except Exception:  # noqa: BLE001 - fall back to raw text
        pass
    return detail[:150]


def _api_failure_reason(exc):
    """Short, safe description of an Inference API failure for the
    on-screen fallback note, including the API's own error
    message when it has one. Never includes the token."""
    status = getattr(exc, "status", None)
    msg = str(exc)
    detail = _short_detail(getattr(exc, "detail", "") or "")
    if status is not None:
        if status == 401 or "Invalid username" in msg:
            base = (
                "HTTP 401 — the token was rejected; check that "
                "HF_TOKEN has the 'Make calls to Inference Providers' "
                "permission"
            )
        elif status == 404:
            base = "HTTP 404 — the model was not found on the Inference API"
        elif status == 429:
            base = "HTTP 429 — rate limit, try again in a minute"
        elif status == 503:
            base = "the model is still loading on the server"
        else:
            base = f"HTTP {status} — the Inference API refused the request"
        return f"{base} ({detail})" if detail else base
    if "401" in msg or "Invalid username" in msg:
        return (
            "HTTP 401 — the token was rejected; check that "
            "HF_TOKEN has the 'Make calls to Inference Providers' "
            "permission"
        )
    if "404" in msg:
        return "HTTP 404 — the model was not found on the Inference API"
    if "429" in msg:
        return "HTTP 429 — rate limit, try again in a minute"
    if "loading" in msg.lower():
        return "the model is still loading on the server"
    if "timed out" in msg.lower() or "Timeout" in msg:
        return "the request timed out"
    return "no answer from the Inference API"


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
            except Exception as exc:  # noqa: BLE001 - fallback is the point
                reason = _api_failure_reason(exc)
            fallback_note = (
                f"BERTimbau API unavailable ({reason}), scored "
                "with the unified model instead."
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
        "[brenindexdev/crivo-factual-fakebr](https://huggingface.co/brenindexdev/crivo-factual-fakebr) "
        "(linear models) and [brenindexdev/crivo-factual-bertimbau](https://huggingface.co/brenindexdev/crivo-factual-bertimbau) "
        "(BERTimbau). "
        "Source code and test set: [Crivo-Factual/crivo-factual-project](https://github.com/Crivo-Factual/crivo-factual-project)."
    )
