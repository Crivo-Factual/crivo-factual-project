# Cobertura das fontes candidatas — medida na fila (12/11/2026)

Pergunta: mais fontes primárias resolvem o gargalo de evidências?
Resposta medida: **não, no mix atual de alegações. As fontes novas cobrem 0%.**

## Método

Sonda sobre as alegações já extraídas (`claims`, 48 itens, 208
alegações) e, como proxy, sobre os títulos dos 224 itens pendentes.
Uma alegação só conta como coberta se carregar informação suficiente
para formar uma consulta determinística naquela fonte. Script
reprodutível em `scripts/probe_coverage.py`.

## Resultado — alegações (48 itens, 208 alegações)

| Fonte | Alegações | Itens | % itens |
|---|---|---|---|
| Proposições (Câmara/Senado — já existe) | 6 | 6 | 12,5% |
| DOU (sanção/promulgação/decreto) | 0 | 0 | 0% |
| Indicadores (BCB SGS / IBGE SIDRA) | 0 | 0 | 0% |
| Votações (Câmara) | 0 | 0 | 0% |
| TSE (eleitoral) | 0 | 0 | 0% |
| Índice local de ementas | 0 | 0 | 0% |

- Itens cobertos por qualquer fonte nova: **0**.
- Itens cobertos por qualquer fonte: **6 (12,5%)**.
- Dos 45 Inconclusivo, só **3 (6,7%)** virariam cobertos — os 3 com
  referência a proposição que não confirmaram (os outros 3 com ref já
  são os Verdadeiros com prova).

Correção no caminho: a primeira rodada da sonda marcou 2 alegações
como TSE — eram falsos positivos de "Wall Street Journal" (a
substring "urna" dentro de "Journal"). Palavras curtas passaram a ser
casadas com fronteira de palavra; TSE real = 0.

## Resíduo — alegações sem consulta possível

- **50 alegações (24%) são números soltos** ("70%", "R$ 60") — sem
  assunto, sem fonte, sem data. Nenhuma fonte responde isso.
- **5 são citações** ("disse", "afirmou") — exigem o discurso original.
- **25 de 208 (12%) contêm HTML ou URL** — fragmentos de markup e
  links de imagem do g1 extraídos como alegação.
- **61 de 208 (29%) são fragmentos numéricos curtos.**

## Proxy — títulos pendentes (224 itens)

- Com referência a proposição: 79 (35,3%) — mas **55 são só a
  referência** (título curto, ex.: "PL 05827/2026", vindo do coletor
  de proposições da Câmara); **só 24 são notícia com ref no título**.
- DOU, indicador, votação e TSE: 0 nos títulos também.
- Composição da fila pendente: g1 110, senado_tramitando 52,
  camara_proposicoes 49, poder360 12, senado_noticias 1. A fila é
  dominada por notícia geral do g1 (crime, local) e por listagens
  cruas de proposições — o material verificável é minoria do fluxo.

## Achados (ordem de impacto medido)

1. **A extração perde a referência.** A notícia traz o nº da
   proposição no título, mas a alegação extraída não o carrega: as
   regras extraem números soltos e o LLM extrai a frase de status sem
   o número. O caminho de busca por proposição já existe — falta a
   alegação chegar a ele com a referência junto.
2. **O LLM traduz as alegações para o inglês.** As alegações recentes
   (ex.: q225) saem em inglês, embora o texto seja pt-BR. Isso quebra
   a confirmação por contenção na ementa oficial (que é em português).
   A extração deve responder na língua da fonte.
3. **Alegações lixo poluem a base.** 12% com HTML/URL e 29% de números
   soltos. O resumo precisa ser limpo de markup antes da extração, e
   URLs não são alegação.
4. **A triagem alimenta os itens errados.** O proxy de score prioriza
   o g1 (40) — notícia geral — e as listagens cruas de proposições
   ocupam 101 dos 224 itens pendentes. O material com ref é minoria.
5. **Fontes novas medem 0% no mix atual.** DOU, BCB/SIDRA, votações e
   TSE não aparecem em nenhuma alegação nem em nenhum título
   pendente. Construí-las agora é trabalho sem retorno medido.
   Reavaliar quando o mix mudar (ex.: cobertura de economia).

## Conclusão

O teto de cobertura com as fontes atuais é ~12,5% dos itens — e com
todas as fontes candidatas juntas, continua ~12,5%, porque o problema
não é a falta de fontes e sim a alegação chegar sem a informação que
a fonte precisa. O próximo passo de maior impacto é corrigir a
extração (manter a referência na alegação, responder em pt-BR, limpar
HTML), seguido da triagem. O aceite da #47 (<50% inconclusivos) é
inalcançável nesse mix de feed, qualquer que seja o número de fontes.

## Pós-correção da extração (12/11/2026)

- Lixo (HTML/URL) nas alegações: **0** na rodada pós-correção
  (era 12%). Inglês: **0** (era maioria das alegações do LLM).
- Teste dirigido (EMC 1/2026, item q271): 3 alegações em pt-BR com a
  referência; veredito Predominantemente verdadeiro (75%) — a
  referência confirmou por existência; as 3 alegações de conteúdo
  ficaram sem evidência porque a API devolve 5 registros diferentes
  para "EMC 1/2026" e o cliente usa o primeiro (ver DEVELOPMENT.md,
  seção #47 — desambiguação por ementa pendente).
- Efeito colateral correto: 5 de 10 itens da rodada saíram como Sem
  índice — os resumos eram só uma tag `<img>`; antes geravam páginas
  Inconclusivo com alegações lixo. Itens sem conteúdo real agora
  saem da fila como fora de escopo, sem página.
