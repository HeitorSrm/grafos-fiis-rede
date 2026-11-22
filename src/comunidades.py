"""
Parte 3 — Comunidades (Girvan-Newman, Louvain, Leiden) nas 3 camadas.

Rodar da raiz do repositório:   python src/comunidades.py

Usa os MESMOS dados e camadas calibradas da Frente 2 (src/camadas.py):
A = backbone kNN, B = MST ∪ limiar de correlação, C = kNN fundamentalista,
com a limpeza de preços e o segmento corrigido. São as camadas descritas na
seção de Modelagem. Se a Frente 2 mudar um limiar, mude lá em camadas.py:
este arquivo acompanha.

Contrato (o que a parte 4 consome):
  - cada método recebe um nx.Graph valorado (atributo "weight") e devolve uma
    partição = lista de conjuntos de tickers;
  - para_dict() converte para {ticker: id}, o MESMO formato que
    grafos.comunidades() e grafos.avalia_carteira() usam;
  - saída em disco: out/comunidades/comunidades.csv (ticker, camada, metodo, comunidade).
"""
import math
import random
import sys
import time
from collections import defaultdict
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import networkx as nx
import numpy as np
import pandas as pd
from networkx.algorithms.community import modularity
from sklearn.metrics import adjusted_rand_score, normalized_mutual_info_score

SRC = Path(__file__).resolve().parent
OUT = Path("out") / "comunidades"                    # relativo à raiz, como o frente4.py
sys.path.insert(0, str(SRC))
import grafos as gr    # noqa: E402  (núcleo do grupo)
import camadas as calib  # noqa: E402  (dados limpos + camadas calibradas da Frente 2)


# ===========================================================================
# 1. MÉTODOS — todos devolvem lista de conjuntos (partição)
# ===========================================================================
def _com_peso(G):
    """Cópia do grafo garantindo o atributo weight em todas as arestas."""
    H = nx.Graph()
    H.add_nodes_from(G.nodes)
    for u, v, d in G.edges(data=True):
        H.add_edge(u, v, weight=float(d.get("weight", 1.0)))
    return H


def para_dict(P):
    """[{'A','B'}, {'C'}] -> {'A': 0, 'B': 0, 'C': 1}
    Numeração canônica (maior comunidade = 0, empate pelo 1º ticker em ordem
    alfabética), para o resultado ser idêntico a cada execução."""
    ordem = sorted(P, key=lambda c: (-len(c), min(c)))
    return {n: i for i, c in enumerate(ordem) for n in sorted(c)}


# ---- Girvan-Newman: remove a aresta de maior intermediação e guarda a ------
# ---- partição de maior modularidade encontrada durante a divisão. ----------
def girvan_newman(G, usar_pesos=False):
    """usar_pesos=True usa distância = 1/peso no betweenness (aresta forte =
    aresta curta). Por padrão ignora pesos, como no GN original."""
    H = _com_peso(G)
    if usar_pesos:
        for u, v, d in H.edges(data=True):
            d["dist"] = 1.0 / d["weight"]
    wkey = "dist" if usar_pesos else None

    melhor = list(nx.connected_components(H))
    q_melhor = modularity(G, melhor, weight="weight")
    n_comp = len(melhor)
    while H.number_of_edges() > 0:
        betw = nx.edge_betweenness_centrality(H, weight=wkey)
        H.remove_edge(*max(betw, key=betw.get))
        comp = list(nx.connected_components(H))
        if len(comp) > n_comp:                       # houve uma divisão
            n_comp = len(comp)
            q = modularity(G, comp, weight="weight")
            if q > q_melhor:
                melhor, q_melhor = comp, q
    return melhor


# ---- Fase 1 (compartilhada por Louvain e Leiden): movimentação local -------
def _mover_nos(H, comm, m, rng):
    grau = dict(H.degree(weight="weight"))
    tot = defaultdict(float)                         # soma dos graus por comunidade
    for v, c in comm.items():
        tot[c] += grau[v]

    mudou = True
    while mudou:
        mudou = False
        ordem = list(H.nodes)
        rng.shuffle(ordem)
        for v in ordem:
            c0 = comm[v]
            kin = defaultdict(float)                 # peso de v para cada comunidade vizinha
            for u, d in H[v].items():
                if u != v:
                    kin[comm[u]] += d["weight"]
            tot[c0] -= grau[v]                       # tira v da comunidade atual
            melhor_c = c0
            melhor_g = kin.get(c0, 0.0) - tot[c0] * grau[v] / (2 * m)
            for c, k in kin.items():
                g = k - tot[c] * grau[v] / (2 * m)   # ganho de modularidade (∝ ΔQ)
                if g > melhor_g + 1e-12:
                    melhor_c, melhor_g = c, g
            tot[melhor_c] += grau[v]
            if melhor_c != c0:
                comm[v] = melhor_c
                mudou = True
    return comm


