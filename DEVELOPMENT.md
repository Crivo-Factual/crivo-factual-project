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
  factbank/            # schema SQL + acesso ao SQLite
  pipeline/
    collectors.py      # RSS via stdlib (sem feedparser)
    triage.py          # score determinístico de triagem
    extraction.py      # extração por regras (números, datas, citações)
    verdict.py         # motor de veredito: índice, veto, trava do centro
    publish.py         # gerador de páginas estáticas (ficha)
scripts/run_demo.py    # pipeline de ponta a ponta sobre exemplos
data/examples.json     # 3 análises documentadas (Bolsa Família, cortes, 6x1)
tests/test_verdict.py  # testes do motor de veredito
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

## Regras do esqueleto

- Nenhum segredo no código. Chaves futuras entram por `.env`
  (ver `.env.example`) e nunca são commitadas.
- O modelo de linguagem, quando existir, só extrai e localiza. O
  veredito é sempre determinístico (ver `crivo/pipeline/verdict.py`).
- `site/` e `*.db` são artefatos gerados e ficam fora do git.
