# 10 — Versão totalmente gratuita (R$ 0/mês)

## Decisão de base (30/10/2026)

O idealizador não tem previsão de orçamento para o projeto. A arquitetura passa a ser **free-first**: R$ 0 de custo em dinheiro por mês, aceitando limites de volume, velocidade e automação em dois canais. O que a gratuidade tira é escala e automação total nesses canais. O que ela **não** tira é o método: mesmas regras, mesmas fontes primárias, mesmo limiar de evidência, mesmo índice, mesma regra do veto e mesma trava do centro.

## O que fica DENTRO da versão gratuita

- **Portal:** páginas estáticas em Cloudflare Pages, Netlify ou GitHub Pages (este último exige repo público no plano gratuito — o que combina com a missão de transparência, quando o repo abrir).
- **Banco de fatos:** SQLite (arquivo, zero infraestrutura) ou tiers gratuitos de PostgreSQL gerenciado (Supabase, Neon) em escala de MVP.
- **Coleta:** RSS e dados abertos gratuitos e sem chave — Câmara, Senado, TSE, IBGE, Diário Oficial e portais oficiais.
- **Veredito:** código determinístico puro, custo zero. É o coração do método e não depende de nenhuma API paga.
- **Extração de alegações:** em duas camadas gratuitas. Primeira, regras determinísticas (números, datas, citações, padrões de boato reciclado) — grátis e ilimitado. Segunda, modelos em tier gratuito com limite (Groq free tier, OpenRouter com modelos `:free`, Gemini free tier) atrás de fila com teto diário. A extração fica mais lenta e menos confiável, mas o veredito continua determinístico, porque o modelo só extrai e localiza, nunca decide.
- **Instagram:** Graph API gratuita para postar (exige conta empresarial e app Meta, sem taxa por post). O custo é burocrático, não financeiro.
- **Boletim:** tiers gratuitos de e-mail (Resend, Brevo) dentro do limite mensal.
- **Automação e observabilidade:** GitHub Actions no limite gratuito e logs próprios.

## O que fica FORA (ou racionado) na versão gratuita

### Monitoramento do X via API oficial — FORA
Desde fevereiro de 2026 não existe tier gratuito para novos desenvolvedores no X. O modelo atual é pay-per-use, verificado em outubro de 2026: US$ 0,005 por post lido, com teto de 3 milhões de leituras por mês. Uma busca que retorna 100 posts custa US$ 0,50. Dez buscas por dia nesse volume custam cerca de US$ 150 por mês. Os antigos planos Basic (US$ 200/mês) e Pro (US$ 5.000/mês) estão fechados para novos cadastros. Ou seja: monitorar o X em escala pela API oficial é incompatível com R$ 0.

Substitutos gratuitos: RSS, dados abertos, alertas e tendências, veículos e canais públicos. Limitação honesta: a triagem por viralização especificamente no X fica enfraquecida. Um boato que nasce e morre só no X pode demorar mais a ser detectado, porque o portal passa a encontrá-lo quando ele transborda para outros lugares, o que na prática acontece com a maioria dos boatos relevantes.

### Postagem no X via API — RACIONALIZADA OU MANUAL
Postar também é pay-per-use: US$ 0,015 por post sem link e US$ 0,20 por post **com link**. O formato do Crivo Factual exige link no fim da mensagem, então cada post do portal custaria US$ 0,20. Cinco posts por dia sairiam por cerca de US$ 30 por mês. Sem link, os mesmos cinco posts custariam cerca de US$ 2,25 por mês, mas quebrariam a promessa do formato, que é levar o leitor ao detalhamento.

Na versão gratuita, o caminho honesto para o X é um destes: postagem manual pelo aplicativo do X (grátis, mas quebra a automação total nesse canal); racionamento extremo (só os vereditos mais importantes, dentro de créditos iniciais pontuais que o X oferece a contas novas); ou pleito de classificação como Public Utility App, que o X concede a apps que ele mesmo classifica como utilidade pública, com acesso gratuito ampliado — uma tentativa paralela válida, sem garantia, que não pode ser o plano principal.

### Broadcast automatizado no WhatsApp — FORA (em massa)
A Cloud API do WhatsApp não cobra acesso, mas cobra por mensagem entregue, por categoria e por país. A única franquia gratuita é de 1.000 mensagens de serviço por mês por número (a partir de outubro de 2026), e ela vale para conversas iniciadas pelo usuário, não para broadcast. A mensagem do portal é um template de marketing, pago desde a primeira mensagem entregue. Não há franquia gratuita para broadcast.

Na versão gratuita, o caminho honesto é o Canal do WhatsApp com postagem manual (grátis, mas quebra a automação) ou a Business API restrita ao que cabe na franquia de serviço, sem broadcast automático em massa. As taxas do Brasil variam por categoria e estão na tabela do Gerenciador do WhatsApp da Meta — conferir lá antes de qualquer estimativa em reais.

### Multimídia pesada (Onda 3) — ADIADA OU LOCAL
Transcrição e visão por API paga ficam fora. A alternativa gratuita é processamento local (por exemplo, Whisper local para áudio) em hardware próprio: viável, mas lento, e fora do escopo do MVP.

### SLA de 24h para os 10 virais do dia — EM RISCO
Sob rate limits gratuitos, a meta de verificar os 10 boatos mais virais em menos de 24h vira melhor esforço com fila, até haver orçamento. A fila prioriza o que tem mais alcance, e o portal publica o que consegue verificar com o limiar intacto, nunca mais rápido do que as provas permitem.

## Resumo em uma frase

Na versão gratuita, o portal verifica tudo que consegue capturar por fontes gratuitas, com o mesmo método e o mesmo rigor, publica no portal e no Instagram de forma automatizada, e distribui no X e no WhatsApp de forma manual ou racionada até haver orçamento — sem jamais baixar o limiar de evidência para publicar mais rápido.
