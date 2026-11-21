# Camada A — backbone kNN com empates

**Decisão:** o backbone da Camada A guarda as k arestas mais fortes de cada fundo
**e também as que empatam com a k-ésima**.

**Motivo:** sem o `tipo_fundo`, fundos que só compartilham o segmento têm arestas
de peso idêntico (ex.: 1,12 entre quaisquer dois fundos de Papel). 29 dos 46 fundos
tinham empate exatamente no corte k = 3, e o desempate era decidido pela ordem das
linhas da planilha.

Reproduzir: `python src/frente2.py` (saída em `out/frente2/`). A mudança está na
função `backbone_knn` de `src/camadas.py`.

## O problema: o resultado dependia da ordem da planilha

| Configuração | Arestas | Arestas iguais à original | Comunidades | Modularidade | ARI com segmento |
|---|---|---|---|---|---|
| Backbone k=3, ordem original | 98 | 98/98 | 6 | 0,656 | 0,452 |
| Mesmo backbone, linhas embaralhadas (1) | 99 | 69/98 | 6 | 0,637 | 0,404 |
| Mesmo backbone, linhas embaralhadas (2) | 95 | 74/98 | 7 | 0,627 | 0,338 |
| **Backbone k=3 com empates (qualquer ordem)** | **191** | **sempre igual** | **6** | **0,600** | **0,857** |

## Opções avaliadas

| Opção | Arestas | Densidade | Grau médio | Componentes | ARI com segmento | Depende da ordem? |
|---|---|---|---|---|---|---|
| Backbone k=3 sem empates (anterior) | 98 | 0,095 | 4,3 | 1 | 0,34–0,45 | sim |
| Grafo completo sem `tipo_fundo` | 233 | 0,225 | 10,1 | 1 | 0,857 | não |
| **Backbone k=3 com empates (adotado)** | **191** | **0,185** | **8,3** | **1** | **0,857** | **não** |

## Varredura de k: antes × depois

| k | Arestas (antes) | Componentes (antes) | ARI (antes) | Arestas (depois) | Componentes (depois) | ARI (depois) |
|---|---|---|---|---|---|---|
| 2 | 67 | 4 | 0,409 | 148 | 2 | 0,626 |
| **3** | 98 | 1 | 0,452 | **191** | **1** | **0,857** |
| 4 | 125 | 1 | 0,525 | 206 | 1 | 0,857 |
| 5 | 149 | 1 | 0,653 | 225 | 1 | 0,857 |
| 6 | 173 | 1 | 0,834 | 229 | 1 | 0,857 |
| 8 | 204 | 1 | 0,836 | 231 | 1 | 0,857 |

k = 3 continua sendo o menor valor que deixa o grafo conexo. Com os empates, o ARI
fica estável para qualquer k ≥ 3: o resultado não depende de ajuste fino.

## Grafos resultantes (atualizado)

| Camada | Arestas | Densidade | Grau médio | Componentes | Comunidades | Modularidade | ARI com segmento |
|---|---|---|---|---|---|---|---|
| A — backbone k=3 com empates | 191 | 0,185 | 8,3 | 1 | 6 | 0,600 | 0,857 |
| B — MST ∪ ρ ≥ 0,32 | 68 | 0,066 | 3,0 | 1 | 5 | 0,422 | 0,210 |
| C — kNN k=3 | 95 | 0,092 | 4,1 | 1 | 6 | 0,664 | 0,122 |

**Custo:** a Camada A fica mais densa que B e C (0,185 contra 0,07–0,09). É
consequência de a camada ser feita de atributos discretos: fundos que compartilham
as mesmas características são idênticos para ela, e igualar a densidade exigiria
escolher arbitrariamente entre eles. As Camadas B e C não mudam.

## Pendências se a decisão for adotada

Os números antigos da Camada A (98 arestas, ARI 0,452) ainda aparecem em
`docs/frente2-thresholds.md`, `docs/frente2-modelagem.tex` e na tabela do
`README.md`, e precisam ser atualizados pela Frente 2.
