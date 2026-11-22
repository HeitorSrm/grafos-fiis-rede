"""
Frente 4 — características gerais, centralidades e carteiras.

Perguntas:
  (b) quais FIIs são centrais / pontes na rede de co-movimento?
  (c) quais pares de segmentos diferentes se movem juntos?
      (diversificação aparente x efetiva)

Dados e camadas vêm de src/camadas.py (Frente 2): mesma base limpa e mesmos
limiares do resto do projeto. A = Jaccard + backbone kNN, B = MST ∪ limiar,
C = kNN.

Uso (a partir da raiz do repositório):
    python src/frente4.py                    # dados reais   -> out/frente4/todos
    python src/frente4.py --top 30           # 30 mais líquidos -> out/frente4/top30
    python src/frente4.py --dados-simulados  # 40 FIIs de data.py
    python src/frente4.py --simular 300      # universo sintético (teste de escala)
"""
import argparse
import os

import numpy as np
import pandas as pd
import networkx as nx
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.patches import Patch

import camadas as cm
import data
import grafos as gr

N_ROTULOS = 60     # acima disso as figuras mostram o segmento, não o fundo
N_AMOSTRA = 300    # acima disso caminho, diâmetro e intermediação são amostrados
K_AMOSTRA = 100    # nº de vértices de origem na amostragem
N_SORTEIOS = 30    # sorteios da remoção aleatória
SEMENTE = 42

# cores dos segmentos reais (camadas.py) e dos simulados (data.py, sem acento)
PALETA = {**cm.PALETA, "Logistica": "#2563eb", "Hibrido": "#64748b"}

NOME_A = f"A (Jaccard, backbone k={cm.K_BACKBONE_A})"
NOME_B = f"B (MST ∪ ρ≥{cm.RHO_MIN_B})"
NOME_MST = "B: só MST (referência)"
NOME_C = f"C (kNN k={cm.K_KNN_C})"


# ---------------------------------------------------------------- dados

def carregar_reais():
    """Base limpa da Frente 2; imprime quem saiu e por quê."""
    atrib, cont, ret, removidos = cm.carregar_dados(verbose=True)
    for _, r in removidos.iterrows():
        print(f"   - {r['ticker']}: {r['motivo']}")
    return atrib, cont, ret, removidos


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
        linhas.append({"ticker": t, "segmento": s, "gestora": rng.choice(gestoras),
                       "inquilinos": list(rng.choice(empresas, 2, replace=False))
                       if tijolo else []})
        cont[t] = dict(dividend_yield=rng.uniform(7, 15), pvp=rng.uniform(0.5, 1.1),
                       patrimonio_liquido=rng.uniform(8, 10), liquidez=rng.uniform(5, 7.5),
                       num_ativos=float(rng.integers(1, 40)) if tijolo else np.nan)
        ret[t] = (rng.uniform(0.6, 1.0) * f_mkt + rng.uniform(0.7, 1.1) * f_seg[s]
                  + rng.normal(0, 0.008, dias))
    atrib = pd.DataFrame(linhas).set_index("ticker")
    ret = pd.DataFrame(ret, index=pd.bdate_range("2023-01-02", periods=dias))  # dias úteis
    return atrib, pd.DataFrame(cont).T.astype(float), ret


def montar_camadas(atrib, cont, ret):
    """As três camadas calibradas (camadas.py)."""
    GA_completo, GA = cm.camada_a(atrib)
    corr = gr.matriz_correlacao(ret)
    GB, MST, _ = cm.camada_b(corr)
    GC = cm.camada_c(cont)
    return GA_completo, GA, corr, GB, MST, GC


# ---------------------------------------------------------------- utilidades

