"""
Coleta da base ampliada (todos os ~380 FIIs negociados) dividida entre os membros do grupo.

O Yahoo limita requisições por IP (erro 429). Por isso a coleta de preços é
dividida em partes: cada pessoa baixa a sua fatia na própria máquina e uma
pessoa junta tudo no fim.

Etapas (a partir da raiz do repositório):
    python src/coleta_ampliada.py universo            # 1x: lista de fundos (Fundamentus + CVM)
    python src/coleta_ampliada.py precos --parte 1    # cada membro, de 1 a 5
    python src/coleta_ampliada.py juntar              # 1x: junta as partes

Saída em dados/ampliado/:
    universo.csv              fundos, segmento, mandato e indicadores
    partes/precos_parte_N.csv preços de cada parte
    precos.csv                base final, no mesmo formato da Frente 1

Diferença importante em relação à coleta da Frente 1: NÃO há bfill. Dias sem
negócio dentro da série são preenchidos só para frente (preço parado);
antes da primeira cotação fica vazio. A limpeza do camadas.py faz o resto.
"""
import argparse
import io
import os
import sys
import time
import zipfile

import numpy as np
import pandas as pd
import requests

PASTA = os.path.join("dados", "ampliado")
PASTA_PARTES = os.path.join(PASTA, "partes")
ARQ_UNIVERSO = os.path.join(PASTA, "universo.csv")
ARQ_PRECOS = os.path.join(PASTA, "precos.csv")

N_PARTES = 5
INICIO, FIM = "2023-01-01", "2025-01-01"   # mesma janela da base da Frente 1
LOTE = 10                                  # tickers por requisição ao Yahoo
PAUSA = 3                                  # segundos entre lotes
TENTATIVAS = 6

ARQ_BASE_V2 = os.path.join("docs", "1. Dados Reais", "Tabelas - Dados", "atributos_fiis_v2.xlsx")
URL_FUNDAMENTUS = "https://www.fundamentus.com.br/fii_resultado.php"
URL_CVM = "https://dados.cvm.gov.br/dados/FII/DOC/INF_MENSAL/DADOS/inf_mensal_fii_2024.zip"
NAVEGADOR = {"User-Agent": "Mozilla/5.0"}

LIMITE_FFILL = 10   # dias sem negócio preenchidos para frente; mais que isso fica vazio

# segmentos já específicos na CVM e no Fundamentus; os demais são decididos
# pela composição do ativo (ver segmento_analise)
SEGMENTO_CVM = {"Logística": "Logística", "Shoppings": "Shoppings",
                "Lajes Corporativas": "Lajes", "Residencial": "Residencial",
                "Hospital": "Hospital", "Hotel": "Hotel"}
SEGMENTO_FUNDAMENTUS = {**SEGMENTO_CVM, "Escritórios": "Lajes", "Varejo": "Renda Urbana",
                        "Títulos e Val. Mob.": "Papel"}


# ---------------------------------------------------------------- 1. universo

def baixar_fundamentus():
    """Uma requisição traz todos os FIIs listados com os indicadores."""
    html = requests.get(URL_FUNDAMENTUS, headers=NAVEGADOR, timeout=60).text
    t = pd.read_html(io.StringIO(html), decimal=",", thousands=".")[0]
    t = t.rename(columns={"Papel": "ticker", "Segmento": "segmento_fundamentus",
                          "Dividend Yield": "dy", "P/VP": "pvp",
                          "Valor de Mercado": "valor_mercado", "Liquidez": "liquidez",
                          "Qtd de imóveis": "num_imoveis", "Vacância Média": "vacancia"})
    for c in ["dy", "vacancia"]:   # vêm como texto "10,5%"
        t[c] = pd.to_numeric(t[c].astype(str).str.replace("%", "").str.replace(".", "")
                             .str.replace(",", "."), errors="coerce")
    # vacância guardada só para referência: o Fundamentus publica valores sem
    # sentido (XPML11 91,8%, BRCR11 0,31%), então ela NÃO entra na análise
    t = t.rename(columns={"vacancia": "vacancia_nao_confiavel"})
    return t[["ticker", "segmento_fundamentus", "dy", "pvp", "valor_mercado",
              "liquidez", "num_imoveis", "vacancia_nao_confiavel"]]


