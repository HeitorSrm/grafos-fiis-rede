"""
Protótipo FIIs-como-rede — 3 camadas valoradas + comparação de carteiras.
Pipeline no estilo CRISP-NET: dados → modelagem → avaliação → figuras.
"""
import numpy as np
import pandas as pd
import networkx as nx
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt

import data
import grafos as gr

OUT = "out"
PALETA = {"Logistica":"#2563eb","Shoppings":"#db2777","Lajes":"#059669",
          "Papel":"#d97706","Renda Urbana":"#7c3aed","FoF":"#0891b2","Hibrido":"#64748b"}

# 1. DADOS -------------------------------------------------------------------
atrib, cont, ret = data.carregar_tudo_simulado()
print(f"[dados] {len(atrib)} FIIs | contínuos {cont.shape} | retornos {ret.shape}")

# 2. CAMADA A — projeção valorada por raridade -------------------------------
GA = gr.grafo_estrutural(atrib)
wA = [d["weight"] for *_, d in GA.edges(data=True)]
print(f"[A estrutural] {GA.number_of_edges()} arestas | peso {min(wA):.2f}–{max(wA):.2f}")

# 3. CAMADA B — correlação → MST + limiar ------------------------------------
corr = gr.matriz_correlacao(ret)
MST = gr.grafo_mst(corr)
GL = gr.grafo_limiar(corr, 0.5)
print(f"[B comportamental] MST {MST.number_of_edges()} | limiar(0.5) {GL.number_of_edges()}")

# 4. CAMADA C — similaridade fundamentalista ---------------------------------
GC = gr.grafo_fundamentalista(cont, k=4)
print(f"[C fundamentalista] {GC.number_of_edges()} arestas (kNN k=4)")

# 5. AVALIAÇÃO ---------------------------------------------------------------
partB, modB = gr.comunidades(GL)
ariB = gr.concorda_com_segmento(partB, atrib)
print(f"[comunidades B] {len(set(partB.values()))} | modularidade={modB:.3f} | ARI vs segmento={ariB:.3f}")
cent = gr.centralidades(MST)
print("[centralidade MST] top-4 pontes:\n" + cent.head(4).round(3).to_string())

# 6. CARTEIRAS — aparente vs. efetiva ----------------------------------------
m_ideal = gr.avalia_carteira(data.CARTEIRA_IDEAL, corr, atrib, cont, MST, partB)
m_falsa = gr.avalia_carteira(data.CARTEIRA_FALSA, corr, atrib, cont, MST, partB)
tab = pd.DataFrame({"Carteira ideal": m_ideal, "Falsa diversificada": m_falsa})
print("\n[carteiras]\n" + tab.to_string())


# FIGURAS --------------------------------------------------------------------
def desenha(G, titulo, arq, part=None, pos=None, destaque=None, wkey="weight"):
    plt.figure(figsize=(9, 7))
    pos = pos or nx.spring_layout(G, seed=3, k=0.6)
    if part is not None:
        cm = plt.get_cmap("tab10")
        cores = [cm(part[n] % 10) for n in G.nodes()]
    else:
        cores = [PALETA.get(atrib.loc[n, "segmento"], "#999") for n in G.nodes()]
    ws = np.array([d.get(wkey, 1) for *_, d in G.edges(data=True)], float)
    lw = 0.5 + 3 * (ws - ws.min()) / (np.ptp(ws) + 1e-9) if len(ws) else 1
    nx.draw_networkx_edges(G, pos, alpha=0.35, width=lw)
    ec = ["#111" if destaque and n in destaque else "white" for n in G.nodes()]
    lwn = [2.8 if destaque and n in destaque else 1 for n in G.nodes()]
    nx.draw_networkx_nodes(G, pos, node_color=cores, node_size=320,
                           edgecolors=ec, linewidths=lwn)
    nx.draw_networkx_labels(G, pos, font_size=6.5)
    plt.title(titulo, fontsize=12.5, weight="bold"); plt.axis("off")
    plt.tight_layout(); plt.savefig(f"{OUT}/{arq}", dpi=140, bbox_inches="tight"); plt.close()
    return pos

desenha(GA, "Camada A — Estrutural valorada (projeção bipartida, peso por raridade)\n"
            "cor=segmento | espessura=força do vínculo", "grafo_A_estrutural.png")
posB = nx.spring_layout(MST, seed=7, k=0.9)
desenha(MST, "Camada B — MST de co-movimento | cor=segmento", "grafo_B_mst_segmento.png", pos=posB)
desenha(MST, f"Camada B — Comunidades (Louvain) | mod={modB:.2f}", "grafo_B_mst_comunidade.png",
        part=partB, pos=posB)
desenha(GC, "Camada C — Similaridade fundamentalista (kNN valorado)\n"
            "cor=segmento | espessura=similaridade", "grafo_C_fundamental.png")

# carteiras destacadas sobre a MST
desenha(MST, "Carteira IDEAL (1 por segmento) destacada na rede de co-movimento",
        "carteira_ideal.png", pos=posB, destaque=set(data.CARTEIRA_IDEAL))
desenha(MST, "Carteira FALSA diversificada (só Logística+Shoppings) destacada",
        "carteira_falsa.png", pos=posB, destaque=set(data.CARTEIRA_FALSA))

# barras comparando as métricas-chave
fig, ax = plt.subplots(1, 2, figsize=(11, 4.2))
ax[0].bar(["Ideal", "Falsa"], [m_ideal["corr_media"], m_falsa["corr_media"]],
          color=["#059669", "#be123c"])
ax[0].set_title("Correlação média intra-carteira\n(menor = mais diversificada)", fontsize=11)
ax[0].set_ylim(0, 1)
for i, v in enumerate([m_ideal["corr_media"], m_falsa["corr_media"]]):
    ax[0].text(i, v + 0.02, f"{v:.2f}", ha="center", weight="bold")
met = ["n_segmentos", "n_comunidades", "num_ativos_medio"]
x = np.arange(len(met)); w = 0.35
ax[1].bar(x - w/2, [m_ideal[k] for k in met], w, label="Ideal", color="#059669")
ax[1].bar(x + w/2, [m_falsa[k] for k in met], w, label="Falsa", color="#be123c")
ax[1].set_xticks(x); ax[1].set_xticklabels(["segmentos", "comunidades", "nº ativos méd."], fontsize=9)
ax[1].set_title("Diversificação por estrutura e atributos", fontsize=11); ax[1].legend()
plt.tight_layout(); plt.savefig(f"{OUT}/carteiras_metricas.png", dpi=140, bbox_inches="tight"); plt.close()

print("\n[ok] figuras em ./out/")
