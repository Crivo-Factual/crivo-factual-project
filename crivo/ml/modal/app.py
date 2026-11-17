"""BERTimbau served as a Modal web endpoint (CPU, scale-to-zero).

The Streamlit demo calls this endpoint instead of the Hugging Face
Inference API, because the HF router does not serve custom fine-tuned
models ("Model not supported by provider hf-inference").

Deploy (after `modal token new` and creating the secret)::

    modal secret create crivo-api-token CRIVO_API_TOKEN=<random-token>
    modal deploy crivo/ml/modal/app.py

`modal deploy` prints the endpoint URL; put it in the Streamlit
Secrets as MODAL_URL, with the same token as MODAL_API_TOKEN.

Cost (Nov 2026 rates): 2 CPU cores + 4 GiB RAM is about
$0.000035/second of container runtime (~$0.13/hour while running).
Containers scale to zero when idle, so a demo click costs a fraction
of a cent warm and a few tenths of a cent on a cold start. The $30/month
Starter credits cover this workload with a wide margin.

Model: brenindexdev/crivo-factual-bertimbau (public). The weights are
cached in a Modal Volume, so they are downloaded from the Hub once.
"""

import os

import modal
from fastapi import Header, HTTPException
from pydantic import BaseModel

MODEL_REPO = "brenindexdev/crivo-factual-bertimbau"
MAX_CHARS = 10_000

image = (
    modal.Image.debian_slim()
    .pip_install("torch", index_url="https://download.pytorch.org/whl/cpu")
    .pip_install("transformers==5.23.0", "fastapi[standard]")
)

app = modal.App("crivo-factual-bertimbau")

volume = modal.Volume.from_name("crivo-bertimbau-cache", create_if_missing=True)


class ClassifyRequest(BaseModel):
    text: str


@app.function(image=image)
@modal.fastapi_endpoint(method="GET", label="health")
def health():
    return {"status": "ok", "model": MODEL_REPO}


@app.cls(
    image=image,
    cpu=2.0,
    memory=4096,
    volumes={"/cache": volume},
    secrets=[modal.Secret.from_name("crivo-api-token")],
    env={"HF_HOME": "/cache", "HF_HUB_DISABLE_PROGRESS_BARS": "1"},
    scaledown_window=60,
    max_containers=2,
    timeout=300,
)
class BertimbauClassifier:
    @modal.enter()
    def load(self):
        from transformers import AutoModelForSequenceClassification, AutoTokenizer

        self.tokenizer = AutoTokenizer.from_pretrained(MODEL_REPO)
        self.model = AutoModelForSequenceClassification.from_pretrained(MODEL_REPO)
        self.model.eval()

    @modal.fastapi_endpoint(method="POST", label="classify")
    def classify(
        self,
        payload: ClassifyRequest,
        authorization: str | None = Header(default=None),
    ):
        import torch

        expected = os.environ.get("CRIVO_API_TOKEN")
        if expected and authorization != f"Bearer {expected}":
            raise HTTPException(status_code=401, detail="Invalid or missing API token")

        text = (payload.text or "").strip()[:MAX_CHARS]
        if not text:
            raise HTTPException(status_code=400, detail="Empty text")

        inputs = self.tokenizer(text, truncation=True, max_length=512, return_tensors="pt")
        with torch.no_grad():
            logits = self.model(**inputs).logits
        probs = torch.softmax(logits, dim=-1)[0]
        return {"suspicion": float(probs[1]), "model": "bertimbau"}
