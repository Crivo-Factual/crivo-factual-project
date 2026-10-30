# 08 — Stack, fases e métricas

## Stack sugerida (referência, não decisão travada)

| Camada | Sugestão | Motivo |
|---|---|---|
| Coletores | Python (feedparser, clientes de API oficiais) | Ecossistema maduro de RSS/APIs; fácil de manter |
| Fila e orquestração | Fila persistente + agendador (ex.: Celery/Redis ou equivalente) | Pipeline em 6 etapas precisa de retry, ordem e backpressure |
| Banco de fatos | PostgreSQL (+ busca textual) | Consultas estruturadas por alegação + evidência; versionamento |
| Motor de extração | Modelo de linguagem via API, com prompts travados e saída estruturada (JSON) | Extrai alegações e formula buscas; **nunca decide veredito** |
| Motor de veredito | Regras determinísticas em código (não probabilísticas) | Veredito precisa ser reproduzível: mesmas evidências → mesmo resultado |
| Portal web | Framework web simples + páginas estáticas geradas por análise (SEO e velocidade) | Cada análise é uma página permanente; estático escala barato |
| Distribuição | APIs oficiais (X, Instagram Graph, WhatsApp Business) + gerador de cards por template | Um único disparo gera os 3 formatos |
| Observabilidade | Logs imutáveis + dashboards de volume, latência e distribuição de vereditos | Auditoria do método e controle de custo |

**Custos que escalam (atenção no orçamento):** API do X (busca), API do modelo de linguagem (extração), e — em menor grau — hospedagem. O banco de fatos é o principal redutor de custo: quanto mais o sistema já verificou, menos ele precisa consultar.

## Fases (ondas de expansão)

### Onda 0 — Validação (2–4 semanas, custo quase zero)
Uma página simples com 3 temas vivos + boletim semanal. Objetivo: testar se o formato (selo + índice + provas) é entendido e compartilhado. Métrica de saída: taxa de compartilhamento e retorno de leitores, não volume.

### Onda 1 — MVP (2–3 meses)
Portal com todas as editorias nacionais (`04-cobertura-mvp.md`), pipeline completo, distribuição para X, Instagram e canal de WhatsApp. Começa com foco reforçado em boatos reciclados, números oficiais e citações — onde a taxa de acerto é mais alta.

### Onda 2 — Profundidade (3–6 meses após o MVP)
Votações ("como votou meu deputado"), promessômetro, personalização por UF/município, importação de verificações históricas para o banco de fatos, cobertura estadual/municipal completa.

### Onda 3 — Escala (6–12 meses após o MVP)
Multimídia (vídeo/áudio/imagem) com peso maior, política mundial, API aberta para pesquisadores e escolas, auditoria externa anual.

## Métricas de sucesso (o que mede se o portal cumpre a missão)

1. **Alcance das correções:** quantas pessoas viram a verificação em comparação com o alcance estimado do boato original.
2. **Tempo até a verificação:** horas entre a viralização do boato e a publicação da análise (meta do MVP: < 24h para os 10 boatos mais virais do dia).
3. **Taxa de inconclusivos:** monitorada, não minimizada à força — subir demais indica falta de fontes; cair a zero indica limiar frouxo (perigo).
4. **Taxa de correção:** quantas análises mudaram de veredito após novas evidências (meta: baixa, mas nunca zero — zero significa que o sistema não aprende).
5. **Retorno e confiança:** leitores recorrentes, assinantes/membros, citações do portal por veículos e escolas.
6. **Equilíbrio:** distribuição de vereditos por espectro (ver `07-confianca-riscos-legais.md`) — métrica de auditoria, não de meta.

## O que NÃO é métrica de sucesso

- Volume bruto de posts (publicar muito e errado é pior que publicar pouco e certo).
- Engajamento por polêmica (o portal não compete por indignação).
- Crescimento a qualquer custo (crescer sem manter o limiar de evidência destrói o produto).
