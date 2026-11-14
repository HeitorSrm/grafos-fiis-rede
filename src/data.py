"""
Camada de dados do protótipo.

Atributos escolhidos pelo grupo:
  Camada A (categóricos): segmento, indexador, gestora, tipo_fundo,
                          tipo_imovel, inquilinos
  Camada C (contínuos):   dividend_yield, pvp, vacancia, patrimonio_liquido,
                          liquidez, num_ativos

Em produção, troque `carregar_tudo_simulado()` por `coletar_dados_reais()`
(usa Fundamentus + yfinance). O resto do pipeline não muda.
"""
import numpy as np
import pandas as pd

# ---------------------------------------------------------------------------
# Universo de exemplo. Para cada FII: segmento, indexador, gestora.
# tipo_fundo e tipo_imovel são derivados do segmento (ver abaixo).
# inquilinos são atribuídos aos fundos de tijolo (pool com sobreposição).
# ---------------------------------------------------------------------------
UNIVERSO = [
    ("HGLG11", "Logistica",    "n/a",   "CSHG"),
    ("XPLG11", "Logistica",    "n/a",   "XP"),
    ("BTLG11", "Logistica",    "n/a",   "BTG"),
    ("VILG11", "Logistica",    "n/a",   "Vinci"),
    ("BRCO11", "Logistica",    "n/a",   "Bluemacaw"),
    ("LVBI11", "Logistica",    "n/a",   "VBI"),
    ("XPIN11", "Logistica",    "n/a",   "XP"),
    ("GGRC11", "Logistica",    "n/a",   "Genial"),
    ("XPML11", "Shoppings",    "n/a",   "XP"),
    ("VISC11", "Shoppings",    "n/a",   "Vinci"),
    ("HSML11", "Shoppings",    "n/a",   "HSI"),
    ("MALL11", "Shoppings",    "n/a",   "Genial"),
    ("VINO11", "Shoppings",    "n/a",   "Vinci"),
    ("KNRI11", "Lajes",        "n/a",   "Kinea"),
    ("HGRE11", "Lajes",        "n/a",   "CSHG"),
    ("PVBI11", "Lajes",        "n/a",   "VBI"),
    ("RCRB11", "Lajes",        "n/a",   "Rio Bravo"),
    ("BRCR11", "Lajes",        "n/a",   "BTG"),
    ("KNCR11", "Papel",        "CDI",   "Kinea"),
    ("KNIP11", "Papel",        "IPCA",  "Kinea"),
    ("MXRF11", "Papel",        "misto", "XP"),
    ("IRDM11", "Papel",        "IPCA",  "Iridium"),
    ("CPTS11", "Papel",        "misto", "Capitania"),
    ("RECR11", "Papel",        "misto", "REC"),
    ("DEVA11", "Papel",        "IPCA",  "Devant"),
    ("RBRR11", "Papel",        "IPCA",  "RBR"),
    ("VGIP11", "Papel",        "IPCA",  "Valora"),
    ("HGCR11", "Papel",        "CDI",   "CSHG"),
    ("VRTA11", "Papel",        "IPCA",  "Fator"),
    ("MCCI11", "Papel",        "misto", "Maua"),
    ("HGRU11", "Renda Urbana", "n/a",   "CSHG"),
    ("TRXF11", "Renda Urbana", "n/a",   "TRX"),
    ("RBVA11", "Renda Urbana", "n/a",   "Rio Bravo"),
    ("HFOF11", "FoF",          "n/a",   "CSHG"),
    ("KFOF11", "FoF",          "n/a",   "Kinea"),
    ("RBRF11", "FoF",          "n/a",   "RBR"),
    ("BCFF11", "FoF",          "n/a",   "BTG"),
    ("ALZR11", "Hibrido",      "n/a",   "Alianza"),
    ("RBRP11", "Hibrido",      "n/a",   "RBR"),
    ("HGPO11", "Hibrido",      "n/a",   "CSHG"),
]