def salva_tabela(df, pasta, nome, index=True):
    """.csv para o grupo e .tex para o relatório."""
    df.to_csv(os.path.join(pasta, nome + ".csv"), index=index)
    try:
        # escape=True protege _ & % do LaTeX; ρ, ≥ e ∪ viram comandos de matemática
        tex = df.to_latex(index=index, float_format="%.3f", na_rep="--", escape=True)
        tex = tex.replace("ρ", r"$\rho$").replace("≥", r"$\geq$").replace("∪", r"$\cup$")
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


def legenda(ax, segmentos, extra=(), **kw):
    handles = [Patch(color=PALETA.get(s, "#999"), label=s) for s in segmentos]
    ax.legend(handles=handles + list(extra), fontsize=8, **kw)


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


N_BOOT = 100   # reamostragens dos pregões para a estabilidade das pontes


def camada_b_p95(ret):
    """Camada B com o limiar recalculado para a amostra: p95 da correlação
    arredondado a 2 casas, a regra da Frente 2 (na base de 46: 0,32)."""
    corr = ret.corr()
    p95 = round(float(np.quantile(corr.values[np.triu_indices(len(corr), 1)], 0.95)), 2)
    GB, MST, _ = cm.camada_b(corr, rho_min=p95)
    return corr, p95, GB, MST


def estabilidade_pontes(ret):
    """Frequência de cada fundo no top-10 da intermediação em N_BOOT
    reamostragens dos pregões (blocos de 5 dias, para preservar a dependência
    de curto prazo). Mede o quanto o ranking de pontes é estável."""
    rng = np.random.default_rng(SEMENTE)
    blocos = [ret.iloc[i:i + 5] for i in range(0, len(ret), 5)]
    vezes = pd.Series(0, index=ret.columns)
    for _ in range(N_BOOT):
        r = pd.concat([blocos[i] for i in rng.integers(0, len(blocos), len(blocos))])
        _, _, GB, _ = camada_b_p95(r)
        btw = pd.Series(nx.betweenness_centrality(GB)).sort_values(ascending=False)
        vezes[btw.index[:10]] += 1
    return vezes / N_BOOT


def tabela_pontes(GB, MST, atrib, pasta, top=10, freq_top10=None):
    """Maior intermediação na Camada B = fundo que está no meio dos caminhos
    entre grupos. A coluna da MST mostra se o ranking depende da construção;
    freq_top10, se dada, mostra a estabilidade em reamostragens."""
    cent = centralidades_f4(GB)
    t = cent.head(top).copy()
    t["segmento"] = atrib.loc[t.index, "segmento"]
    t["grau"] = [GB.degree(v) for v in t.index]
    t["intermediacao_mst"] = centralidades_f4(MST)["intermediacao"].reindex(t.index)
    colunas = ["segmento", "grau", "grau_pond", "intermediacao", "intermediacao_mst", "autovetor"]
    if freq_top10 is not None:
        t["freq_top10_reamostragem"] = freq_top10.reindex(t.index)
        colunas.append("freq_top10_reamostragem")
    t = t[colunas].round(3)
    t.index.name = "ticker"
    salva_tabela(t, pasta, "03_pontes")

    fig, ax = plt.subplots(figsize=(7, 4.5))
    ax.barh([rotulo(v, atrib) for v in t.index][::-1], t["intermediacao"][::-1],
            color=[cor(v, atrib) for v in t.index][::-1])
    legenda(ax, list(dict.fromkeys(t["segmento"])), loc="lower right")
    ax.set_xlabel(f"intermediação na Camada B (MST ∪ ρ≥{cm.RHO_MIN_B})")
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


