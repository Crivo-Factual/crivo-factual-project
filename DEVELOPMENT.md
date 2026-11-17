# Desenvolvimento — Crivo Factual (esqueleto M1)

Esqueleto executável do MVP, arquitetura free-first: só biblioteca padrão
do Python, sem chaves de API e sem serviços pagos.

## Rodar os testes

```bash
python3 -m unittest discover -s tests -t . -v
```

## Rodar a demonstração

```bash
python3 scripts/run_demo.py
```

A demonstração lê `data/examples.json` (3 análises documentadas),
calcula os vereditos com o motor determinístico, grava no banco SQLite
(`crivo.db`) e gera páginas estáticas em `site/` (ignorado pelo git).

## Integração contínua

A cada push e pull request na `main`, o GitHub Actions
(`.github/workflows/ci.yml`) roda os testes e a demonstração. O status
aparece na aba Actions do repositório.

## Estrutura

```text
crivo/
  config.py            # caminhos e variáveis de ambiente
  factbank/            # schema SQL + acesso ao SQLite + fila
  pipeline/
    collectors.py      # RSS e dados abertos (sem chave)
    triage.py          # score determinístico + verificabilidade
    extraction.py      # extração por regras
    llm.py             # extração por LLM free tier (só extrai)
    evidence.py        # evidências do banco de fatos (reciclados)
    verdict.py         # motor de veredito: índice, veto, trava do centro
    verdict_pipeline.py # fila -> extração -> evidências -> veredito
    publish.py         # gerador de páginas estáticas (ficha)
scripts/run_demo.py       # pipeline de ponta a ponta sobre exemplos
scripts/run_collectors.py # coleta ao vivo -> fila
scripts/run_verdicts.py   # fila -> vereditos -> páginas
data/examples.json        # 3 análises documentadas (Bolsa Família, cortes, 6x1)
data/sources.json         # fontes verificadas ao vivo
tests/                    # testes por módulo (veredito, fila, triagem, LLM...)
```

O endpoint de matérias em tramitação do Senado devolve milhares de
itens, incluindo alguns de décadas atrás; o coletor ordena por data de
apresentação e o teto de 50 por fonte fica com os mais recentes. Itens
antigos sem palavra-chave nem recência ficam no fim da fila pelo score.
Registros sem nenhum conteúdo (só o identificador, sem ementa) são
descartados pela triagem — não há o que verificar neles.

Pendentes de verificação: IBGE (instável a partir desta VM, retestar),
Agência Brasil e Câmara por RSS (URLs testadas retornam 404), TSE e
DOU (sem endpoint público verificado).

## Coleta (M2)

Fontes registradas em `data/sources.json`, verificadas ao vivo em
12/11/2026 (G1, Senado Notícias e Poder360 por RSS; proposições da
Câmara e matérias em tramitação do Senado por dados abertos). Nenhuma
exige chave. **O g1 usa o feed só de política**
(`g1.globo.com/rss/g1/politica/`): o feed geral entregava notícia
local e de crime, sem fonte primária possível — a rodada de notícias
de 12/11 foi 10 de 10 inconclusivos. Com o feed de política, a
rodada seguinte foi 6 de 10 com prova.

```bash
python3 scripts/run_collectors.py            # uma passada
python3 scripts/run_collectors.py --loop 900 # repete a cada 15 min
```

