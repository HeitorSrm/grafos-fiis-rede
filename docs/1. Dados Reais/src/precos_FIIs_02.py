import yfinance as yf
import pandas as pd

# Lista de FIIs ativos e testados
tickers = [
    # Logística
    "HGLG11.SA", "XPLG11.SA", "BTLG11.SA", "LVBI11.SA", "VILG11.SA",
    "BRCO11.SA", "HSLG11.SA", "GARE11.SA", "TRBL11.SA", "GGRC11.SA",

    # Shoppings e Varejo
    "XPML11.SA", "VISC11.SA", "HSML11.SA", "HGBS11.SA", "CPSH11.SA",
    "FIGS11.SA", "FVPQ11.SA", "PQDP11.SA", "TRXF11.SA", "RBVA11.SA",

    # Lajes Corporativas
    "KNRI11.SA", "BRCR11.SA", "PVBI11.SA", "HGRE11.SA", "JSRE11.SA",
    "RBRR11.SA", "VINO11.SA", "RCRB11.SA", "TEPP11.SA", "BROF11.SA",

    # Papel / CRIs
    "KNCR11.SA", "KNIP11.SA", "HGCR11.SA", "RECR11.SA", "CPTS11.SA",
    "MXRF11.SA", "KNSC11.SA", "RBRY11.SA", "PORD11.SA", "HABT11.SA",
    "MCCI11.SA", "VRTA11.SA", "VGIA11.SA", "XPCA11.SA",

    # Outros / FoFs / Renda Urbana
    "ALZR11.SA", "TGAR11.SA", "VGIR11.SA", "HFOF11.SA", "HGRU11.SA",
    "KCRE11.SA", "VSLH11.SA", "RBRP11.SA", "KFOF11.SA", "BCIA11.SA",
    "SNCI11.SA"
]

#* Baixa os preços
df_precos = yf.download(
    tickers,
    start="2023-01-01",
    end="2025-01-01"
)['Close']

#* Preenche pequenas lacunas pontuais de feriados/finais de semana
df_precos = df_precos.ffill().bfill()

#* Arrendonda as cotações para 4 casas decimais
df_precos = df_precos.round(4)

df_precos.to_csv(
    "precos_diarios_FIIs_1_excel.csv",
    sep=";",
    decimal=","
)