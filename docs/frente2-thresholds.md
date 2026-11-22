# Frente 2 — calibragem dos limiares

Documento técnico da frente de modelagem formal. Registra os cinco limiares
do projeto, o que foi testado e por que cada valor foi escolhido.

Reproduzir: `python src/frente2.py` (saída em `out/frente2/`).

Amostra: 46 FIIs, 497 pregões (02/01/2023 a 30/12/2024).

## Tabela final

| Limiar | Valor | Camada | Critério |
|---|---|---|---|
| `COBERTURA_MIN` | 0,90 | dados | fundo precisa de cotação real em 90% do período |
| `ZEROS_MAX` | 0,30 | dados | acima disso o preço está travado, não parado por falta de co-movimento |
| `K_BACKBONE_A` | 3 | A | menor k que deixa A e C com grau médio acima de 3 |
| `RHO_MIN_B` | 0,32 | B | percentil 95 da correlação entre pares |
| `K_KNN_C` | 3 | C | mesmo k e mesma regra da Camada A |

Resultado nas três camadas (`out/frente2/06_camadas_calibradas.csv`):

| Camada | Arestas | Densidade | Grau médio | Componentes | Isolados | Comunidades | Modularidade | ARI com segmento |
|---|---|---|---|---|---|---|---|---|
| A — Jaccard + backbone k=3 | 122 | 0,118 | 5,3 | 1 | 0 | 6 | 0,574 | 0,519 |
| B — MST ∪ ρ ≥ 0,32 | 68 | 0,066 | 3,0 | 1 | 0 | 5 | 0,422 | 0,210 |
| C — kNN k=3 | 95 | 0,092 | 4,1 | 1 | 0 | 6 | 0,664 | 0,122 |

As três ficam conexas, sem fundos isolados, com grau médio entre 3,0 e 5,3 e
densidade entre 0,066 e 0,118. Isso é deliberado: se as camadas tivessem
densidades muito diferentes, a comparação entre elas mediria a calibragem em
vez da estrutura.

## 1 e 2. Qualidade dos dados

O CSV de preços não tem nenhum valor ausente, o que é artificial: a coleta
aplicou `ffill().bfill()`, então todo fundo sem histórico no início da janela
recebeu o primeiro preço real copiado para trás. GARE11 fica com o mesmo
preço por 292 pregões, PVBI11 por 269, HSLG11 por 271.

Preço parado produz retorno zero. Fundos que destravam na mesma data passam
metade da série com retorno zero simultâneo, o que a correlação de Pearson lê
como concordância — apareceriam como um agrupamento de fundos que na verdade
ainda não existiam.

Dois critérios, para duas patologias diferentes:

- **`COBERTURA_MIN = 0,90`** remove o fundo que não era negociado no início da
  janela. O trecho inicial copiado é apagado antes da contagem.
- **`ZEROS_MAX = 0,30`** remove o fundo cujo preço trava no meio da série, por
  iliquidez ou falha da fonte. CPTS11 tem 98,6% de cobertura e mesmo assim 81%
  dos pregões com retorno zero: o preço repete por semanas seguidas.

Nove dos 55 fundos saem (`out/frente2/00_fundos_removidos.csv`). Encurtar a
janela recuperaria parte deles — começando em 2024 sobrariam 53 fundos — mas
com 251 pregões a razão entre observações e ativos cai de 10,8 para 4,7 e a
matriz de correlação fica bem mais ruidosa. Optou-se por manter a janela de
dois anos.

## 3. Camada A — Jaccard ponderado + backbone kNN, k = 3

Justificativa detalhada, com os testes, em
[`frente2-camada-a.md`](frente2-camada-a.md).

### 3.1 Atributos

`indexador` e `tipo_imovel` nunca foram coletados: estão como `n/a` nos 46
fundos e não geram aresta nenhuma. `tipo_fundo` saiu porque gerava aresta sem
carregar informação: ele é função determinística do segmento, então duplicava
o peso do setor e ligava qualquer par de fundos de tijolo. **200 das 433
arestas existiam apenas por causa dele**, e 340 das 433 não diziam nada além
do setor compartilhado.

