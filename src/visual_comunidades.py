"""
Visual das comunidades: ANTES x Girvan-Newman x Louvain x Leiden, nas 3 camadas.

Rodar da raiz do repositório:
  python src/visual_comunidades.py            # abre a janela interativa
  python src/visual_comunidades.py --salvar   # só salva os PNGs em out/comunidades/

Teclas na janela:
  ← →     Antes / Girvan-Newman / Louvain / Leiden
  1 2 3   troca a camada (A estrutural, B comportamental, C fundamentalista)
  s       alterna a cor dos nós: COMUNIDADE <-> SEGMENTO oficial
          (no modo segmento, arestas escuras = fundos na mesma comunidade)
  p       salva a tela atual em PNG

Precisa do src/comunidades.py (ele calcula as partições).
"""
import sys
from collections import defaultdict

import matplotlib
import matplotlib.pyplot as plt
BACKEND_PADRAO = matplotlib.get_backend()      # guarda ANTES de importar o comunidades (ele força "Agg")

import networkx as nx
import comunidades as com

plt.switch_backend("agg")
QUADROS = ["Antes", "Girvan-Newman", "Louvain", "Leiden"]
NEUTRO, ISOLADO = "#9DB4CE", "#D0D0D0"
# cores bem distintas entre si (tab10 sem o cinza, que fica reservado aos isolados) + Set3
TAB = [c for i, c in enumerate(plt.cm.tab10.colors) if i != 7] + list(plt.cm.Set3.colors)


def layout(G):
    """Mola no maior grupo conectado; fundos isolados (ou grupinhos) vão numa grade embaixo,
    para não esticar o desenho (acontece na camada B, que tem muitos isolados)."""
    def mola(H, **kw):
        return nx.spring_layout(H, weight="weight", seed=42, iterations=300,
                                k=1.6 / max(H.number_of_nodes(), 1) ** 0.5, **kw)
    comps = sorted(nx.connected_components(G), key=len, reverse=True)
    pos = mola(G.subgraph(comps[0]))
    por_linha = 10
    for i, comp in enumerate(comps[1:]):
        linha, col = divmod(i, por_linha)
        x, y = -1 + 2 * col / (por_linha - 1), -1.5 - 0.3 * linha
        sub = mola(G.subgraph(comp), scale=0.12) if len(comp) > 1 else {next(iter(comp)): (0, 0)}
        for n, (a, b) in sub.items():
            pos[n] = (x + a, y + b)
    return pos


def preparar():
    """Calcula layout e partições de cada camada (uma vez só)."""
    camadas, seg = com.carregar_real()
    dados = []
    for nome, G in camadas.items():
        n = G.number_of_nodes()
        pos = layout(G)
        quadros = {"Antes": dict(part=None, titulo=f"Antes — {n} fundos, {G.number_of_edges()} arestas")}
        for m, f in com.METODOS.items():
            P = f(G)
            met = com.metricas(G, P, seg)
            quadros[m] = dict(
                part=com.para_dict(P),
                titulo=(f"{m} — Q = {met['modularidade']:.3f} · {met['n_comunidades']} comunidades · "
                        f"ARI seg = {met['ARI_segmento']:.2f}"))
        dados.append(dict(nome=nome, G=G, pos=pos, quadros=quadros))
    return dados, seg


def cores_nos(G, part, seg, modo):
    if modo == "segmento":
        segs = sorted(seg.reindex(list(G.nodes)).astype(str).unique())
        mapa = {s: TAB[i % len(TAB)] for i, s in enumerate(segs)}
        return {n: mapa[str(seg[n])] for n in G.nodes}, mapa
    if part is None:
        return {n: NEUTRO for n in G.nodes}, {}
    tam = defaultdict(int)
    for c in part.values():
        tam[c] += 1
    return {n: (TAB[part[n] % len(TAB)] if tam[part[n]] > 1 else ISOLADO) for n in G.nodes}, {}


def desenhar(ax, G, pos, quadro, seg, modo, escala=1.0):
    ax.clear()
    ax.axis("off")
    part = quadro["part"]
    grupo = part                                      # arestas escuras = mesma comunidade
    if grupo is None and modo == "segmento":          # "Antes" por segmento: escuras = mesmo segmento
        grupo = {n: str(seg[n]) for n in G.nodes}
    cor, _ = cores_nos(G, part, seg, modo)

    ws = [d["weight"] for _, _, d in G.edges(data=True)]
    lo, hi = min(ws), max(ws)
    def larg(w):
        return (1.1 + 2.6 * (w - lo) / (hi - lo + 1e-12)) * escala

    dentro = [(u, v) for u, v in G.edges if grupo and grupo[u] == grupo[v]]
    fora = [(u, v) for u, v in G.edges if not grupo or grupo[u] != grupo[v]]
    if grupo:   # arestas entre grupos ficam apagadas; dentro do grupo, em destaque
        nx.draw_networkx_edges(G, pos, ax=ax, edgelist=fora, edge_color="#8C8C8C", style="dashed",
                               width=[max(larg(G[u][v]["weight"]) * 0.7, 0.9 * escala) for u, v in fora], alpha=0.85)
        nx.draw_networkx_edges(G, pos, ax=ax, edgelist=dentro, edge_color="#2E2E2E",
                               width=[larg(G[u][v]["weight"]) for u, v in dentro])
    else:
        nx.draw_networkx_edges(G, pos, ax=ax, edge_color="#7A7A7A",
                               width=[larg(G[u][v]["weight"]) for u, v in G.edges])
    nx.draw_networkx_nodes(G, pos, ax=ax, node_color=[cor[n] for n in G.nodes],
                           node_size=620 * escala ** 2, edgecolors="white", linewidths=1.5 * escala)
    nx.draw_networkx_labels(G, pos, ax=ax, font_size=6.2 * escala, font_color="#111111")
    ax.set_title(quadro["titulo"], fontsize=11 * escala + 1, fontweight="bold")