def _agregar(H, part):
    """Fase de agregação: cada comunidade vira um super-nó (pesos somados;
    arestas internas viram laço)."""
    ids = {c: i for i, c in enumerate(sorted(set(part.values()), key=str))}
    K = nx.Graph()
    K.add_nodes_from(ids.values())
    for u, v, d in H.edges(data=True):
        a, b, w = ids[part[u]], ids[part[v]], d["weight"]
        if K.has_edge(a, b):
            K[a][b]["weight"] += w
        else:
            K.add_edge(a, b, weight=w)
    return K, ids


def louvain(G, seed=42):
    rng = random.Random(seed)
    H = _com_peso(G)
    if H.size(weight="weight") == 0:
        return [{v} for v in H]
    membros = {v: {v} for v in H}                    # super-nó -> nós originais
    while True:
        m = H.size(weight="weight")
        comm = _mover_nos(H, {v: v for v in H}, m, rng)
        if len(set(comm.values())) == H.number_of_nodes():
            break                                    # ninguém se juntou: convergiu
        K, ids = _agregar(H, comm)
        novo = defaultdict(set)
        for v, c in comm.items():
            novo[ids[c]] |= membros[v]
        membros, H = dict(novo), K
    return list(membros.values())


# ---- Leiden: movimentação + REFINAMENTO + agregação pela partição refinada --
def _refinar(H, comm, m, rng, theta, gamma):
    """Dentro de cada comunidade de `comm`, junta nós bem conectados em
    sub-comunidades (escolha aleatória ∝ exp(ΔQ/θ))."""
    grau = dict(H.degree(weight="weight"))
    ref = {v: v for v in H}                          # começa singleton
    mem = {v: {v} for v in H}
    tot = dict(grau)
    por_com = defaultdict(list)
    for v, c in comm.items():
        por_com[c].append(v)

    def entre(A, B):                                 # peso das arestas entre A e B
        return sum(d["weight"] for x in A for y, d in H[x].items() if y in B and y != x)

    for nos in por_com.values():
        C = set(nos)
        K_C = sum(grau[v] for v in C)
        rng.shuffle(nos)
        for v in nos:
            if len(mem[ref[v]]) > 1:                 # só nós ainda sozinhos
                continue
            if entre({v}, C - {v}) < gamma * grau[v] * (K_C - grau[v]) / (2 * m):
                continue                             # v não é bem conectado a C
            cands, ganhos = [], []
            for r in sorted({ref[u] for u in H[v] if u in C and u != v}, key=str):   # ordem fixa = reprodutível
                R = mem[r]
                if entre(R, C - R) < gamma * tot[r] * (K_C - tot[r]) / (2 * m):
                    continue                         # R não é bem conectada a C
                g = (entre({v}, R) - tot[r] * grau[v] / (2 * m)) / m
                if g >= 0:
                    cands.append(r)
                    ganhos.append(g)
            if cands:
                mx = max(ganhos)
                r = rng.choices(cands, weights=[math.exp((g - mx) / theta) for g in ganhos])[0]
                mem[ref[v]].discard(v)
                ref[v] = r
                mem[r].add(v)
                tot[r] += grau[v]
    return ref


def leiden(G, seed=42, theta=0.01, gamma=1.0):
    rng = random.Random(seed)
    H = _com_peso(G)
    if H.size(weight="weight") == 0:
        return [{v} for v in H]
    membros = {v: {v} for v in H}
    comm = {v: v for v in H}                         # P: começa singleton
    for _ in range(50):                              # trava de segurança
        m = H.size(weight="weight")
        comm = _mover_nos(H, comm, m, rng)           # 1. movimentação local
        if len(set(comm.values())) == H.number_of_nodes():
            break
        ref = _refinar(H, comm, m, rng, theta, gamma)  # 2. refinamento
        if len(set(ref.values())) == H.number_of_nodes():
            break                                    # refinamento não juntou nada
        K, ids = _agregar(H, ref)                    # 3. agrega pela partição refinada
        novo = defaultdict(set)
        for v, r in ref.items():
            novo[ids[r]] |= membros[v]
        comm = {ids[r]: comm[v] for v, r in ref.items()}   # projeta P nos super-nós
        membros, H = dict(novo), K
    final = defaultdict(set)
    for v, c in comm.items():
        final[c] |= membros[v]
    return list(final.values())


