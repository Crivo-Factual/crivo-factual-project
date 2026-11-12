# Revisão da Onda 1 (MVP) — 12/11/2026

Revisão do MVP contra os critérios de saída de
`09-plano-onda-1.md`, com números medidos no sistema ao vivo em
12/11/2026 (~15:00 UTC). Não é uma autoavaliação: cada afirmação
abaixo cita a medição que a sustenta.

## Método

- Banco ao vivo (`crivo.db`) consultado diretamente: fila, vereditos,
  distribuição e auditoria.
- Prova cronometrada de ponta a ponta: coleta → vereditos (10 itens)
  → distribuição → dashboard, em 17 s.
- Testes: `python3 -m unittest discover -s tests -t .` → **53/53 OK**;
  CI verde (run #43238763370, head `2e87ab3`).
- Demo M1 re-executada: Bolsa Família Falso 20% (veto), cortes-2027
  Inconclusivo 50% (trava do centro), fim-6x1 Verdadeiro 100%.

## Números medidos

| Medição | Valor |
|---|---|
| Vereditos publicados em 12/11 | 26, todos Inconclusivo (100%) |
| Latência coleta → veredito | média 26,1 min, máxima 57,7 min (n=26) |
| Tempo de um ciclo completo (coleta + 10 vereditos + distribuição) | 17 s |
| Fila | 32 done / 254 pending |
| Crescimento da fila por coleta | ~68 itens novos |
| Mensagens preparadas | 19 Instagram, 19 WhatsApp, 3 X |
| Postagens reais feitas | 0 (sem contas) |
| Eventos de auditoria | 61, cadeia íntegra |
| Páginas em `site/` | 31 HTML (análises + índice + dashboard) |

A latência é quase toda espera na fila entre execuções manuais: o
processamento em si leva segundos. O gargalo é operacional (ninguém
rodando os scripts em loop), não computacional.

## Critério por critério

### 1. "Verificação publicada em menos de 24h para os 10 boatos mais virais do dia" — NÃO ATENDIDO

- **Tempo: sim.** Latência máxima medida 57,7 min, muito abaixo de
  24h; o ciclo completo leva 17 s.
- **"Os 10 mais virais": não comprovado.** A triagem ordena por um
  score proxy (palavras-chave + recência). Viralização real exige a
  API paga do X — fora do desenho free-first. Não há como afirmar
  que os 10 processados são os 10 mais virais do dia.
- **"Verificados": não.** Os 26 vereditos do dia são 100%
  Inconclusivo: processados e publicados, mas sem prova. Inconclusivo
  é a declaração de que não foi possível verificar, não uma
  verificação. O critério, como escrito, exige vereditos com prova.

### 2. "Taxa de inconclusivos monitorada" — MONITORADA, EM 100%

A métrica existe (dashboard, por rótulo) e está sendo acompanhada.
O valor é 100%: o próprio plano diz que subir demais indica falta
de fontes. É o diagnóstico, não um acidente — a causa é a ausência
de busca de fontes primárias ao vivo (só boato reciclado conta como
evidência hoje).

### 3. "Taxa de correção baixa, mas nunca zero" — NÃO MENSURÁVEL AINDA

Zero correções e zero contestações até aqui. O mecanismo existe
(vereditos versionados, correção versionada), mas nada foi publicado
com prova para ser contestado. Não é falha; é falta de amostra.

### 4. "Distribuição de vereditos por espectro acompanhada" — ACOMPANHADA, SEM ESPECTRO

A métrica existe, mas 26/26 Inconclusivo não formam espectro algum.
Nada a auditar até haver vereditos com prova.

## Marcos

- **M1 — Esqueleto: cumprido.** Estrutura, schema, páginas, pipeline
  em 6 etapas, testes e CI.
- **M2 — Coletores e triagem: cumprido com ressalvas.** 5 fontes ao
  vivo e verificadas (g1, Senado Notícias, Poder360, Câmara, Senado
  tramitando). TSE, IBGE e DOU ficaram fora (sem endpoint público
  verificado). Viralização é proxy, não medição. Fila persistente com
  retry e backpressure funciona; o banco acumula verificações reais.
- **M3 — Veredito de verdade: cumprido com ressalvas.** Extração por
  regras + LLM free tier, motor determinístico, páginas com trilha de
  provas e versões. Tensão documentada: a meta interna "nenhuma
  publicação sem fonte primária" convive com páginas Inconclusivo
  publicadas — a página declara a falta de prova, mas é uma publicação
  sem fonte primária no sentido estrito.
- **M4 — Distribuição e observabilidade: cumprido como preparação,
  não como disparo.** Outbox, cliente Instagram real (só com
  `--live`), X racionado (teto de 3/dia, atingido), WhatsApp manual,
  auditoria hash-chain, dashboard e boletim. Zero postagens reais:
  faltam as contas.

## Desvios do plano

- **Banco de fatos em SQLite, não PostgreSQL.** Decisão free-first
  (doc 10): SQLite local no MVP; a migração para Postgres fica para
  a hospedagem.
- **Sem execução contínua.** Coleta e vereditos rodavam só por
  comando manual; a fila cresce ~68 itens por coleta. Correção
  aplicada nesta revisão: `--loop` no `run_verdicts.py` (o coletor
  já tinha). Rodar os dois em loop (ou cron) é o que sustenta o
  "menos de 24h" na prática.
- **Decisões do idealizador pendentes:** contas business (Instagram,
  WhatsApp), hospedagem, domínio `crivofactual.com.br` e @,
  validação da Onda 0 com público real.

## Veredito

**A Onda 1 não cumpre o critério de saída nº 1 como escrito.**
O que o MVP prova hoje: capturar, triar, processar e publicar 10
itens em minutos, com auditoria íntegra e custo zero. O que ele não
prova: verificar boatos com prova nem identificar os mais virais.

## Decisão (só o idealizador)

1. **Fechar a Onda 1 com ressalvas:** aceitar o MVP como "operacional
   com ressalvas" e reescrever o critério de saída nº 1 para a
   realidade free-first — por exemplo, "10 itens processados e
   publicados em menos de 24h, com taxa de inconclusivos e causa
   registradas" — e levar a busca de evidências primárias ao vivo
   para a Onda 2.
2. **Manter a Onda 1 aberta:** só fechar quando existir busca de
   fontes primárias ao vivo e medição de viralização, isto é, quando
   vereditos com prova forem a maioria dos processados.

## Decisão registrada (12/11/2026)

**Opção 2 — manter a Onda 1 aberta até a busca primária.** A Onda 1
não está fechada. O trabalho que a bloqueia está rastreado na issue
#47 ("Onda 1 — Busca de evidências primárias ao vivo"), no quadro
como Todo: busca por tipo de alegação (proposições via APIs da Câmara
e do Senado; números oficiais a avaliar), regras determinísticas
mantidas, aceite = vereditos com prova como maioria e inconclusivos
abaixo de 50% numa rodada ao vivo de 10 itens.

## Progresso #47 (12/11/2026, ~15:20 UTC)

Busca implementada e medida. Cobertura de ~10% dos itens (4/40 na
sonda offline); nas duas primeiras rodadas ao vivo de 10 itens:
3 Verdadeiros com prova primária (q21, q22, q23), 10 Inconclusivo,
7 Sem índice (sem alegação extraível). No dia: 39 vereditos, 3 com
prova (8%), 36 Inconclusivo (92%). **Aceite NÃO atingido.** A busca
funciona e nunca confirmou nada falso — o limite é a mistura de
alegações da fila, não o motor. Próximos caminhos: extração por LLM
(precisa de `GROQ_API_KEY`), busca no corpus oficial coletado e DOU
por download da edição. Issue #47 segue aberta com os números.