def baixar_cvm():
    """Informe mensal de 2024: segmento, mandato, PL, ISIN e composição do ativo."""
    z = zipfile.ZipFile(io.BytesIO(requests.get(URL_CVM, timeout=120).content))
    le = lambda nome: pd.read_csv(z.open(nome), sep=";", encoding="latin-1", dtype=str)
    ultimo = lambda df: df.sort_values("Data_Referencia").groupby("CNPJ_Fundo_Classe").last()

    geral = ultimo(le("inf_mensal_fii_geral_2024.csv"))
    comp = ultimo(le("inf_mensal_fii_complemento_2024.csv"))
    ativo = ultimo(le("inf_mensal_fii_ativo_passivo_2024.csv"))

    num = lambda s: pd.to_numeric(s.str.replace(",", "."), errors="coerce").fillna(0)
    total = num(ativo["Total_Investido"])
    papel = sum(num(ativo[c]) for c in ["CRI", "CRI_CRA", "LCI", "LCI_LCA", "Titulos_Privados"])
    fii = num(ativo["FII"])

    cvm = pd.DataFrame({
        # ISIN de FII: BR + código de 4 letras + ... ; o ticker é o código + "11"
        "ticker": geral["Codigo_ISIN"].str[2:6] + "11",
        "nome": geral["Nome_Fundo_Classe"],
        "segmento_cvm": geral["Segmento_Atuacao"],
        "mandato": geral["Mandato"],
        "patrimonio_liquido": num(comp["Patrimonio_Liquido"]),
        "frac_papel": (papel / total.replace(0, np.nan)).reindex(geral.index),
        "frac_fii": (fii / total.replace(0, np.nan)).reindex(geral.index),
    })
    return cvm.rename_axis("cnpj").reset_index()


def segmento_analise(r):
    """Devolve (segmento, origem). Ordem:
    (1) segmento revisado pelo grupo na base v2, se o fundo estiver lá;
    (2) Fiagro pelo nome legal ("FIAGRO" ou "cadeias produtivas");
    (3) com dados da CVM: segmento da CVM se for específico; senão a
        composição do ativo (mais da metade em CRI/LCI/títulos = Papel, em
        cotas de FII = FoF, o resto = Híbrido);
    (4) sem CVM (fundo que mudou de código depois do ISIN): segmento do
        Fundamentus se for específico; sem imóveis = Papel; senão Híbrido.
    Os itens 2 a 4 são heurística automática, sem revisão manual."""
    if isinstance(r["segmento_v2"], str):
        return r["segmento_v2"], "revisado (base v2)"
    nome = str(r["nome"]).upper()
    if "FIAGRO" in nome or "CADEIAS PROD" in nome:
        return "Fiagro", "automático (CVM)"
    if isinstance(r["segmento_cvm"], str):
        if r["segmento_cvm"] in SEGMENTO_CVM:
            seg = SEGMENTO_CVM[r["segmento_cvm"]]
        elif r["frac_papel"] > 0.5:
            seg = "Papel"
        elif r["frac_fii"] > 0.5:
            seg = "FoF"
        else:
            seg = "Híbrido"
        return seg, "automático (CVM)"
    if r["segmento_fundamentus"] in SEGMENTO_FUNDAMENTUS:
        return SEGMENTO_FUNDAMENTUS[r["segmento_fundamentus"]], "automático (Fundamentus)"
    return ("Papel" if r["num_imoveis"] == 0 else "Híbrido"), "automático (Fundamentus)"


def montar_universo():
    f = baixar_fundamentus()
    c = baixar_cvm().drop_duplicates("ticker")
    # left join: fundo que mudou de código não casa com o ISIN da CVM, mas
    # continua na lista com os dados do Fundamentus
    u = f[f["liquidez"] > 0].merge(c, on="ticker", how="left")   # só fundos com negociação
    # PL = valor de mercado / (P/VP), a própria definição do P/VP; usado
    # quando o fundo não tem o PL da CVM
    pl_fundamentus = u["valor_mercado"] / u["pvp"].replace(0, np.nan)
    u["origem_pl"] = np.where(u["patrimonio_liquido"].notna(), "CVM", "Fundamentus (valor de mercado / P/VP)")
    u["patrimonio_liquido"] = u["patrimonio_liquido"].fillna(pl_fundamentus)
    v2 = pd.read_excel(ARQ_BASE_V2, sheet_name="Planilha A").set_index("ticker")
    u["segmento_v2"] = u["ticker"].map(v2["segmento"])
    u["gestora_v2"] = u["ticker"].map(v2["gestora"].str.strip())   # só os 55 revisados
    u[["segmento", "origem_segmento"]] = u.apply(lambda r: pd.Series(segmento_analise(r)), axis=1)
    u = u.sort_values("ticker").reset_index(drop=True)
    u["parte"] = u.index % N_PARTES + 1           # divisão intercalada e equilibrada
    os.makedirs(PASTA, exist_ok=True)
    u.to_csv(ARQ_UNIVERSO, index=False)
    print(f"[universo] {len(f)} no Fundamentus, {len(u)} negociados "
          f"({u['cnpj'].notna().sum()} casados com a CVM)")
    print(u["segmento"].value_counts().to_string())
    print(u["origem_segmento"].value_counts().to_string())
    print(u["parte"].value_counts().sort_index().rename("fundos por parte").to_string())