def pares_cruzados(corr, atrib, GA_completo, pasta, top=15):
    """Pares de segmentos diferentes com maior ρ. peso_A é o Jaccard da
    Camada A (0 a 1); peso_A = 0 quer dizer que os fundos não têm nada em
    comum, mas andam juntos no preço: é a diversificação aparente."""
    seg = atrib["segmento"]
    itens = cm.itens_de(atrib)
    nomes = list(corr.index)
    linhas = []
    for i, a in enumerate(nomes):
        for b in nomes[i + 1:]:
            if seg[a] == seg[b]:
                continue
            aresta = GA_completo.get_edge_data(a, b, default={})
            linhas.append({"fundo_1": a, "segmento_1": seg[a],
                           "fundo_2": b, "segmento_2": seg[b],
                           "rho": corr.loc[a, b],
                           "peso_A": aresta.get("weight", 0.0),
                           "em_comum_A": ", ".join(sorted(itens[a] & itens[b]))})
    t = (pd.DataFrame(linhas).sort_values("rho", ascending=False)
         .head(top).reset_index(drop=True).round(3))
    t.index += 1
    salva_tabela(t, pasta, "05_pares_cruzados")
    return t


# ---------------------------------------------------------------- 06 carteiras

# carteiras de exemplo do data.py, com nomes que dizem o que elas são: a
# "referência" pega o fundo líder de cada segmento, e isso já é
# diversificação aparente (é mais correlacionada que carteiras sorteadas)
CARTEIRAS_EXEMPLO = [("Referência (líderes por segmento)", data.CARTEIRA_IDEAL),
                     ("Concentrada (só Logística e Shoppings)", data.CARTEIRA_FALSA)]
N_ACASO = 2000                 # carteiras sorteadas para comparação
MIN_FUNDOS_SEGMENTO = 3        # segmentos menores ficam fora das carteiras da rede


def rho_medio_carteira(corr, fundos):
    sub = corr.loc[fundos, fundos].values
    return sub[np.triu_indices(len(fundos), 1)].mean()


def sorteia_mesma_composicao(corr, seg, fundos, n, rng):
    """ρ médio de n carteiras sorteadas com a mesma quantidade de fundos de
    cada segmento que a carteira dada."""
    cota = seg[fundos].value_counts()
    return np.array([rho_medio_carteira(corr, [f for s, k in cota.items()
                                              for f in rng.choice(seg.index[seg == s], k, replace=False)])
                     for _ in range(n)])


def avalia_carteiras(corr, atrib, MST, pasta):
    """Carteiras de exemplo: ρ médio, distância na MST e a posição da carteira
    entre as sorteadas com a mesma composição de segmentos (percentil alto =
    mais correlacionada que o acaso, ou seja, diversificação aparente)."""
    seg = atrib["segmento"]
    rng = np.random.default_rng(SEMENTE)
    resultado = {}
    for nome, fundos in CARTEIRAS_EXEMPLO:
        presentes = [f for f in fundos if f in corr.index]
        faltam = [f for f in fundos if f not in corr.index]
        if faltam:
            print(f"   [aviso] {nome}: fora do universo, seguindo sem {', '.join(faltam)}")
        if len(presentes) < 2:
            print(f"   [aviso] {nome}: menos de 2 fundos no universo, pulada")
            continue
        rho = rho_medio_carteira(corr, presentes)
        acaso = sorteia_mesma_composicao(corr, seg, presentes, N_ACASO, rng)
        dist = [nx.shortest_path_length(MST, a, b, weight="distance")
                for i, a in enumerate(presentes) for b in presentes[i + 1:]]
        resultado[nome] = {"n_fundos": len(presentes), "n_segmentos": seg[presentes].nunique(),
                           "corr_media": round(rho, 3), "dist_media_mst": round(float(np.mean(dist)), 3),
                           "rho_medio_sorteadas": round(float(acaso.mean()), 3),
                           "pct_sorteadas_com_rho_menor": round(100 * float((acaso < rho).mean()), 1),
                           "fundos": " ".join(presentes)}
    if not resultado:
        return None
    tab = pd.DataFrame(resultado)
    salva_tabela(tab, pasta, "06_carteiras")
    return tab


