# Modelagem (texto para o relatório)

> Rascunho da seção de Modelagem, escrito para ser transposto ao Overleaf.
> A notação matemática já está em LaTeX. Os números conferem com
> `out/frente2/` e com `docs/frente2-thresholds.md`.

---

## Modelagem

A modelagem adotada representa o conjunto de fundos como três grafos não
direcionados, valorados e sobre o mesmo conjunto de vértices. Formalmente,
cada camada é um grafo $G_\ell = (V, E_\ell, w_\ell)$, com $\ell \in \{A, B,
C\}$, em que $V$ é o conjunto dos 46 Fundos de Investimento Imobiliário da
amostra, $E_\ell \subseteq V \times V$ é o conjunto de arestas daquela camada
e $w_\ell: E_\ell \rightarrow \mathbb{R}_{+}$ atribui a cada aresta a
intensidade da relação que ela representa. A separação em camadas decorre do
fato de que "fundos semelhantes" admite mais de uma definição: dois fundos
podem compartilhar características declaradas, podem oscilar juntos no mercado
ou podem apresentar perfis financeiros próximos sem que nenhuma das duas
condições anteriores se verifique. Tratar essas três noções como grafos
distintos, e não como um único índice agregado, permite verificar onde elas
concordam e, principalmente, onde divergem — que é o ponto em que a
diversificação aparente de uma carteira se separa da diversificação efetiva.

### Camada A — similaridade estrutural

A primeira camada parte das características declaradas de cada fundo. A
amostra é representada por uma matriz bipartida $M \in \{0,1\}^{n \times m}$,
em que $n = 46$ é o número de fundos e $m$ é o número de itens observados,
sendo cada item um par atributo–valor, como `segmento=Logística` ou
`inquilino=Amazon`. Tem-se $M_{iq} = 1$ quando o fundo $i$ apresenta o item
$q$. A projeção dessa matriz sobre o conjunto de fundos, $M M^{\top}$, produz
uma matriz cujo elemento $(i,j)$ conta os itens que os fundos $i$ e $j$
compartilham.

A contagem simples, entretanto, trata todos os itens como igualmente
informativos, o que não se sustenta: compartilhar um segmento presente em 15
dos 46 fundos é menos informativo do que compartilhar uma gestora presente em
dois. Adota-se então uma ponderação por raridade, análoga ao fator de
frequência inversa empregado em recuperação de informação. Sendo $n_q$ o
número de fundos que apresentam o item $q$, define-se

$$\mathrm{idf}(q) = \ln\!\left(\frac{n}{n_q}\right),$$

e o peso da aresta entre dois fundos é a soma do $\mathrm{idf}$ dos itens que
ambos compartilham:

$$w_A(i,j) = \sum_{q \,:\, M_{iq} = M_{jq} = 1} \mathrm{idf}(q).$$

Itens presentes em todos os fundos recebem peso nulo e não geram aresta.

A projeção bipartida tende, porém, a produzir grafos densos, uma vez que um
atributo categórico com $n_q$ fundos gera um subgrafo completo de $n_q$
vértices. Uma redução por limiar de peso seria inadequada neste caso: como o
peso de uma aresta originada apenas do segmento compartilhado é
$\ln(n/n_q)$, qualquer limiar elimina primeiro os segmentos mais numerosos,
que são exatamente aqueles de maior interesse para a análise de concentração
de risco. Adota-se, em lugar disso, uma extração de *backbone* por vizinhança:
cada fundo retém as $k$ arestas de maior peso incidentes sobre si, e o grafo
final é a união dessas seleções. O critério passa a ser interno a cada
vértice, tornando-se invariante ao tamanho do grupo a que ele pertence, e
nenhum fundo permanece isolado.

### Camada B — co-movimento de mercado

A segunda camada não utiliza atributos declarados, e sim as séries de preços.
A partir das cotações diárias de fechamento ajustado $P_i(t)$, calcula-se o
retorno logarítmico

$$r_i(t) = \ln P_i(t) - \ln P_i(t-1),$$

e, sobre esses retornos, o coeficiente de correlação de Pearson $\rho_{ij}$
entre cada par de fundos. A correlação é convertida na métrica proposta por
Mantegna (1999),

$$d_{ij} = \sqrt{2\,(1 - \rho_{ij})},$$

que satisfaz os axiomas de distância e é monotonicamente decrescente em
$\rho_{ij}$: pares fortemente correlacionados tornam-se próximos.

Sobre essa matriz de distâncias constrói-se a árvore geradora mínima (MST),
que conecta os 46 fundos com o menor custo total e evidencia, para cada fundo,
o seu vizinho mais próximo em termos de co-movimento. A MST, contudo, é
restrita a $n-1$ arestas e descarta ligações fortes que não pertencem à
árvore. O grafo da camada é, portanto, a união da MST com o grafo por limiar:

$$E_B = E_{\mathrm{MST}} \cup \{(i,j) : \rho_{ij} \geq \rho^{*}\}.$$

A construção por união é necessária porque a distribuição de correlação da
amostra é estreita — mediana de 0,185 e máximo de 0,484 —, de modo que um
limiar isolado ou retém quase todos os pares ou fragmenta o grafo. Com
$\rho^{*} = 0{,}32$, o grafo por limiar sozinho deixaria 18 dos 46 fundos sem
nenhuma aresta, inviabilizando o cálculo de intermediação, caminho médio,
diâmetro e dos ensaios de robustez. A união preserva a conectividade e admite
duas leituras distintas para as arestas: as provenientes do limiar indicam
pares efetivamente co-movidos, ao passo que as provenientes apenas da árvore
indicam o vizinho mais próximo de um fundo, ainda que a correlação seja
moderada. Essa distinção é registrada como atributo da aresta e representada
graficamente por traço descontínuo.

