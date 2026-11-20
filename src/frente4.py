"""
Frente 4 — características gerais, centralidades e carteiras.

Perguntas:
  (b) quais FIIs são centrais / pontes na rede de co-movimento?
  (c) quais pares de segmentos diferentes se movem juntos?
      (diversificação aparente x efetiva)

Uso (a partir da raiz do repositório):
    python src/frente4.py                    # dados reais   -> out/frente4/todos
    python src/frente4.py --top 30           # 30 mais líquidos -> out/frente4/top30
    python src/frente4.py --dados-simulados  # 40 FIIs de data.py
    python src/frente4.py --simular 300      # universo sintético (teste de escala)
"""
import argparse
import os
import sys

import numpy as np
import pandas as pd
import networkx as nx
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Patch

import data
import grafos as gr

# Limiar da Camada B. Com dados diários a correlação entre FIIs é baixa
# (mediana ~0,19, máx ~0,48): com 0,5 o grafo fica vazio.
# O valor final vem da Frente 2.
RHO_MIN = 0.3
K_KNN = 4          # vizinhos por nó na Camada C
LIMIAR_A = 0.0     # peso mínimo de aresta na Camada A

COBERTURA_MIN = 0.90   # fração mínima do período com cotação real
ZEROS_MAX = 0.30       # fração máxima de dias com retorno exatamente zero
REPETICAO_MAX = 4      # lista de inquilinos repetida em mais fundos = preenchimento padrão

N_ROTULOS = 60     # acima disso as figuras mostram o segmento, não o fundo
N_AMOSTRA = 300    # acima disso caminho, diâmetro e intermediação são amostrados
K_AMOSTRA = 100    # nº de vértices de origem na amostragem
N_SORTEIOS = 30    # sorteios da remoção aleatória
SEMENTE = 42

PASTA_DADOS = os.path.join("docs", "1. Dados Reais", "Tabelas - Dados")
ARQ_PRECOS = os.path.join(PASTA_DADOS, "precos_diarios_FIIs_1_excel.csv")
ARQ_ATRIB = os.path.join(PASTA_DADOS, "atributos_fiis.xlsx")

PALETA = {"Logistica": "#2563eb", "Shoppings": "#db2777", "Lajes": "#059669",
          "Papel": "#d97706", "Renda Urbana": "#7c3aed", "FoF": "#0891b2",
          "Hibrido": "#64748b", "Fiagro": "#65a30d", "Desenvolvimento": "#92400e"}

# Segmento usado na análise. A planilha veio com quase tudo "Multicategoria",
# MXRF11 como "Logística" e tipo_fundo "Tijolo" para todos.
# TODO Frente 1: conferir esta classificação (a original fica em "segmento_planilha").
SEGMENTO_ANALISE = {
    "Logistica": "HGLG11 XPLG11 BTLG11 LVBI11 VILG11 BRCO11 HSLG11 GGRC11 TRBL11",
    "Shoppings": "XPML11 VISC11 HSML11 HGBS11 CPSH11 FIGS11 FVPQ11 PQDP11",
    "Lajes": "BRCR11 PVBI11 HGRE11 JSRE11 RCRB11 BROF11 VINO11 TEPP11",
    "Renda Urbana": "TRXF11 RBVA11 HGRU11",
    "Hibrido": "KNRI11 ALZR11 GARE11 RBRP11",
    "Papel": "KNCR11 KNIP11 HGCR11 RECR11 CPTS11 MXRF11 KNSC11 RBRY11 PORD11 "
             "HABT11 MCCI11 VRTA11 VGIR11 KCRE11 SNCI11 RBRR11 VSLH11",
    "FoF": "HFOF11 KFOF11 BCIA11",
    "Fiagro": "VGIA11 XPCA11",
    "Desenvolvimento": "TGAR11",
}
SEGMENTO_DE = {t: s for s, lista in SEGMENTO_ANALISE.items() for t in lista.split()}
CORRECOES_INQ = {"petrobas": "petrobras", "carregour": "carrefour"}


# ---------------------------------------------------------------- dados reais