def carteiras_por_rede(corr, seg):
    """Uma carteira por regra, com 1 fundo por segmento, a partir da MST:
    aparente = o mais central (maior intermediação) de cada segmento;
    efetiva = o mais periférico (menor intermediação).
    Desempate pela correlação média com o resto do mercado, para não
    depender da ordem dos fundos."""
    mst = gr.grafo_mst(corr)
    btw = pd.Series(nx.betweenness_centrality(mst))
    rho_medio = (corr.sum() - 1) / (len(corr) - 1)
    aparente, efetiva = [], []
    for s in sorted(seg.unique()):
        f = seg.index[seg == s]
        chave = pd.DataFrame({"btw": btw[f], "rho": rho_medio[f]})
        aparente.append(chave.sort_values(["btw", "rho"], ascending=False).index[0])
        efetiva.append(chave.sort_values(["btw", "rho"]).index[0])
    return aparente, efetiva


def carteiras_so_correlacao(corr, seg):
    """Comparação sem grafo: maior e menor correlação média de cada segmento.
    Mostra o quanto da regra da rede vem só da exposição ao mercado."""
    rho_medio = (corr.sum() - 1) / (len(corr) - 1)
    grupos = [rho_medio[seg.index[seg == s]] for s in sorted(seg.unique())]
    return [g.idxmax() for g in grupos], [g.idxmin() for g in grupos]


def carteiras_fora_da_amostra(ret, seg, nome):
    """Escolhe as carteiras com a 1ª metade dos pregões e mede o ρ médio na
    2ª metade (fora da amostra). Só segmentos com MIN_FUNDOS_SEGMENTO fundos
    ou mais. Devolve a tabela e os ρ das carteiras sorteadas."""
    grandes = seg.value_counts()
    seg = seg[seg.isin(grandes[grandes >= MIN_FUNDOS_SEGMENTO].index)]
    if seg.nunique() < 2:
        print(f"   [aviso] menos de 2 segmentos com {MIN_FUNDOS_SEGMENTO}+ fundos: carteiras pela rede puladas")
        return None, None
    r = ret[seg.index]
    meio = len(r) // 2
    c1, c2 = r.iloc[:meio].corr(), r.iloc[meio:].corr()
    ap, ef = carteiras_por_rede(c1, seg)
    ap_rho, ef_rho = carteiras_so_correlacao(c1, seg)
    rng = np.random.default_rng(SEMENTE)
    grupos = [seg.index[seg == s] for s in sorted(seg.unique())]
    acaso = np.array([rho_medio_carteira(c2, [rng.choice(g) for g in grupos])
                      for _ in range(N_ACASO)])
    rho = lambda f: rho_medio_carteira(c2, f)
    linhas = {
        "rede: aparente (mais central na MST)": ap,
        "só correlação: maior ρ médio": ap_rho,
        "rede: efetiva (mais periférico na MST)": ef,
        "só correlação: menor ρ médio": ef_rho,
    }
    tab = pd.DataFrame([{"regra": k, "rho_2o_periodo": rho(v),
                         "pct_sorteadas_com_rho_menor": 100 * (acaso < rho(v)).mean(),
                         "fundos": " ".join(v)} for k, v in linhas.items()])
    tab.loc[len(tab)] = {"regra": f"ao acaso (média de {N_ACASO})", "rho_2o_periodo": acaso.mean(),
                         "pct_sorteadas_com_rho_menor": 50.0, "fundos": ""}
    tab.insert(0, "base", nome)
    tab["segmentos"] = len(grupos)
    tab["inicio_2o_periodo"] = str(r.index[meio].date())
    return tab, acaso


