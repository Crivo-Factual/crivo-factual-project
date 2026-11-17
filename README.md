
**Nome escolhido:** Crivo Factual (30/10/2026) — *todo fato passa pelo crivo. A conclusão é sua.*
**Versão:** 0.4 — 16/11/2026
**Status:** M1–M4 concluídos; busca primária ao vivo (Câmara, Senado, DOU) implementada e medida, issue #47 fechada; classificador de ML (Fake.Br) treinado e integrado como sinal de triagem — ver `crivo/ml/README.md`. Onda 1 segue aberta nos critérios restantes (viralização = proxy; taxa de correção não mensurável sem público real).

## Decisões travadas

1. **Inconclusivo expandido:** o veredito "inconclusivo" é ampliado com um **índice de veracidade em porcentagem**, mostrando o quanto um conteúdo tende a ser verdadeiro ou falso com base nas comprovações encontradas (ver `02-modelo-de-veredito.md`).
2. **MVP com cobertura máxima da política nacional:** todas as editorias nacionais desde o lançamento; política mundial fica para fases posteriores (ver `04-cobertura-mvp.md`).
3. **Tom institucional + popular:** sóbrio no método, simples na linguagem — uma centralização de publicações políticas focada em expor a veracidade dos fatos à população (ver `01-visao-e-principios.md`).
4. **Nome — Crivo Factual (30/10/2026):** "crivo" (peneira, escrutínio) + "factual" (base exclusiva em fatos). Slogan: *"Todo fato passa pelo crivo. A conclusão é sua."* Nomes anteriores considerados e descartados: Prumo, Na Real, Fato Claro, A Prova, Confere, Veja Bem, Prova Real, Fiel da Balança, Fato Crivado (descartado por ambiguidade — "crivado" também significa "cheio de furos" — e por semelhança fonética com o projeto existente Fato Carimbado). Pendente: confirmar domínio (.com.br) e @ no Instagram e no X.
5. **Onda 0 aprovada (30/10/2026):** formato validado na demonstração (v3 — identidade própria "ficha de verificação carimbada", 4 áreas numeradas, imagens dos assuntos, mensagens de canal simplificadas). Ajustes futuros ficam para depois, sem travar o avanço. A validação com público real (taxa de compartilhamento e retorno de leitores) segue pendente e pode rodar em paralelo ao MVP.

## Índice dos documentos

| Arquivo | Conteúdo |
|---|---|
| `01-visao-e-principios.md` | Missão, princípios inegociáveis, o que o portal é e não é, tom de voz |
| `02-modelo-de-veredito.md` | Alegações atômicas, 5 vereditos, índice de veracidade (fórmula, bandas, regra do veto) |
| `03-arquitetura-pipeline.md` | As 6 etapas automatizadas, componentes, papel do modelo de linguagem, logs |
| `04-cobertura-mvp.md` | Taxonomia nacional máxima do MVP e o que fica para depois |
| `05-captura-e-fontes.md` | Fontes por plataforma, limites técnicos e de custo, triagem por viralização |
| `06-distribuicao.md` | Portal → X, Instagram e canal de WhatsApp, formatos e frequência |
| `07-confianca-riscos-legais.md` | Metodologia pública, correções, direito de resposta, lei eleitoral |
| `08-stack-fases-metricas.md` | Stack sugerida, ondas de expansão, esforço estimado, métricas de sucesso |
| `09-plano-onda-1.md` | Plano de execução do MVP (escopo, marcos M1–M4, critérios de saída, decisões pendentes) |
| `10-versao-gratuita.md` | O que fica dentro e fora de uma versão com R$ 0/mês (decisão de arquitetura free-first) |
| `crivo/ml/README.md` | Classificador de veracidade (ML): TF-IDF + regressão logística no Fake.Br Corpus, métricas, limites e publicação no Hugging Face |

## Classificador de veracidade (ML, 16/11/2026)

Um classificador treinado no Fake.Br Corpus estima a probabilidade
de uma notícia em português ser falsa (acurácia 0,9708, F1-macro
0,9708, ROC-AUC 0,9960, teste n=1440). Ele é **sinal de triagem,
nunca veredito**: prioriza a fila e registra o score na auditoria;
o veredito continua decidido só por regras sobre fontes primárias.
Só opina sobre artigos completos (500+ caracteres) — manchete
sozinha não serve. Detalhes, reprodução e publicação no Hugging
Face: ver `crivo/ml/README.md` e `crivo/ml/hf/README-publicar.md`.

## Resumo em uma frase

Um portal 100% automatizado que captura publicações políticas em circulação, quebra cada uma em alegações verificáveis, compara cada alegação com fontes primárias e bancos de fatos, e publica uma análise conclusiva — **Verdadeiro, Predominantemente verdadeiro, Inconclusivo, Predominantemente falso ou Falso, com índice de veracidade em %** — mostrando todas as provas, sem opinião, para que o leitor tire as próprias conclusões.