def legenda(seg, G):
    from matplotlib.patches import Patch
    _, mapa = cores_nos(G, None, seg, "segmento")
    return [Patch(color=c, label=s) for s, c in mapa.items()]


def resumo(quadro, seg, modo, G):
    """Texto do painel lateral: comunidades (ou segmentos) com tamanho e segmento dominante."""
    part = quadro["part"]
    if part is None:
        cont = seg.reindex(list(G.nodes)).astype(str).value_counts()
        return "Segmentos oficiais\n\n" + "\n".join(f"{s}: {n}" for s, n in cont.items())
    grupos = defaultdict(list)
    for t, c in part.items():
        grupos[c].append(t)
    linhas, solo = [], 0
    for c in sorted(grupos):
        m = grupos[c]
        if len(m) == 1:
            solo += 1
            continue
        top = seg.reindex(m).astype(str).value_counts().head(2)
        linhas.append(f"C{c} · {len(m)} fundos\n    " + ", ".join(f"{s} {n}" for s, n in top.items()))
    if solo:
        linhas.append(f"+ {solo} fundo(s) isolado(s)")
    return "Comunidades\n\n" + "\n".join(linhas[:14])


def salvar_grades(dados, seg):
    """Um PNG 2x2 por camada e por modo de cor (para o relatório)."""
    com.OUT.mkdir(parents=True, exist_ok=True)
    for d in dados:
        for modo in ("comunidade", "segmento"):
            fig, axs = plt.subplots(2, 2, figsize=(16, 12))
            for ax, nome in zip(axs.ravel(), QUADROS):
                desenhar(ax, d["G"], d["pos"], d["quadros"][nome], seg, modo, escala=0.8)
            sub = ("cor = segmento oficial · arestas escuras = mesma comunidade" if modo == "segmento"
                   else "cor = comunidade · cinza = fundo isolado")
            fig.suptitle(f"{d['nome']} — {sub}", fontsize=15, fontweight="bold")
            plt.tight_layout()
            if modo == "segmento":
                plt.subplots_adjust(bottom=0.07)
                fig.legend(handles=legenda(seg, d["G"]), loc="lower center", ncol=5, fontsize=11)
            sufixo = "" if modo == "comunidade" else "_segmento"
            arq = com.OUT / f"visual_{d['nome']}{sufixo}.png"
            fig.savefig(arq, dpi=130)
            plt.close(fig)
            print("salvo:", arq)


def janela(dados, seg):
    plt.switch_backend(BACKEND_PADRAO)
    fig = plt.figure(figsize=(14, 8))
    ax = fig.add_axes([0.01, 0.06, 0.70, 0.86])
    painel = fig.add_axes([0.72, 0.06, 0.27, 0.86])
    painel.axis("off")
    fig.text(0.36, 0.015, "← →  método    |    1 2 3  camada    |    s  cor por comunidade/segmento    |    p  salvar PNG",
             ha="center", color="gray")
    est = {"cam": 0, "q": 0, "modo": "comunidade"}

    def mostrar():
        d = dados[est["cam"]]
        quadro = d["quadros"][QUADROS[est["q"]]]
        desenhar(ax, d["G"], d["pos"], quadro, seg, est["modo"])
        painel.clear()
        painel.axis("off")
        painel.text(0, 1, f"Camada: {d['nome']}\n\n" + resumo(quadro, seg, est["modo"], d["G"]),
                    va="top", fontsize=9, family="monospace")
        if est["modo"] == "segmento":
            painel.legend(handles=legenda(seg, d["G"]), loc="lower left", title="Segmento oficial", fontsize=9)
        fig.canvas.draw_idle()

    def tecla(ev):
        if ev.key == "right":
            est["q"] = min(est["q"] + 1, len(QUADROS) - 1)
        elif ev.key == "left":
            est["q"] = max(est["q"] - 1, 0)
        elif ev.key in ("1", "2", "3") and int(ev.key) <= len(dados):
            est["cam"] = int(ev.key) - 1
        elif ev.key == "s":
            est["modo"] = "segmento" if est["modo"] == "comunidade" else "comunidade"
        elif ev.key == "p":
            com.OUT.mkdir(parents=True, exist_ok=True)
            arq = com.OUT / f"tela_{dados[est['cam']]['nome']}_{QUADROS[est['q']]}_{est['modo']}.png"
            fig.savefig(arq, dpi=150)
            print("salvo:", arq)
            return
        else:
            return
        mostrar()

    fig.canvas.mpl_connect("key_press_event", tecla)
    mostrar()
    plt.show()


def main():
    com.main()                 # imprime as tabelas e salva CSV/TEX/heatmaps
    dados, seg = preparar()
    sem_janela = BACKEND_PADRAO.lower() == "agg"
    if "--salvar" in sys.argv or sem_janela:
        if sem_janela and "--salvar" not in sys.argv:
            print("(sem janela gráfica disponível: salvando PNGs)")
        salvar_grades(dados, seg)
    else:
        janela(dados, seg)


if __name__ == "__main__":
    main()