def figura_carteiras_rede(tab, acaso, pasta):
    """Distribuição das carteiras sorteadas, com as regras marcadas."""
    fig, ax = plt.subplots(figsize=(8, 4.2))
    ax.hist(acaso, bins=40, color="#cbd5e1", edgecolor="white",
            label=f"{N_ACASO} carteiras sorteadas (1 fundo por segmento)")
    estilos = {"rede: aparente (mais central na MST)": ("#be123c", "-"),
               "só correlação: maior ρ médio": ("#be123c", ":"),
               "rede: efetiva (mais periférico na MST)": ("#059669", "-"),
               "só correlação: menor ρ médio": ("#059669", ":")}
    for _, r in tab.iterrows():
        if r["regra"] in estilos:
            c, ls = estilos[r["regra"]]
            ax.axvline(r["rho_2o_periodo"], color=c, ls=ls, lw=2,
                       label=f"{r['regra']} ({r['rho_2o_periodo']:.3f})")
    ax.set_xlabel(f"ρ médio da carteira no 2º período (a partir de {tab['inicio_2o_periodo'].iloc[0]})")
    ax.set_ylabel("nº de carteiras sorteadas")
    ax.set_title("Carteiras escolhidas no 1º período, medidas no 2º", weight="bold")
    ax.legend(fontsize=7.5, loc="upper right")
    salva_figura(pasta, "06_carteiras_rede.png")


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

def desenha_grafo(G, atrib, titulo, pasta, nome, pos, destaque=(), tracejadas=()):
    """Cor = segmento, espessura = peso da aresta, contorno preto = destaque,
    tracejado = aresta só da MST."""
    fig, ax = plt.subplots(figsize=(10, 8))
    cheias = [e for e in G.edges() if frozenset(e) not in tracejadas]
    pesos = np.array([G.edges[e].get("weight", 1.0) for e in cheias])
    if len(pesos):
        larg = 0.4 + 2.5 * (pesos - pesos.min()) / (np.ptp(pesos) + 1e-9)
        nx.draw_networkx_edges(G, pos, edgelist=cheias, ax=ax, alpha=0.35, width=larg)
    if tracejadas:
        # ordenado: a ordem de um set muda a cada execução e mudaria a figura
        nx.draw_networkx_edges(G, pos, edgelist=sorted(tuple(sorted(e)) for e in tracejadas), ax=ax,
                               style="dashed", alpha=0.5, width=0.8, edge_color="#94a3b8")
    nx.draw_networkx_nodes(G, pos, ax=ax, node_size=260 if len(G) <= N_ROTULOS else 30,
                           node_color=[cor(v, atrib) for v in G],
                           edgecolors=["black" if v in destaque else "white" for v in G],
                           linewidths=[2.0 if v in destaque else 0.8 for v in G])
    if len(G) <= N_ROTULOS:
        nx.draw_networkx_labels(G, pos, ax=ax, font_size=6.5)
    extra = [Line2D([0], [0], color="#94a3b8", ls="--", label="aresta só da MST")] \
        if tracejadas else []
    legenda(ax, sorted(atrib.loc[list(G), "segmento"].unique()), extra, loc="best")
    ax.set_title(titulo, weight="bold")
    ax.axis("off")
    salva_figura(pasta, nome)


def figuras_grafos(GA, GB, MST, GC, atrib, pasta):
    """As 3 camadas e as carteiras destacadas na MST. Layout de Kamada-Kawai
    pela distância em saltos (não depende da escala dos pesos)."""
    lay = lambda G: nx.kamada_kawai_layout(G, weight=None)
    so_mst = {frozenset((a, b)) for a, b, d in GB.edges(data=True) if d["origem"] == "mst"}
    desenha_grafo(GA, atrib, f"Camada A — características em comum (Jaccard, k={cm.K_BACKBONE_A})",
                  pasta, "08_grafo_A.png", lay(GA))
    desenha_grafo(GB, atrib, f"Camada B — co-movimento (MST ∪ ρ ≥ {cm.RHO_MIN_B})",
                  pasta, "08_grafo_B.png", lay(GB), tracejadas=so_mst)
    desenha_grafo(GC, atrib, f"Camada C — perfil fundamentalista (kNN, k={cm.K_KNN_C})",
                  pasta, "08_grafo_C.png", lay(GC))
    posM = lay(MST)
    for (titulo, fundos), arq in zip(CARTEIRAS_EXEMPLO, ["referencia", "concentrada"]):
        presentes = set(fundos) & set(MST)
        if len(presentes) >= 2:
            desenha_grafo(MST, atrib, f"Carteira {titulo.lower()} destacada na MST", pasta,
                          f"09_carteira_{arq}.png", posM, destaque=presentes)


