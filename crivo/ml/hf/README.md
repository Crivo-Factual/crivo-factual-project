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

# Crivo Factual — Classificador de veracidade (Fake.Br)

Classificador que estima a probabilidade de uma notícia em
português brasileiro ser falsa. Treinado no
[Fake.Br Corpus](https://github.com/roneysco/Fake.br-Corpus)
(Monteiro et al., 2018) — 7.200 notícias, 3.600 falsas + 3.600
verdadeiras, em pares alinhados sobre o mesmo fato.

Modelo: TF-IDF (unigramas + bigramas, sublinear, 50k features,
stopwords em português) + regressão logística. O artefato é o
pipeline inteiro (vetorizador + modelo), salvo com joblib.

## Resultados medidos

Split **por par** (a falsa e a verdadeira do mesmo fato nunca caem
em lados diferentes do split) com seed 42, teste n=1440:

| Métrica | Valor |
|---|---|
| Acurácia | 0,9708 |
| F1-macro | 0,9708 |
| F1 classe falsa | 0,9710 (precisão 0,9669, recall 0,9750) |
| ROC-AUC | 0,9960 |
| CV 5-fold F1-macro | 0,9663 ± 0,0064 |

## Uso

```python
import joblib
pipe = joblib.load("model.joblib")
proba_falsa = pipe.predict_proba(["Cole o texto da notícia aqui."])[0][1]
```

## Limites — leia antes de usar

- **Texto curto não serve.** O modelo só viu artigos completos no
  treino. Em manchetes e resumos (~200 caracteres) ele pontua
  0,91–0,98 mesmo quando a notícia é verdadeira. Use apenas com
  artigos completos (500+ caracteres); abaixo disso, não opine.
- **Corpus de 2016–2018.** O vocabulário e os temas são dessa época;
  notícias de hoje podem trazer palavras que o modelo nunca viu.
- **É um sinal de triagem, não um veredito.** No projeto Crivo
  Factual, esse score só prioriza a fila de verificação. O veredito
  continua sendo decidido por regras determinísticas sobre fontes
  primárias (Câmara, Senado, Diário Oficial). Nenhum número deste
  modelo declara uma notícia falsa.
- **Viés do corpus.** Notícias falsas do Fake.Br têm marcas de
  estilo fortes (sensacionalismo, clickbait); o modelo aprende
  estilo tanto quanto conteúdo.

## Citação do corpus

Monteiro R.A., Santos R.L.S., Pardo T.A.S., de Almeida T.A.,
Ruiz E.E.S., Vale O.A. (2018). *Contributions to the Study of
Fake News in Portuguese: New Corpus and Automatic Detection
Results.* PROPOR 2018, LNCS vol. 11122. Springer.
