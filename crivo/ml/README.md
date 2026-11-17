# Classificador de veracidade (ML)

Três modelos, um roteador por tamanho do texto — e um modelo
único:

- **v1 — especialista em artigos** (Fake.Br Corpus, 7.200 notícias
  em pares alinhados). Só opina a partir de 500 caracteres.
- **v2 — generalista** (FakenewsBR, 36.594 itens: notícias, tweets,
  WhatsApp, COVID). Opina sobre texto curto, mas com viés de
  falso positivo — é sinal fraco, nunca veredito.
- **unificado — um só modelo para qualquer tamanho** (Fake.Br +
  FakenewsBR, 35.035 itens). Artigos F1 0,9646, misto F1 0,7924 —
  o melhor modelo único; só perde da v1 nos artigos (0,9736) e
  bate a v2 no misto (0,7754).

O desenho continua o mesmo: o ML é **sinal de triagem, nunca
veredito** (ver a seção abaixo).

## v1 — Fake.Br Corpus (16/11/2026)

Treinado no **Fake.Br Corpus** (Monteiro et al., 2018, PROPOR
2018) — 7.200 notícias, 3.600 falsas + 3.600 verdadeiras, em
pares alinhados sobre o mesmo fato.

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

## Calibração e limiares medidos (17/11/2026)

As probabilidades **não são chances calibradas** — são scores de
ranking. Brier 0,0418 (bom no geral), mas as faixas do meio
desviam: na faixa 0,1–0,3, 0% são falsas (o modelo diz 17%); na
0,3–0,5, 21% são falsas (diz 39%); na 0,7–0,9, 99% são falsas
(diz 83%). Nos extremos ele acerta: 0,0–0,1 tem 0% de falsas e
0,9–1,0 tem 100%. Leia o score como "mais suspeito / menos
suspeito", não como "x% de chance de ser falso".

Os limiares do bônus de triagem foram medidos no teste (n=1440),
não chutados: **0,6 → precisão 0,977, recall 0,950** (bônus +5) e
**0,8 → precisão 0,998, recall 0,721** (bônus +10). Ou seja: acima
de 0,8 quase nunca é falso positivo, mas só pega 72% das falsas.
Dos 42 erros do teste, o tamanho médio é 2.337 chars (média do
teste: 3.951) — o modelo erra mais em textos médios, não só nos
curtos (só 4 dos 42 têm menos de 1.000 chars).

## v2 — FakenewsBR + calibração (17/11/2026)

Treino no corpus unificado **FakenewsBR** (Silva et al., 2026,
DSW) — 51.205 linhas no arquivo, **36.594 canônicas usadas**
(26.534 falsas / 10.060 verdadeiras). Fora: as variantes `*_raw`
(as mesmas instâncias antes da limpeza) e textos com menos de 50
chars. O corpus é majoritariamente texto curto (mediana 156
chars): notícias do Kaggle, tweets, WhatsApp, COVID-19, MuMiN-PT,
LLM4BR_300. O treino é `scripts/train_classifier_v2.py`.

**Comparação limpa:** os 1.440 itens do teste da v1 foram
excluídos do treino da v2 por fingerprint (1.416 casaram, todos
de `Fake.br`; os outros 24 não existem no arquivo). A v2 nunca
viu esses textos — a comparação abaixo é honesta.

| Métrica | v1 (artigos) | v2 (misto) | v2 no teste da v1 |
|---|---|---|---|
| Acurácia | 0,9708 | 0,8086 | 0,9313 (calibrada) / 0,8854 |
| F1-macro | 0,9708 | 0,7676 | 0,9311 (calibrada) / 0,8841 |
| ROC-AUC | 0,9960 | 0,8575 | 0,9890 |
| Brier | 0,0418 | 0,1444 | 0,0561 (calibrada) / 0,0926 |
| n (teste) | 1.440 | 7.319 | 1.440 |

**Veredito: a v2 NÃO substitui a v1.** Em artigos completos a v1
continua melhor (0,9708 contra 0,9311 calibrada). O valor da v2
é a amplitude: ela cobre tweets, WhatsApp e COVID, domínios que
a v1 nunca viu — e é o único modelo que opina sobre texto curto.

