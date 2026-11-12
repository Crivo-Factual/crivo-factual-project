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
```

A extração por LLM usa o Groq free tier (sem cartão): copie
`.env.example` para `.env` com `GROQ_API_KEY` (o modelo vem de
`GROQ_MODEL`, padrão `llama-3.1-8b-instant`). O modelo só extrai e
localiza alegações; o veredito continua determinístico. Sem chave, o
pipeline segue só com regras e avisa.

Evidências nesta versão vêm do próprio banco de fatos: uma alegação
igual a outra já verificada (mesmo texto, ignorando caixa, acentos e
pontuação) herda o status anterior, com link para a análise original
— é a detecção de boato reciclado. Busca de fontes primárias externas
ao vivo ainda não existe: sem prova, a alegação fica sem evidência e
a trava do centro segura o veredito em Inconclusivo. Por isso, itens
frescos da fila viram maioria Inconclusivo até as fontes de evidência
crescerem — o motor nunca inventa prova. Cada novo veredito da mesma
publicação incrementa a versão (histórico em `verdicts`).

## Regras do esqueleto

- Nenhum segredo no código. Chaves futuras entram por `.env`
  (ver `.env.example`) e nunca são commitadas.
- O modelo de linguagem, quando existir, só extrai e localiza. O
  veredito é sempre determinístico (ver `crivo/pipeline/verdict.py`).
- `site/` e `*.db` são artefatos gerados e ficam fora do git.
