# FIIs como Rede de Similaridades (SMAC03 / Grafos, UNIFEI)

**Cenário 1 — Análise do Mercado de FIIs.** Modela 46 Fundos de Investimento
Imobiliário como uma rede e analisa similaridade e dependência sob três
perspectivas, para responder à pergunta do cenário: *onde a diversificação
aparente de uma carteira esconde dependência real?*

Amostra: 46 FIIs, 499 datas de negociação (02/01/2023 a 30/12/2024), que
dão 497 observações de retorno; dados reais da B3.

## Comece por aqui

1. **Relatório e slides** são a descrição completa do trabalho (o texto final está no relatório entregue).
2. Para **reproduzir** os resultados, nesta ordem, da raiz do repositório:

```bash
pip install -r requirements.txt
python src/frente2.py      # limiares + camadas calibradas   -> out/frente2/
python src/comunidades.py  # comunidades (3 algoritmos)      -> out/comunidades/
python src/frente4.py      # pontes, segmentos e carteiras   -> out/frente4/todos/
```

3. **O que é código final, validação, protótipo e pseudocódigo** está em
   [`src/README.md`](src/README.md). Em resumo: `grafos.py` e `camadas.py` são
   o núcleo; `main.py` e `data.py` são do protótipo com dados simulados;
   `src/pseudocodigo/` é só material de estudo.

## Quais algoritmos rodam de verdade

| Etapa | Algoritmo | Onde está o código que roda |
|---|---|---|
| Camada A | projeção bipartida, Jaccard ponderado por `idf`, *backbone* por vizinhança (k = 3, mantendo empates) | `src/grafos.py`, `src/camadas.py` |
| Camada B | correlação → distância de Mantegna → MST (Kruskal) ∪ limiar ρ ≥ 0,32 | `src/grafos.py`, `src/camadas.py` |
| Camada C | z-score → distância euclidiana → kNN (k = 3) | `src/grafos.py`, `src/camadas.py` |
| Comunidades | Girvan-Newman, Louvain e Leiden, **implementados do zero** | `src/comunidades.py` |
| Comunidades (Tabela 1) | Louvain via biblioteca `python-louvain` | `src/grafos.py` |
| Centralidades e pontes | grau ponderado, intermediação, autovetor | `src/grafos.py`, `src/frente4.py` |
| Carteiras e robustez | caminho mínimo na MST, remoção de vértices | `src/grafos.py`, `src/frente4.py` |

Os arquivos de `src/pseudocodigo/` (Louvain, Leiden e Girvan-Newman) são
pseudocódigo de estudo e **não são executados**. Há duas implementações de
Louvain de propósito (a da Tabela 1 e a das comparações); ver `src/README.md`.

## As três camadas

| Camada | O que captura | Como é construída |
|---|---|---|
| **A — Estrutural** | similaridade de *características declaradas* | projeção bipartida FII×característica, peso = Jaccard ponderado pelo `idf` (fração do perfil compartilhada) → *backbone* kNN |
| **B — Comportamental** | *co-movimento* de preços | retorno log → correlação de Pearson → distância `d=√(2(1−ρ))` → **MST de Mantegna ∪ grafo por limiar** |
| **C — Fundamentalista** | similaridade de *perfil financeiro* | vetor contínuo padronizado (z-score) → distância euclidiana → similaridade `1/(1+d)` → grafo kNN |

**Atributos da Camada A:** segmento, gestora, inquilinos (só fundos de tijolo).
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
| `K_BACKBONE_A` | 3 | A | menor k que deixa A e C com grau médio acima de 3 |
| `RHO_MIN_B` | 0,32 | B | percentil 95 da correlação entre pares |
| `K_KNN_C` | 3 | C | mesmo critério da Camada A |

Grafos resultantes:

| Camada | Arestas | Densidade | Grau médio | Componentes | Comunidades | Modularidade | ARI com segmento |
|---|---|---|---|---|---|---|---|
| A — Jaccard + backbone k=3 | 122 | 0,118 | 5,3 | 1 | 6 | 0,574 | 0,519 |
| B — MST ∪ ρ ≥ 0,32 | 68 | 0,066 | 3,0 | 1 | 5 | 0,422 | 0,210 |
| C — kNN k=3 | 95 | 0,092 | 4,1 | 1 | 6 | 0,664 | 0,122 |

As três ficam conexas, sem fundos isolados e com densidade comparável, para
que a comparação entre camadas reflita estrutura e não calibragem. Os três
valores distintos de ARI mostram que elas captam coisas diferentes: a Camada A
segue o setor em boa parte (o resto é gestora e inquilino em comum), a B o
acompanha parcialmente e a C é quase ortogonal a ele. O ARI é validação, não
objetivo: o segmento é entrada da Camada A.

> O Louvain é estocástico, e a coluna de ARI acima vem de uma única execução.
> Em 200 execuções com sementes diferentes (`out/frente2/10_estabilidade_ari.csv`),
> o ARI médio com o segmento é 0,49 na Camada A, 0,17 na B e 0,11 na C. A
> Camada B é a que mais varia (de 0,10 a 0,27): sua estrutura de comunidades
> é fraca, coerente com a baixa correlação entre os fundos.

## Rodando