# ---------------------------------------------------------------- execução

def inteiro_minimo(valor):
    """N precisa ser >= 3: com menos fundos não há rede para analisar
    (e --top 0 seria lido como "sem --top", sobrescrevendo a pasta todos/)."""
    n = int(valor)
    if n < 3:
        raise argparse.ArgumentTypeError("use um N de pelo menos 3")
    return n


def argumentos():
    p = argparse.ArgumentParser(description="Frente 4: centralidades e carteiras")
    g = p.add_mutually_exclusive_group()
    g.add_argument("--top", type=inteiro_minimo, metavar="N",
                   help="só os N FIIs mais líquidos")
    g.add_argument("--dados-simulados", action="store_true",
                   help="os 40 FIIs simulados de data.py")
    g.add_argument("--simular", type=inteiro_minimo, metavar="N",
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
        atrib, cont, ret, removidos = carregar_reais()
        modo = "todos"
        if args.top is not None:
            if args.top > len(atrib):
                print(f"   [aviso] só há {len(atrib)} fundos; usando --top {len(atrib)}")
                args.top = len(atrib)
            # liquidez está em log10, então a ordem é a mesma da liquidez em R$
            top = cont["liquidez"].sort_values(ascending=False).head(args.top).index
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

    GA_completo, GA, corr, GB, MST, GC = montar_camadas(atrib, cont, ret)
    camadas = {NOME_A: GA, NOME_B: GB, NOME_MST: MST, NOME_C: GC}

    print("\n[01] descritiva por camada")
    print(tabela_descritiva(camadas, pasta).to_string())
    figura_graus(camadas, pasta)

    print("\n[03] pontes (intermediação na Camada B)")
    freq = None
    if len(atrib) <= N_ROTULOS:     # em universos grandes a reamostragem fica lenta
        print(f"   estabilidade: {N_BOOT} reamostragens dos pregões...")
        freq = estabilidade_pontes(ret)
    print(tabela_pontes(GB, MST, atrib, pasta, freq_top10=freq).to_string())

    figura_matriz_correlacao(corr, atrib, pasta)

    print("\n[05] correlação média segmento × segmento")
    print(correlacao_segmentos(corr, atrib, pasta).to_string())
    print("\n[05] pares de segmentos diferentes com maior ρ")
    print(pares_cruzados(corr, atrib, GA_completo, pasta).drop(columns="em_comum_A").to_string())

    print("\n[06] carteiras de exemplo (comparadas com sorteadas de mesma composição)")
    tab = avalia_carteiras(corr, atrib, MST, pasta)
    if tab is not None:
        print(tab.to_string())

    print("\n[06b] carteiras pela rede: escolha no 1º período, medida no 2º")
    tab_rede, acaso = carteiras_fora_da_amostra(ret, atrib["segmento"], "base")
    if tab_rede is not None:
        tab_rede = tab_rede.round(3)
        salva_tabela(tab_rede, pasta, "06_carteiras_rede", index=False)
        figura_carteiras_rede(tab_rede, acaso, pasta)
        print(tab_rede.drop(columns=["fundos", "base"]).to_string(index=False))

    print("\n[07] robustez e choque de segmento")
    grafos_b = {"MST": MST, f"MST ∪ ρ≥{cm.RHO_MIN_B}": GB}
    figura_robustez(grafos_b, pasta)
    print(choque_segmento(grafos_b, atrib, pasta).to_string(index=False))

    print("\n[08] figuras dos grafos")
    figuras_grafos(GA, GB, MST, GC, atrib, pasta)

    print(f"\n[ok] tudo salvo em {pasta}/")


if __name__ == "__main__":
    main()
