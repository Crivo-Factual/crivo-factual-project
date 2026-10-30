# 09 — Plano da Onda 1 (MVP)

## Objetivo

Transformar a demonstração aprovada na Onda 0 num portal de verdade: captura contínua de publicações políticas nacionais, pipeline completo de verificação automatizada e distribuição para X, Instagram e canal de WhatsApp. Prazo de referência: 2–3 meses (ver `08-stack-fases-metricas.md`).

## Escopo (o que entra no MVP)

- Todas as 11 editorias nacionais de `04-cobertura-mvp.md`, desde o lançamento. Política mundial fica para a Onda 3.
- Pipeline completo em 6 etapas de `03-arquitetura-pipeline.md`: captura → triagem → extração de alegações → busca de evidências → veredito determinístico → publicação + distribuição.
- Foco reforçado no começo em boatos reciclados, números oficiais e citações — onde a taxa de acerto é mais alta.
- Formato validado na Onda 0: ficha de verificação carimbada, 4 áreas, imagens dos assuntos, mensagens de canal simplificadas (foto + resumo + link direto).
- O que NÃO entra no MVP: votações por parlamentar, promessômetro completo, personalização por UF/município, multimídia pesada, política mundial, API aberta (tudo de Ondas 2 e 3).

## Stack de referência (não travada — confirmar antes do M1)

Python nos coletores, PostgreSQL como banco de fatos, páginas estáticas geradas por análise no portal, APIs oficiais na distribuição. Ver tabela completa em `08-stack-fases-metricas.md`.

## Marcos

### M1 — Esqueleto do repo (semanas 1–2)
Estrutura do projeto, configuração, schema do banco de fatos (alegação, evidência, veredito, versão), gerador de páginas estáticas e pipeline com as 6 etapas como módulos (coletor, triagem, extração, evidências, veredito, publicação) — primeiro com dados de exemplo, sem fontes ao vivo.

### M2 — Coletores e triagem (semanas 3–5)
Coletores de RSS, dados abertos (Câmara, Senado, TSE, IBGE, Diário Oficial) e APIs oficiais. Triagem por viralização e verificabilidade, com fila persistente e retry. Banco de fatos começa a acumular verificações reais.

### M3 — Veredito de verdade (semanas 5–8)
Motor de extração (modelo de linguagem só extrai e localiza, nunca decide) + motor de veredito determinístico (alegações atômicas, índice de veracidade, regra do veto, trava do centro) + páginas de análise com trilha de provas. Meta interna: nenhuma publicação sem fonte primária.

### M4 — Distribuição e observabilidade (semanas 8–12)
Disparo para X, Instagram e canal de WhatsApp no formato simplificado validado (foto + resumo + link). Logs imutáveis, dashboards de volume, latência e distribuição de vereditos. Boletim semanal.

## Critérios de saída do MVP

- Verificação publicada em menos de 24h para os 10 boatos mais virais do dia.
- Taxa de inconclusivos monitorada (subir demais indica falta de fontes; zerar indica limiar frouxo).
- Taxa de correção baixa, mas nunca zero.
- Distribuição de vereditos por espectro acompanhada como métrica de auditoria, não de meta.

## Decisões que só o idealizador pode tomar (travam o M1/M4)

1. **Orçamento de APIs:** a API do X para busca é paga e o modelo de linguagem cobra por volume. Sem um teto mensal, o desenho precisa começar por fontes gratuitas (RSS, dados abertos) e deixar a busca no X para depois. **Decidido 30/10/2026: sem previsão de orçamento — arquitetura free-first, detalhada em `10-versao-gratuita.md`.**
2. **Contas business:** canal de WhatsApp exige WhatsApp Business API e o Instagram exige conta empresarial no Graph API. São cadastros do idealizador, não automatizáveis daqui.
3. **Hospedagem:** páginas estáticas são baratas em qualquer lugar; o PostgreSQL do banco de fatos define o custo fixo mensal. Escolher provedor antes do M2.
4. **Domínio e @:** confirmar `crivofactual.com.br` (usado como modelo nos links do demo) e os @ no Instagram e no X antes do lançamento — sem isso, os links das mensagens não apontam para lugar nenhum.
5. **Validação real da Onda 0:** publicar a página demo para público real e medir compartilhamento e retorno, em paralelo ao MVP, ou pular direto para o MVP.