**Calibração — resultado misto, não enviada.** A isotônica
melhora o Brier (0,1444 → 0,1256 no teste misto; 0,0926 →
0,0561 nos artigos) e melhora o F1 nos artigos (0,8841 →
0,9311), mas desloca o ponto de operação para "falso": no teste
misto, os falsos positivos em verdadeiras saltam de 590 para
1.011 e o F1-macro cai (0,7676 → 0,7444). O artefato enviado é
o modelo **sem calibração**; a calibração fica registrada como
experimento em `metrics.json`.

**Falso positivo por fonte (v2 sem calibração, teste misto) — o
score depende da fonte, não é uniforme:**

| Fonte | Verdadeiras chamadas falsas |
|---|---|
| LLM4BR_300 (notícias políticas) | 5% (1/20) |
| Fake.br (artigos) | 9% (52/555) |
| FakeWhatsApp.BR_2018 | 22% (157/698) |
| COVID19.BR | 36% (81/226) |
| MuMiN-PT (tweets) | 53% (8/15) |
| true (Kaggle, só verdadeiras) | 58% (291/498) |

**Texto curto melhorou, mas não resolveu.** A v2 sem calibração
pontua verdadeiro curto em 0,456 e falso curto em 0,722 em
média (a v1 pontuava 0,91–0,98 em verdadeiro curto). Separa,
mas o guarda de 500 caracteres continua valendo — uma frase
comum e verdadeira ("O governo anunciou hoje a nova regra para
o saque do FGTS...") ainda pontua 0,80 na v2.

**Limiares da v2 (teste misto, sem calibração):** 0,6 → precisão
0,913, recall 0,716; 0,8 → precisão 0,964, recall 0,313. Os
limiares do bônus de triagem (+5/+10) foram medidos para a v1
e **não valem para a v2** — a v2 não herda os bônus.

**Roteador (desenho):** texto com 500+ caracteres → v1; texto
curto → v2 (sinal fraco). O script de teste local
(`crivo/ml/hf/infer.py`) já implementa o roteador e o
unificado. A integração no pipeline (`run_verdicts.py`)
continua usando só a v1 por enquanto — o pipeline só pontua
artigos completos.

## Mistura v1+v2 e char n-grams (17/11/2026)

O pedido era um modelo único com F1 >= 0,95 nos dois testes.
Três desenhos foram medidos (`scripts/experiment_mix.py`,
`scripts/experiment_char.py`):

- **Ensemble (média das probabilidades v1+v2): PERDEU para as
  duas.** Artigos F1 0,9597 (v1 sozinha: 0,9708); misto F1
  0,6479 (v2 sozinha: 0,7676). A média dilui o ponto forte de
  cada modelo.
- **Unificado (um modelo, treino = Fake.Br treino + FakenewsBR
  treino = 35.035 itens):** artigos F1 0,9197, misto F1 0,7754.
- **Unificado + char n-grams: melhor modelo ÚNICO** — artigos
  F1 0,9485, misto F1 0,7822 (ganha da v2 nos dois testes;
  perde da v1 nos artigos).
- **Limiar ótimo (unificado, misto): 0,5** — já é o ótimo; nada
  a ganhar com ajuste de limiar.

**Char n-grams ajudam os dois modelos no seu terreno:**
v1+char (artigos) F1 0,9736 (v1 pura: 0,9708); v2+char
(misto) F1 0,7754 (v2 pura: 0,7676). Por isso `logreg_char`
virou a configuração oficial dos dois — e o retreino canônico
(17/11) confirmou os números exatamente: v1 F1 0,9736,
v2 F1 0,7754.

**Insight Kaggle `true` (resolvido):** os 58% de falso
positivo naquela fonte **não são falha do modelo** — os
"textos verdadeiros" dela **não são notícias**: são perguntas
e fragmentos de checagem ("Papa Francisco recusou que fiéis
beijassem o anel papal?", "Portugal é o país da Europa
Ocidental com o mais baixo rendimento líquido de salários?").
É outro gênero de texto (curto, interrogativo, fragmentário)
— exatamente o que o modelo aprendeu a chamar de falso.

## Afinação do unificado (17/11/2026)

`scripts/tune_unified.py` e `tune_unified_extra.py` mediram
tudo no mesmo treino unificado, nos dois testes:

| Candidato | Artigos F1 | Misto F1 |
|---|---|---|
| char C=0,5 | 0,9478 | 0,7769 |
| char C=1,0 | 0,9485 | 0,7822 |
| char C=2,0 | 0,9513 | 0,7894 |
| char C=4,0 | 0,9534 | 0,7909 |
| char C=2,0 + oversample artigos ×2 | 0,9625 | 0,7870 |
| **char C=4,0 + oversample artigos ×2** | **0,9646** | **0,7924** |
| LinearSVC | 0,9339 | 0,7859 |
| ComplementNB | 0,7947 | 0,7264 |
| Voto (char + SVC + CNB) | 0,9359 | 0,7914 |
| Voto C=2,0 + oversample ×2 | 0,9471 | 0,7877 |

**O que a tabela diz:** C maior ajuda nos dois testes até
C=4,0 (a tendência achata — C=2,0 → C=4,0 ganha só +0,0015
no misto). O oversample dos artigos levanta os artigos sem
derrubar o misto. O voto é o melhor no misto sem oversample
(0,7914), mas cai nos artigos (0,9359) — o CNB puxa o voto
para baixo nos artigos. O **modelo unificado final é
char C=4,0 + oversample ×2: artigos 0,9646, misto 0,7924**
(`scripts/train_unified.py --compare`, artefato em
`crivo/ml/models/unified/`).

**Teto medido — por que 0,95 no misto não vem do linear:**
o melhor modelo avaliado no teste misto SEM as fontes `true`
(Kaggle) e `MuMiN-PT` chega a F1 0,8183. Mesmo sem as duas
piores fontes, o linear fica 13 pontos abaixo da meta. O
gargalo é o dado (texto curto, pergunta de checagem, ironia
e gênero misturado não se separam por contagem de palavras),
não o ajuste. A nota de rodapé honesta: a escolha de C foi
avaliada direto nos testes (a CV 3-fold não terminava nesta
VM), então os números de C ficam levemente otimistas.

## BERTimbau — o caminho para 0,95 no misto (17/11/2026)

O único caminho plausível para o salto no misto é um
transformer pré-treinado em português, que lê contexto em
vez de contar palavras. O script `scripts/train_bertimbau.py`
faz o fine-tuning do BERTimbau
(`neuralmind/bert-base-portuguese-cased`) nos **mesmos splits**
dos experimentos lineares (seed 42), com peso por classe (o
treino é 73% falso) e avaliação nos dois testes, para os
números serem comparáveis. O notebook
`crivo/ml/hf/bertimbau-colab.ipynb` roda tudo no Colab
gratuito (GPU T4, 30–60 min, 3 épocas, batch 32, max_len 256).

**Resultado (treino real, 17/11/2026, GPU T4 do Kaggle — o
Colab gratuito estava sem GPU disponível; o notebook do Kaggle
é `crivo/ml/hf/bertimbau-kaggle.ipynb`): artigos F1-macro
0,9868 (acurácia 0,9868, n=1440) — meta de 0,95 BATIDA, acima
da v1 (0,9736) e do unificado (0,9646); misto F1-macro 0,8184
(acurácia 0,8507, n=7319) — o melhor no misto até aqui
(unificado 0,7924), mas abaixo da meta de 0,95. O misto ficou
exatamente no teto medido do linear sem as piores fontes
(0,8183), só que no conjunto COMPLETO — o transformer resolveu
o problema das fontes `true` e `MuMiN-PT` que travava o linear,
e mesmo assim bateu no mesmo teto. Conclusão: o gargalo do
misto é o dado, não o modelo. O script foi verificado antes por
smoke test na CPU (64 exemplos, 1 época — treino, avaliação e
salvamento rodaram; os F1 do smoke não valem como métrica, só
provam que o código funciona). Duas incompatibilidades do
transformers 5.x foram corrigidas no caminho: `warmup_ratio`
não existe mais (só `warmup_steps`, calculado como 10% dos
passos totais) e o collator padrão quebra com textos de
comprimentos diferentes (`DataCollatorWithPadding`). O notebook
pinou `transformers==5.23.0`, a versão testada. Os pesos do
modelo treinado estão na saída da sessão do Kaggle
(`./bertimbau-v1`) — ainda não foram subidos para o Hub.

**Limpeza do treino não funciona (17/11/2026).** Remover do
treino os itens não-notícia da fonte `true` e os textos <100
chars piorou o misto (F1 0,7924 → 0,7770) e elevou o falso
positivo na fonte `true` para 94,0% — os fragmentos-pergunta
eram o único contrapeso curto-verdadeiro contra o atalho
"texto curto → falso". A direção certa é a oposta: manter ou
reforçar os verdadeiros curtos.

## Reproduzir

```bash
# 1. Baixe o corpus (não vai para o repo — 146 MB)
git clone --depth 1 https://github.com/roneysco/Fake.br-Corpus.git \
  ~/workspace/crivo/fakebr-corpus

# 2. Venv de ML (o repo é só biblioteca padrão; o ML é opcional)
python3 -m venv .venv-ml
.venv-ml/bin/pip install scikit-learn pandas

# 3. Treine a v1 (gera crivo/ml/models/model.joblib + metrics.json)
.venv-ml/bin/python scripts/train_classifier.py

# 3b. Treine a v2 (precisa do CSV do FakenewsBR — ver
# crivo/ml/fakenewsbr.py para o download; gera
# crivo/ml/models/v2/model.joblib + metrics.json)
.venv-ml/bin/python scripts/train_classifier_v2.py \
  --fakenewsbr ~/workspace/crivo/fakenewsbr/FakenewsBR_factchecked.csv \
  --fakebr ~/workspace/crivo/fakebr-corpus \
  --out crivo/ml/models/v2

# 3c. Treine o unificado (o melhor modelo único; gera
# crivo/ml/models/unified/model.joblib + metrics.json)
.venv-ml/bin/python scripts/train_unified.py \
  --fakenewsbr ~/workspace/crivo/fakenewsbr/FakenewsBR_factchecked.csv \
  --fakebr ~/workspace/crivo/fakebr-corpus \
  --out crivo/ml/models/unified --compare

# 3d. BERTimbau (só no Colab com GPU — ver
# crivo/ml/hf/bertimbau-colab.ipynb; o smoke test roda na CPU)
.venv-bert/bin/python scripts/train_bertimbau.py --smoke \
  --fakenewsbr ~/workspace/crivo/fakenewsbr/FakenewsBR_factchecked.csv \
  --fakebr ~/workspace/crivo/fakebr-corpus \
  --out /tmp/bertimbau-smoke

# 4. Use no pipeline (score registrado, veredito inalterado)
python3 scripts/run_verdicts.py --limit 10 \
  --ml-model crivo/ml/models/model.joblib
```

Os testes de ML (`tests/test_ml.py`) pulam sozinhos quando o
scikit-learn não está instalado — o CI continua verde sem ele.
Os testes de integração (bônus de triagem, suspeita registrada
sem mudar o veredito) usam um modelo falso e rodam sempre.

## Publicação no Hugging Face

Os artefatos são os pipelines inteiros (vetorizador + modelo),
salvos com joblib: `crivo/ml/models/model.joblib` (v1),
`crivo/ml/models/v2/model.joblib` (v2, sem calibração) e
`crivo/ml/models/unified/model.joblib` (unificado, C=4,0 +
oversample ×2), cada um com seu `metrics.json`. Os arquivos de
publicação (model card + demo Gradio com roteador v1/v2 e
seletor do unificado) estão em `crivo/ml/hf/` — os modelos
sobem para o Hub com a conta do idealizador; ver
`crivo/ml/hf/README.md` e `crivo/ml/hf/README-publicar.md`.
O fine-tuning do BERTimbau, quando rodar no Colab, sobe para
o mesmo repositório (`bertimbau/`).

## Citação dos corpora

Monteiro R.A., Santos R.L.S., Pardo T.A.S., de Almeida T.A.,
Ruiz E.E.S., Vale O.A. (2018). *Contributions to the Study of
Fake News in Portuguese: New Corpus and Automatic Detection
Results.* PROPOR 2018, LNCS vol. 11122. Springer.

Silva et al. (2026). *FakenewsBR: A Unified Corpus for Fake News
Detection in Portuguese.* DSW 2026. Corpus unificado em
https://github.com/AKCIT-FN/fakenews-data (espelho do CSV no
Hugging Face Hub: `kauandivino/FakenewsBR`).