### Camada C — similaridade de perfil fundamentalista

A terceira camada descreve cada fundo por um vetor de cinco indicadores
quantitativos: *dividend yield* acumulado em doze meses, razão entre preço e
valor patrimonial, patrimônio líquido, liquidez diária e número de ativos. O
patrimônio líquido e a liquidez são transformados por $\log_{10}$, por
variarem entre milhões e bilhões, e todos os indicadores são padronizados por
escore-padrão, de forma que nenhuma variável domine a distância em razão de
sua unidade. Valores inaplicáveis — como o número de ativos em fundos de papel
e fundos de fundos — são tratados como ausentes e imputados pela média da
variável, equivalente a zero após a padronização.

A dissimilaridade entre dois fundos é a distância euclidiana $d_{ij}$ entre
seus vetores padronizados, convertida em similaridade por

$$w_C(i,j) = \frac{1}{1 + d_{ij}},$$

que é limitada ao intervalo $(0,1]$ e decresce suavemente com a distância.
Como essa definição produziria um grafo completo, aplica-se a mesma extração
por vizinhança da Camada A: cada fundo retém os seus $k$ vizinhos mais
similares.

### Tratamento dos dados e calibragem dos limiares

A base de cotações entregue não apresentava valores ausentes, o que se
mostrou artificial: o procedimento de coleta propagou o primeiro preço
disponível para trás, de modo que fundos sem histórico no início da janela
receberam uma sequência de preços repetidos — em um dos casos, 292 pregões
consecutivos. Preços constantes produzem retornos nulos, e fundos cujas séries
se iniciam na mesma data apresentam retornos nulos simultâneos, que a
correlação de Pearson interpreta como concordância. Foram, portanto,
estabelecidos dois critérios de qualidade: exige-se cotação efetiva em ao
menos 90% do período, o que exclui fundos ainda não negociados no início da
janela, e admite-se no máximo 30% de pregões com retorno nulo, o que exclui
fundos cujo preço permanece travado por iliquidez. Nove dos 55 fundos
originais foram removidos por esses critérios, restando 46 fundos e 497
pregões, entre 02/01/2023 e 30/12/2024.

Os parâmetros das três camadas foram submetidos a uma análise de
sensibilidade, na qual se observou a resposta do número de arestas, da
densidade, do grau médio, do número de componentes e da modularidade a cada
valor testado. O limiar da Camada B foi fixado no percentil 95 da distribuição
de correlação da própria amostra ($0{,}315$, arredondado para $0{,}32$), de
modo que as arestas de limiar correspondam, por definição, aos 5% de pares
mais correlacionados. Para as Camadas A e C adotou-se $k = 3$, o menor valor
que mantém ambos os grafos conexos — com $k = 2$, a Camada A se fragmenta em
quatro componentes. A adoção de um mesmo critério para as duas camadas resulta
em grafos de densidade comparável, entre 0,066 e 0,095, e grau médio entre 3,0
e 4,3, condição necessária para que a comparação entre camadas reflita
diferenças de estrutura e não de calibragem.

**Tabela — limiares adotados.**

| Limiar | Valor | Camada | Critério |
|---|---|---|---|
| Cobertura mínima | 0,90 | dados | cotação efetiva em 90% do período |
| Máximo de retornos nulos | 0,30 | dados | acima disso, preço travado por iliquidez |
| $k$ do *backbone* | 3 | A | menor valor que mantém A e C conexas |
| $\rho^{*}$ | 0,32 | B | percentil 95 da correlação entre pares |
| $k$ da vizinhança | 3 | C | mesmo critério da Camada A |

**Tabela — grafos resultantes.**

| Camada | Arestas | Densidade | Grau médio | Componentes | Comunidades | Modularidade |
|---|---|---|---|---|---|---|
| A | 98 | 0,095 | 4,3 | 1 | 6 | 0,656 |
| B | 68 | 0,066 | 3,0 | 1 | 5 | 0,422 |
| C | 95 | 0,092 | 4,1 | 1 | 6 | 0,664 |

Como validação da modelagem, comparou-se a partição obtida pelo algoritmo de
Louvain em cada camada com a classificação setorial dos fundos, por meio do
índice Rand ajustado. A Camada A apresenta concordância de 0,452 no grafo
reduzido e de 0,857 no grafo completo, o que era esperado, dado que o segmento
é um de seus atributos de entrada. A Camada B apresenta 0,210 e a Camada C,
0,122. A divergência entre esses valores sustenta a decisão de manter as três
camadas: o co-movimento de mercado acompanha apenas parcialmente a divisão
setorial, e o perfil financeiro é praticamente ortogonal a ela. Caso alguma
camada fosse redundante em relação às demais, essa redundância se manifestaria
nesse indicador.

### Limitações

A modelagem está sujeita a quatro limitações que condicionam a leitura dos
resultados. Primeiro, os limiares são decisões de modelagem e não parâmetros
estimados; a análise de sensibilidade documenta o comportamento das métricas
sob valores alternativos. Segundo, a correlação é sensível à janela adotada e
a mudanças de regime, de modo que os resultados se referem ao biênio
2023–2024. Terceiro, a presença de aresta na Camada B não implica correlação
elevada, dado que a árvore geradora impõe $n-1$ arestas independentemente de
sua intensidade. Quarto, a Camada A depende da qualidade dos atributos
declarados: a lista de locatários está ausente em 21 dos 46 fundos, e listas
idênticas repetidas em mais de quatro fundos foram descartadas por
caracterizarem preenchimento padrão.