def carregar_precos():
    """Separador ';', decimal ',' e data DD/MM/AAAA (o dicionário está errado)."""
    px = pd.read_csv(ARQ_PRECOS, sep=";", decimal=",", index_col=0)
    px.index = pd.to_datetime(px.index, dayfirst=True)
    px.columns = [c.replace(".SA", "") for c in px.columns]
    return px.sort_index()


def limpar_precos(px):
    """
    A coleta fez ffill().bfill(): fundos sem histórico no início ganharam
    meses de preço repetido (retorno zero), o que inventa correlação.
    1) apaga esse trecho parado inicial;
    2) remove fundos com cotação real em menos de 90% do período;
    3) remove fundos com mais de 30% de dias com retorno zero.
    """
    px = px.copy()
    for c in px.columns:
        s = px[c]
        mudou = (s != s.iloc[0]).values
        inicio = mudou.argmax() if mudou.any() else len(s)
        # o dia anterior à 1ª mudança é a 1ª cotação real; antes dele é cópia
        if inicio > 1:
            px.iloc[:inicio - 1, px.columns.get_loc(c)] = np.nan

    cobertura = px.notna().mean()
    ret = np.log(px).diff()
    zeros = (ret == 0).sum() / ret.notna().sum()

    saidas = []
    for t in px.columns:
        motivos = []
        if cobertura[t] < COBERTURA_MIN:
            motivos.append(f"cotação real em só {cobertura[t]:.0%} do período")
        if zeros[t] > ZEROS_MAX:
            motivos.append(f"{zeros[t]:.0%} dos dias com retorno zero")
        if motivos:
            saidas.append({"ticker": t, "cobertura": round(cobertura[t], 3),
                           "frac_retorno_zero": round(zeros[t], 3),
                           "motivo": "; ".join(motivos)})
    removidos = pd.DataFrame(saidas, columns=["ticker", "cobertura",
                                              "frac_retorno_zero", "motivo"])
    return px.drop(columns=removidos["ticker"]), removidos


def retornos_log(px):
    """Retorno log diário, só nas datas em que todos os fundos têm cotação."""
    return np.log(px).diff().dropna(how="any")


def separa_inquilinos(texto):
    """'A, B e C.' -> ['a', 'b', 'c']"""
    texto = texto.strip().rstrip(".").lower().replace(" e ", ",")
    nomes = [n.strip().rstrip(".") for n in texto.split(",")]
    return [CORRECOES_INQ.get(n, n) for n in nomes if n]


def carregar_atributos(tickers):
    """Planilhas A e C no formato que o grafos.py espera.
    Devolve também a liquidez em R$/dia (usada no --top)."""
    A = pd.read_excel(ARQ_ATRIB, sheet_name="Planilha A").set_index("ticker").loc[tickers]
    C = pd.read_excel(ARQ_ATRIB, sheet_name="Planilha C").set_index("ticker").loc[tickers]

    atrib = pd.DataFrame(index=A.index)
    atrib["segmento_planilha"] = A["segmento"]
    atrib["segmento"] = [SEGMENTO_DE.get(t, "Outros") for t in A.index]
    tipo = {"Papel": "Papel", "Fiagro": "Papel", "FoF": "FoF", "Hibrido": "Hibrido"}
    atrib["tipo_fundo"] = atrib["segmento"].map(lambda s: tipo.get(s, "Tijolo"))
    atrib["gestora"] = A["gestora"].str.strip()
    atrib["indexador"] = "n/a"      # não coletado
    atrib["tipo_imovel"] = "n/a"    # não coletado

    # A mesma lista de inquilinos aparece em muitos fundos (ex.: ~20 de papel):
    # é preenchimento padrão, então é ignorada.
    texto = A["inquilinos"].fillna("").str.strip().str.lower()
    repeticoes = texto.map(texto.value_counts())
    atrib["inquilinos"] = [
        [] if txt == "" or repeticoes[t] > REPETICAO_MAX else separa_inquilinos(txt)
        for t, txt in texto.items()]

    cont = pd.DataFrame(index=C.index)
    cont["dividend_yield"] = C["dy_12m"].replace(0, np.nan)    # DY 0 = faltando
    cont["pvp"] = C["p_vp"]
    cont["vacancia"] = np.nan                                  # não coletada
    # PL e liquidez vão de milhões a bilhões: log10 antes do z-score
    cont["patrimonio_liquido"] = np.log10(C["patrimonio_liquido"])
    cont["liquidez"] = np.log10(C["liquidez_diaria"])
    # num_ativos = 0 em todo fundo de papel/FoF: é "não se aplica", não zero
    cont["num_ativos"] = C["num_ativos"].replace(0, np.nan)
    return atrib, cont.astype(float), C["liquidez_diaria"]


