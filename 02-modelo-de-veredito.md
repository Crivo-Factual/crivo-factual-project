# 02 — Modelo de veredito e índice de veracidade

## Unidade de análise: a alegação atômica

O portal nunca verifica "uma matéria" como um bloco. Cada publicação capturada é quebrada em **alegações atômicas**: uma afirmação factual por vez ("o Bolsa Família acabou", "o deputado X votou contra o projeto Y", "o valor do benefício caiu para R$ 500"). Uma publicação pode gerar várias alegações, cada uma com seu próprio veredito e suas próprias provas. Opiniões, previsões e juízos de valor não geram alegações — não há o que verificar neles.

## As quatro saídas possíveis por alegação

| Veredito | Critério |
|---|---|
| **Confirmada** | Fonte primária (documento oficial, dado de órgão público, registro audiovisual íntegro) confirma a alegação nos mesmos termos. |
| **Contraditada** | Fonte primária contradiz a alegação nos mesmos termos. |
| **Sem evidência** | Nenhuma fonte primária localizada que confirme ou contradiga. Não é "falso" — é ausência de prova. |
| *(não existe "meio-verdadeira" por alegação)* | A nuance vive no nível da publicação (abaixo), não da alegação. |

## Peso das alegações

Nem toda alegação vale o mesmo dentro de uma publicação. O sistema atribui peso por **centralidade**:

- **Alegação central (peso 3):** a afirmação principal da publicação — aquilo que o título/manute promete. Normalmente 1 por publicação.
- **Alegação de suporte (peso 1):** detalhes, números secundários, contexto factual que sustenta a tese.

A centralidade é determinada por regra: posição no texto (título, primeiro parágrafo, legenda do vídeo) + repetição ao longo do conteúdo.

## O índice de veracidade (0–100%)

O índice responde à pergunta do leitor: **"no conjunto das provas encontradas, esse conteúdo tende mais para verdadeiro ou para falso?"** Ele é calculado assim:

```
Sejam:
  Pc = soma dos pesos das alegações CONFIRMADAS
  Pf = soma dos pesos das alegações CONTRADITADAS
  Ps = soma dos pesos das alegações SEM EVIDÊNCIA
  Pt = Pc + Pf + Ps  (peso total)

Índice = 50 + 50 × (Pc − Pf) / Pt
```

**Por que essa fórmula:**

- Tudo confirmado → 100%. Tudo contraditado → 0%.
- Tudo sem evidência → 50% (o meio exato = inconclusivo, não "meio-verdadeiro").
- Alegações sem evidência puxam o índice para o centro (ignorância), **não** para o zero (falsidade). É a diferença entre "não sei" e "é mentira" — e o sistema nunca confunde as duas coisas.
- Uma alegação confirmada pesa tanto quanto uma contraditada; o que decide é o saldo das provas.

**Exemplos:**

| Caso | Cálculo | Índice |
|---|---|---|
| Central confirmada (3) + 2 suportes confirmados (1+1) | 50 + 50 × (5−0)/5 | **100%** |
| Central confirmada (3) + 1 suporte contraditado (1) + 1 sem evidência (1) | 50 + 50 × (3−1)/5 | **70%** |
| Central contraditada (3) + 2 suportes confirmados (1+1) | 50 + 50 × (2−3)/5 → mas ver regra do veto abaixo | **40% → travado em Falso** |
| Central sem evidência (3) + resto sem evidência | 50 + 50 × 0 | **50%** |
| Nada verificável (nenhuma alegação extraível) | — | **Sem índice** (publicação fora do escopo de verificação) |

## A regra do veto (a mais importante do modelo)

**Se a alegação central for contraditada por fonte primária, o veredito geral da publicação é FALSO, independentemente do índice aritmético.** Motivo: uma publicação cuja tese principal é falsa não vira "parcialmente verdadeira" porque os detalhes laterais estão certos. Nesse caso o portal exibe o índice calculado **e** o selo FALSO com a explicação: "a afirmação principal foi contraditada; detalhes secundários confirmados não alteram o veredito".

Sem a regra do veto, um texto que acerta 4 detalhes e erra a tese marcaria 70% e pareceria "mais verdadeiro" — exatamente o tipo de distorção que o portal existe para combater.

## A trava do centro

**Se a alegação central não tiver evidência primária (nem confirmada, nem contraditada), o veredito geral da publicação é INCONCLUSIVO e o índice é exibido em 50%, mesmo que alegações de suporte estejam confirmadas.** Motivo: sem prova sobre o ponto central, não há como o conteúdo tender a verdadeiro ou falso — os suportes confirmados descrevem o contexto, não provam a tese. O índice só se move quando a alegação central tem evidência. Texto exibido nesses casos: "a afirmação principal ainda não tem comprovação em fonte primária; o índice fica no centro até surgir prova".

## As faixas de leitura (o que o leitor vê)

| Índice | Rótulo exibido | Cor |
|---|---|---|
| 80–100% | **Verdadeiro** | Verde |
| 60–79% | **Predominantemente verdadeiro** | Verde-claro |
| 40–59% | **Inconclusivo** (tende a nenhum dos lados) | Amarelo |
| 20–39% | **Predominantemente falso** | Laranja |
| 0–19% | **Falso** | Vermelho |

Regras de exibição:

- O rótulo **sempre** vem acompanhado do índice, do número de alegações verificadas e da lista de alegações com o status de cada uma. Nunca um selo sozinho.
- O índice **não** é uma probabilidade ("72% de chance de ser verdade"). É uma medida de **sustentação por evidências encontradas até aquele momento**. O texto padrão do portal deixa isso explícito: *"Índice de sustentação pelas provas localizadas. Novas evidências podem alterá-lo."*
- O índice é **recalculado** automaticamente sempre que uma nova evidência entra no banco de fatos ou uma alegação muda de status — com histórico de versões (ver `07-confianca-riscos-legais.md`).

## O que o índice NÃO significa (texto obrigatório na metodologia pública)

1. Não mede a importância, a gravidade ou o caráter de quem publicou.
2. Não mede "intenção" (o sistema não sabe se o autor mentiu ou se enganou — e não afirma isso).
3. Não é uma nota de credibilidade permanente de um veículo ou pessoa: cada publicação tem seu índice; veículos acumulam apenas um histórico consultável.
4. Não substitui o julgamento do leitor: o índice resume as provas; a conclusão sobre "bom ou ruim" é do leitor.
