# BERTimbau on Modal

Serves the fine-tuned BERTimbau classifier (`brenindexdev/crivo-factual-bertimbau`)
as a CPU web endpoint, so the Streamlit demo can call it live. Built because
the Hugging Face Inference API refuses custom fine-tuned models
("Model not supported by provider hf-inference").

## Cost

Nov 2026 Modal rates: CPU $0.0000131/core/s, memory $0.00000222/GiB/s.
This app requests 2 cores + 4 GiB, about **$0.13/hour of container runtime**.
Containers scale to zero when idle, so a demo click costs a fraction of a cent
warm and a few tenths of a cent on a cold start. The $30/month Starter credits
cover this workload with a wide margin.

## The payment-method catch

Modal's billing docs say: "you must have a payment method on file in order to
use Modal." So a card has to be on file even to use the free credits. Two
safeguards make that safe:

1. The $30/month Starter credits are spent first; the demo uses a few dollars
   of compute a month at most.
2. Set the Workspace **spend limit to $0** (Settings → Usage & Billing):
   when the limit is reached, "Modal stops workloads that would incur
   additional out-of-pocket charges". With a $0 spend limit the card can never
   be charged — workloads simply stop when the credits run out.

## Setup

1. Create a Modal account at modal.com/signup (GitHub or Google login).
2. Add a payment method (Settings → Usage & Billing → Manage payment details).
   Required by Modal, see above.
3. Set the spend limit to **$0** on the same page.
4. Install the CLI and log in (on your own machine):

   ```bash
   pip install modal
   modal token new
   ```

5. Create the API token the demo will use (pick a random value):

   ```bash
   modal secret create crivo-api-token CRIVO_API_TOKEN=<random-token>
   ```

6. Deploy:

   ```bash
   modal deploy crivo/ml/modal/app.py
   ```

   `modal deploy` prints the endpoint URLs. Copy the `classify` URL.

7. In the Streamlit Cloud dashboard, add to Secrets:

   ```toml
   MODAL_URL = "https://<workspace>--crivo-factual-bertimbau-classify.modal.run"
   MODAL_API_TOKEN = "<same random token>"
   ```

   The demo calls `MODAL_URL` when set, and falls back to the unified model
   (with a visible note) if the endpoint is unreachable.

## API

`POST {MODAL_URL}` with header `Authorization: Bearer <MODAL_API_TOKEN>`:

```json
{"text": "A Câmara dos Deputados aprovou..."}
```

Response:

```json
{"suspicion": 0.01, "model": "bertimbau"}
```

`suspicion` is P(fake) from the classifier, 0–1. `GET {health URL}` returns
`{"status": "ok", "model": "brenindexdev/crivo-factual-bertimbau"}`.

## Local test

The inference code path (same tokenizer call, same softmax over label 1)
was tested locally against the dedicated repo: accuracy 0.85 on the
20-item current-politics set (articles 8/8), matching the earlier
evaluation of the same weights.