def carregar_reais():
    px, removidos = limpar_precos(carregar_precos())
    print(f"[dados] {px.shape[1] + len(removidos)} FIIs no CSV, "
          f"{len(removidos)} removidos na limpeza:")
    for _, r in removidos.iterrows():
        print(f"   - {r['ticker']}: {r['motivo']}")
    ret = retornos_log(px)
    atrib, cont, liq = carregar_atributos(list(ret.columns))
    return atrib, cont, ret, liq, removidos


def gerar_universo_sintetico(n, dias=500, seed=SEMENTE):
    """N fundos falsos (fator de mercado + fator de segmento), só para testar escala."""
    rng = np.random.default_rng(seed)
    segs = list(data.SEG_LIST)
    gestoras = [f"Gestora{i:02d}" for i in range(max(5, n // 8))]
    empresas = [f"empresa{i:02d}" for i in range(max(10, n // 4))]
    f_mkt = rng.normal(0, 0.010, dias)
    f_seg = {s: rng.normal(0, 0.012, dias) for s in segs}

    linhas, cont, ret = [], {}, {}
    for i in range(n):
        t, s = f"SIM{i:04d}", segs[i % len(segs)]
        tijolo = s not in ("Papel", "FoF")
        linhas.append({"ticker": t, "segmento": s, "indexador": "n/a",
                       "gestora": rng.choice(gestoras),
                       "tipo_fundo": data.TIPO_FUNDO[s], "tipo_imovel": "n/a",
                       "inquilinos": list(rng.choice(empresas, 2, replace=False))
                       if tijolo else []})
        cont[t] = dict(dividend_yield=rng.uniform(7, 15), pvp=rng.uniform(0.5, 1.1),
                       vacancia=np.nan, patrimonio_liquido=rng.uniform(8, 10),
                       liquidez=rng.uniform(5, 7.5),
                       num_ativos=float(rng.integers(1, 40)) if tijolo else np.nan)
        ret[t] = (rng.uniform(0.6, 1.0) * f_mkt + rng.uniform(0.7, 1.1) * f_seg[s]
                  + rng.normal(0, 0.008, dias))
    atrib = pd.DataFrame(linhas).set_index("ticker")
    return atrib, pd.DataFrame(cont).T.astype(float), pd.DataFrame(ret)


# ---------------------------------------------------------------- utilidades

def salva_tabela(df, pasta, nome, index=True):
    """.csv para o grupo e .tex para o relatório."""
    df.to_csv(os.path.join(pasta, nome + ".csv"), index=index)
    try:
        # escape=True protege _ & % do LaTeX; ρ e ≥ viram comandos de matemática
        tex = df.to_latex(index=index, float_format="%.3f", na_rep="--", escape=True)
        tex = tex.replace("ρ", r"$\rho$").replace("≥", r"$\geq$")
        with open(os.path.join(pasta, nome + ".tex"), "w", encoding="utf-8") as f:
            f.write(tex)
    except ImportError:
        print(f"   [aviso] jinja2 não instalado: {nome}.tex não gerado")


def salva_figura(pasta, nome):
    plt.tight_layout()
    plt.savefig(os.path.join(pasta, nome), dpi=140, bbox_inches="tight")
    plt.close()


def rotulo(t, atrib):
    """Nome do fundo; em universos grandes, o segmento."""
    return atrib.loc[t, "segmento"] if len(atrib) > N_ROTULOS else t


def cor(t, atrib):
    return PALETA.get(atrib.loc[t, "segmento"], "#999999")


# ---------------------------------------------------------------- 01/02 descritiva

def caminho_e_diametro(G):
    """Em saltos, no maior componente. Acima de N_AMOSTRA nós, calcula a partir
    de K_AMOSTRA origens sorteadas (o diâmetro vira estimativa por baixo)."""
    H = G.subgraph(max(nx.connected_components(G), key=len))
    if H.number_of_nodes() < 2:
        return 0.0, 0
    if H.number_of_nodes() <= N_AMOSTRA:
        return nx.average_shortest_path_length(H), nx.diameter(H)
    origens = np.random.default_rng(SEMENTE).choice(list(H), K_AMOSTRA, replace=False)
    soma, pares, diam = 0, 0, 0
    for o in origens:
        dist = nx.single_source_shortest_path_length(H, o)
        soma += sum(dist.values())
        pares += len(dist) - 1
        diam = max(diam, max(dist.values()))
    return soma / pares, diam


def descreve_camada(G):
    n = G.number_of_nodes()
    graus = [d for _, d in G.degree()]
    caminho, diam = caminho_e_diametro(G)
    return {"nos": n, "arestas": G.number_of_edges(), "densidade": nx.density(G),
            "grau_medio": np.mean(graus), "grau_max": max(graus),
            "clustering_medio": nx.average_clustering(G),
            "componentes": nx.number_connected_components(G),
            "isolados": nx.number_of_isolates(G),
            "pct_maior_comp": 100 * len(max(nx.connected_components(G), key=len)) / n,
            "caminho_medio": caminho, "diametro": diam}


def tabela_descritiva(camadas, pasta):
    tab = pd.DataFrame({nome: descreve_camada(G) for nome, G in camadas.items()}).T
    tab = tab.astype(float).round(3)
    for c in ["nos", "arestas", "grau_max", "componentes", "isolados", "diametro"]:
        tab[c] = tab[c].astype(int)
    salva_tabela(tab, pasta, "01_descritiva")
    return tab


def figura_graus(camadas, pasta):
    fig, axs = plt.subplots(1, len(camadas), figsize=(4 * len(camadas), 3.6))
    for ax, (nome, G) in zip(axs, camadas.items()):
        graus = [d for _, d in G.degree()]
        ax.hist(graus, bins=range(0, max(graus) + 2), align="left",
                color="#2563eb", edgecolor="white")
        ax.xaxis.set_major_locator(plt.MaxNLocator(integer=True))
        ax.yaxis.set_major_locator(plt.MaxNLocator(integer=True))
        ax.set_title(nome, fontsize=11)
        ax.set_xlabel("grau")
        ax.set_ylabel("nº de fundos")
    fig.suptitle("Distribuição de grau por camada", weight="bold")
    salva_figura(pasta, "02_grau_distribuicao.png")


# ---------------------------------------------------------------- 03 pontes

def centralidades_f4(G):
    """gr.centralidades; acima de N_AMOSTRA nós a intermediação é amostrada."""
    if G.number_of_nodes() <= N_AMOSTRA:
        return gr.centralidades(G)
    btw = nx.betweenness_centrality(G, k=K_AMOSTRA, weight=None, seed=SEMENTE)
    try:
        eig = nx.eigenvector_centrality_numpy(G, weight="weight")
    except Exception:
        eig = {v: np.nan for v in G}
    cent = pd.DataFrame({"grau_pond": dict(G.degree(weight="weight")),
                         "intermediacao": btw, "autovetor": eig})
    return cent.sort_values("intermediacao", ascending=False)


def tabela_pontes(MST, cent, atrib, pasta, top=10):
    """Maior intermediação = fundo que está no meio dos caminhos entre grupos."""
    t = cent.head(top).copy()
    t["segmento"] = atrib.loc[t.index, "segmento"]
    t["grau"] = [MST.degree(v) for v in t.index]
    t = t[["segmento", "grau", "grau_pond", "intermediacao", "autovetor"]].round(3)
    t.index.name = "ticker"
    salva_tabela(t, pasta, "03_pontes")

    fig, ax = plt.subplots(figsize=(7, 4.5))
    ax.barh([rotulo(v, atrib) for v in t.index][::-1], t["intermediacao"][::-1],
            color=[cor(v, atrib) for v in t.index][::-1])
    segs = list(dict.fromkeys(t["segmento"]))
    ax.legend(handles=[Patch(color=PALETA.get(s, "#999"), label=s) for s in segs],
              fontsize=8, loc="lower right")
    ax.set_xlabel("intermediação na MST")
    ax.set_title(f"Top-{top} pontes da rede de co-movimento", weight="bold")
    salva_figura(pasta, "03_pontes.png")
    return t


# ---------------------------------------------------------------- 04 matriz

def figura_matriz_correlacao(corr, atrib, pasta):
    ordem = list(atrib.loc[corr.index].sort_values("segmento").index)
    segs = atrib.loc[ordem, "segmento"].values
    n = len(ordem)

    fig, ax = plt.subplots(figsize=(10, 9))
    im = ax.imshow(corr.loc[ordem, ordem].values, cmap="RdBu_r", vmin=-1, vmax=1)
    cortes = [i for i in range(1, n) if segs[i] != segs[i - 1]]
    for c in cortes:
        ax.axhline(c - 0.5, color="black", lw=0.8)
        ax.axvline(c - 0.5, color="black", lw=0.8)
    if n <= N_ROTULOS:
        ticks, nomes, tam = range(n), ordem, 6.5
    else:  # um rótulo no meio de cada bloco de segmento
        limites = [0] + cortes + [n]
        ticks = [(a + b - 1) / 2 for a, b in zip(limites[:-1], limites[1:])]
        nomes, tam = [segs[a] for a in limites[:-1]], 8
    ax.set_xticks(ticks); ax.set_xticklabels(nomes, rotation=90, fontsize=tam)
    ax.set_yticks(ticks); ax.set_yticklabels(nomes, fontsize=tam)
    plt.colorbar(im, ax=ax, fraction=0.046, pad=0.04, label="correlação ρ")
    ax.set_title("Correlação dos retornos diários, ordenada por segmento", weight="bold")
    salva_figura(pasta, "04_matriz_correlacao.png")


# ---------------------------------------------------------------- 05 segmentos

def correlacao_segmentos(corr, atrib, pasta):
    """ρ médio entre fundos do segmento S1 e do S2.
    Na diagonal, o par de um fundo com ele mesmo (ρ = 1) não entra."""
    seg = atrib.loc[corr.index, "segmento"].values
    nomes = sorted(set(seg))
    C = corr.values.copy()
    np.fill_diagonal(C, np.nan)
    tab = pd.DataFrame(index=nomes, columns=nomes, dtype=float)
    for a in nomes:
        for b in nomes:
            bloco = C[np.ix_(seg == a, seg == b)]
            if np.isfinite(bloco).any():   # segmento com 1 fundo não tem diagonal
                tab.loc[a, b] = np.nanmean(bloco)
    tab = tab.round(3)
    salva_tabela(tab, pasta, "05_segmentos_corr")

    n = len(nomes)
    lim = max(0.1, np.nanmax(np.abs(tab.values)))
    fig, ax = plt.subplots(figsize=(n + 2, 0.85 * n + 1.5))
    im = ax.imshow(tab.values, cmap="RdBu_r", vmin=-lim, vmax=lim)
    for i in range(n):
        for j in range(n):
            v = tab.values[i, j]
            ax.text(j, i, "--" if np.isnan(v) else f"{v:.2f}", ha="center",
                    va="center", fontsize=9,
                    color="white" if abs(v) > 0.8 * lim else "black")
    ax.set_xticks(range(n)); ax.set_xticklabels(nomes, rotation=45, ha="right")
    ax.set_yticks(range(n)); ax.set_yticklabels(nomes)
    plt.colorbar(im, ax=ax, fraction=0.046, pad=0.04, label="ρ médio")
    ax.set_title("Correlação média segmento × segmento", weight="bold")
    salva_figura(pasta, "05_segmentos_corr.png")
    return tab


def pares_cruzados(corr, atrib, GA, pasta, top=15):
    """Pares de segmentos diferentes com maior ρ. peso_A = 0 quer dizer que os
    fundos não têm nada em comum na Camada A, mas andam juntos no preço:
    é a diversificação aparente."""
    seg = atrib["segmento"]
    nomes = list(corr.index)
    linhas = []
    for i, a in enumerate(nomes):
        for b in nomes[i + 1:]:
            if seg[a] == seg[b]:
                continue
            aresta = GA.get_edge_data(a, b, default={})
            linhas.append({"fundo_1": a, "segmento_1": seg[a],
                           "fundo_2": b, "segmento_2": seg[b],
                           "rho": corr.loc[a, b],
                           "peso_A": aresta.get("weight", 0.0),
                           "em_comum_A": ", ".join(aresta.get("compartilham", []))})
    t = (pd.DataFrame(linhas).sort_values("rho", ascending=False)
         .head(top).reset_index(drop=True).round(3))
    t.index += 1
    salva_tabela(t, pasta, "05_pares_cruzados")
    return t


# ---------------------------------------------------------------- 06 carteiras

def avalia_carteiras(corr, atrib, cont, MST, part, pasta):
    resultado = {}
    for nome, fundos in [("Carteira ideal", data.CARTEIRA_IDEAL),
                         ("Falsa diversificada", data.CARTEIRA_FALSA)]:
        presentes = [f for f in fundos if f in corr.index]
        faltam = [f for f in fundos if f not in corr.index]
        if faltam:
            print(f"   [aviso] {nome}: fora do universo, seguindo sem {', '.join(faltam)}")
        if len(presentes) < 2:
            print(f"   [aviso] {nome}: menos de 2 fundos no universo, pulada")
            continue
        m = gr.avalia_carteira(presentes, corr, atrib, cont, MST, part)
        m["fundos"] = " ".join(presentes)
        resultado[nome] = m
    if not resultado:
        return None
    tab = pd.DataFrame(resultado)
    salva_tabela(tab, pasta, "06_carteiras")
    return tab


# ---------------------------------------------------------------- 07 robustez

def frac_maior_componente(G, n0):
    if G.number_of_nodes() == 0:
        return 0.0
    return len(max(nx.connected_components(G), key=len)) / n0


def trajetoria(G, ordem):
    """Fração no maior componente a cada remoção (gr.robustez_remocao).
    Acima de N_AMOSTRA nós, mede em passos de 1% para não ficar lento."""
    n0 = G.number_of_nodes()
    if n0 <= N_AMOSTRA:
        traj = gr.robustez_remocao(G, ordem)
        return np.linspace(0, 1, len(traj)), np.array(traj)
    passo = max(1, n0 // 100)
    H = G.copy()
    xs, ys = [0.0], [frac_maior_componente(H, n0)]
    for i in range(0, n0, passo):
        H.remove_nodes_from(ordem[i:i + passo])
        xs.append(min(i + passo, n0) / n0)
        ys.append(frac_maior_componente(H, n0))
    return np.array(xs), np.array(ys)


def figura_robustez(grafos_b, pasta):
    """Remoção dirigida (maior intermediação primeiro) x aleatória.
    Se a dirigida derruba a rede bem mais rápido, ela depende de poucas pontes."""
    rng = np.random.default_rng(SEMENTE)
    fig, axs = plt.subplots(1, len(grafos_b), figsize=(6 * len(grafos_b), 4.2))
    for ax, (nome, G) in zip(axs, grafos_b.items()):
        ordem = list(centralidades_f4(G).index)
        x, y_dir = trajetoria(G, ordem)
        y_ale = np.mean([trajetoria(G, list(rng.permutation(list(G))))[1]
                         for _ in range(N_SORTEIOS)], axis=0)
        ax.plot(x, y_dir, color="#be123c", lw=2, label="dirigida (maior intermediação)")
        ax.plot(x, y_ale, color="#2563eb", lw=2, ls="--",
                label=f"aleatória (média de {N_SORTEIOS})")
        ax.set_xlabel("fração de fundos removidos")
        ax.set_ylabel("fração no maior componente")
        ax.set_title(nome, fontsize=11)
        ax.set_ylim(0, 1.02)
        ax.grid(alpha=0.3)
        ax.legend(fontsize=8)
    fig.suptitle("Robustez da rede de co-movimento (Camada B)", weight="bold")
    salva_figura(pasta, "07_robustez.png")


def choque_segmento(grafos_b, atrib, pasta):
    """Remove todos os fundos de um segmento e mede o estrago.
    pct_maior_comp_depois é sobre os fundos que sobraram."""
    linhas = []
    for nome, G in grafos_b.items():
        m0 = G.number_of_edges()
        for s in sorted(atrib["segmento"].unique()):
            H = G.copy()
            H.remove_nodes_from([v for v in G if atrib.loc[v, "segmento"] == s])
            n = H.number_of_nodes()
            linhas.append({
                "grafo": nome, "segmento": s,
                "fundos_removidos": G.number_of_nodes() - n,
                "arestas_perdidas": m0 - H.number_of_edges(),
                "pct_arestas_perdidas": 100 * (m0 - H.number_of_edges()) / max(1, m0),
                "componentes_antes": nx.number_connected_components(G),
                "componentes_depois": nx.number_connected_components(H) if n else 0,
                "pct_maior_comp_depois": 100 * frac_maior_componente(H, n) if n else 0.0})
    t = pd.DataFrame(linhas).round(1)
    salva_tabela(t, pasta, "07_choque_segmento", index=False)
    return t


# ---------------------------------------------------------------- 08 figuras dos grafos

def desenha_grafo(G, atrib, titulo, pasta, nome, pos, destaque=()):
    """Cor = segmento, espessura = peso da aresta, contorno preto = destaque."""
    fig, ax = plt.subplots(figsize=(10, 8))
    pesos = np.array([d.get("weight", 1.0) for *_, d in G.edges(data=True)])
    if len(pesos):
        larg = 0.4 + 2.5 * (pesos - pesos.min()) / (np.ptp(pesos) + 1e-9)
        nx.draw_networkx_edges(G, pos, ax=ax, alpha=0.35, width=larg)
    nx.draw_networkx_nodes(G, pos, ax=ax, node_size=260 if len(G) <= N_ROTULOS else 30,
                           node_color=[cor(v, atrib) for v in G],
                           edgecolors=["black" if v in destaque else "white" for v in G],
                           linewidths=[2.8 if v in destaque else 0.8 for v in G])
    if len(G) <= N_ROTULOS:
        nx.draw_networkx_labels(G, pos, ax=ax, font_size=6.5)
    segs = sorted(atrib.loc[list(G), "segmento"].unique())
    ax.legend(handles=[Patch(color=PALETA.get(s, "#999"), label=s) for s in segs],
              fontsize=8, loc="best")
    ax.set_title(titulo, weight="bold")
    ax.axis("off")
    salva_figura(pasta, nome)


def figuras_grafos(GA, MST, GC, atrib, pasta):
    """As 3 camadas e as carteiras destacadas na MST."""
    posB = nx.kamada_kawai_layout(MST, weight=None)   # árvore fica bem espalhada
    desenha_grafo(GA, atrib, "Camada A — características em comum (peso por raridade)",
                  pasta, "08_grafo_A.png", nx.spring_layout(GA, seed=3, k=0.6))
    desenha_grafo(MST, atrib, "Camada B — MST de co-movimento dos preços",
                  pasta, "08_grafo_B_mst.png", posB)
    desenha_grafo(GC, atrib, f"Camada C — perfil fundamentalista (kNN, k={K_KNN})",
                  pasta, "08_grafo_C.png", nx.spring_layout(GC, seed=3, k=0.6))
    for nome, fundos in [("ideal", data.CARTEIRA_IDEAL), ("falsa", data.CARTEIRA_FALSA)]:
        presentes = set(fundos) & set(MST)
        if len(presentes) >= 2:
            desenha_grafo(MST, atrib, f"Carteira {nome} destacada na MST", pasta,
                          f"09_carteira_{nome}.png", posB, destaque=presentes)


# ---------------------------------------------------------------- execução

def argumentos():
    p = argparse.ArgumentParser(description="Frente 4: centralidades e carteiras")
    g = p.add_mutually_exclusive_group()
    g.add_argument("--top", type=int, metavar="N", help="só os N FIIs mais líquidos")
    g.add_argument("--dados-simulados", action="store_true",
                   help="os 40 FIIs simulados de data.py")
    g.add_argument("--simular", type=int, metavar="N",
                   help="universo sintético de N fundos (teste de escala)")
    return p.parse_args()


def carregar(args):
    """Devolve (atrib, cont, ret, pasta de saída) conforme a opção escolhida."""
    removidos = None
    if args.simular:
        atrib, cont, ret = gerar_universo_sintetico(args.simular)
        modo = f"simulado{args.simular}"
    elif args.dados_simulados:
        atrib, cont, ret = data.carregar_tudo_simulado()
        modo = "simulado_dados"
    else:
        atrib, cont, ret, liq, removidos = carregar_reais()
        modo = "todos"
        if args.top:
            top = liq.sort_values(ascending=False).head(args.top).index
            atrib, cont, ret = atrib.loc[top], cont.loc[top], ret[top]
            modo = f"top{args.top}"

    pasta = os.path.join("out", "frente4", modo)
    os.makedirs(pasta, exist_ok=True)
    if removidos is not None:
        salva_tabela(removidos.set_index("ticker"), pasta, "00_fundos_removidos")
        salva_tabela(atrib.assign(inquilinos=atrib["inquilinos"].map(", ".join)),
                     pasta, "00_atributos_limpos")
    return atrib, cont, ret, pasta


def main():
    args = argumentos()
    atrib, cont, ret, pasta = carregar(args)
    print(f"[frente4] {len(atrib)} fundos | {len(ret)} dias | saída em {pasta}/")

    GA = gr.grafo_estrutural(atrib, limiar=LIMIAR_A)
    corr = gr.matriz_correlacao(ret)
    MST = gr.grafo_mst(corr)
    GL = gr.grafo_limiar(corr, rho_min=RHO_MIN)
    GC = gr.grafo_fundamentalista(cont, k=K_KNN)
    if GL.number_of_edges() == 0:
        maior = corr.values[np.triu_indices(len(corr), k=1)].max()
        sys.exit(f"ERRO: com RHO_MIN={RHO_MIN} o grafo por limiar ficou sem arestas "
                 f"(maior ρ = {maior:.2f}). Diminua RHO_MIN em src/frente4.py.")

    camadas = {"A (estrutural)": GA, "B (MST)": MST,
               f"B (limiar ρ≥{RHO_MIN})": GL, f"C (kNN k={K_KNN})": GC}
    grafos_b = {"MST": MST, f"Limiar ρ≥{RHO_MIN}": GL}

    print("\n[01] descritiva por camada")
    print(tabela_descritiva(camadas, pasta).to_string())
    figura_graus(camadas, pasta)

    print("\n[03] pontes (intermediação na MST)")
    print(tabela_pontes(MST, centralidades_f4(MST), atrib, pasta).to_string())

    figura_matriz_correlacao(corr, atrib, pasta)

    print("\n[05] correlação média segmento × segmento")
    print(correlacao_segmentos(corr, atrib, pasta).to_string())
    print("\n[05] pares de segmentos diferentes com maior ρ")
    print(pares_cruzados(corr, atrib, GA, pasta).drop(columns="em_comum_A").to_string())

    print("\n[06] carteiras")
    part, mod = gr.comunidades(GL)
    print(f"   Louvain no grafo por limiar: {len(set(part.values()))} comunidades, "
          f"modularidade {mod:.3f}")
    tab = avalia_carteiras(corr, atrib, cont, MST, part, pasta)
    if tab is not None:
        print(tab.to_string())

    print("\n[07] robustez e choque de segmento")
    figura_robustez(grafos_b, pasta)
    print(choque_segmento(grafos_b, atrib, pasta).to_string(index=False))

    print("\n[08] figuras dos grafos")
    figuras_grafos(GA, MST, GC, atrib, pasta)

    print(f"\n[ok] tudo salvo em {pasta}/")


if __name__ == "__main__":
    main()
