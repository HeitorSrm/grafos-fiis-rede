# FIIs como Rede de Similaridades (SMAC03 / Grafos, UNIFEI)

**Cenário 1 — Análise do Mercado de FIIs.** Modela 46 Fundos de Investimento
Imobiliário como uma rede e analisa similaridade e dependência sob três
perspectivas, para responder à pergunta do cenário: *onde a diversificação
aparente de uma carteira esconde dependência real?*

Amostra: 46 FIIs, 497 pregões (02/01/2023 a 30/12/2024), dados reais da B3.

## As três camadas

| Camada | O que captura | Como é construída |
|---|---|---|
| **A — Estrutural** | similaridade de *características declaradas* | projeção bipartida FII×característica, peso = soma do `idf` dos itens compartilhados → *backbone* kNN |
| **B — Comportamental** | *co-movimento* de preços | retorno log → correlação de Pearson → distância `d=√(2(1−ρ))` → **MST de Mantegna ∪ grafo por limiar** |
| **C — Fundamentalista** | similaridade de *perfil financeiro* | vetor contínuo padronizado (z-score) → distância euclidiana → similaridade `1/(1+d)` → grafo kNN |

**Atributos da Camada A:** segmento, gestora, inquilinos.
**Indicadores da Camada C:** DY 12m, P/VP, patrimônio líquido, liquidez
diária, nº de ativos.

> `indexador`, `tipo_imovel` e `vacância` constavam do plano inicial mas não
> foram coletados. `tipo_fundo` foi removido da Camada A por ser função
> determinística do segmento: ele duplicava o peso do setor e respondia
> sozinho por 200 das 433 arestas da versão anterior.

## Limiares calibrados

Cinco limiares, todos com análise de sensibilidade em `out/frente2/` e
justificativa em [`docs/frente2-thresholds.md`](docs/frente2-thresholds.md).

| Limiar | Valor | Camada | Critério |
|---|---|---|---|
| `COBERTURA_MIN` | 0,90 | dados | cotação real em 90% do período |
| `ZEROS_MAX` | 0,30 | dados | acima disso o preço está travado por iliquidez |
| `K_BACKBONE_A` | 3 | A | menor k que mantém A e C conexas |
| `RHO_MIN_B` | 0,32 | B | percentil 95 da correlação entre pares |
| `K_KNN_C` | 3 | C | mesmo critério da Camada A |

Grafos resultantes:

| Camada | Arestas | Densidade | Grau médio | Componentes | Comunidades | Modularidade | ARI com segmento |
|---|---|---|---|---|---|---|---|
| A — backbone k=3 | 98 | 0,095 | 4,3 | 1 | 6 | 0,656 | 0,452 |
| B — MST ∪ ρ ≥ 0,32 | 68 | 0,066 | 3,0 | 1 | 5 | 0,422 | 0,210 |
| C — kNN k=3 | 95 | 0,092 | 4,1 | 1 | 6 | 0,664 | 0,122 |

As três ficam conexas, sem fundos isolados e com densidade comparável, para
que a comparação entre camadas reflita estrutura e não calibragem. Os três
valores distintos de ARI mostram que elas captam coisas diferentes: a Camada A
reconstrói o setor, a B o acompanha parcialmente e a C é quase ortogonal a ele.

## Rodando

```bash
pip install -r requirements.txt

python src/frente2.py    # sensibilidade dos limiares + camadas calibradas
python src/frente4.py    # centralidades, pontes, segmentos e carteiras
python src/main.py       # protótipo inicial, com dados simulados
```

A base de atributos usada pela Frente 2 é gerada por
`python src/gera_base_v2.py` e já está versionada.

## Arquivos

### Dados — `docs/1. Dados Reais/`
- `Tabelas - Dados/precos_diarios_FIIs_1_excel.csv` — cotações diárias dos 55 FIIs
- `Tabelas - Dados/atributos_fiis.xlsx` — atributos como coletados (v1)
- `Tabelas - Dados/atributos_fiis_v2.xlsx` — v2, com o `segmento` reclassificado
- `Dicionário/dicionario.md` e `Dicionário/dicionario_v2.md`

### Código — `src/`
- `grafos.py` — núcleo algorítmico: projeção bipartida, MST, limiar, kNN,
  Louvain, centralidades, ARI, robustez, avaliação de carteira
- `camadas.py` — **Frente 2**: construção calibrada das três camadas
  (backbone kNN, MST ∪ limiar) e carregamento da base v2
- `frente2.py` — **Frente 2**: análise de sensibilidade dos cinco limiares,
  tabelas e figuras → `out/frente2/`
- `frente4.py` — **Frente 4**: descritiva, pontes, segmentos que andam juntos,
  carteiras e robustez → `out/frente4/<modo>/`
- `gera_base_v2.py` — gera `atributos_fiis_v2.xlsx`
- `data.py`, `main.py` — protótipo inicial com dados simulados

### Documentação — `docs/`
- `frente2-thresholds.md` — calibragem dos limiares, com as tabelas da varredura
- `frente2-modelagem.tex` — seção de Modelagem em LaTeX, pronta para o Overleaf
- `cronograma-frente2.md`, `roteiro.md`

## Algoritmos de teoria dos grafos usados

Projeção de grafo bipartido · extração de *backbone* por vizinhança ·
árvore geradora mínima (Kruskal/Prim via `networkx`) · grafo por limiar ·
k-vizinhos mais próximos · detecção de comunidades (modularidade / Louvain) ·
centralidades (grau ponderado, intermediação, autovetor) · componentes
conexos · caminho mínimo e diâmetro · análise de robustez por remoção de
vértices.

## Contribuindo

Ver [`CONTRIBUTING.md`](CONTRIBUTING.md). A `main` é protegida: só recebe
Pull Request. O trabalho novo entra em `develop` a partir de uma branch
própria.
