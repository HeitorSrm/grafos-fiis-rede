# Roteiro e cronograma — SMAC03 (Cenário 1: FIIs como rede)

> Versão gerada neste chat (a do chat anterior não estava acessível). Substitua/ajuste se o grupo tiver outra.

## Papéis e cronograma (entrega final: 22/11)
| Frente | Responsável | Entrega |
|---|---|---|
| Coordenação, questão de pesquisa, relatório | Coordenador | transversal |
| Curadoria do dataset (preços + atributos) | Modelador B | até 11/11 |
| Modelagem formal (camadas A/B/C), hipóteses, thresholds | Modelador A | até 12/11 |
| Núcleo algorítmico (grafos.py) + arquitetura | Desenvolvedor A | até 15/11 |
| Métricas, validação, figuras, demo/vídeo | Desenvolvedor B | até 18/11 |
| Interpretação dos resultados, slides | Modeladores + todos | 19–21/11 |
| Revisão final e entrega | Coordenador | 22/11 |

## Roteiro da reunião com o professor
1. Problema relacional + questão de pesquisa e hipóteses;
2. Modelagem em camadas (A estrutural valorada, B mercado/MST, C fundamentalista) e por que atende ao cenário;
3. Prova de conceito rodando (dados simulados) + comparação carteira ideal × falsa;
4. Metodologia CRISP-NET e vínculo com os papers;
5. Pedir feedback: definição das arestas, métricas, tamanho do universo.

## Limitações a declarar
- yfinance é não-oficial; salvar preços em CSV após baixar;
- correlação sensível à janela/regime; reportar o período;
- ~30–60 fundos (além disso vira "novelo");
- limiar da projeção e ρ-mínimo são decisões de modelagem — testar valores.

Ver também: [cronograma da frente 2](cronograma-frente2.md).