```bash
pip install -r requirements.txt

python src/frente2.py      # sensibilidade dos limiares + camadas calibradas
python src/comunidades.py  # comunidades nas 3 camadas (3 algoritmos)
python src/frente4.py      # centralidades, pontes, segmentos e carteiras
python src/main.py         # PROTÓTIPO inicial, com dados simulados (não é o resultado final)

# validação
python src/teste_sintetico.py   # 500 fundos sintéticos de estrutura conhecida
python src/analise_ampliada.py  # base real ampliada (156 FIIs) x base de 46
```

A base ampliada já está versionada em `dados/ampliado/`. Para coletá-la de
novo: `python src/coleta_ampliada.py universo`, depois `precos --parte N`
(N de 1 a 5, uma parte por pessoa, para dividir o limite do Yahoo) e
`juntar`.

A base de atributos usada pela Frente 2 é gerada por
`python src/gera_base_v2.py` e já está versionada.

## Arquivos

### Dados — `docs/1. Dados Reais/`
- `Tabelas - Dados/precos_diarios_FIIs_1_excel.csv` — cotações diárias dos 55 FIIs
- `Tabelas - Dados/atributos_fiis.xlsx` — atributos como coletados (v1)
- `Tabelas - Dados/atributos_fiis_v2.xlsx` — v2, com o `segmento` reclassificado
- `Dicionário/dicionario.md` e `Dicionário/dicionario_v2.md`
- `src/` — scripts da coleta original (atributos e preços)

### Dados ampliados — `dados/ampliado/`
- `universo.csv` — os 379 FIIs negociados, com segmento (e a origem dele:
  revisado na base v2, CVM ou Fundamentus) e indicadores
- `precos.csv` — cotações diárias 2023–2024, no formato da base da Frente 1;
  156 fundos passam na limpeza do projeto

### Código — `src/`
- `grafos.py` — núcleo algorítmico: projeção bipartida, MST, limiar, kNN,
  Louvain, centralidades, ARI, robustez, avaliação de carteira
- `camadas.py` — **Frente 2**: construção calibrada das três camadas
  (backbone kNN, MST ∪ limiar) e carregamento da base v2
- `frente2.py` — **Frente 2**: análise de sensibilidade dos cinco limiares,
  tabelas e figuras → `out/frente2/`
- `frente4.py` — **Frente 4**: descritiva, pontes (com a estabilidade em
  reamostragens), segmentos que andam juntos, carteiras de exemplo (contra
  sorteadas de mesma composição), carteiras aparente × efetiva pela MST
  (escolhidas em 2023, medidas em 2024) e robustez, sobre as camadas
  calibradas de `camadas.py` →
  `out/frente4/<modo>/` (modos: padrão, `--top N`, `--dados-simulados`,
  `--simular N`)
- `comunidades.py` — **Frente 3**: detecção de comunidades nas três camadas
  com Girvan-Newman, Louvain e Leiden; compara os três entre si, com o
  segmento e entre camadas → `out/comunidades/`
- `visual_comunidades.py` — **Frente 3**: comparação visual das partições
  (`--salvar` grava os PNGs sem abrir janela)
- `pseudocodigo/` (`louvain.py`, `leiden.py`, `girvan_newman.py`) —
  **só pseudocódigo comentado**, material de estudo; não é executado
- `teste_sintetico.py` — **validação**: 500 fundos sintéticos com segmentos,
  pontes, pares de diversificação aparente e perfis plantados; verifica se o
  pipeline os recupera, em três cenários (forte, realista e com mudança de
  regime) → `out/teste_sintetico/`
- `coleta_ampliada.py` — **validação**: coleta de todos os FIIs negociados
  (Fundamentus + CVM + Yahoo), em 5 partes → `dados/ampliado/`
- `analise_ampliada.py` — **validação**: Camadas B e C, pontes, pares
  cruzados e carteiras na base ampliada, lado a lado com a base de 46 →
  `out/ampliada/`
- `gera_base_v2.py` — gera `atributos_fiis_v2.xlsx`
- `data.py`, `main.py` — protótipo inicial com dados simulados (o `frente4.py`
  ainda importa o `data.py` para as carteiras de exemplo)
- Detalhe de cada arquivo: [`src/README.md`](src/README.md)

### Documentação — `docs/`
- `frente2-thresholds.md` — calibragem dos limiares, tabelas da varredura e
  limitações a declarar (números em `out/frente2/09_diagnostico_limitacoes.csv`)
- `frente2-camada-a.md` — decisões da Camada A (inquilinos, peso Jaccard,
  backbone com empates), com os testes de cada uma
- `frente2-modelagem.tex` — rascunho longo da Modelagem (o texto final está no relatório)
- `planejamento/` — `cronograma-frente2.md` e `roteiro.md` (organização interna do grupo)
- Índice da pasta: [`docs/README.md`](docs/README.md); das saídas: [`out/README.md`](out/README.md)

## Algoritmos de teoria dos grafos usados

Projeção de grafo bipartido · extração de *backbone* por vizinhança ·
árvore geradora mínima (Kruskal/Prim via `networkx`) · grafo por limiar ·
k-vizinhos mais próximos · detecção de comunidades (Girvan-Newman, Louvain e
Leiden; modularidade) ·
centralidades (grau ponderado, intermediação, autovetor) · componentes
conexos · caminho mínimo e diâmetro · análise de robustez por remoção de
vértices.

## Contribuindo

Ver [`CONTRIBUTING.md`](CONTRIBUTING.md). A `main` é protegida: só recebe
Pull Request. O trabalho novo entra em `develop` a partir de uma branch
própria.