**Inquilino só conta para fundos de tijolo** (Logística, Shoppings, Lajes,
Renda Urbana e Híbrido). Em Papel, FoF e Fiagro não há locatário: a planilha
traz uma descrição genérica do lastro, a mesma para todos os fundos do
segmento (os mesmos 11 devedores de CRI em 16 fundos de papel). Os nomes são
reais e o dado não foi inventado, ele só não é específico por fundo. Além
disso, as descrições de FoF ("cotas de outros FIIs…") e Fiagro ("CRAs de
produtores rurais…") eram quebradas pelo separador de vírgulas em quatro
"inquilinos" falsos cada, e geravam as quatro arestas mais fortes do grafo
inteiro. Listas idênticas em mais de quatro fundos continuam ignoradas (é o
caso da lista de lojistas dos shoppings). Ficam com inquilinos 19 dos 26
fundos de tijolo.

### 3.2 Peso: Jaccard ponderado pelo idf

$$w_A(i,j) = \frac{\sum_{q \in A_i \cap A_j} \mathrm{idf}(q)}{\sum_{q \in A_i \cup A_j} \mathrm{idf}(q)}, \qquad \mathrm{idf}(q) = \ln\frac{N}{n_q}$$

É a fração do perfil conjunto dos dois fundos que é compartilhada, entre 0 e
1. A versão anterior somava o idf dos itens em comum, o que tinha dois
defeitos:

- **favorecia quem tem mais atributos**: peso médio intra-Logística 4,75
  contra 1,31 intra-Papel no backbone, só porque tijolo tem inquilino para
  somar;
- **resolução baixa**: o peso só dependia de *quais* itens coincidem. Eram
  20 valores distintos em 233 arestas, 60% delas existindo só pelo segmento;
  97 das 105 arestas internas do Papel valiam exatamente 1,121.

Evolução da camada, uma decisão por linha
(`out/frente2/02_evolucao_camada_a.csv`):

| Configuração | Arestas | Pesos distintos | Densidade | Grau médio | Modularidade | ARI |
|---|---|---|---|---|---|---|
| 1. com `tipo_fundo`, soma do idf | 433 | 27 | 0,418 | 18,8 | 0,455 | 0,558 |
| 2. sem `tipo_fundo`, soma do idf | 233 | 20 | 0,225 | 10,1 | 0,513 | 0,724 |
| 3. sem `tipo_fundo`, Jaccard | 233 | 114 | 0,225 | 10,1 | 0,474 | 0,428 |
| **4. Jaccard + backbone k=3** | **122** | **61** | **0,118** | **5,3** | **0,574** | **0,519** |

Fórmulas comparadas sob as mesmas regras (inquilino só de tijolo, backbone
k = 3 com empates), em `out/frente2/08_comparacao_peso_a.csv`. Arestas e
métricas são do backbone; pesos distintos, do grafo completo. "Viés de
cobertura" é a correlação entre o número de itens de um fundo e a força média
das suas arestas: positivo favorece quem tem mais atributos, negativo
penaliza.

| Fórmula | Arestas | Pesos distintos | Densidade | Modularidade | ARI | Viés de cobertura | Intra Log ÷ Papel |
|---|---|---|---|---|---|---|---|
| soma do idf | 191 | 20 | 0,185 | 0,549 | 0,646 | +0,73 | 3,63 |
| **Jaccard ponderado** | **122** | **114** | **0,118** | **0,574** | **0,519** | **−0,72** | **0,49** |
| cosseno (TF-IDF) | 118 | 115 | 0,114 | 0,598 | 0,297 | −0,58 | 0,75 |
| Gower | 203 | 15 | 0,196 | 0,420 | 0,690 | −0,88 | 0,77 |

O Jaccard foi escolhido por: cinco vezes mais resolução de peso que a soma,
densidade próxima das Camadas B e C, peso limitado a [0, 1] e fácil de
explicar. O cosseno tem resolução parecida, mas perde a relação com o setor
(ARI 0,297). O Gower equilibra melhor os segmentos, mas volta a ter poucos
valores de peso (15) e fica denso. Nenhuma fórmula é neutra em relação à
cobertura: a soma favorece os fundos com mais atributos e as normalizadas os
penalizam (ver Limitações).

O ARI cai em relação à soma, e isso não é um problema: o segmento é entrada da
Camada A, então ARI alto ali mede em parte tautologia. O ARI é validação, não
objetivo.

### 3.3 Redução: backbone kNN, mantendo empates

**Por que não cortar por peso.** Um limiar global apaga primeiro o grupo cujas
arestas têm peso menor, e isso depende da fórmula, não da similaridade.
Cortando na mediana: com a soma, o Papel perde 97 das 105 arestas internas
(o peso de uma aresta "só segmento" é `ln(N / tamanho do segmento)`, menor
nos segmentos grandes); com o Jaccard, a Logística perde 18 de 21 e as Lajes
perdem todas (o denominador é maior para quem tem mais atributos). Nos dois
casos o corte destrói segmentos inteiros, incluindo o Papel, o de maior risco
de concentração.

**O backbone kNN** troca a pergunta: em vez de "esta aresta é forte em termos
absolutos?", pergunta "esta aresta está entre as k mais fortes deste fundo?".
Cada fundo guarda as suas k ligações de maior peso e o grafo é a união dessas
escolhas. A seleção é interna a cada fundo, portanto invariante ao tamanho
do segmento e à escala do peso, e nenhum fundo fica isolado. É a mesma
mecânica da Camada C.

**Empates com a k-ésima aresta são mantidos.** Sem isso, entre arestas de
mesmo peso, quem decidia era a ordem das linhas da planilha, e o grafo não
era reprodutível. Com a regra, o grafo é idêntico em qualquer ordem.

**Escolha do k** (`out/frente2/03_sensibilidade_camada_a.csv`): com o Jaccard
a Camada A já fica conexa em k = 2, então "menor k conexo" deixou de decidir
sozinho. Critério: menor k que deixa A e C com grau médio acima de 3,
alinhado à Camada B (com k = 2, a Camada C fica com grau 2,9). Na Camada A,
entre os valores que deixam o grafo conexo, a modularidade é máxima em k = 2
e 3 (0,574) e cai a partir de k = 4 (0,527).
Adotou-se k = 3.

## 4. Camada B — MST ∪ ρ ≥ 0,32

A distribuição de correlação entre os pares é estreita: mediana 0,185,
percentil 95 em 0,315 e máximo 0,484. Com uma distribuição assim, limiar
nenhum funciona sozinho — ou mantém quase tudo, ou despedaça o grafo:

| Configuração | Arestas | Componentes | Isolados | Maior componente | Modularidade |
|---|---|---|---|---|---|
| só limiar ρ ≥ 0,25 | 217 | 6 | 5 | 89% | 0,155 |
| só limiar ρ ≥ 0,30 | 77 | 19 | 18 | 61% | 0,246 |
| só limiar ρ ≥ 0,35 | 22 | 31 | 30 | 35% | 0,386 |
| só MST | 45 | 1 | 0 | 100% | 0,672 |
| **MST ∪ ρ ≥ 0,32** | **68** | **1** | **0** | **100%** | **0,422** |

Com ρ ≥ 0,30, que era o valor em uso, 18 dos 46 fundos ficavam com grau zero.
Isso é um problema de interpretação antes de ser um problema estético: um
fundo sem aresta parece descorrelacionado de todos, quando na verdade apenas
não passou do corte. E intermediação, caminho médio, diâmetro e o teste de
robustez por remoção perdem o sentido em um grafo já fragmentado em 19 partes.

A árvore geradora mínima sobre a distância de Mantegna, $d_{ij} =
\sqrt{2(1-\rho_{ij})}$, conecta os 46 fundos com o menor custo total. A união
com o grafo por limiar mantém essa conectividade e acrescenta os pares de
correlação alta que a árvore não contém. Das 68 arestas, 44 vêm do limiar e
24 vêm só da MST.

As duas origens têm leituras distintas, e cada aresta carrega o atributo
`origem` para que isso fique explícito:

- **aresta do limiar**: o par está entre os 5% mais correlacionados da amostra;
- **aresta só da MST**: é o vizinho mais próximo daquele fundo, mesmo com
  correlação baixa. Diz qual é o parente mais próximo, não que exista
  co-movimento forte.

A limitação é o outro lado disso: como a MST força N−1 arestas, a presença de
aresta deixa de implicar correlação alta. Nas figuras as arestas só-MST são
tracejadas.

**ρ = 0,32** é o percentil 95 da distribuição (0,315, arredondado). O critério
é relativo à amostra, não um número escolhido à mão: as arestas do limiar são,
por definição, os 5% de pares mais correlacionados.

## 5. Camada C — kNN, k = 3

Mesma regra da Camada A, mesmo valor. A varredura
(`out/frente2/05_sensibilidade_camada_c.csv`) mostra o compromisso usual:
k = 2 dá modularidade 0,739 com grau médio 2,9; k = 6 dá 0,523 com grau 8,2.
Com k = 3 o grafo fica conexo, com grau médio 4,1 e modularidade 0,664,
alinhado às outras duas camadas.

O ARI com o segmento é 0,122, o mais baixo das três camadas. Isso não é
defeito de calibragem: a Camada C mede perfil financeiro (DY, P/VP, patrimônio
líquido, liquidez, número de ativos), que é quase ortogonal ao setor. É o que
justifica mantê-la como camada separada — se ela reproduzisse o segmento, seria
redundante com a Camada A.

## Validação cruzada entre camadas

| Camada | ARI com segmento | Leitura |
|---|---|---|
| A | 0,519 (0,428 no grafo completo) | segue o setor em parte; o resto é gestora e inquilino em comum |
| B | 0,210 | o co-movimento só em parte segue o setor |
| C | 0,122 | perfil financeiro é quase ortogonal ao setor |

Os três valores diferentes são a evidência de que as camadas capturam coisas
diferentes. Se uma delas fosse redundante, apareceria aqui.

## Limitações a declarar no relatório

- Os cinco limiares são decisões de modelagem. A varredura em
  `out/frente2/` mostra como as métricas respondem a cada um.
- A correlação é sensível à janela e a mudanças de regime. O período usado é
  2023–2024 e deve ser reportado junto com qualquer resultado.
- Nove fundos ficaram fora por qualidade de dados, não por irrelevância.
- A Camada A depende de `segmento`, `gestora` e `inquilinos`. Inquilino só
  existe para os 26 fundos de tijolo, e 7 deles (os shoppings) têm lista
  genérica, ignorada: 27 dos 46 fundos ficam sem inquilino.
- O Jaccard divide pela união, então o fundo sobre o qual temos mais
  informação tem mais chance de divergir (viés de cobertura −0,72). Peso
  médio intra-Logística 0,158 contra 0,324 intra-Papel no backbone. Comparar
  pesos **entre** segmentos exige essa ressalva; **dentro** do mesmo segmento
  vale. O atributo que resolveria os empates que restam no Papel é o
  `indexador` (CDI × IPCA), que não foi coletado.
- A presença de aresta na Camada B não implica correlação alta, por causa das
  arestas da MST.