# segmento -> tipo_fundo (classe ampla) e tipo_imovel
TIPO_FUNDO = {"Logistica": "Tijolo", "Shoppings": "Tijolo", "Lajes": "Tijolo",
              "Renda Urbana": "Tijolo", "Hibrido": "Hibrido", "Papel": "Papel",
              "FoF": "FoF"}
TIPO_IMOVEL = {"Logistica": "Galpao", "Shoppings": "Shopping", "Lajes": "Laje",
               "Renda Urbana": "Varejo", "Hibrido": "Misto", "Papel": "n/a",
               "FoF": "n/a"}

# inquilinos por fundo de tijolo (pool com sobreposição proposital:
# fundos que dividem inquilino carregam risco em comum -> aresta na Camada A)
INQUILINOS = {
    "HGLG11": ["Amazon", "BRF"],      "XPLG11": ["Amazon", "MercadoLivre"],
    "BTLG11": ["MercadoLivre", "Ambev"], "VILG11": ["Ambev", "Magalu"],
    "BRCO11": ["Amazon", "Magalu"],   "LVBI11": ["Ambev", "GPA"],
    "XPIN11": ["MercadoLivre", "BRF"], "GGRC11": ["Ambev", "GPA"],
    "XPML11": ["Renner", "CeA"],      "VISC11": ["Renner", "Riachuelo"],
    "HSML11": ["CeA", "Riachuelo"],   "MALL11": ["Renner", "Centauro"],
    "VINO11": ["Caixa", "BancoBrasil"],
    "KNRI11": ["Natura", "Vivo"],     "HGRE11": ["Vivo", "Petrobras"],
    "PVBI11": ["Natura", "Google"],   "RCRB11": ["Petrobras", "Itau"],
    "BRCR11": ["Petrobras", "Google"],
    "HGRU11": ["GPA", "BIG"],         "TRXF11": ["Assai", "BIG"],
    "RBVA11": ["Assai", "GPA"],
    "ALZR11": ["Natura", "Ambev"],    "RBRP11": ["Vivo", "Magalu"],
    "HGPO11": ["Itau", "Google"],
}

SEG_LIST = ["Logistica", "Shoppings", "Lajes", "Papel", "Renda Urbana",
            "FoF", "Hibrido"]

# Carteiras de exemplo para a demonstração (seção de carteiras)
CARTEIRA_IDEAL = ["HGLG11", "XPML11", "KNRI11", "KNIP11", "HGRU11",
                  "HFOF11", "ALZR11"]            # 1 por segmento
CARTEIRA_FALSA = ["HGLG11", "XPLG11", "BTLG11", "VILG11",
                  "XPML11", "VISC11", "HSML11", "MALL11"]  # só Log + Shoppings


def tabela_atributos() -> pd.DataFrame:
    """Atributos categóricos (Camada A) de cada FII."""
    df = pd.DataFrame(UNIVERSO,
                      columns=["ticker", "segmento", "indexador", "gestora"]
                      ).set_index("ticker")
    df["tipo_fundo"] = df["segmento"].map(TIPO_FUNDO)
    df["tipo_imovel"] = df["segmento"].map(TIPO_IMOVEL)
    df["inquilinos"] = df.index.map(lambda t: INQUILINOS.get(t, []))
    return df


