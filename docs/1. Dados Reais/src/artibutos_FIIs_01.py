import os
from io import StringIO

import pandas as pd
import requests

HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
BASE = "https://www.fundamentus.com.br"


def pct_para_float(serie):
    """Converte '8,50%' / '1.234,5%' em float; se já for número, mantém."""
    if pd.api.types.is_numeric_dtype(serie):
        return serie
    return pd.to_numeric(
        serie.astype(str)
        .str.replace("%", "", regex=False)
        .str.replace(".", "", regex=False)
        .str.replace(",", ".", regex=False),
        errors="coerce",
    )


def para_float(serie):
    """Converte números em texto ('1.234.567,89') para float; se já for número, mantém."""
    if pd.api.types.is_numeric_dtype(serie):
        return serie
    return pd.to_numeric(
        serie.astype(str)
        .str.replace(".", "", regex=False)
        .str.replace(",", ".", regex=False),
        errors="coerce",
    )


def classificar_tipo(segmento):
    """Aproximação do tipo de fundo a partir do segmento. Revise manualmente."""
    s = str(segmento).lower()
    if s in ("", "nan"):
        return ""
    if "títulos" in s or "recebíveis" in s or "papel" in s:
        return "Papel"
    if "fundo de fundos" in s or "fof" in s:
        return "FoF"
    if "híbrido" in s or "hibrido" in s:
        return "Híbrido"
    return "Tijolo"


try:
    # 1. Lista de FIIs do CSV de preços
    df_precos = pd.read_csv("precos_diarios_FIIs_1_excel.csv", sep=";", index_col=0)
    tickers_amostra = [c.replace(".SA", "").strip() for c in df_precos.columns]
    print(f"FIIs encontrados no CSV: {len(tickers_amostra)}")

    # 2. Tabela geral do Fundamentus
    req = requests.get(f"{BASE}/fii_resultado.php", headers=HEADERS, timeout=30)
    req.raise_for_status()
    df_fund = pd.read_html(StringIO(req.text), decimal=",", thousands=".")[0]
    print("Colunas encontradas:", df_fund.columns.tolist())

    df_fund = df_fund.rename(columns={
        "Papel": "ticker",
        "Segmento": "segmento",
        "Dividend Yield": "dy_12m",
        "P/VP": "p_vp",
        "Valor de Mercado": "valor_mercado",
        "Liquidez": "liquidez_diaria",
        "Qtd de imóveis": "num_ativos",
    })

    obrigatorias = ["ticker", "segmento", "dy_12m", "p_vp", "valor_mercado",
                    "liquidez_diaria", "num_ativos"]
    faltantes = [c for c in obrigatorias if c not in df_fund.columns]
    if faltantes:
        raise ValueError(f"Colunas não encontradas: {faltantes}")

    # 3. Filtra os FIIs do CSV
    df_fund["ticker"] = df_fund["ticker"].astype(str).str.strip()
    df = df_fund[df_fund["ticker"].isin(tickers_amostra)][obrigatorias].copy()
    print(f"FIIs correspondentes: {len(df)}")

    # 4. Conversões numéricas
    df["dy_12m"] = pct_para_float(df["dy_12m"])
    df["p_vp"] = para_float(df["p_vp"])
    df["valor_mercado"] = para_float(df["valor_mercado"])

    # 5. Patrimônio líquido = valor de mercado / P/VP (aproximação)
    df["patrimonio_liquido"] = (
        (df["valor_mercado"] / df["p_vp"]).where(df["p_vp"] > 0).round(0)
    )

    # 6. Colunas sem fonte no Fundamentus
    df["tipo_fundo"] = df["segmento"].apply(classificar_tipo)
    df["gestora"] = ""      # preencher via CVM ou manualmente
    df["inquilinos"] = ""   # preencher manualmente / relatórios gerenciais

    # 7. Duas planilhas no mesmo arquivo
    planilha_a = df[["ticker", "segmento", "gestora", "tipo_fundo", "inquilinos"]]
    planilha_c = df[["ticker", "dy_12m", "p_vp", "patrimonio_liquido",
                     "liquidez_diaria", "num_ativos"]]

    nome_saida = "atributos_fiis.xlsx"
    with pd.ExcelWriter(nome_saida, engine="openpyxl") as writer:
        planilha_a.to_excel(writer, sheet_name="Planilha A", index=False)
        planilha_c.to_excel(writer, sheet_name="Planilha C", index=False)

    print("\nArquivo criado com sucesso!")
    print(f"Caminho: {os.path.abspath(nome_saida)}")

except Exception as e:
    print(f"\nERRO DURANTE A EXECUÇÃO: {str(e)[:500]}")