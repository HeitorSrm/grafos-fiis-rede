# `src/` — o que é o quê

Rodar sempre **da raiz do repositório** (`python src/<script>.py`): os scripts
leem `docs/1. Dados Reais/` e gravam em `out/` com caminhos relativos.

## Pipeline final (o que gera os resultados do relatório)

| Ordem | Arquivo | Papel | Saída |
|---|---|---|---|
| 0 | `grafos.py` | **núcleo algorítmico** (projeção bipartida, MST, limiar, kNN, Louvain via `python-louvain`, centralidades, ARI, robustez, carteiras). Não roda sozinho; é importado pelos demais | — |
| 0 | `camadas.py` | limpeza dos dados e construção calibrada das **Camadas A, B e C** (todos os limiares ficam aqui). Importado pelos demais | — |
| 1 | `frente2.py` | análise de sensibilidade dos cinco limiares e tabela das camadas calibradas (Tabela 1 do relatório) | `out/frente2/` |
| 2 | `comunidades.py` | comunidades nas três camadas com **Girvan-Newman, Louvain e Leiden implementados do zero** (comparação entre algoritmos, com o segmento e entre camadas) | `out/comunidades/` |
| 2 | `visual_comunidades.py` | figuras (mapas de calor) das partições; `--salvar` grava os PNGs | `out/comunidades/` |
| 3 | `frente4.py` | centralidades, **fundos-ponte**, segmentos que andam juntos, carteiras (referência × concentrada, aparente × efetiva) e robustez | `out/frente4/<modo>/` |

> **Duas implementações de Louvain, de propósito.** A Tabela 1 do relatório
> (Q = 0,574 / 0,422 / 0,664) usa o `python-louvain` via `grafos.py` (semente 1).
> As comparações entre algoritmos usam o `comunidades.py` (semente 42). Na
> Camada B os dois diferem um pouco (Q = 0,422 contra 0,433) porque o Louvain
> é estocástico; nas Camadas A e C coincidem.

## Validação (confere se o pipeline recupera o que deveria)

| Arquivo | Papel | Saída |
|---|---|---|
| `teste_sintetico.py` | 500 fundos sintéticos com estrutura conhecida, em três cenários | `out/teste_sintetico/` |
| `analise_ampliada.py` | repete a análise na base real ampliada (156 fundos) | `out/ampliada/` |
| `coleta_ampliada.py` | coleta de todos os FIIs negociados (Fundamentus + CVM + Yahoo), em 5 partes | `dados/ampliado/` |

## Preparação dos dados

| Arquivo | Papel |
|---|---|
| `gera_base_v2.py` | gera `atributos_fiis_v2.xlsx` (segmento reclassificado). O resultado já está versionado |
| `docs/1. Dados Reais/src/` | scripts da coleta original (atributos e preços); mantidos como registro |

## Exemplo / protótipo (não são o resultado final)

| Arquivo | Situação |
|---|---|
| `main.py` | protótipo inicial com **dados simulados** e parâmetros antigos (limiar 0,5; k = 4). Serve de demonstração e de teste rápido de que `grafos.py` roda |
| `data.py` | dados simulados (40 FIIs) do protótipo. **Ainda é importado** pelo `frente4.py` (carteiras de exemplo e modo `--dados-simulados`): não apagar |
| `pseudocodigo/` | `louvain.py`, `leiden.py` e `girvan_newman.py`: **só pseudocódigo comentado**, material de estudo. Não são importados nem executados |
