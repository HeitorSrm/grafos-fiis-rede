"""
Núcleo algorítmico. TODOS os grafos são valorados (ponderados).

Camada A (estrutural)  — projeção bipartida FII×característica, peso = soma
    das características compartilhadas PONDERADA POR RARIDADE (estilo TF-IDF):
    dividir um inquilino raro vale mais que dividir "segmento Papel", comum.
Camada B (comportamental) — correlação de retornos → distância de Mantegna
    → MST + grafo por limiar (peso = correlação).
Camada C (fundamentalista) — vetor contínuo normalizado → similaridade
    (grafo kNN valorado, peso = similaridade).
"""
import numpy as np
import pandas as pd
import networkx as nx
import community as community_louvain
from sklearn.metrics import adjusted_rand_score


# ===========================================================================
# CAMADA A — projeção bipartida valorada por raridade (TF-IDF)
# ===========================================================================
def _itens_por_fii(atrib: pd.DataFrame):
    """Transforma cada FII num conjunto de 'itens' característica=valor.
    Atributos 'n/a' são ignorados; inquilinos viram vários itens."""
    itens = {}
    for t, row in atrib.iterrows():
        s = set()
        for col in ["segmento", "indexador", "gestora", "tipo_fundo", "tipo_imovel"]:
            v = row[col]
            if v and v != "n/a":
                s.add(f"{col}={v}")
        for inq in row.get("inquilinos", []) or []:
            s.add(f"inquilino={inq}")
        itens[t] = s
    return itens


def grafo_estrutural(atrib: pd.DataFrame, limiar: float = 0.0) -> nx.Graph:
    itens = _itens_por_fii(atrib)
    n = len(itens)
    # idf de cada item: itens raros pesam mais
    from collections import Counter
    df = Counter()
    for s in itens.values():
        for it in s:
            df[it] += 1
    idf = {it: np.log(n / c) for it, c in df.items()}   # c=n -> idf=0 (comum)

    G = nx.Graph(); G.add_nodes_from(itens)
    tickers = list(itens)
    for i, a in enumerate(tickers):
        for b in tickers[i + 1:]:
            comuns = itens[a] & itens[b]
            w = sum(idf[it] for it in comuns)
            if w > limiar:
                G.add_edge(a, b, weight=round(float(w), 3),
                           compartilham=sorted(comuns))
    return G


# ===========================================================================
# CAMADA B — correlação → distância de Mantegna → MST + limiar
# ===========================================================================
def matriz_correlacao(ret: pd.DataFrame) -> pd.DataFrame:
    return ret.corr()


def grafo_mst(corr: pd.DataFrame) -> nx.Graph:
    d = np.sqrt(2 * (1 - corr))
    G = nx.Graph()
    for i, a in enumerate(corr.index):
        for b in corr.index[i + 1:]:
            G.add_edge(a, b, distance=float(d.loc[a, b]),
                       weight=float(corr.loc[a, b]))
    return nx.minimum_spanning_tree(G, weight="distance")


def grafo_limiar(corr: pd.DataFrame, rho_min: float = 0.5) -> nx.Graph:
    G = nx.Graph(); G.add_nodes_from(corr.index)
    for i, a in enumerate(corr.index):
        for b in corr.index[i + 1:]:
            r = float(corr.loc[a, b])
            if r >= rho_min:
                G.add_edge(a, b, weight=round(r, 3))
    return G


# ===========================================================================
# CAMADA C — similaridade de perfil fundamentalista (kNN valorado)
# ===========================================================================
def grafo_fundamentalista(cont: pd.DataFrame, k: int = 4) -> nx.Graph:
    """
    z-score por coluna (com imputação da mediana para NaN, ex. vacância de
    fundos de papel) -> distância euclidiana -> similaridade 1/(1+d).
    Mantém as k arestas mais fortes por nó (kNN) para não virar grafo completo.
    """
    X = cont.copy()
    X = (X - X.mean()) / X.std(ddof=0)      # z-score
    X = X.fillna(0.0)                        # NaN -> média da coluna (0 após z)
    nodes = list(X.index); V = X.values
    # distância euclidiana par a par
    D = np.sqrt(((V[:, None, :] - V[None, :, :]) ** 2).sum(-1))
    S = 1.0 / (1.0 + D)                      # similaridade em (0,1]
    np.fill_diagonal(S, 0.0)

    G = nx.Graph(); G.add_nodes_from(nodes)
    for i, a in enumerate(nodes):
        viz = np.argsort(-S[i])[:k]         # k vizinhos mais similares
        for j in viz:
            b = nodes[j]
            w = round(float(S[i, j]), 3)
            if G.has_edge(a, b):
                continue
            G.add_edge(a, b, weight=w)
    return G


# ===========================================================================
# ALGORITMOS DE GRAFO / MÉTRICAS
# ===========================================================================
def comunidades(G, weight="weight"):
    part = community_louvain.best_partition(G, weight=weight, random_state=1)
    return part, community_louvain.modularity(part, G, weight=weight)


def centralidades(G, weight="weight") -> pd.DataFrame:
    grau = dict(G.degree(weight=weight))
    btw = nx.betweenness_centrality(G, weight=None)
    try:
        eig = nx.eigenvector_centrality_numpy(G, weight=weight)
    except Exception:
        eig = {n: np.nan for n in G}
    return pd.DataFrame({"grau_pond": grau, "intermediacao": btw,
                         "autovetor": eig}).sort_values("intermediacao",
                                                        ascending=False)


def concorda_com_segmento(part, atrib) -> float:
    nodes = list(part)
    seg = atrib.loc[nodes, "segmento"].astype("category").cat.codes
    return adjusted_rand_score(seg, [part[n] for n in nodes])


def robustez_remocao(G, ordem):
    H = G.copy(); n0 = H.number_of_nodes()
    traj = [len(max(nx.connected_components(H), key=len)) / n0]
    for v in ordem:
        if v in H:
            H.remove_node(v)
        if H.number_of_nodes() == 0:
            traj.append(0.0); break
        traj.append(len(max(nx.connected_components(H), key=len)) / n0)
    return traj


# ===========================================================================
# CARTEIRAS — diversificação aparente vs. efetiva
# ===========================================================================
def avalia_carteira(fundos, corr, atrib, cont, mst, part):
    """Métricas que misturam rede + atributos para medir diversificação real."""
    fundos = [f for f in fundos if f in corr.index]
    sub = corr.loc[fundos, fundos].values
    iu = np.triu_indices(len(fundos), k=1)
    corr_media = float(sub[iu].mean())

    # distância média na MST entre os fundos (quanto mais longe, mais diverso)
    dists = []
    for i in range(len(fundos)):
        for j in range(i + 1, len(fundos)):
            try:
                dists.append(nx.shortest_path_length(
                    mst, fundos[i], fundos[j], weight="distance"))
            except nx.NetworkXNoPath:
                pass
    dist_mst = float(np.mean(dists)) if dists else float("nan")

    return {
        "n_fundos": len(fundos),
        "n_segmentos": atrib.loc[fundos, "segmento"].nunique(),
        "n_comunidades": len({part[f] for f in fundos if f in part}),
        "corr_media": round(corr_media, 3),
        "dist_media_mst": round(dist_mst, 3),
        "num_ativos_medio": round(float(cont.loc[fundos, "num_ativos"].mean()), 1),
        "vacancia_media": round(float(cont.loc[fundos, "vacancia"].mean()), 3),
        "indice_diversificacao": round(1 - corr_media, 3),  # 0..1, maior=melhor
    }
