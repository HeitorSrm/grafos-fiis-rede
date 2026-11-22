# Camada A — inquilinos, peso Jaccard e backbone com empates

Três correções na Camada A, cada uma com o problema que resolve e o teste que
a sustenta. Reproduzir: `python src/frente2.py` (saída em `out/frente2/`). O
código está em `src/camadas.py` (`carregar_atributos`, `grafo_estrutural` e
`backbone_knn`).

## Resumo

| Decisão | Problema que resolve |
|---|---|
| Inquilino só para fundos de tijolo | descrições de lastro viravam "inquilinos" falsos e geravam as 4 arestas mais fortes do grafo |
| Peso = Jaccard ponderado pelo idf | a soma favorecia quem tem mais atributos e empatava quase tudo |
| Backbone mantém empates com a k-ésima aresta | o desempate era decidido pela ordem das linhas da planilha |

Resultado final: 122 arestas, densidade 0,118, grau médio 5,3, conexa,
6 comunidades, modularidade 0,574, ARI com o segmento 0,519. Grafo idêntico
em qualquer ordem das linhas.

## 1. Inquilino só para fundos de tijolo

**Problema.** O campo `inquilinos` da planilha tem três situações:

| Situação | Fundos | Tratamento anterior |
|---|---|---|
| Lista genérica de devedores de CRI ("Brookfield, Cyrela, MRV…") | 16 de Papel | já ignorada (repetida em mais de 4 fundos) |
| Lista genérica de lojistas ("Lojas Renner, C&A…") | 8 Shoppings | já ignorada (idem) |
| Descrição do lastro: "cotas de outros FIIs…" | 3 FoF | **passava** (só 3 fundos) |
| Descrição do lastro: "CRAs de produtores rurais…" | 2 Fiagro | **passava** (só 2 fundos) |

Os nomes das listas genéricas são reais e plausíveis; o problema é não serem
específicos por fundo. As descrições de FoF e Fiagro eram quebradas pelo
separador de vírgulas em quatro itens cada (`"kncr11"`, `"pvbi11)"`,
`"empresas como minerva"`…), que contavam como inquilinos raros em comum:

| Aresta | Peso (soma do idf) | Posição |
|---|---|---|
| VGIA11–XPCA11 | 15,7 | 1ª mais forte do grafo |
| BCIA11–HFOF11, BCIA11–KFOF11, HFOF11–KFOF11 | 13,7 | 2ª a 4ª |
| BTLG11–LVBI11 (segmento + 3 inquilinos reais) | 9,9 | 5ª |

**Correção.** Inquilino só existe em Logística, Shoppings, Lajes, Renda
Urbana e Híbrido. Papel, FoF e Fiagro não têm locatário. Ficam com inquilinos
19 dos 26 fundos de tijolo (os 7 shoppings têm a lista genérica).

**Efeito.** Pequeno em número de arestas, grande no resultado: com o Jaccard,
o ARI com o segmento vai de 0,733 (com os itens falsos) para 0,519. O valor
mais alto vinha de os itens falsos manterem FoF e Fiagro artificialmente
unidos.

## 2. Peso: Jaccard ponderado pelo idf

**Problema.** O peso anterior somava o idf dos itens em comum:

- favorecia quem tem mais atributos: peso médio intra-Logística 4,75 contra
  1,31 intra-Papel no backbone (3,6 vezes), só porque tijolo tem inquilino
  para somar;
- tinha resolução baixa: o peso só dependia de *quais* itens coincidem.
  Eram 20 valores distintos em 233 arestas; 60% existiam só pelo segmento, e
  97 das 105 arestas internas do Papel valiam exatamente 1,121.

**Correção.**

$$w_A(i,j) = \frac{\sum_{q \in A_i \cap A_j} \mathrm{idf}(q)}{\sum_{q \in A_i \cup A_j} \mathrm{idf}(q)}, \qquad \mathrm{idf}(q) = \ln\frac{N}{n_q}$$

A fração do perfil conjunto dos dois fundos que é compartilhada, entre 0 e 1.
Mantém o idf (compartilhar algo raro vale mais) e normaliza pelo que cada
fundo tem.

**Teste.** Quatro fórmulas sob as mesmas regras (inquilino só de tijolo,
backbone k = 3 com empates), em `out/frente2/08_comparacao_peso_a.csv`:

| Fórmula | Arestas | Pesos distintos | Densidade | Modularidade | ARI | Viés de cobertura | Intra Log ÷ Papel |
|---|---|---|---|---|---|---|---|
| soma do idf | 191 | 20 | 0,185 | 0,549 | 0,646 | +0,73 | 3,63 |
| **Jaccard ponderado** | **122** | **114** | **0,118** | **0,574** | **0,519** | **−0,72** | **0,49** |
| cosseno (TF-IDF) | 118 | 115 | 0,114 | 0,598 | 0,297 | −0,58 | 0,75 |
| Gower | 203 | 15 | 0,196 | 0,420 | 0,690 | −0,88 | 0,77 |

