# Publicar os modelos e a demo no Hugging Face

**Status 17/11/2026:** o repositório do modelo está PUBLICADO em
https://huggingface.co/brenindexdev/crivo-factual-fakebr
(`model_v1.joblib`, `model_v2.joblib`, `model_unified.joblib` +
model card). O Space (demo) está TRAVADO — ver a seção 3.

Os modelos treinados (`crivo/ml/models/model.joblib` v1, 2,7 MB,
`crivo/ml/models/v2/model.joblib` v2, 2,8 MB, e
`crivo/ml/models/unified/model.joblib` unificado, 4,2 MB) e as
métricas (`metrics.json` em cada pasta) estão no seu ambiente
local — o repo não versiona artefatos gerados. A publicação
precisa da conta do idealizador no Hugging Face (o token nunca
vai para o chat nem para o repo).

## 1. Conta e token

1. Crie a conta em https://huggingface.co/join (use o mesmo
   nome de usuário do GitHub, `brenindexdev`, se estiver livre).
2. Em Settings → Access Tokens, crie um token **Write**.
3. Guarde o token no cofre seguro (o mesmo fluxo usado para a
   chave do Groq) — nunca cole o token no chat.

## 2. Repositório do modelo

1. Crie o repositório `crivo-factual-fakebr` no Hub (tipo Model).
2. Suba estes arquivos:
   - `crivo/ml/models/model.joblib` → `model_v1.joblib`
   - `crivo/ml/models/v2/model.joblib` → `model_v2.joblib`
   - `crivo/ml/models/unified/model.joblib` → `model_unified.joblib`
   - `crivo/ml/hf/README.md` → `README.md` (o model card)
3. Confira a página do modelo: o card mostra métricas, uso e
   limites.

## 3. Space (demo) — TRAVADO 17/11/2026

A criação do Space `crivo-factual-demo` (SDK Gradio) foi
tentada via API e **rejeitada com 402 Payment Required**.
Política do Hub desde agosto/2026: criar um Space Gradio ou
Docker que rode código exige plano pago (PRO, US$ 9/mês).
Conta gratuita mantém até 2 Spaces Gradio em hardware ZeroGPU,
mas só com conta com mais de 30 dias e e-mail verificado — a
conta `brenindexdev` foi criada em 17/11/2026, então não se
qualifica ainda. Static Spaces continuam gratuitos, mas não
rodam código de servidor — não servem para a demo ao vivo.

Alternativas gratuitas para a demo:
- **Streamlit Community Cloud (grátis):** reescrever a demo
  em Streamlit (`app.py` vira `streamlit_app.py`, mesma lógica
  de classificação, modelos baixados do repositório do passo 2)
  e publicar a partir do GitHub. É o caminho recomendado.
- **Esperar 30 dias** e tentar o Space ZeroGPU de novo quando
  a conta se qualificar (não serve para o prazo do GenAI).
- **PRO (US$ 9/mês):** só se ele quiser pagar — não é o caso.

`crivo/ml/hf/app.py` já aponta para o repositório real
(`brenindexdev/crivo-factual-fakebr`). O Space baixa os três
modelos do repositório do passo 2 na primeira execução: o
seletor oferece o roteador (texto com 500+ caracteres → v1;
texto curto → v2) e o unificado (um só modelo, qualquer
tamanho). Teste com um artigo completo e com uma mensagem
curta.

## 4. Depois de publicar

- Adicione os links (modelo + demo) ao README do repositório
  Crivo Factual e ao LinkedIn, na seção de projetos. O link do
  modelo já existe: https://huggingface.co/brenindexdev/crivo-factual-fakebr
- O artigo técnico usa os números de `metrics.json` e o limite
  de texto curto como seção de limitações — os dois já estão
  medidos, não precisam ser re-escritos.
