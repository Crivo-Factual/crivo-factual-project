# Publicar os modelos e a demo no Hugging Face

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

## 3. Space (demo)

1. Crie um Space `crivo-factual-demo`, SDK **Gradio**.
2. Edite `crivo/ml/hf/app.py`: troque `SEU_USUARIO` em
   `HF_MODEL_REPO` pelo seu nome de usuário do Hub.
3. Suba `app.py` + `requirements.txt` para o Space.
4. O Space baixa os três modelos do repositório do passo 2 na
   primeira execução: o seletor oferece o roteador (texto com
   500+ caracteres → v1; texto curto → v2) e o unificado (um só
   modelo, qualquer tamanho). Teste com um artigo completo e com
   uma mensagem curta.

## 4. Depois de publicar

- Adicione os links (modelo + Space) ao README do repositório
  Crivo Factual e ao LinkedIn, na seção de projetos.
- O artigo técnico usa os números de `metrics.json` e o limite
  de texto curto como seção de limitações — os dois já estão
  medidos, não precisam ser re-escritos.