Arestas e métricas são do backbone; pesos distintos, do grafo completo.
"Viés de cobertura" é a correlação entre o número de itens de um fundo e a
força média das suas arestas no grafo completo.

**Por que o Jaccard.** Cinco vezes mais resolução de peso que a soma,
densidade próxima das Camadas B (0,066) e C (0,092), peso entre 0 e 1 e
fácil de explicar ("fração do perfil compartilhada"). Permite incluir no
futuro um atributo que só exista para um tipo de fundo, como o `indexador`
para Papel, sem favorecer esse tipo. O cosseno perde a relação com o setor;
o Gower volta a ter poucos valores de peso e fica denso.

**Limitação.** Nenhuma fórmula é neutra em relação à cobertura dos dados. A
soma favorece os fundos com mais atributos; o Jaccard os penaliza, porque
itens que o par não compartilha entram no denominador. Exemplo: HGLG11–XPLG11
(Logística + inquilino Mercado Livre) pesa 0,146, menos que KNCR11–RECR11
(só Papel), 0,160. Comparar pesos **entre** segmentos exige essa ressalva;
**dentro** do mesmo segmento vale.

**Sobre o ARI.** Ele cai em relação à soma (0,646 → 0,519). Isso não é um
problema: o segmento é entrada da Camada A, então ARI alto ali mede em parte
tautologia. O ARI é validação, não objetivo.

## 3. Backbone mantendo empates

**Problema.** O backbone guardava exatamente as k arestas mais fortes de cada
fundo. Com pesos empatados, quem decidia era a ordem das linhas da planilha.
Teste com a soma do idf, antes das outras correções: 29 dos 46 fundos tinham
empate no corte k = 3, e embaralhar só a ordem das linhas mudava o grafo.

| Configuração (soma do idf) | Arestas | Arestas iguais à original | Comunidades | Modularidade | ARI |
|---|---|---|---|---|---|
| Backbone k=3, ordem original | 98 | 98/98 | 6 | 0,656 | 0,452 |
| Mesmo backbone, linhas embaralhadas (1) | 99 | 69/98 | 6 | 0,637 | 0,404 |
| Mesmo backbone, linhas embaralhadas (2) | 95 | 74/98 | 7 | 0,627 | 0,338 |

**Correção.** Cada fundo guarda as k arestas mais fortes e também as que
empatam com a k-ésima. O Jaccard reduz os empates (15 fundos no corte, contra
29), mas não os elimina: fundos que coincidem em tudo o que foi coletado são,
para a Camada A, de fato iguais. Esses empates são reais e ficam no grafo.

**Teste.** Com o Jaccard e a regra de empates, o grafo é idêntico (arestas e
pesos) em 200 ordens aleatórias das linhas da planilha. Sem a regra, as
mesmas ordens produziriam 21 grafos diferentes em 30.

**Robustez a tirar um fundo.** Removendo um fundo por vez (46 casos), a
Camada A continua conexa em todos, com densidade mediana de 0,121 e ARI entre
0,38 e 0,57. Em 39 casos a densidade fica entre 0,117 e 0,127. Nos outros 7
(os seis fundos da Kinea e o XPCA11) ela sobe para 0,130–0,145, por um
mecanismo previsível: fundos de Papel da mesma gestora (os quatro da Kinea;
HABT11 e MXRF11, da XP) têm exatamente 3 vizinhos fortes pela gestora. Tirando
um deles, a 3ª aresta passa a ser "só Papel", que empata com os demais fundos
de Papel, e a regra guarda todos os empates. É a regra funcionando como deve:
na falta de um terceiro vizinho preferido, ela não escolhe um arbitrariamente.

## Escolha do k

Varredura em `out/frente2/03_sensibilidade_camada_a.csv`:

| k | Arestas | Densidade | Grau médio | Componentes | Modularidade | ARI | Grau médio da Camada C |
|---|---|---|---|---|---|---|---|
| 1 | 62 | 0,060 | 2,7 | 10 | 0,701 | 0,542 | — |
| 2 | 109 | 0,105 | 4,7 | 1 | 0,574 | 0,460 | 2,9 |
| **3** | **122** | **0,118** | **5,3** | **1** | **0,574** | **0,519** | **4,1** |
| 4 | 144 | 0,139 | 6,3 | 1 | 0,527 | 0,408 | 5,5 |
| 6 | 193 | 0,186 | 8,4 | 1 | 0,478 | 0,405 | 8,2 |

Com o Jaccard a Camada A já é conexa em k = 2, então "menor k conexo" deixou
de decidir sozinho. Critério: menor k que deixa A e C com grau médio acima
de 3, alinhado à Camada B. Entre os valores conexos, a modularidade da
Camada A é máxima em k = 2 e 3 e cai a partir de k = 4.

## Figura

`out/frente2/11_camada_a.png`. As figuras das três camadas passaram a usar o
layout de Kamada-Kawai (distância em saltos): o layout anterior usava o peso
como força de atração e, com os pesos entre 0 e 1 do Jaccard, espalhava os
segmentos. Na figura nova cada segmento forma um bloco, e as ligações entre
blocos são gestora ou inquilino em comum.
