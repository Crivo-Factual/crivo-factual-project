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

## Classificador de veracidade — ML (16/11/2026)

Adaptação do projeto como peça de portfólio de IA (decisão do
idealizador, 16/11): um classificador TF-IDF + regressão logística
treinado no Fake.Br Corpus (7.200 notícias, 3.600 falsas + 3.600
verdadeiras), com o modelo publicado no Hugging Face e demo em
Space. Detalhes em `crivo/ml/README.md`.

**Regra central: o ML é sinal de triagem, nunca veredito.** A
suspeita (0–1) prioriza a fila (`triage.score`, bônus +10/+5, que
nunca passa na frente de um item com referência) e fica registrada
no resultado e na auditoria (`run_verdicts.py --ml-model`). O
veredito continua decidido só por regras sobre fontes primárias.

**Medido (16/11, split por par, teste n=1440):** acurácia 0,9708,
F1-macro 0,9708, F1 falsa 0,9710, ROC-AUC 0,9960, CV 5-fold
0,9663 ± 0,0064. Matriz [[696, 24], [18, 702]].

**Limite medido: texto curto não serve.** Manchetes (~200 chars)
pontuam 0,91–0,98 mesmo verdadeiras — o modelo só viu artigos
completos. `suspicion_score` devolve None abaixo de 500 chars, e
a integração só pontua o texto completo do artigo. Em artigos
completos: verdadeiros 0,04–0,18; falsos 0,69–0,93. Ao vivo
(16/11, 5 itens): notícias reais do g1/Senado pontuaram
0,09–0,13, vereditos inalterados.

**Ambiente:** o repo é só biblioteca padrão; o ML vive num venv
separado (`.venv-ml`, `scikit-learn pandas`). Os testes de treino
pulam sem o sklearn; os de integração usam modelo falso e rodam
sempre. O corpus (146 MB) e o modelo treinado (`crivo/ml/models/`)
não são versionados. Publicação no Hub: ver
`crivo/ml/hf/README-publicar.md` — precisa da conta e do token do
idealizador.

## v2 — FakenewsBR + calibração (17/11/2026)

Treino no corpus unificado FakenewsBR (Silva et al., 2026):
51.205 linhas no arquivo, **36.594 canônicas** (26.534 falsas /
10.060 verdadeiras; fora `*_raw` e textos <50 chars). Loader em
`crivo/ml/fakenewsbr.py`, treino em `scripts/train_classifier_v2.py`.

**Veredito: a v2 NÃO substitui a v1.** Em artigos a v1 continua
melhor (F1 0,9708 contra 0,8841 sem calibração / 0,9311
calibrada, no teste da v1 — comparação limpa, com os 1.440 itens
do teste da v1 excluídos do treino da v2 por fingerprint). O
valor da v2 é a amplitude (tweets, WhatsApp, COVID) e o texto
curto: verdadeiro curto 0,456 / falso curto 0,722 em média (a v1
pontuava 0,91–0,98 em verdadeiro curto), mas o guarda de 500
chars continua valendo. No teste misto (n=7.319): F1-macro
0,7676, acurácia 0,8086, ROC-AUC 0,8575, Brier 0,1444.

**Calibração — resultado misto, não enviada.** Isotônica melhora
o Brier (0,1444 → 0,1256) e o F1 nos artigos (0,8841 → 0,9311),
mas desloca o ponto de operação para "falso": falsos positivos
em verdadeiras saltam de 590 para 1.011 no teste misto e o
F1-macro cai (0,7676 → 0,7444). Artefato enviado: sem calibração.
**Bug encontrado e corrigido no caminho:** `calibration_report`
devolvia np.int64 em "n" e `save_model` quebrava no json.dump no
fim do treino — com o modelo salvo e as métricas perdidas; corrigido
(int() na fonte + default no json.dump) com teste de regressão.

**Falso positivo por fonte (v2 sem calibração):** LLM4BR 5%,
Fake.br 9%, WhatsApp 22%, COVID 36%, MuMiN-PT 53%, Kaggle `true`
58%. Os limiares do bônus de triagem (+5/+10) foram medidos
para a v1 e não valem para a v2. **Desenho:** roteador por tamanho
(500+ chars → v1; curto → v2, sinal fraco), implementado no
`infer.py` de teste; o pipeline continua usando só a v1.
Modelo v2: 2,8 MB (a versão calibrada, descartada, tinha 16,7 MB
— 5 modelos base embutidos).

## Modelo unificado + BERTimbau (17/11/2026)

Pedido do idealizador: um modelo unificado com F1 >= 0,95 nos
dois testes (artigos e misto). Medido em três rodadas
(`scripts/experiment_mix.py`, `experiment_char.py`,
`tune_unified.py`, `tune_unified_extra.py`):

**Ensemble (média v1+v2) PERDEU para as duas** (artigos 0,9597,
misto 0,6479). **Unificado + char n-grams** é o melhor modelo
único. **Char ajuda os dois** (v1+char 0,9736; v2+char 0,7754)
e virou a configuração oficial. **Limiar ótimo 0,5** (nada a
ganhar com ajuste). **Insight Kaggle `true`:** os 58% de falso
positivo não são falha do modelo — os "verdadeiros" daquela
fonte são perguntas e fragmentos de checagem, outro gênero.

**Afinação do unificado:** C=4,0 + oversample artigos ×2 é o
melhor (artigos 0,9646, misto 0,7924). Voto majoritário
(char+SVC+CNB) é o melhor no misto sem oversample (0,7914),
mas cai nos artigos (0,9359). **Teto medido:** sem as fontes
`true` e `MuMiN-PT`, o melhor linear chega a 0,8183 no misto —
0,95 no misto não vem do linear; o gargalo é o dado. Caveat:
a escolha de C foi avaliada direto nos testes (a CV 3-fold não
terminava nesta VM), números levemente otimistas.

**Artefato final:** `scripts/train_unified.py --compare`
(char C=4,0, oversample ×2), modelo em
`crivo/ml/models/unified/` (4,2 MB). O roteador v1/v2 continua
para comparação; o unificado é o modelo único do zip e da demo
(seletor em `crivo/ml/hf/app.py`, score em `infer.py`).

**BERTimbau — o caminho para 0,95 no misto.** Script
`scripts/train_bertimbau.py` (fine-tuning, mesmos splits,
peso por classe) + notebook `crivo/ml/hf/bertimbau-colab.ipynb`
(Colab T4, 30–60 min). Smoke test na CPU passou (treino,
avaliação e salvamento rodam); o treino real ainda não rodou
— precisa da GPU do Colab. Corrigidos no caminho: transformers
5.x não tem `warmup_ratio` (só `warmup_steps`, 10% dos passos)
e o collator padrão quebra sem padding dinâmico
(`DataCollatorWithPadding`); amostra do smoke era só falsa
(peso inf) — agora é estratificada. Notebook pinou
`transformers==5.23.0`.

**Dois bugs encontrados e corrigidos nesta rodada:**
(1) `train_unified.py` chamava `save_model(pipe, caminho)` —
a assinatura é `save_model(pipe, metrics, out_dir)`, e o
modelo não foi salvo na primeira tentativa (métricas
computadas, artefato perdido); (2) `tune_unified.py` original
usava CV 3-fold que não terminava nesta VM — trocado por
avaliação direta de C nos testes, com salvamento incremental
dos resultados (um restart não apaga o que já mediu; o
restart de 00:22 interrompeu a primeira cadeia no meio).
