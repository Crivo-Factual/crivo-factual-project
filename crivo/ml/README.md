# Classificador de veracidade (ML)

Um classificador que estima a probabilidade de uma notícia em
português ser falsa, treinado no **Fake.Br Corpus** (Monteiro et
al., 2018, PROPOR 2018) — 7.200 notícias, 3.600 falsas + 3.600
verdadeiras, em pares alinhados sobre o mesmo fato.

## O que ele é — e o que ele não é

**É um sinal de triagem.** A suspeita (0–1) prioriza a fila: o que
parece mais falso é verificado primeiro, e o score fica registrado
no veredito e na auditoria (`run_verdicts.py --ml-model`).

**Não é um juiz.** Ele NUNCA decide um veredito. O veredito do
Crivo continua sendo decidido por regras determinísticas sobre
fontes primárias (Câmara, Senado, DOU). Um texto com suspeita 0,99
e outro com 0,01 passam pelo mesmo crivo: sem fonte primária, os
dois saem Inconclusivo. Essa separação é o ponto central do
desenho — e é o que torna o modelo publicável sem comprometer a
metodologia do portal.

## Resultados medidos (16/11/2026)

Treino: TF-IDF (unigramas + bigramas, sublinear, 50k features,
stopwords em português) + regressão logística, contra um baseline
de Naive Bayes. Split **por par** (a falsa e a verdadeira do mesmo
fato nunca caem em lados diferentes — sem isso o modelo decoraria
o evento).

| Métrica | Valor |
|---|---|
| Modelo escolhido | Regressão logística |
| Acurácia (teste, n=1440) | 0,9708 |
| F1-macro (teste) | 0,9708 |
| F1 classe falsa | 0,9710 (precisão 0,9669, recall 0,9750) |
| ROC-AUC | 0,9960 |
| CV 5-fold F1-macro | 0,9663 ± 0,0064 |
| Matriz de confusão | [[696, 24], [18, 702]] |

## Limite medido: texto curto não serve

O modelo só viu artigos completos no treino. Em manchetes e
resumos (~200 chars) ele pontua 0,91–0,98 **mesmo quando a notícia
é verdadeira** — não sabe o que fazer com texto curto. Por isso
`suspicion_score` devolve **None abaixo de 500 caracteres** em vez
de um número enganoso, e a integração só calcula a suspeita sobre
o **texto completo do artigo** (`get_item_text`), nunca sobre o
título. Em artigos completos o comportamento é o esperado:
verdadeiros do corpus pontuam 0,04–0,18; falsos, 0,69–0,93.

## Reproduzir

```bash
# 1. Baixe o corpus (não vai para o repo — 146 MB)
git clone --depth 1 https://github.com/roneysco/Fake.br-Corpus.git \
  ~/workspace/crivo/fakebr-corpus

# 2. Venv de ML (o repo é só biblioteca padrão; o ML é opcional)
python3 -m venv .venv-ml
.venv-ml/bin/pip install scikit-learn pandas

# 3. Treine (gera crivo/ml/models/model.joblib + metrics.json)
.venv-ml/bin/python scripts/train_classifier.py

# 4. Use no pipeline (score registrado, veredito inalterado)
python3 scripts/run_verdicts.py --limit 10 \
  --ml-model crivo/ml/models/model.joblib
```

Os testes de ML (`tests/test_ml.py`) pulam sozinhos quando o
scikit-learn não está instalado — o CI continua verde sem ele.
Os testes de integração (bônus de triagem, suspeita registrada
sem mudar o veredito) usam um modelo falso e rodam sempre.

## Publicação no Hugging Face

O artefato é o pipeline inteiro (vetorizador + modelo) em
`crivo/ml/models/model.joblib`, com as métricas em
`crivo/ml/models/metrics.json`. Os arquivos de publicação
(model card + demo Gradio) estão em `crivo/ml/hf/` — o modelo
sobe para o Hub com a conta do idealizador; ver
`crivo/ml/hf/README.md`.

## Citação do corpus

Monteiro R.A., Santos R.L.S., Pardo T.A.S., de Almeida T.A.,
Ruiz E.E.S., Vale O.A. (2018). *Contributions to the Study of
Fake News in Portuguese: New Corpus and Automatic Detection
Results.* PROPOR 2018, LNCS vol. 11122. Springer.