METODOS = {"Girvan-Newman": girvan_newman, "Louvain": louvain, "Leiden": leiden}


# ===========================================================================
# 2. MÉTRICAS
# ===========================================================================
def metricas(G, P, seg):
    """Q, ARI e NMI da partição P contra o segmento oficial."""
    part = para_dict(P)
    nos = sorted(part)
    ref = seg.loc[nos].astype(str).tolist()
    lab = [part[n] for n in nos]
    return {
        "n_comunidades": len(P),
        "modularidade": modularity(G, P, weight="weight"),
        "ARI_segmento": adjusted_rand_score(ref, lab),
        "NMI_segmento": normalized_mutual_info_score(ref, lab),
    }


def estabilidade(metodo, G, seeds=range(10)):
    """Roda várias seeds: Q médio, desvio e ARI médio entre execuções."""
    Ps = [metodo(G, seed=s) for s in seeds]
    qs = [modularity(G, P, weight="weight") for P in Ps]
    base = para_dict(Ps[0])
    nos = sorted(base)
    aris = [adjusted_rand_score([base[n] for n in nos], [para_dict(P)[n] for n in nos])
            for P in Ps[1:]]
    return {"Q_medio": np.mean(qs), "Q_desvio": np.std(qs), "ARI_entre_seeds": np.mean(aris)}


def entre_camadas(partes, metodos):
    """ARI/NMI entre as partições de duas camadas (mesmo método)."""
    linhas = []
    camadas = sorted({c for c, _ in partes})
    for m in metodos:
        for i, a in enumerate(camadas):
            for b in camadas[i + 1:]:
                pa, pb = partes[(a, m)], partes[(b, m)]
                nos = sorted(set(pa) & set(pb))
                x, y = [pa[n] for n in nos], [pb[n] for n in nos]
                linhas.append({"metodo": m, "camadas": f"{a} x {b}",
                               "ARI": adjusted_rand_score(x, y),
                               "NMI": normalized_mutual_info_score(x, y)})
    return pd.DataFrame(linhas)


def fora_do_segmento(part, seg, min_tam=3):
    """Fundos cujo segmento difere do segmento dominante da sua comunidade
    (só comunidades com pelo menos `min_tam` fundos)."""
    df = pd.DataFrame({"comunidade": pd.Series(part)})
    df["segmento"] = seg.reindex(df.index).astype(str)
    dom = df.groupby("comunidade")["segmento"].agg(lambda s: s.value_counts().idxmax())
    tam = df.groupby("comunidade")["segmento"].size()
    df["segmento_dominante"] = df["comunidade"].map(dom)
    df["tam_comunidade"] = df["comunidade"].map(tam)
    fora = df[(df["segmento"] != df["segmento_dominante"]) & (df["tam_comunidade"] >= min_tam)]
    return fora.rename_axis("ticker").reset_index()


def heatmap(part, seg, titulo, arq):
    """Comunidade x segmento: onde segmentos diferentes caem juntos."""
    tab = pd.crosstab(pd.Series(part, name="comunidade"),
                      seg.reindex(list(part)).astype(str).rename("segmento"))
    fig, ax = plt.subplots(figsize=(1.1 * len(tab.columns) + 2, 0.5 * len(tab) + 2))
    ax.imshow(tab.values, cmap="Blues")
    ax.set_xticks(range(len(tab.columns)))
    ax.set_xticklabels(tab.columns, rotation=40, ha="right")
    ax.set_yticks(range(len(tab)))
    ax.set_yticklabels([f"C{i}" for i in tab.index])
    for i in range(tab.shape[0]):
        for j in range(tab.shape[1]):
            if tab.values[i, j]:
                ax.text(j, i, tab.values[i, j], ha="center", va="center", fontsize=9)
    ax.set_title(titulo, fontsize=11, weight="bold")
    plt.tight_layout()
    plt.savefig(OUT / arq, dpi=140)
    plt.close()


# ===========================================================================
# 3. DADOS REAIS (camadas calibradas da Frente 2, em src/camadas.py)
# ===========================================================================
def carregar_real():
    atrib, cont, ret, _removidos = calib.carregar_dados()
    corr = gr.matriz_correlacao(ret)
    _, GA = calib.camada_a(atrib)                 # backbone kNN (k = K_BACKBONE_A)
    GB, _mst, _limiar = calib.camada_b(corr)      # união MST ∪ limiar (conexa)
    GC = calib.camada_c(cont)                     # kNN fundamentalista
    camadas = {
        f"A_backbone_k{calib.K_BACKBONE_A}": GA,
        f"B_MST_limiar_{calib.RHO_MIN_B}": GB,
        f"C_knn_k{calib.K_KNN_C}": GC,
    }
    return camadas, atrib["segmento"]


