# 03 — Arquitetura do pipeline automatizado

O sistema é um pipeline de 6 etapas. Cada etapa é um serviço independente, com fila de entrada e saída, logs completos e regras determinísticas. Nenhuma etapa depende de decisão humana.

## Etapa 1 — Captura contínua

**O que faz:** coleta publicações em circulação a partir das fontes listadas em `05-captura-e-fontes.md` (RSS, APIs oficiais, Diário Oficial, portais do Congresso e do Judiciário, redes sociais dentro do permitido por cada plataforma).

**Regras:**
- Cada item capturado guarda: texto/legenda integral, autor, veículo/conta, data/hora, URL original, métricas de alcance no momento da captura e hash do conteúdo (para detectar republicações e edições).
- Captura é temática (política nacional, ver `04-cobertura-mvp.md`), não generalista: o filtro de tema acontece aqui, por lista de fontes + palavras-chave + classificadores.
- Itens duplicados (mesmo conteúdo republicado) são agrupados: uma única análise cobre todas as ocorrências, e a página mostra onde o conteúdo circulou.

## Etapa 2 — Triagem por viralização e verificabilidade

**O que faz:** ordena a fila de verificação. É impossível checar tudo; checa-se o que importa.

**Critérios de prioridade (pontuação combinada):**
1. **Alcance e velocidade:** engajamento absoluto + taxa de crescimento de compartilhamentos (o que está explodindo entra na frente do que está parado).
2. **Alcance do emissor:** contas e veículos com grande audiência pesam mais.
3. **Verificabilidade:** a publicação contém alegações factuais extraíveis (número, data, citação, evento)? Se não contém, sai da fila — opinião pura não é verificável.
4. **Potencial de dano:** temas sensíveis (eleições, saúde pública, programas sociais, segurança) sobem na fila.
5. **Recorrência:** conteúdo já visto antes (boato reciclado) é verificado quase de graça contra o banco de fatos — entra na frente.

**Saída:** fila ordenada; o restante aguarda (não é descartado — pode subir se viralizar depois).

## Etapa 3 — Extração de alegações

**O que faz:** quebra a publicação em alegações atômicas (ver `02-modelo-de-veredito.md`) e classifica a centralidade de cada uma.

**Papel do modelo de linguagem aqui — e só aqui:** o modelo é usado como **extrator e localizador**, nunca como juiz. Ele extrai alegações, sugere a centralidade e formula consultas de busca por evidências. A decisão de veredito é uma **regra determinística** aplicada sobre as evidências retornadas (etapa 5). Essa separação é deliberada: modelos alucinam; regras não.

**Controles de qualidade da extração:**
- Cada alegação extraída precisa ser rastreável a um trecho literal da publicação original (citação com posição no texto).
- Alegações vagas demais ("o governo está destruindo o país") são marcadas como não-verificáveis e não geram veredito.
- Se nenhuma alegação verificável for extraída, a publicação é marcada como fora do escopo — e não recebe índice.

## Etapa 4 — Busca de evidências

**O que faz:** para cada alegação, consulta as fontes em ordem de precedência:

1. **Banco de fatos do portal:** verificações anteriores (alegação idêntica ou equivalente já decidida). É o que faz o sistema ficar mais rápido e preciso com o tempo.
2. **Fontes primárias oficiais:** Diário Oficial, registros de votação (Câmara/Senado), dados de IBGE/BC/Tesouro/TSE, notas oficiais de órgãos, transcrições e vídeos íntegros.
3. **Bases de checagem existentes** (Aos Fatos, Lupa, Fato ou Fake): usadas como **referência cruzada**, nunca como única prova de um veredito. Se só existir checagem de terceiros e nenhuma fonte primária, a alegação fica como "sem evidência primária" — o portal não terceiriza seu veredito.

**Regra de evidência:** uma alegação só é "confirmada" ou "contraditada" com fonte primária. Checagem de terceiros, matéria jornalística ou declaração de autoridade **não** bastam sozinhas — no máximo sustentam "sem evidência primária localizada", exibido como tal.

## Etapa 5 — Veredito (regras determinísticas)

**O que faz:** aplica o modelo de `02-modelo-de-veredito.md`:

1. Cada alegação recebe: Confirmada / Contraditada / Sem evidência, com as fontes linkadas.
2. Calcula-se o índice de veracidade pela fórmula.
3. Aplica-se a regra do veto (central contraditada → selo FALSO).
4. Determina-se a faixa e o rótulo exibido.
5. Gera-se o texto da análise em template fixo: o que foi dito → alegação por alegação com provas → conclusão. O texto é montado a partir de campos estruturados, não redigido livremente — isso garante uniformidade e impede que "opinião" entre pela redação.

**Limiar de publicação:** análises são publicadas automaticamente em qualquer faixa, **incluindo inconclusivo** — o inconclusivo é um produto legítimo do portal, não um rascunho. A única condição para não publicar é a ausência total de alegações verificáveis.

## Etapa 6 — Publicação e distribuição

**O que faz:** publica a análise no portal (página permanente, com URL estável e versionamento) e dispara as versões adaptadas para X, Instagram e canal de WhatsApp, conforme `06-distribuicao.md`. Cada post nas redes linka de volta para a análise completa no portal — a rede é vitrine, o portal é a prova.

## Infraestrutura de confiança do próprio sistema

- **Logs imutáveis:** cada decisão do sistema (captura, triagem, evidência consultada, veredito) é registrada com timestamp. O log é a prova de que o método foi seguido — e permite auditoria externa futura.
- **Versionamento:** qualquer mudança de veredito gera nova versão da análise, com a anterior preservada e o motivo da mudança registrado.
- **Monitoramento de deriva:** métricas contínuas de proporção de vereditos por espectro político dos emissores. Se o sistema passar a marcar desproporcionalmente um lado, isso é um sinal de alerta investigável (viés de fonte, de triagem ou de cobertura) — e o relatório é público.
- **Custo controlado:** a etapa mais cara é a busca de evidências; o banco de fatos e o agrupamento de duplicatas são o que mantêm o custo sob controle à medida que o volume cresce.
