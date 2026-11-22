"""
Frente 2 — gera a versao 2 da base de atributos.

A Planilha A entregue pela Frente 1 tem dois campos inutilizaveis:

  * `segmento`: 29 dos 55 fundos vieram como "Multicategoria" e 7 como
    "Outros" (65% da amostra em dois rotulos que nao discriminam nada);
    MXRF11, que e fundo de papel, veio como "Logistica".
  * `tipo_fundo`: veio "Tijolo" para os 55 fundos, incluindo KNCR11,
    KNIP11 e MXRF11, que sao de papel. O campo nao foi preenchido.

A reclassificacao manual dos 55 fundos ja existia, mas estava embutida no
`src/frente4.py` (dicionario SEGMENTO_ANALISE). Isso deixava duas versoes
do mesmo atributo: uma na planilha, descrita no dicionario de dados, e
outra dentro do script, que era a de fato usada nas figuras.

Este script passa a reclassificacao para a base, gerando
`atributos_fiis_v2.xlsx`. O arquivo original e preservado.

O que muda na Planilha A:
  * `segmento` passa a ser a classificacao revisada (9 segmentos);
  * `segmento_planilha` guarda o valor original, para rastreabilidade;
  * `tipo_fundo` sai, por nao ter sido coletado.

Uso (a partir da raiz do repositorio):
    python src/gera_base_v2.py
"""
import os

import pandas as pd

PASTA = os.path.join("docs", "1. Dados Reais", "Tabelas - Dados")
ENTRADA = os.path.join(PASTA, "atributos_fiis.xlsx")
SAIDA = os.path.join(PASTA, "atributos_fiis_v2.xlsx")

# Classificacao revisada dos 55 fundos da amostra.
# Origem: dicionario SEGMENTO_ANALISE da primeira versao de src/frente4.py
# (Frente 4), que hoje le a classificacao desta base.
SEGMENTOS = {
    "Logística": "HGLG11 XPLG11 BTLG11 LVBI11 VILG11 BRCO11 HSLG11 GGRC11 TRBL11",
    "Shoppings": "XPML11 VISC11 HSML11 HGBS11 CPSH11 FIGS11 FVPQ11 PQDP11",
    "Lajes": "BRCR11 PVBI11 HGRE11 JSRE11 RCRB11 BROF11 VINO11 TEPP11",
    "Renda Urbana": "TRXF11 RBVA11 HGRU11",
    "Híbrido": "KNRI11 ALZR11 GARE11 RBRP11",
    "Papel": "KNCR11 KNIP11 HGCR11 RECR11 CPTS11 MXRF11 KNSC11 RBRY11 PORD11 "
             "HABT11 MCCI11 VRTA11 VGIR11 KCRE11 SNCI11 RBRR11 VSLH11",
    "FoF": "HFOF11 KFOF11 BCIA11",
    "Fiagro": "VGIA11 XPCA11",
    "Desenvolvimento": "TGAR11",
}
SEGMENTO_DE = {t: s for s, lista in SEGMENTOS.items() for t in lista.split()}


def main():
    A = pd.read_excel(ENTRADA, sheet_name="Planilha A")
    C = pd.read_excel(ENTRADA, sheet_name="Planilha C")

    faltando = sorted(set(A["ticker"]) - set(SEGMENTO_DE))
    if faltando:
        raise SystemExit(f"ERRO: sem classificacao para {faltando}")

    A2 = pd.DataFrame({
        "ticker": A["ticker"],
        "segmento": [SEGMENTO_DE[t] for t in A["ticker"]],
        "segmento_planilha": A["segmento"],
        "gestora": A["gestora"].str.strip(),
        "inquilinos": A["inquilinos"],
    })

    with pd.ExcelWriter(SAIDA, engine="openpyxl") as xls:
        A2.to_excel(xls, sheet_name="Planilha A", index=False)
        C.to_excel(xls, sheet_name="Planilha C", index=False)

    mudou = (A2["segmento"] != A2["segmento_planilha"]).sum()
    print(f"[ok] {SAIDA}")
    print(f"     {len(A2)} fundos | {mudou} tiveram o segmento corrigido "
          f"| {A2['segmento'].nunique()} segmentos")
    print(A2["segmento"].value_counts().to_string())


if __name__ == "__main__":
    main()