def _salvar(df, nome):
    """.csv para o grupo e .tex para o relatório (mesmo padrão do frente4.py)."""
    df.to_csv(OUT / f"{nome}.csv", index=False)
    try:
        tex = df.to_latex(index=False, float_format="%.3f", na_rep="--", escape=True)
        (OUT / f"{nome}.tex").write_text(tex, encoding="utf-8")
    except ImportError:
        print(f"   [aviso] jinja2 não instalado: {nome}.tex não gerado")


# ===========================================================================
# 4. EXECUÇÃO
# ===========================================================================
def main():
    OUT.mkdir(parents=True, exist_ok=True)
    camadas, seg = carregar_real()
    for nome, G in camadas.items():
        print(f"[{nome}] {G.number_of_nodes()} nós | {G.number_of_edges()} arestas | "
              f"{nx.number_connected_components(G)} componentes")

    partes, linhas_met, linhas_csv, linhas_fora = {}, [], [], []
    for cam, G in camadas.items():
        for nome_m, f in METODOS.items():
            t0 = time.time()
            P = f(G)
            dt = time.time() - t0
            part = para_dict(P)
            partes[(cam, nome_m)] = part
            met = {"camada": cam, "metodo": nome_m, **metricas(G, P, seg), "tempo_s": dt}
            if nome_m != "Girvan-Newman":            # GN é determinístico
                met.update(estabilidade(f, G))
            linhas_met.append(met)
            linhas_csv += [{"ticker": t, "camada": cam, "metodo": nome_m, "comunidade": c}
                           for t, c in sorted(part.items())]
            for _, r in fora_do_segmento(part, seg).iterrows():
                linhas_fora.append({"camada": cam, "metodo": nome_m, **r.to_dict()})

    met = pd.DataFrame(linhas_met)
    cols = ["camada", "metodo", "n_comunidades", "modularidade", "ARI_segmento",
            "NMI_segmento", "Q_medio", "Q_desvio", "ARI_entre_seeds", "tempo_s"]
    met = met[cols]
    cruz = entre_camadas(partes, METODOS)
    fora = pd.DataFrame(linhas_fora)

    # validação das implementações do zero contra a biblioteca (networkx)
    print("\n[validação] Q do seu código vs. biblioteca (mesma camada, seed 42)")
    try:
        for cam, G in camadas.items():
            Gp = _com_peso(G)
            q_lou = modularity(Gp, nx.community.louvain_communities(Gp, weight="weight", seed=42),
                               weight="weight")
            q_lei = modularity(Gp, nx.community.leiden_communities(
                Gp, weight="weight", metric="modularity", seed=42), weight="weight")
            mine = met[met.camada == cam].set_index("metodo")["modularidade"]
            print(f"  {cam:18s} Louvain: seu={mine['Louvain']:.3f} lib={q_lou:.3f} | "
                  f"Leiden: seu={mine['Leiden']:.3f} lib={q_lei:.3f}")
    except AttributeError:
        print("  (pulado: este networkx não tem leiden_communities — atualize: pip install -U networkx)")

    _salvar(met.round(3), "comunidades_metricas")
    _salvar(cruz.round(3), "comunidades_entre_camadas")
    _salvar(fora.round(3), "comunidades_fora_segmento")
    pd.DataFrame(linhas_csv).to_csv(OUT / "comunidades.csv", index=False)   # <- contrato com a parte 4

    for cam in camadas:                              # heatmap do método de maior Q em cada camada
        sub = met[met.camada == cam]
        m_best = sub.loc[sub.modularidade.idxmax(), "metodo"]
        heatmap(partes[(cam, m_best)], seg, f"{cam} — {m_best}: comunidade x segmento",
                f"comunidades_heatmap_{cam}.png")

    pd.set_option("display.width", 200)
    print("\n[métricas]\n" + met.round(3).to_string(index=False))
    print("\n[entre camadas]\n" + cruz.round(3).to_string(index=False))
    print(f"\n[fora do segmento] {len(fora)} linhas -> out/comunidades/comunidades_fora_segmento.csv")
    print(f"[ok] arquivos em {OUT}/")


if __name__ == "__main__":
    main()