# ---------------------------------------------------------------- 2. preços

def baixar_lote(tickers):
    """Fechamento ajustado de um lote; tenta de novo com espera crescente."""
    import yfinance as yf
    for tentativa in range(TENTATIVAS):
        try:
            px = yf.download([t + ".SA" for t in tickers], start=INICIO, end=FIM,
                             auto_adjust=True, progress=False, threads=False)["Close"]
            if isinstance(px, pd.Series):
                px = px.to_frame(tickers[0] + ".SA")
            if px.notna().any().any():
                px.columns = [c.replace(".SA", "") for c in px.columns]
                return px
        except Exception as e:
            print(f"   erro: {e}")
        espera = PAUSA * 2 ** tentativa
        print(f"   lote sem dados (tentativa {tentativa + 1}/{TENTATIVAS}); esperando {espera}s")
        time.sleep(espera)
    return pd.DataFrame(columns=tickers)


def coletar_parte(parte):
    u = pd.read_csv(ARQ_UNIVERSO)
    tickers = list(u.loc[u["parte"] == parte, "ticker"])
    print(f"[parte {parte}] {len(tickers)} fundos")
    lotes = []
    for i in range(0, len(tickers), LOTE):
        lote = tickers[i:i + LOTE]
        print(f"   lote {i // LOTE + 1}: {', '.join(lote)}")
        lotes.append(baixar_lote(lote))
        time.sleep(PAUSA)
    px = pd.concat(lotes, axis=1).sort_index()
    faltam = [t for t in tickers if t not in px or px[t].isna().all()]
    os.makedirs(PASTA_PARTES, exist_ok=True)
    arq = os.path.join(PASTA_PARTES, f"precos_parte_{parte}.csv")
    px.to_csv(arq)
    print(f"[ok] {arq}: {px.shape[1] - len(faltam)} fundos com preço"
          + (f"; SEM DADOS: {', '.join(faltam)}" if faltam else ""))


# ---------------------------------------------------------------- 3. juntar

def juntar():
    u = pd.read_csv(ARQ_UNIVERSO)
    partes = []
    for p in range(1, N_PARTES + 1):
        arq = os.path.join(PASTA_PARTES, f"precos_parte_{p}.csv")
        if not os.path.exists(arq):
            sys.exit(f"ERRO: falta {arq} (quem ficou com a parte {p}?)")
        partes.append(pd.read_csv(arq, index_col=0, parse_dates=True))
    px = pd.concat(partes, axis=1).sort_index()
    px = px.loc[:, ~px.columns.duplicated()]

    sem = sorted(set(u["ticker"]) - set(px.columns[px.notna().any()]))
    # só para frente e no máximo LIMITE_FFILL dias: dia sem negócio repete o
    # último preço; antes da 1ª cotação e depois de o fundo sair da bolsa fica vazio
    px = px.ffill(limit=LIMITE_FFILL)
    px.index.name = "Date"
    # mesmo formato da base da Frente 1 (separador ';', decimal ',', data DD/MM/AAAA)
    px.to_csv(ARQ_PRECOS, sep=";", decimal=",", date_format="%d/%m/%Y")
    print(f"[ok] {ARQ_PRECOS}: {px.shape[1]} fundos x {px.shape[0]} pregões")
    if sem:
        print(f"   {len(sem)} fundos do universo sem nenhum preço: {', '.join(sem)}")


# ---------------------------------------------------------------- execução

def main():
    ap = argparse.ArgumentParser(description="Coleta da base ampliada, dividida em partes")
    sub = ap.add_subparsers(dest="etapa", required=True)
    sub.add_parser("universo", help="lista de fundos (Fundamentus + CVM)")
    p = sub.add_parser("precos", help="baixa os preços de uma parte")
    p.add_argument("--parte", type=int, required=True, choices=range(1, N_PARTES + 1))
    sub.add_parser("juntar", help="junta as partes na base final")
    a = ap.parse_args()
    if a.etapa == "universo":
        montar_universo()
    elif a.etapa == "precos":
        coletar_parte(a.parte)
    else:
        juntar()


if __name__ == "__main__":
    main()
