# Dicionário de Dados — versão 2 (adendo)

Complementa `dicionario.md`, que continua válido para
`precos_diarios_FIIs_1_excel.csv` e para a `Planilha C`. Este adendo descreve
apenas o que mudou na `Planilha A`, agora em
`Tabelas - Dados/atributos_fiis_v2.xlsx`.

O arquivo original `atributos_fiis.xlsx` foi preservado. Quem reproduzir a v2
deve rodar `python src/gera_base_v2.py`.

## Por que houve uma versão 2

Dois campos da `Planilha A` não podiam ser usados como estavam.

**`segmento`.** Dos 55 fundos, 29 vieram classificados como "Multicategoria"
e 7 como "Outros" — 65% da amostra em dois rótulos que não distinguem nada.
Havia ainda erros pontuais, como MXRF11, que é fundo de papel, classificado
como "Logística". Como a Camada A da modelagem é construída sobre atributos
compartilhados, um campo nesse estado faria praticamente toda a amostra
compartilhar o mesmo valor.

**`tipo_fundo`.** Veio preenchido como "Tijolo" para os 55 fundos, incluindo
KNCR11, KNIP11 e MXRF11, que são fundos de papel. O campo não foi coletado.

A reclassificação manual dos 55 fundos já existia, mas estava embutida no
código de análise (`src/frente4.py`, dicionário `SEGMENTO_ANALISE`). Isso
mantinha duas versões do mesmo atributo: uma na planilha, descrita neste
dicionário, e outra dentro do script, que era a efetivamente usada nas
figuras. A v2 existe para unificá-las.

## O que mudou na Planilha A

| Coluna | Situação na v2 |
|---|---|
| `ticker` | inalterada |
| `segmento` | **substituída** pela classificação revisada (9 segmentos) |
| `segmento_planilha` | **nova**: guarda o valor original, para rastreabilidade |
| `gestora` | inalterada (apenas espaços nas pontas removidos) |
| `tipo_fundo` | **removida**: não foi coletada |
| `inquilinos` | inalterada |

A `Planilha C` é copiada sem alteração.

### Coluna `segmento` (v2)

Classificação revisada fundo a fundo, a partir dos relatórios gerenciais.
41 dos 55 fundos tiveram o valor corrigido.

| Valor | Fundos | Descrição |
|---|---|---|
| `Papel` | 17 | carteira majoritariamente de CRI |
| `Logística` | 9 | galpões e centros de distribuição |
| `Lajes` | 8 | lajes corporativas e escritórios |
| `Shoppings` | 8 | shopping centers |
| `Híbrido` | 4 | mais de uma classe de imóvel, sem predominância |
| `FoF` | 3 | fundo de fundos: carteira de cotas de outros FIIs |
| `Renda Urbana` | 3 | varejo de rua, educação, logística urbana |
| `Fiagro` | 2 | recebíveis do agronegócio |
| `Desenvolvimento` | 1 | incorporação e desenvolvimento imobiliário |

### Observação sobre `inquilinos`

O campo permanece como foi coletado; o tratamento é feito na análise
(`src/camadas.py`). Ele contém três tipos de conteúdo:

- **locatários específicos do fundo**, nos fundos de tijolo — é o dado usado;
- **listas genéricas por segmento**: os mesmos 11 devedores de CRI em 16
  fundos de papel e os mesmos lojistas em 8 fundos de shopping. Os nomes são
  reais, mas não são específicos de cada fundo;
- **descrições do lastro**, não nomes: "cotas de outros FIIs listados…" em
  3 FoFs e "CRAs de produtores rurais…" em 2 Fiagros.

Regras da análise: inquilino só é considerado para fundos de tijolo
(Logística, Shoppings, Lajes, Renda Urbana e Híbrido), porque Papel, FoF e
Fiagro não têm locatário; e listas idênticas repetidas em mais de quatro
fundos são ignoradas por serem genéricas. Entre os 46 fundos analisados,
19 ficam com inquilinos e 27 com lista vazia (20 que não são de tijolo e os
7 shoppings).

## Campos previstos e não coletados

`indexador` e `tipo_imovel` constavam do plano da Camada A, mas não foram
coletados e não existem em nenhuma das versões da planilha. A `vacância`,
prevista para a Camada C, também não foi coletada; a camada usa cinco
indicadores, não seis.
