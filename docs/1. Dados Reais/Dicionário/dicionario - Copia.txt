# Dicionário de Dados - Fase 1 (Dados Reais)

## Visão Geral
- **Universo de Fundos**: Amostra representativa de FIIs negociados na B3 (segmentos como Tijolos, Papel/CRI e híbridos).
- **Período de Análise**: Entre 01/01/2023 a 01/01/2025 (2 anos de cotações diárias).
- **Frequência**: Diária (dias úteis de negociação).
- **Fontes**: Yahoo Finance (yfinance), Fundamentus e pesquisa individual dos fundos

## 1. 'precos_diarios_FIIs_1_excel.csv'
Matriz que contem as cotações históricas de fechamento ajustado (55 FIIs).

* **Estrutura**: As linhas representam as datas de negociação e as colunas representam os códigos de cada FII.
* **Formato**: CSV (separador: ';' , decimal: '.')

|'Date' *(1ª Coluna)* | Data (`YYYY-MM-DD`) | Data do pregão negociado na B3 | `2023-01-02` | Yahoo Finance |
|'<TICKER>' *(demais colunas)* | Numérico ('float') | Preço de fechamento diário do fundo | '162.50' (R$) | Yahoo Finance

## 2. `atributos_fiis.xlsx`
Atributos dos 55 FIIs, visando a construção da Matriz Bipartida. O arquivo é dividido em duas planilhas (abas), cada uma com uma linha por FII e `ticker` como chave de ligação entre elas.

* **Formato**: Excel (.xlsx), com as abas `Planilha A` e `Planilha C`.

### 2.1 Planilha A – Características qualitativas
| Coluna | Tipo de Dado | Descrição | Exemplo | Fonte |
|---|---|---|---|---|
| `ticker` | Texto (`string`) | Código de negociação do FII na B3 | `HGLG11` | Fundamentus |
| `segmento` | Texto (`string`) | Setor de atuação principal do fundo | `Logística` | Fundamentus |
| `gestora` | Texto (`string`) | Instituição responsável pela gestão do fundo | `Bresco Gestão` | Pesquisa manual |
| `tipo_fundo` | Texto (`string`) | Classificação do fundo quanto à natureza dos ativos (ex.: Tijolo, Papel, Híbrido) | `Tijolo` | Pesquisa manual |
| `inquilinos` | Texto (`string`) | Principais inquilinos/locatários dos imóveis do fundo | `Natura, Mercado Livre, Carrefour` | Pesquisa manual |

### 2.2 Planilha C – Indicadores quantitativos
| Coluna | Tipo de Dado | Descrição | Exemplo / Unidade | Fonte |
|---|---|---|---|---|
| `ticker` | Texto (`string`) | Código de negociação do FII na B3 | `ALZR11` | Fundamentus |
| `dy_12m` | Numérico (`float`) | Dividend Yield acumulado nos últimos 12 meses | `10.38` (%) | Fundamentus |
| `p_vp` | Numérico (`float`) | Razão Preço sobre Valor Patrimonial | `0.89` | Fundamentus |
| `patrimonio_liquido` | Inteiro (`integer`) | Patrimônio líquido do fundo | `1771808989` (R$) | Fundamentus |
| `liquidez_diaria` | Inteiro (`integer`) | Volume médio diário negociado | `3935680` (R$) | Fundamentus |
| `num_ativos` | Inteiro (`integer`) | Quantidade de ativos no portfólio do fundo | `20` | Fundamentus |

## Observações sobre a coleta
- Os dados de `gestora` e `inquilinos` não puderam ser coletados de forma automatizada; cada fundo foi pesquisado individualmente (sites das gestoras, relatórios gerenciais e páginas dos fundos).
- Os campos da Planilha C foram coletados via script (`atributos_FIIs.py`) a partir do Fundamentus e refletem a data da coleta, não o período das cotações.