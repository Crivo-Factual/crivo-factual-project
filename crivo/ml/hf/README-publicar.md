# Publishing the models and the demo on Hugging Face

**Status 17/11/2026:** the model repository is PUBLISHED at
https://huggingface.co/brenindexdev/crivo-factual-fakebr
(`model_v1.joblib`, `model_v2.joblib`, `model_unified.joblib` +
model card). The Space (demo) is BLOCKED — see section 3.

The trained models (`crivo/ml/models/model.joblib` v1, 2.7 MB,
`crivo/ml/models/v2/model.joblib` v2, 2.8 MB, and
`crivo/ml/models/unified/model.joblib` unified, 4.2 MB) and the
metrics (`metrics.json` in each folder) live in your local
environment — the repo does not version generated artifacts.
Publishing needs the creator's Hugging Face account (the token
never goes to the chat or the repo).

## 1. Account and token

1. Create the account at https://huggingface.co/join (use the
   same username as on GitHub, `brenindexdev`, if it is free).
2. In Settings → Access Tokens, create a **Write** token.
3. Store the token in the secure vault (the same flow used for
   the Groq key) — never paste the token in the chat.

## 2. Model repository

1. Create the repository `crivo-factual-fakebr` on the Hub (Model
   type).
2. Upload these files:
   - `crivo/ml/models/model.joblib` → `model_v1.joblib`
   - `crivo/ml/models/v2/model.joblib` → `model_v2.joblib`
   - `crivo/ml/models/unified/model.joblib` → `model_unified.joblib`
   - `crivo/ml/hf/README.md` → `README.md` (the model card)
3. Check the model page: the card shows metrics, usage and
   limits.

## 3. Space (demo) — BLOCKED 17/11/2026

Creating the Space `crivo-factual-demo` (Gradio SDK) was
attempted via API and **rejected with 402 Payment Required**.
Hub policy since August/2026: creating a Gradio or Docker Space
that runs code requires a paid plan (PRO, US$ 9/month). A free
account keeps up to 2 Gradio Spaces on ZeroGPU hardware, but
only accounts in good standing — the `brenindexdev` account
(created 2025-06-09) got "Your account is not eligible to host
ZeroGPU Spaces for free" on the second attempt. Static Spaces
are still free, but they do not run server code — they do not
work for the live demo.

Free alternatives for the demo:
- **Streamlit Community Cloud (free) — DONE 17/11/2026:**
  the demo was rewritten in Streamlit
  (`crivo/ml/hf/streamlit_app.py`, same classification logic,
  models downloaded from the repository in step 2) on the
  `feature/demo-streamlit` branch. To deploy: open
  share.streamlit.io, sign in with GitHub, "Create app",
  repository `Crivo-Factual/crivo-factual-project`, branch
  `main` (after the PR is merged), main file path
  `crivo/ml/hf/streamlit_app.py`. The repository is private
  under the `Crivo-Factual` organization, so Streamlit needs
  access to it: install the Streamlit GitHub App on the
  organization (Settings → GitHub Apps) or deploy from a fork.
  BERTimbau is intentionally not loaded in the demo: the free
  tier gives the app 1 GB of RAM, and torch + a 440 MB BERT
  model does not fit in it.
- **Wait 30 days** and try the ZeroGPU Space again once the
  account qualifies (does not fit the GenAI deadline).
- **PRO (US$ 9/month):** only if he wants to pay — not the case.

**Watch out when publishing BERTimbau from Kaggle:** the
publish cell must run **in the same session as the training**.
If the Kaggle session restarts after training, the
`./bertimbau-v1` folder disappears from the new session's disk
(the sidebar shows the saved outputs of the previous session,
not the live disk) and `upload_folder` fails with `ValueError:
... is not a directory`. In that case, either train again in
the current session and publish right after, or download the
folder from the sidebar download icon and upload the files
through the Hub web UI, inside the `bertimbau/` folder.

`crivo/ml/hf/app.py` already points to the real repository
(`brenindexdev/crivo-factual-fakebr`). The Space downloads the
three models from the repository in step 2 on first run: the
selector offers the router (text with 500+ characters → v1;
short text → v2) and the unified model (one model, any length).
Test with a full article and with a short message.

## 4. After publishing

- Add the links (model + demo) to the README of the Crivo
  Factual repository and to LinkedIn, in the projects section.
  The model link already exists:
  https://huggingface.co/brenindexdev/crivo-factual-fakebr
- The technical article uses the numbers from `metrics.json`
  and the short-text limit as a limitations section — both are
  already measured, they do not need to be rewritten.
