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
exige chave.

```bash
python3 scripts/run_collectors.py            # uma passada
python3 scripts/run_collectors.py --loop 900 # repete a cada 15 min
```

A coleta alimenta a fila persistente (`queue` no SQLite): cada item
recebe score de triagem e só o verificável entra (tem link ou traz
número, data ou citação no título/resumo). Duplicatas são descartadas
por hash de conteúdo. Falha de uma fonte não derruba as demais. A fila
tem teto de 500 pendentes (backpressure) e retry com backoff
exponencial (1, 2, 4, 8 e 16 minutos, teto de 1h; após 5 tentativas o
item fica `failed`).

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
precisa, não a falta de fontes. Limite encontrado no teste dirigido:
**EMC, PAR e SBT não são identificadores únicos** — são numerados
por proposição, e a API da Câmara devolve até 5 registros
diferentes para o mesmo "EMC 1/2026"; o cliente usa o primeiro
(`dados[0]`), então a confirmação por ementa falha quando o registro
certo não é o primeiro. Para esses tipos, a busca precisa testar a
ementa de cada registro retornado. Próximos caminhos: desambiguação
por ementa (EMC/PAR/SBT), busca no corpus oficial já coletado e DOU
por download da edição (XML/ZIP).

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
