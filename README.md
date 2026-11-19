# FIIs como Rede de Similaridades — Protótipo (SMAC03 / Grafos, UNIFEI)

Protótipo do **Cenário 1 — Análise do Mercado de FIIs** da disciplina SMAC03.
Modela o conjunto de FIIs como uma **rede** e analisa similaridade e
dependência sob duas perspectivas complementares.

## Ideia central: três camadas de grafo (todas valoradas)

| Camada | O que captura | Como é construída |
|--------|---------------|-------------------|
| **A — Estrutural** | similaridade de *características* | **projeção bipartida** FII×característica, peso = itens compartilhados **ponderados por raridade** (TF-IDF) |
| **B — Comportamental** | *co-movimento* de preços | correlação dos retornos → distância `d=√(2(1−ρ))` → **MST de Mantegna** + grafo por limiar |
| **C — Fundamentalista** | similaridade de *perfil* | vetor contínuo normalizado (z-score) → distância → similaridade `1/(1+d)` → grafo **kNN** valorado |

Atributos (Camada A): segmento, indexador, gestora, tipo de fundo, tipo de
imóvel, inquilinos. Atributos (Camada C): DY, P/VP, vacância, patrimônio
líquido, liquidez, nº de ativos.

Cruzar as camadas responde à pergunta do cenário: *onde a diversificação
aparente esconde dependência real?* — demonstrado pela comparação de duas
carteiras (ideal × falsa diversificada) em `main.py`.

## Coleta de dados real (sem trabalho manual)

11 dos 12 atributos são coletáveis por código:
- **Fundamentus** (`coletar_continuos_fundamentus` em `data.py`): uma
  requisição traz todos os ~550 FIIs com segmento, DY, P/VP, liquidez,
  vacância média e nº de imóveis.
- **brapi.dev** (API): mandato, gestora, tipo de gestão, cotistas, PL.
- **CVM Dados Abertos** (Informe Mensal Estruturado): imóveis e vacância.
- **inquilinos**: único que exige parsing de PDF / coleta manual.

## Rodando

```bash
pip install -r requirements.txt
python src/main.py          # gera as figuras em ./out/
```

Por padrão usa **dados simulados** (estrutura realista de fatores por
segmento), porque o ambiente de desenvolvimento não tinha acesso ao Yahoo.
**Para usar dados reais**, em `main.py` troque:

```python
ret = data.carregar_dados_simulados()
# por:
ret = data.carregar_dados_yfinance("2y")
```

A função `carregar_dados_yfinance()` já está pronta em `data.py` (usa
`yfinance`, sufixo `.SA`). Os **atributos fundamentalistas** ficam na tabela
`UNIVERSO` em `data.py` — foram preenchidos à mão a partir de
Investidor10/Fundamentus/StatusInvest (essas fontes é que têm segmento e
indexador; o Yahoo não traz).

## Arquivos

- `data.py` — universo de FIIs, atributos e carregamento (simulado | yfinance)
- `grafos.py` — **núcleo algorítmico**: projeção bipartida, MST, limiar,
  comunidades (Louvain), centralidades, concordância com segmento (ARI),
  robustez
- `main.py` — pipeline CRISP-NET (dados → modelagem → avaliação → figuras)
- `frente4.py` — Frente 4 (descritiva, pontes, segmentos que andam juntos, carteiras, robustez) com os **dados reais**: `python src/frente4.py` (todos), `--top N` (N mais líquidos), `--dados-simulados` (40 FIIs de `data.py`) ou `--simular N` (teste de escala); saída em `out/frente4/<modo>/` (.csv, .tex e .png)
- `out/` — figuras geradas

## Algoritmos de teoria dos grafos usados

Projeção de grafo bipartido · árvore geradora mínima (Kruskal/Prim via
`networkx`) · detecção de comunidades (modularidade / Louvain) ·
centralidades (grau, intermediação, autovetor) · componentes conexos ·
análise de robustez por remoção de vértices.
