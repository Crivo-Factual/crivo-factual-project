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

## Regras do esqueleto

- Nenhum segredo no código. Chaves futuras entram por `.env`
  (ver `.env.example`) e nunca são commitadas.
- O modelo de linguagem, quando existir, só extrai e localiza. O
  veredito é sempre determinístico (ver `crivo/pipeline/verdict.py`).
- `site/` e `*.db` são artefatos gerados e ficam fora do git.