A coleta alimenta a fila persistente (`queue` no SQLite): cada item
recebe score de triagem e só o verificável entra — referência a
proposição ou palavra-chave política no título (corrigido em
12/11/2026; antes, ter link bastava, e número sozinho também
bastava — os dois deixavam entrar notícia de crime e local, "roubou
R$ 12 mil", "70% de desconto"). Prioridade: notícia com
referência (40) > notícia política (10 por palavra-chave no título)
> listagem com ementa (15) > ref solta (5), mais bônus de recência.
Listagens cruas de proposições ficam no fim da fila. Duplicatas são
descartadas por hash de conteúdo. Falha de uma fonte não derruba as
demais. A fila tem teto de 500 pendentes (backpressure) e retry com
backoff exponencial (1, 2, 4, 8 e 16 minutos, teto de 1h; após 5
tentativas o item fica `failed`).

## Vereditos (M3)

O pipeline consome a fila e publica análises:

```bash
python3 scripts/run_verdicts.py --limit 10   # só regras
python3 scripts/run_verdicts.py --limit 10 --llm  # + Groq free tier
python3 scripts/run_verdicts.py --limit 10 --loop 900  # repete a cada 15 min
```

A extração por LLM usa o Groq free tier (sem cartão): copie
`.env.example` para `.env` com `GROQ_API_KEY` (o modelo vem de
`GROQ_MODEL`, padrão `openai/gpt-oss-20b` — o antigo padrão
`llama-3.1-8b-instant` foi removido do catálogo da Groq em 12/11/2026
e devolve 404 `model_not_found`). Alternativa sem arquivo:
guarde a chave no Secure Vault (conexão `custom.groq`) e o
`run_verdicts.py --llm` usa o cofre quando não há `GROQ_API_KEY` no
ambiente (`via_vault=True` em `crivo/pipeline/llm.py`). O modelo só
extrai e localiza alegações; o veredito continua determinístico. Sem
chave, o pipeline segue só com regras e avisa.

Extração corrigida em 12/11/2026 (sonda de cobertura, #47): o resumo
de RSS traz HTML, e o padrão de citação casava atributos (`src=`) —
URLs de imagem viravam "alegação" (12% do banco). `clean_text()` em
`crivo/pipeline/extraction.py` tira as tags antes de extrair (regras
e LLM) e a saída do LLM é filtrada (sem URL/HTML). O prompt exige
alegações autocontidas na língua do texto (antes o modelo traduzia
para o inglês, o que quebrava a confirmação por contenção na ementa)
e, quando o texto menciona uma proposição, a sigla, o número e o ano
na alegação. Medido na rodada pós-correção: 0 alegações lixo e 0 em
inglês; o teste dirigido (EMC 1/2026) extraiu 3 alegações em pt-BR
com a referência e o veredito foi Predominantemente verdadeiro (75%).

Evidências nesta versão vêm do próprio banco de fatos: uma alegação
igual a outra já verificada (mesmo texto, ignorando caixa, acentos e
pontuação) herda o status anterior, com link para a análise original
— é a detecção de boato reciclado. Busca de fontes primárias externas
ao vivo ainda não existe: sem prova, a alegação fica sem evidência e
a trava do centro segura o veredito em Inconclusivo. Por isso, itens
frescos da fila viram maioria Inconclusivo até as fontes de evidência
crescerem — o motor nunca inventa prova. Cada novo veredito da mesma
publicação incrementa a versão (histórico em `verdicts`).

## Busca de evidências primárias ao vivo (#47)

Alegações sobre proposições são conferidas nas APIs de dados abertos
da Câmara e do Senado (gratuitas, sem chave), em
`crivo/pipeline/evidence_search.py`:

```bash
python3 scripts/run_verdicts.py --limit 10   # busca ligada (padrão)
python3 scripts/run_verdicts.py --limit 10 --no-evidence  # só banco de fatos
```

Regras conservadoras: status só decide quando a situação oficial
mapeia com clareza; ementa confirma por contenção do texto na ementa
oficial; "não encontrada" só contradiz com status federal nomeado;
qualquer erro de rede vira sem_evidencia, nunca quebra o pipeline.
A extração ordena a proposição como primeira candidata (a mais
verificável) — antes, um número solto ("50%") virava a central e a
trava segurava o veredito mesmo com a proposição confirmada.

Medido ao vivo em 12/11/2026: cobertura de ~10% dos itens (4/40 na
sonda); 3 Verdadeiros com prova primária nas duas primeiras rodadas
de 10 (8% dos vereditos do dia). O aceite da issue (<50%
inconclusivos, prova como maioria) NÃO foi atingido — a maioria dos
itens da fila não traz proposição nem alegação extraível.

Sonda de cobertura completa em `docs/cobertura-fontes-2026-11-12.md`
(48 itens / 208 alegações): DOU, indicadores, votações e TSE cobrem
0 — o problema é a alegação chegar sem a informação que a fonte
precisa, não a falta de fontes. Desambiguação corrigida em 12/11/2026:
**EMC, PAR e SBT não são identificadores únicos** — são numerados
por proposição (132 registros para o mesmo "EMC 1/2026"); o cliente
agora pagina a consulta (`itens=100`, até 3 páginas) e testa a
ementa de cada registro retornado (`search_all`, `Searcher`
trabalha com a lista). Status de tipo ambíguo só vale do registro
cuja ementa a alegação cita; sem ementa que case, o status não é
atribuível. Detalhe: o artigo que acompanhava a referência ("O PL
... institui") é tirado antes da contenção — sem isso, a alegação
verbatim não casa com a ementa. Medido no teste dirigido (EMC
1/2026, q271): veredito foi de Predominantemente verdadeiro (75%)
para **Verdadeiro (91,7%)**, 3 de 4 alegações confirmadas na ementa
do registro exato; a 4ª é paráfrase e fica sem evidência, como manda
a regra conservadora.

O pipeline busca o texto completo do artigo na hora do veredito
(`crivo/pipeline/article.py`, 12/11/2026): só para fontes de notícia
com link; falha de rede volta para título+resumo. A extração usa
HTMLParser, não regex — o g1 embute um JSON enorme num atributo
data-props e o JSON contém `>` dentro de strings, o que despejava o
JSON como texto (caso real q294: alegações "recommendationSummary",
"cropOptions", UUIDs). Widgets de cotação são ignorados (o ticker
virava alegação de número solto).

O DOU entrou em 12/11/2026 (`crivo/pipeline/dou.py` + busca em
`evidence_search.py`): a busca web do portal, com a frase exata
entre aspas e ordenação por relevância, devolve o próprio ato em
primeiro. O portal exige cabeçalho Accept de navegador (403 sem
ele). Só vale para alegação sem ref de proposição — um ato citado
dentro de outra alegação não prova a alegação. Status que o ato
implica: Lei sancionada/aprovada, EC promulgada/aprovada; outro
status não confirma nem contradiz. Ato não encontrado + status
federal -> contraditada (mesma regra das proposições). A extração
por regras também encontra o ato (`extraction.ACT`, mesmo padrão
que `evidence_search.ACT_RE`): "Lei nº 14.973, de 2024" vira
candidato kind "ato" e pode ser a central.

Triagem corrigida em 12/11/2026: 213 pendentes → 107 mantidos
(re-score) e 106 descartados (g1 72, poder360 8, camara_proposicoes
26 — estes últimos com ano 0 ou tipo fora do padrão, ref quebrada).
Rodada pós-triagem (10 itens): **9 com prova** (6 Verdadeiro, 3
Predominantemente verdadeiro), 1 Inconclusivo. Ressalva honesta: 5
dos 9 são listagens de ref solta, que verificam por existência
(100% trivial). No dia: 66 vereditos, 51 Inconclusivo (77%), 5
Predominantemente verdadeiro, 10 Verdadeiro. Aceite segue não
atingido no dia, mas a rodada pós-triagem é 90% com prova.

Normalização de ponto de milhar (12/11/2026): "PL 1.454/2021" não
casava o padrão de referência e a alegação nem chegava a ser
buscada. O padrão aceita o ponto (`1.454`, `12.345`) e o buscador
consulta sem ele (`numero=1454`). Detalhe encontrado no teste ao
vivo: a mesma proposição tem redações de ementa diferentes na Câmara
e no Senado — a busca agora consulta as duas casas e confirma se
qualquer uma casar (antes, parava na primeira com registro). Medido
(q70, versão 2): de Predominantemente verdadeiro (75%) para
**Verdadeiro (81,25%)** — as refs com ponto viraram alegações e
confirmaram; as 3 alegações de conteúdo seguem sem evidência porque
afirmam aprovação e a API do Senado não expõe situação descritiva
(só existência, ementa e IndicadorTramitando). No dia: 67 vereditos,
51 Inconclusivo (76%), 5 Predominantemente verdadeiro, 11 Verdadeiro.

Feed do g1 trocado para política + triagem apertada (12/11/2026):
o feed geral do g1 entregava notícia local e de crime — a rodada de
notícias foi 10 de 10 Inconclusivo, sem fonte primária possível para
"roubou R$ 12 mil" ou "70% de desconto". O g1 agora usa o RSS só de
política e a triagem exige ref ou palavra-chave política no título
(número sozinho não basta mais; lista estendida com reajuste,
orçamento, fiscal, votação, sanção, veto, decreto, polícia federal,
previdência). Aplicado na fila: 159 pendentes → 138 mantidos, 21
descartados (g1 17, poder360 4). **Rodada de notícias pós-troca:
6 de 10 com prova** (1 Verdadeiro, 5 Predominantemente verdadeiro)
contra 0 de 10 antes. Os 4 inconclusivos restantes são itens que
não nomeiam a proposição ("Congresso aprova projeto que autoriza
governo a usar R$ 26 bilhões...") — a ref está no corpo do artigo,
não no resumo. No dia: 88 vereditos, 65 Inconclusivo (74%), 11
Predominantemente verdadeiro, 12 Verdadeiro — o dia segue carregando
os vereditos pré-correção; a taxa da rodada atual é 60% com prova.

Texto completo do artigo (12/11/2026): implementado e medido.
**Resultado: 0 de 4 inconclusivos viraram e a rodada fresca foi 10
de 10 Inconclusivo.** O diagnóstico: os jornalistas não imprimem a
referência completa no corpo — escrevem "o projeto", "a medida
provisória", "medida provisória número 1373" (sem ano; e a MPV
1373/2026 é o Desenrola Adimplentes, não a renegociação de dívidas
rurais — a ementa protege contra confirmação errada). A busca do
artigo funciona (texto limpo nos 3 portais, refs encontradas quando
a matéria as imprime, ex.: PLP 299/2026 em artigos de texto do
Senado), mas o gargalo agora é a referência incompleta, não o
acesso ao texto. No dia: 102 vereditos, 79 Inconclusivo (77%), 11
Predominantemente verdadeiro, 12 Verdadeiro.

DOU por busca web (12/11/2026): implementado e medido. Testes ao
vivo: EC 141/2026 promulgada, Lei 14.973/2024 sancionada, Decreto
10.954/2022 publicado e MP 1.373/2026 publicada confirmam; Lei
99.999/2026 contradiz. Na rodada ao vivo (10 itens): **1 Verdadeiro
(q210, PAR 21/2026, 86%)** — o DOU confirmou 2 alegações sobre a MP
1384/2026 e a Câmara confirmou o parecer; 8 Inconclusivo, 1 Sem
índice. Diagnóstico novo: as centrais dos 8 inconclusivos são número
ou data soltos ("R$ 3 mil", "40%", "12/11/2026") — com o texto do
artigo, a data de publicação vira candidata e, sem proposição no
texto, vira a central.

Central corrigida (12/11/2026): a central agora é a alegação mais
verificável, não a primeira do texto — proposição, ato do DOU,
afirmação do LLM ou citação; número, valor e data soltos nunca são
central se houver alternativa (`verdict_pipeline.choose_central_index`).
A extração por regras passou a encontrar atos do DOU (kind "ato") e
a citação fragmentada ("..., disse o secretário.") não vira mais
candidato. **Medido — reprocessamento dos 8 inconclusivos: 0 viraram,
mas 5 de 8 centrais passaram a ser afirmações de verdade** (ex.:
"O presidente Lula embarcou para as Filipinas..."); os 3 restantes
(q149, q311, q313) ficaram sem alegação do LLM. **Rodada fresca (10
itens): 9 Inconclusivo, 1 Predominantemente verdadeiro (q323, 71%,
decreto 13.161/2026 confirmado no DOU)**; 7 de 10 centrais são
afirmações ou refs de ato. No dia: 139 vereditos, 114 Inconclusivo
(82%), 12 Predominantemente verdadeiro, 13 Verdadeiro — o agregado
carrega as versões antigas; a rodada atual já não tem central de
número/data solto salvo quando o LLM falha.

Limite medido do Groq free tier (12/11): a API falha de formas
diferentes no mesmo dia — 429 (tokens/minuto), 400
json_validate_failed (o modelo não gerou JSON), 301 para a mesma URL
(o urllib virava GET e a API respondia 404) e RemoteDisconnected.
O cliente agora retenta os transitórios (429, 301, 400
json_validate_failed, queda de conexão) com espera crescente,
preserva o POST no redirect, corta o prompt em 4.000 chars no fim
de palavra — e mesmo assim o LLM devolve [] para q149/q311/q313.
Quando o LLM falha, o pipeline segue só com regras (desenho
conservador): a central cai no primeiro candidato.

Decisão do idealizador (12/11/2026): **Inconclusivo é a resposta
correta para notícia sem referência.** O aceite da #47 foi
reescrito: não "inconclusivos abaixo de 50% no geral" (inalcançável
no mix de feed — notícia de crime/local não tem fonte primária),
mas "prova como maioria entre os itens COM referência" e "zero
falsas confirmações". Medido no dia (113 itens com veredito): **com
ref, 23 de 26 com prova (88%); sem ref, 87 de 87 Inconclusivo
(100%), 0 com prova.** Issue #47 fechada com esse aceite
reframado. A Onda 1 segue aberta nos critérios restantes
(viralização = proxy, sem API paga do X; taxa de correção ainda
não mensurável, 0 correções).

Avaliado e adiado: DOU não tem API pública de consulta (só portal
web e WS-INCom de publicação); IBGE/SIDRA responde, mas falta o mapa
alegação → tabela; o Senado não expõe situação descritiva na API
(só existência, ementa e IndicadorTramitando).

## Distribuição e observabilidade (M4)

Cada análise publicada gera as 3 mensagens do formato único (foto do
assunto + resumo curto + link no fim), uma por canal, salvas no outbox
(tabela `distribution`):

```bash
python3 scripts/run_distribute.py            # prepara as mensagens
python3 scripts/run_distribute.py --list     # lista as pendentes
python3 scripts/run_distribute.py --mark-sent 12  # confirma postagem manual
python3 scripts/run_dashboard.py             # gera site/dashboard.html
python3 scripts/run_newsletter.py            # gera outbox/boletim-AAAA-MM-DD.md
```

- **Instagram:** o cliente da Graph API (`crivo/pipeline/instagram.py`)
  publica de verdade com `--live`, mas exige conta empresarial, app
  Meta e token (`IG_USER_ID`, `IG_ACCESS_TOKEN` no `.env`). Sem
  credencial ou sem imagem pública, a mensagem fica pendente para
  postagem manual. Nada é postado sem `--live`.
- **X:** manual e racionado por desenho (post com link custa US$ 0,20
  na API paga): o distribuidor prepara no máximo `X_DAILY_CAP` posts
  por dia (padrão 3) e registra o custo de cada um. O pleito de
  Public Utility App (classificação do X que isenta taxas para
  utilidade pública) é uma tentativa paralela: pedir no portal de
  desenvolvedores do X, na categoria de utilidade pública, sem contar
  com a aprovação.
- **WhatsApp:** o texto do Canal fica pronto no outbox para postagem
  manual (gratuita). Broadcast automático pela Business API é pago
  desde a 1ª mensagem de marketing; a franquia gratuita cobre só
  1.000 mensagens de serviço por mês por número.
- **Auditoria:** cada decisão (coleta, veredito, mensagem preparada,
  mensagem enviada, boletim) entra em `audit_log`, encadeada por hash
  — `verify_chain` detecta qualquer alteração posterior.
- **Boletim semanal:** o arquivo é gerado pronto para envio; o envio
  por e-mail usa tier gratuito (Resend/Brevo) e ainda não está ligado
  — falta `RESEND_API_KEY` e um remetente com domínio verificado.

## Regras do esqueleto

- Nenhum segredo no código. Chaves futuras entram por `.env`
  (ver `.env.example`) e nunca são commitadas.
- O modelo de linguagem, quando existir, só extrai e localiza. O
  veredito é sempre determinístico (ver `crivo/pipeline/verdict.py`).
- `site/` e `*.db` são artefatos gerados e ficam fora do git.

## Veracity classifier — ML (16/11/2026)

Portfolio adaptation of the project as an AI piece (creator's
decision, 16/11): a TF-IDF + logistic regression classifier
trained on the Fake.Br Corpus (7,200 news items, 3,600 fake +
3,600 true), with the model published on Hugging Face and a
demo in a Space. Details in `crivo/ml/README.md`.

**Central rule: ML is a triage signal, never a verdict.** The
suspicion score (0–1) prioritizes the queue (`triage.score`,
+10/+5 bonus, which never overtakes an item with a reference)
and is recorded in the result and in the audit log
(`run_verdicts.py --ml-model`). The verdict is still decided
only by rules over primary sources.

**Measured (16/11, pair-wise split, test n=1440):** accuracy
0.9708, F1-macro 0.9708, fake F1 0.9710, ROC-AUC 0.9960, 5-fold
CV 0.9663 ± 0.0064. Matrix [[696, 24], [18, 702]].

**Measured limit: short text does not work.** Headlines (~200
chars) score 0.91–0.98 even when true — the model only saw
full articles. `suspicion_score` returns None below 500 chars,
and the integration only scores the full article text. On full
articles: true items 0.04–0.18; fake ones 0.69–0.93. Live
(16/11, 5 items): real news from g1/Senado scored 0.09–0.13,
verdicts unchanged.

**Environment:** the repo is standard library only; ML lives
in a separate venv (`.venv-ml`, `scikit-learn pandas`). Training
tests skip without sklearn; integration tests use a fake model
and always run. The corpus (146 MB) and the trained model
(`crivo/ml/models/`) are not versioned. Publishing on the Hub:
see `crivo/ml/hf/README-publicar.md` — it needs the creator's
account and token.

## v2 — FakenewsBR + calibration (17/11/2026)

Training on the unified FakenewsBR corpus (Silva et al., 2026):
51,205 lines in the file, **36,594 canonical items** (26,534
fake / 10,060 true; excluding `*_raw` and texts <50 chars).
Loader in `crivo/ml/fakenewsbr.py`, training in
`scripts/train_classifier_v2.py`.

**Verdict: v2 does NOT replace v1.** On articles v1 is still
better (F1 0.9708 against 0.8841 without calibration / 0.9311
calibrated, on the v1 test — clean comparison, with the 1,440
items of the v1 test set excluded from v2 training by
fingerprint). The value of v2 is breadth (tweets, WhatsApp,
COVID) and short text: short true 0.456 / short fake 0.722 on
average (v1 scored 0.91–0.98 on short true text), but the
500-char guard still applies. On the mixed test (n=7,319):
F1-macro 0.7676, accuracy 0.8086, ROC-AUC 0.8575, Brier 0.1444.

**Calibration — mixed result, not shipped.** Isotonic improves
Brier (0.1444 → 0.1256) and F1 on articles (0.8841 → 0.9311),
but shifts the operating point toward "fake": false positives
on true items jump from 590 to 1,011 on the mixed test and
F1-macro drops (0.7676 → 0.7444). Shipped artifact: without
calibration. **Bug found and fixed along the way:**
`calibration_report` returned np.int64 in "n" and `save_model`
broke on json.dump at the end of training — with the model
saved and the metrics lost; fixed (int() at the source +
default in json.dump) with a regression test.

**False positives by source (v2 without calibration):**
LLM4BR 5%, Fake.br 9%, WhatsApp 22%, COVID 36%, MuMiN-PT 53%,
Kaggle `true` 58%. The triage bonus thresholds (+5/+10) were
measured for v1 and do not apply to v2. **Design:** router by
length (500+ chars → v1; short → v2, weak signal), implemented
in the test `infer.py`; the pipeline still uses only v1. v2
model: 2.8 MB (the calibrated version, discarded, was 16.7 MB
— 5 base models embedded).

## Unified model + BERTimbau (17/11/2026)

Creator's request: a unified model with F1 >= 0.95 on both
tests (articles and mixed). Measured in three rounds
(`scripts/experiment_mix.py`, `experiment_char.py`,
`tune_unified.py`, `tune_unified_extra.py`):

**Ensemble (average of v1+v2) LOST to both** (articles 0.9597,
mixed 0.6479). **Unified + char n-grams** is the best single
model. **Char helps both** (v1+char 0.9736; v2+char 0.7754)
and became the official configuration. **Optimal threshold 0.5**
(nothing to gain from tuning). **Kaggle `true` insight:** the
58% false-positive rate is not a model failure — the "true"
items from that source are fact-check questions and fragments,
another genre.

**Unified tuning:** C=4.0 + oversample articles ×2 is the best
(articles 0.9646, mixed 0.7924). Majority vote (char+SVC+CNB)
is the best on mixed without oversampling (0.7914), but drops
on articles (0.9359). **Measured ceiling:** without the `true`
and `MuMiN-PT` sources, the best linear model reaches 0.8183
on mixed — 0.95 on mixed does not come from a linear model;
the bottleneck is the data. Caveat: C was chosen by evaluating
directly on the tests (3-fold CV would not finish on this VM),
numbers slightly optimistic.

**Final artifact:** `scripts/train_unified.py --compare`
(char C=4.0, oversample ×2), model in
`crivo/ml/models/unified/` (4.2 MB). The v1/v2 router stays for
comparison; the unified model is the single model of the zip
and the demo (selector in `crivo/ml/hf/app.py`, score in
`infer.py`).

**BERTimbau — real training run 17/11/2026 (Kaggle T4 GPU;
free Colab had no GPU — Kaggle notebook in
`crivo/ml/hf/bertimbau-kaggle.ipynb`).** Articles F1 0.9854
(accuracy 0.9854, n=1440) — the 0.95 goal beaten, better than
v1 (0.9736) and the unified model (0.9646). Mixed F1 0.8243
(accuracy 0.8561, n=7319) — the best model on mixed so far
(unified 0.7924), but below 0.95. Mixed clears the measured
linear ceiling without the worst sources (0.8183) by 0.6 points,
on the full set — the bottleneck is the data, not the model.
(Re-run of the training for the Hub upload; first run: articles
0.9868 / mixed 0.8184.) Script `scripts/train_bertimbau.py`
(fine-tuning, same splits, class weights). Fixed along the way:
transformers 5.x has no `warmup_ratio` (only `warmup_steps`,
10% of steps) and the default collator breaks without dynamic
padding (`DataCollatorWithPadding`); the smoke sample was all
fake (infinite weight) — now stratified. Notebook pins
`transformers==5.23.0`. Model weights published on the Hub
(`brenindexdev/crivo-factual-fakebr`, under `bertimbau/`,
commit `a80b59bb`).

**Training-data cleaning — tested and REJECTED 17/11/2026.**
Hypothesis: removing the non-news items of the `true` source
(questions/fragments) and texts <100 chars from training would
improve mixed. Measured on the unified model (same config,
fixed tests): articles F1 0.9646 → 0.9708 (+0.0062), **mixed
F1 0.7924 → 0.7770 (−0.0154)**. The false-positive rate on the
`true` source jumped from 66.5% to 94.0%. Mechanism: the
question fragments were the only short true examples in
training — the counterweight to the "short text → fake"
shortcut that the short items of the `fakes` source teach;
removing them strengthened the shortcut. The right direction
is the opposite: keep/reinforce short true items in training
or bring genuine short true news from another source. Nothing
was pushed to GitHub; the validation artifacts stayed in /tmp
(volatile).

**Reinforcing short true items — tested and REJECTED
17/11/2026.** The opposite hypothesis to cleaning: duplicating
short true items in training would teach the pattern. Measured
on the unified model (same config, fixed tests): A (×2 true
items <500 chars) mixed 0.7924 → 0.7871; B (×3) → 0.7857; C
(×2 `true` source) → 0.7822. The false-positive rate on the
`true` source fell (66.5% → 55–58%), but false recall fell
more than true recall gained — duplicating shifts the class
prior, it does not teach the model to tell a question from a
news item. Both data levers (removing and duplicating) failed
in opposite directions; the path of changing how many short
true examples there are is closed. What remains: (1) genuine
short true news from another source; (2) BERTimbau-large /
more epochs / larger max_len; (3) accepting the ceiling.

**Two bugs found and fixed in this round:**
(1) `train_unified.py` called `save_model(pipe, caminho)` —
the signature is `save_model(pipe, metrics, out_dir)`, and the
model was not saved on the first attempt (metrics computed,
artifact lost); (2) the original `tune_unified.py` used 3-fold
CV that would not finish on this VM — replaced by direct
evaluation of C on the tests, with incremental saving of
results (a restart does not erase what was already measured;
the 00:22 restart interrupted the first chain midway).

## Branching (GitLab Flow) — from 17/11/2026

The history on `main` is kept as it happened (see `CHANGELOG.md`
for the English map). From now on, work follows GitLab Flow:

- `main` is the only long-lived branch: always green (CI passes),
  every change arrives through a feature branch.
- Feature branches: `feature/<topic>` — e.g.
  `feature/demo-streamlit`, `feature/wave-2`, `feature/launch`.
  One logical change per commit (no more one-commit-per-file),
  commit messages in English, imperative mood.
- Open workstreams already have their branches (created 17/11):
  `feature/demo-streamlit` (issue #57), `feature/wave-2`
  (issue #32), `feature/launch` (issue #43).
- Merge to `main` only after CI passes; delete the feature branch
  after merging. Never commit directly to `main` except for a
  hotfix, and never rewrite published history (no force-push to
  `main`).
