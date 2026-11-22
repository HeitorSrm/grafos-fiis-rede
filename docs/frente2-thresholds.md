# Frente 2 — calibragem dos limiares

Documento técnico da frente de modelagem formal. Registra os cinco limiares
do projeto, o que foi testado e por que cada valor foi escolhido.

Reproduzir: `python src/frente2.py` (saída em `out/frente2/`).

Amostra: 46 FIIs, 497 observações de retorno (02/01/2023 a 30/12/2024).

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
| A — backbone k=3 | 122 | 0,118 | 5,3 | 1 | 0 | 6 | 0,574 | 0,519 |
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

## 3. Camada A — Jaccard ponderado e backbone kNN, k = 3

A Camada A passou por três decisões. A tabela
`out/frente2/02_evolucao_camada_a.csv` separa o efeito de cada uma:

| Configuração | Arestas | Densidade | Grau médio | Modularidade | ARI com segmento |
|---|---|---|---|---|---|
| 1. soma de idf, com `tipo_fundo` (original) | 433 | 0,418 | 18,8 | 0,486 | 0,488 |
| 2. soma de idf, sem `tipo_fundo` | 233 | 0,225 | 10,1 | 0,555 | 0,857 |
| 3. Jaccard, inquilino só tijolo (completa) | 233 | 0,225 | 10,1 | 0,474 | 0,428 |
| 4. Jaccard + backbone k=3 (adotada) | 122 | 0,118 | 5,3 | 0,574 | 0,519 |

### 3.1 Remoção do `tipo_fundo`

`indexador` e `tipo_imovel` nunca foram coletados: estão como `n/a` nos 46
fundos e não geram aresta nenhuma. `tipo_fundo` era pior, porque gerava aresta
sem carregar informação: ele é função determinística do segmento, então
duplicava o peso do setor e ligava qualquer par de fundos de tijolo.
**200 das 433 arestas existiam apenas por causa dele**, e 336 das 433 não
diziam nada além do setor compartilhado.

### 3.2 Inquilino só para fundos de tijolo

Fundo de papel, FoF e Fiagro não têm locatário. O que a planilha traz nesses
casos é uma descrição do que o fundo carrega, genérica por segmento: a mesma
lista de onze devedores de CRI aparece em 16 fundos de papel, a mesma lista de
doze lojistas aparece em 8 fundos de shopping, e HFOF11 e KFOF11 trazem "cotas
de outros FIIs listados na bolsa".

Os nomes são reais e o dado não foi inventado; ele apenas não é específico por
fundo. Usado como atributo, faria os fundos de papel compartilharem onze itens
de uma vez, formando um clique de peso altíssimo que apenas repete o que o
segmento já diz. O atributo passa a valer somente para os segmentos de tijolo,
onde é de fato locatário. Após o filtro, 19 dos 46 fundos contribuem com
inquilinos.

### 3.3 Peso: Jaccard ponderado pelo idf

A soma do idf tinha dois defeitos simultâneos.

**Desequilíbrio entre segmentos.** Somar favorece quem tem mais atributos. O
peso médio de uma aresta dentro da Logística era 2,57 contra 1,31 dentro do
Papel: fundos de tijolo pareciam o dobro de similares entre si apenas porque
tinham inquilinos para somar.

**Resolução baixa.** O peso dependia só de *quais* atributos coincidiam, e com
três atributos existem apenas 10 padrões de casamento possíveis na amostra. O
grafo completo tinha 233 arestas e **22 valores distintos de peso**, sendo que
136 delas (58%) existiam só por segmento compartilhado — e, dentro de um mesmo
segmento, todas essas são obrigatoriamente idênticas. Os 15 fundos de Papel
formavam um clique de 105 arestas, todas valendo exatamente 1,121. Foi esse
empate em massa que tornava o backbone dependente da ordem das linhas da
planilha, problema corrigido em `docs/frente2-backbone-empates.md`.

Vale registrar que um peso fixo por atributo, escolhido à mão, pioraria o
segundo defeito: o peso passaria a ser função apenas do padrão de casamento,
limitando o grafo a 10 valores distintos.

A correção é normalizar pela união, medindo que fração do perfil conjunto dos
dois fundos é compartilhada:

$$w_A(i,j) = \frac{\sum_{q \in A \cap B} \mathrm{idf}(q)}{\sum_{q \in A \cup B} \mathrm{idf}(q)}$$

O peso fica em (0, 1], mantém a ponderação por raridade e passa a depender
também do que cada fundo tem de diferente. O grafo completo vai de 22 para
**114 valores distintos de peso**, e o backbone sai de 0,178 para 0,118 de
densidade.

Alternativas medidas na mesma base, todas com inquilino só para tijolo e
backbone k = 3 com empates:

| Método | Arestas | Pesos distintos | Densidade | intra Log × Papel | Razão | ARI |
|---|---|---|---|---|---|---|
| soma de idf | 184 | 28 | 0,178 | 2,572 × 1,309 | 1,96 | 0,469 |
| **Jaccard ponderado** | **122** | **61** | **0,118** | 0,158 × 0,324 | 0,49 | 0,519 |
| Gower simples | 203 | 12 | 0,196 | 0,413 × 0,538 | 0,77 | 0,690 |
| Gower × raridade | 178 | 30 | 0,172 | 0,227 × 0,171 | 1,33 | 0,576 |

A razão ideal entre os pesos médios intra-segmento é 1,00. O Gower simples
equilibra melhor, mas ao custo de abandonar a ponderação por raridade: cai
para 12 valores distintos de peso, o pior dos quatro, e deixa o grafo mais
denso que a versão original. O Jaccard foi adotado por corrigir os dois
defeitos de origem mantendo o idf, e o desequilíbrio residual está declarado
nas limitações.

### 3.4 Por que backbone e não limiar de peso

O peso de uma aresta que existe só por segmento compartilhado é dominado por
`ln(N / tamanho do segmento)`. Papel tem 15 fundos e Logística tem 7, de modo
que um limiar de peso elimina primeiro os segmentos maiores — justamente os de
maior risco de concentração.

O backbone kNN troca a pergunta: em vez de "esta aresta é forte em termos
absolutos?", pergunta "esta aresta está entre as k mais fortes deste fundo?".
A seleção passa a ser interna a cada fundo, portanto invariante ao tamanho do
segmento, e nenhum fundo fica isolado. Empates com a k-ésima aresta são
mantidos, para que o resultado não dependa da ordem da planilha.

### 3.5 Escolha de k

Varredura em `out/frente2/03_sensibilidade_camada_a.csv`. Com o peso em
Jaccard a Camada A já fica conexa em k = 2, de modo que a conectividade
sozinha não decide. Adotou-se k = 3 por duas razões: é o menor valor que deixa
as duas camadas kNN com grau médio acima de 3, alinhado à Camada B; e a
modularidade da Camada A é máxima até k = 3 (0,574) e cai a partir de k = 4
(0,527).

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
| A | 0,519 | reconstrói parcialmente o setor, como esperado |
| B | 0,210 | o co-movimento só em parte segue o setor |
| C | 0,122 | perfil financeiro é quase ortogonal ao setor |

Os três valores diferentes são a evidência de que as camadas capturam coisas
diferentes. Se uma delas fosse redundante, apareceria aqui.

## Limitações a declarar no relatório

- Os cinco limiares são decisões de modelagem. A varredura em
  `out/frente2/` mostra como as métricas respondem a cada um.
- **Viés de cobertura na Camada A.** O Jaccard divide pela união, então o
  fundo sobre o qual temos mais informação tem mais oportunidade de divergir:
  o peso médio dentro da Logística é 0,158 contra 0,324 dentro do Papel. A
  comparação de pesos *entre* segmentos precisa levar isso em conta; dentro de
  um mesmo segmento a comparação é válida.
- A correlação é sensível à janela e a mudanças de regime. O período usado é
  2023–2024 e deve ser reportado junto com qualquer resultado.
- Nove fundos ficaram fora por qualidade de dados, não por irrelevância.
- A Camada A depende de `segmento`, `gestora` e `inquilinos`. O atributo
  inquilino vale só para os segmentos de tijolo e contribui em 19 dos 46
  fundos.
- A presença de aresta na Camada B não implica correlação alta, por causa das
  arestas da MST.
