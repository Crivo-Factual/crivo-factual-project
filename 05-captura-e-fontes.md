# 05 — Captura e fontes

## Princípio

Capturar o máximo dentro do que cada plataforma **permite oficialmente**. Nada de scraping contra termos de uso como base do sistema: uma fonte que pode ser bloqueada amanhã não pode sustentar o produto. Onde a API oficial é paga, o custo entra no orçamento (ver `08-stack-fases-metricas.md`).

## Fontes de captura

### Google e web aberta
- **Google Notícias / RSS** de veículos, agências (Agência Brasil, Senado, Câmara) e blogs políticos relevantes.
- **Alertas por palavras-chave** (temas das editorias de `04-cobertura-mvp.md`).
- **Busca reversa de imagem e vídeo** para detectar conteúdo fora de contexto ou reciclado.
- Limite: a web aberta é a fonte mais completa e barata; o desafio é volume, resolvido pela triagem.

### Fontes oficiais (a espinha dorsal da evidência)
- Diário Oficial da União (e diários estaduais para repercussão nacional).
- Dados abertos da Câmara e do Senado (proposições, votações nominais, discursos).
- STF, STJ, TSE (decisões, pautas, comunicados).
- IBGE, Banco Central, Tesouro, SOF/MPO (números).
- Notas oficiais de ministérios, PF, PGR, TCU, CGU.
- Essas fontes alimentam **tanto a captura quanto a evidência**: uma nota oficial é notícia a verificar e prova para verificar outras.

### X (Twitter)
- **Publicação:** API oficial, plano pago — viável.
- **Monitoramento:** API oficial de busca, plano pago, com custo que escala com o volume. É a rede onde mais circula desinformação política, então o custo aqui é prioritário no orçamento.
- **O que não fazer:** scraping da web do X como base — bloqueios frequentes e violação de termos.

### Instagram
- **Publicação:** API oficial (Graph API) para conta empresarial — feed, carrossel e reels viáveis; stories com limitações.
- **Monitoramento:** restrito pela API. A captura de conteúdo circulante no Instagram é a mais fraca do sistema — compensa-se com monitoramento de contas públicas relevantes via fontes secundárias legítimas e com denúncias de leitores (link "sugerir checagem", sem moderação humana no fluxo principal: a sugestão entra na fila de triagem como qualquer outra fonte).

### WhatsApp — ajuste de escopo importante
- **Não existe API pública para monitorar grupos ou comunidades.** O portal não captura o que circula no WhatsApp.
- **O que funciona:** canal de transmissão (WhatsApp Channels) alimentado automaticamente pela API oficial do WhatsApp Business — o portal **empurra** verificações para inscritos.
- **Consequência:** no WhatsApp, o portal é emissor, não observador. Boatos que circulam só no WhatsApp chegam ao sistema quando já tiverem vazado para a web ou quando leitores os submeterem pelo formulário de sugestão.
- Comunidade de debate no WhatsApp exigiria moderação humana e, por isso, **não faz parte do produto automatizado** (pode existir como iniciativa separada, fora da promessa de automação total).

### Outras redes
- TikTok, YouTube, Facebook: monitoramento via APIs oficiais onde disponível; caso contrário, via republicações e links que chegam à web aberta. Vídeos são tratados como publicações (transcrição automática → extração de alegações, como texto).

## Sugestões de leitores

O formulário "sugerir uma checagem" é uma fonte de captura como outra qualquer: entra na fila de triagem e segue o mesmo pipeline. Não cria atendimento humano nem promessa de prazo — a prioridade segue sendo viralização.

## Triagem em números (ordens de grandeza do MVP)

- Captura bruta estimada: milhares de itens/dia (RSS + redes + DOU).
- Após deduplicação e filtro temático: centenas/dia.
- Após triagem por viralização + verificabilidade: **dezenas de verificações/dia** no MVP — volume compatível com publicação automática e com a atenção do público.
- O número exato é calibrado nas primeiras semanas: se o volume de "inconclusivos" explodir, o limiar de viralização sobe; se sobrar capacidade, desce.
