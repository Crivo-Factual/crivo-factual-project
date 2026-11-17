"""Classificador de veracidade de notícias em português (Fake.Br Corpus).

O que este módulo É: um sinal de triagem. Ele estima a probabilidade
de um texto ser notícia falsa e serve para PRIORIZAR a fila do Crivo
(o que é mais suspeito é verificado primeiro).

O que este módulo NÃO É: um juiz. Ele NUNCA decide um veredito. O
veredito do Crivo continua sendo decidido por regras determinísticas
sobre fontes primárias (Câmara, Senado, DOU) — ver
`crivo/pipeline/verdict.py`. Um texto com suspeita 0,99 e outro com
0,01 passam pelo mesmo crivo: sem fonte primária, os dois saem
Inconclusivo.

Corpus: Fake.Br Corpus (Monteiro et al., 2018, PROPOR) — 7.200
notícias em português brasileiro, 3.600 falsas + 3.600 verdadeiras,
em pares alinhados (falsa e verdadeira sobre o mesmo fato).
O corpus NÃO vai para o repositório: baixe de
https://github.com/roneysco/Fake.br-Corpus e aponte --corpus.
"""

STOPWORDS_PT = frozenset("""
a ao aos aquela aquelas aquele aqueles aquilo as até com como da das de
do dos e ela elas ele eles em entre era eram essa essas esse esses esta
estas este estes eu foi foram havia isso isto já lhe lhes mais mas me
meu meus minha minhas muito na nas nem no nos não nós o os ou para pela
pelas pelo pelos por qual quando que quem se seja sejam sem ser seu seus
só sua suas são também tem têm tenho ter teu teus tua tuas um uma umas
uns você vocês vos é és somos sois estou está estão estava estavam
estive esteve estivemos estiveram seja sejamos sejam sendo sido ter
tendo tido haja hajamos hajam havemos havendo havido hei havemos hão
houve houvemos houveram houverei houverá houveremos houverão houveria
houveríamos houveriam assim bem cada demais depois donde embaixo encima
então frente fora hoje lá logo mal menos muito nunca onde ontem pouco
porque portanto quando quanto sempre sobre tudo vai vamos vão ir indo
ida ido pode podem podia podiam possa possam poder podendo podido devo
devem devia deviam deva devam dever devendo devido dizer diz dizem
disse disseram fazer faz fazem fez fizeram ficar fica ficam ficou
ficaram saber sabe sabem soube souberam ver vê veem viu viram dar dá
dão deu deram querer quer querem quis quiseram
""".split())
