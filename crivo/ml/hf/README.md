---
language: pt
license: mit
library_name: sklearn
tags:
- fake-news
- portuguese
- text-classification
- fact-checking
---

# Crivo Factual — Classificadores de veracidade (v1 + v2 + unificado)

Três classificadores que estimam a probabilidade de um texto em
português brasileiro ser falso:

- **v1 — especialista em artigos.** Treinada no
  [Fake.Br Corpus](https://github.com/roneysco/Fake.br-Corpus)
  (Monteiro et al., 2018) — 7.200 notícias, 3.600 falsas + 3.600
  verdadeiras, em pares alinhados sobre o mesmo fato. Só opina a
  partir de 500 caracteres.
- **v2 — generalista.** Treinada no
  [FakenewsBR](https://github.com/AKCIT-FN/fakenews-data) (Silva
  et al., 2026) — 36.594 itens canônicos: notícias, tweets,
  WhatsApp, COVID-19. Opina sobre texto curto, mas com viés de
  falso positivo.
- **unificado — um só modelo para qualquer tamanho.** Treinado
  em Fake.Br + FakenewsBR (35.035 itens). Artigos F1 0,9646,
  misto F1 0,7924 — o melhor modelo único do projeto.

Modelo: TF-IDF (unigramas + bigramas, sublinear, 50k features,
stopwords em português) + TF-IDF de char n-grams (3–5, 30k) +
regressão logística (C=4,0 no unificado; C=1,0 nas v1/v2). O
artefato é o pipeline inteiro (vetorizador + modelo), salvo com
joblib. `model_v1.joblib`, `model_v2.joblib` e
`model_unified.joblib` são os três artefatos; `model.joblib`
(v1) é mantido por compatibilidade.

## Resultados medidos

| Métrica | v1 (artigos, n=1440) | v2 (misto, n=7319) | v2 nos artigos da v1 | unificado (artigos) | unificado (misto) | BERTimbau (artigos) | BERTimbau (misto) |
|---|---|---|---|---|---|---|---|
| Acurácia | 0,9708 | 0,8086 | 0,8854 | 0,9646 | 0,8386 | 0,9868 | 0,8507 |
| F1-macro | 0,9708 | 0,7676 | 0,8841 | 0,9646 | 0,7924 | 0,9868 | 0,8184 |
| ROC-AUC | 0,9960 | 0,8575 | 0,9888 | — | — | — | — |
| Brier | 0,0418 | 0,1444 | 0,0926 | — | — | — | — |

Treino real do BERTimbau em 17/11/2026, GPU T4 do Kaggle
(o Colab gratuito estava sem GPU disponível). Mesmos splits
(seed 42) e mesmos testes dos lineares — os números são
comparáveis. Os pesos do modelo treinado estão na saída da
sessão do Kaggle (`./bertimbau-v1`), ainda não subidos aqui.

A comparação v2 × v1 nos artigos é limpa: os 1.440 itens do
teste da v1 foram excluídos do treino da v2 por fingerprint.
O unificado usa os mesmos splits (seed 42) e os mesmos testes.

## Uso (roteador)

```python
import joblib
v1 = joblib.load("model_v1.joblib")
v2 = joblib.load("model_v2.joblib")

def suspicion(text):
    if len(text.strip()) >= 500:
        return float(v1.predict_proba([text])[0][1]), "v1"
    return float(v2.predict_proba([text])[0][1]), "v2"
```

## Uso (unificado — um só modelo, qualquer tamanho)

```python
import joblib
uni = joblib.load("model_unified.joblib")

def suspicion(text):
    return float(uni.predict_proba([text])[0][1])
```

## Limites — leia antes de usar

- **A v2 não substitui a v1.** Em artigos completos a v1 continua
  melhor (F1 0,9708 contra 0,8841). A v2 vale pela amplitude
  (tweets, WhatsApp, COVID) e pelo texto curto.
- **O BERTimbau é o melhor modelo nos dois testes, mas o misto
  continua abaixo de 0,95.** Artigos F1 0,9868 (meta batida),
  misto F1 0,8184. O misto ficou exatamente no teto medido do
  linear sem as piores fontes (0,8183), no conjunto completo —
  o gargalo é o dado, não o modelo. Ver `crivo/ml/README.md`.
- **Falso positivo por fonte (v2).** O score depende da fonte:
  5% em notícias políticas, 9% em artigos do Fake.Br, 22% em
  WhatsApp, 36% em COVID, 53% em tweets do MuMiN, 58% nas
  notícias verdadeiras do Kaggle. Leia como sinal fraco, não
  como probabilidade.
- **Texto curto (v2).** Verdadeiro curto pontua 0,46 e falso
  curto 0,72 em média — separa, mas uma frase comum e verdadeira
  ainda pode pontuar 0,80. O guarda de 500 caracteres da v1
  continua valendo para artigos.
- **Calibração não enviada.** A calibração isotônica melhora o
  Brier, mas desloca o ponto de operação para "falso" (falsos
  positivos de 590 para 1.011 no teste misto). O artefato é o
  modelo sem calibração.
- **É um sinal de triagem, não um veredito.** No projeto Crivo
  Factual, esse score só prioriza a fila de verificação. O
  veredito continua sendo decidido por regras determinísticas
  sobre fontes primárias (Câmara, Senado, Diário Oficial).
  Nenhum número deste modelo declara uma notícia falsa.
- **Viés dos corpora.** Notícias falsas têm marcas de estilo
  fortes (sensacionalismo, clickbait); o modelo aprende estilo
  tanto quanto conteúdo. O Fake.Br é de 2016–2018; o FakenewsBR
  vai até 2022.

## Citação dos corpora

Monteiro R.A., Santos R.L.S., Pardo T.A.S., de Almeida T.A.,
Ruiz E.E.S., Vale O.A. (2018). *Contributions to the Study of
Fake News in Portuguese: New Corpus and Automatic Detection
Results.* PROPOR 2018, LNCS vol. 11122. Springer.

Silva et al. (2026). *FakenewsBR: A Unified Corpus for Fake News
Detection in Portuguese.* DSW 2026.
https://github.com/AKCIT-FN/fakenews-data