def tabela_continua(seed: int = 7) -> pd.DataFrame:
    """
    Atributos contínuos (Camada C), simulados por segmento. Em produção
    vêm do Fundamentus/StatusInvest. vacancia e num_ativos não existem para
    Papel/FoF (ficam NaN, como no mundo real) -> o pipeline trata isso.
    """
    rng = np.random.default_rng(seed)
    at = tabela_atributos()
    linhas = {}
    for t, row in at.iterrows():
        s = row["segmento"]
        if s == "Papel":
            dy = rng.uniform(0.11, 0.14); pvp = rng.uniform(0.95, 1.03)
            vac = np.nan; nat = np.nan
            pl = rng.uniform(300, 4000); liq = rng.uniform(1, 12)
        elif s == "FoF":
            dy = rng.uniform(0.09, 0.11); pvp = rng.uniform(0.90, 1.00)
            vac = np.nan; nat = rng.integers(8, 30)
            pl = rng.uniform(200, 1500); liq = rng.uniform(0.5, 6)
        else:  # tijolo / híbrido
            dy = rng.uniform(0.07, 0.10); pvp = rng.uniform(0.80, 1.05)
            vac = rng.uniform(0.02, 0.12); nat = rng.integers(3, 25)
            pl = rng.uniform(300, 5000); liq = rng.uniform(1, 15)
        linhas[t] = dict(dividend_yield=dy, pvp=pvp, vacancia=vac,
                         patrimonio_liquido=pl, liquidez=liq, num_ativos=nat)
    df = pd.DataFrame(linhas).T

    # overrides para a carteira "falsa diversificada" ficar nitidamente ruim:
    # mono-ativo e vacância alta (atributos ruins, como o grupo pediu)
    ruins = {"VILG11": (1, 0.22), "MALL11": (1, 0.19), "HSML11": (2, 0.17),
             "BTLG11": (2, 0.15)}
    for t, (nat, vac) in ruins.items():
        df.loc[t, "num_ativos"] = nat
        df.loc[t, "vacancia"] = vac
    return df.astype(float)


# ---------------------------------------------------------------------------
# RETORNOS (Camada B) — simulados com estrutura de fatores por segmento
# ---------------------------------------------------------------------------
def carregar_retornos_simulados(dias: int = 500, seed: int = 42) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    at = tabela_atributos()
    seg = at["segmento"]
    f_mkt = rng.normal(0, 0.010, dias)
    f_seg = {s: rng.normal(0, 0.012, dias) for s in SEG_LIST}
    f_cdi = rng.normal(0, 0.008, dias); f_ipca = rng.normal(0, 0.008, dias)
    out = {}
    for t in at.index:
        s = seg[t]
        r = rng.uniform(0.6, 1.0) * f_mkt + rng.uniform(0.7, 1.1) * f_seg[s]
        if s == "Papel":
            idx = at.loc[t, "indexador"]
            if idx == "CDI":   r = r + 0.9 * f_cdi
            elif idx == "IPCA":r = r + 0.9 * f_ipca
            else:              r = r + 0.45 * f_cdi + 0.45 * f_ipca
        r = r + rng.normal(0, 0.006, dias)
        out[t] = r
    idx = pd.bdate_range(end=pd.Timestamp.today().normalize(), periods=dias)
    return pd.DataFrame(out, index=idx)


def carregar_tudo_simulado():
    """Conveniência: (atributos categóricos, contínuos, retornos)."""
    return tabela_atributos(), tabela_continua(), carregar_retornos_simulados()


# ===========================================================================
# PRODUÇÃO — coleta real (rode na máquina de vocês; aqui o proxy bloqueia)
# ===========================================================================
def coletar_continuos_fundamentus() -> pd.DataFrame:
    """
    UMA requisição traz TODOS os ~550 FIIs com segmento, DY, P/VP, liquidez,
    valor de mercado, qtd de imóveis, vacância média etc. Sem trabalho manual.
    """
    import pandas as pd
    url = "https://www.fundamentus.com.br/fii_resultado.php"
    # Fundamentus exige um User-Agent de navegador:
    tabs = pd.read_html(url, decimal=",", thousands=".",
                        storage_options={"User-Agent": "Mozilla/5.0"})
    return tabs[0]     # colunas: Papel, Segmento, Cotação, FFO Yield,
                       # Dividend Yield, P/VP, Valor de Mercado, Liquidez,
                       # Qtd de imóveis, Preço do m2, Aluguel/m2, Cap Rate,
                       # Vacância Média


def coletar_retornos_yfinance(periodo: str = "2y") -> pd.DataFrame:
    import yfinance as yf
    tickers = [t + ".SA" for t in tabela_atributos().index]
    px = yf.download(tickers, period=periodo, auto_adjust=True,
                     progress=False)["Close"]
    px.columns = [c.replace(".SA", "") for c in px.columns]
    px = px.dropna(axis=1, how="all").ffill().dropna()
    return np.log(px).diff().dropna()
