"""
Frente 2 — analise de sensibilidade e calibragem dos limiares.

Roda cada camada sob varios valores do seu parametro, mede o que acontece
com a estrutura do grafo e grava as tabelas que justificam a escolha final.
Depois monta as tres camadas ja calibradas e desenha as figuras.

Uso (a partir da raiz do repositorio):
    python src/frente2.py              # varredura + camadas finais
    python src/frente2.py --so-final   # pula a varredura

Saida: out/frente2/
"""
import argparse
import collections
import itertools
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import networkx as nx
import numpy as np
import pandas as pd
from matplotlib.lines import Line2D
from matplotlib.patches import Patch

import camadas as cam
import grafos as gr

PASTA = os.path.join("out", "frente2")
SEMENTE = 42

GRADE_K_A = [2, 3, 4, 5, 6, 8]
GRADE_RHO = [0.20, 0.25, 0.28, 0.30, 0.32, 0.35, 0.40]
GRADE_K_C = [2, 3, 4, 5, 6]


# ------------------------------------------------------------- utilidades
def salva_tabela(df, nome, index=True):
    df.to_csv(os.path.join(PASTA, nome + ".csv"), index=index)
    tex = df.to_latex(index=index, escape=True, float_format="%.3f")
    with open(os.path.join(PASTA, nome + ".tex"), "w", encoding="utf-8") as f:
        f.write(tex)


def salva_figura(nome):
    plt.tight_layout()
    plt.savefig(os.path.join(PASTA, nome), dpi=150, bbox_inches="tight")
    plt.close()


def metricas(G, atrib, rotulo):
    """Resumo estrutural de um grafo, para uma linha da tabela."""
    n = G.number_of_nodes()
    e = G.number_of_edges()
    isolados = sum(1 for _, g in G.degree() if g == 0)
    componentes = list(nx.connected_components(G))
    maior = max((len(c) for c in componentes), default=0)
    if e:
        part, q = gr.comunidades(G)
        ncom = len(set(part.values()))
        a = gr.concorda_com_segmento(part, atrib)
    else:
        q = ncom = a = np.nan
    pesos = {round(d["weight"], 6) for _, _, d in G.edges(data=True)}
    return {"configuracao": rotulo, "arestas": e,
            "pesos_distintos": len(pesos),
            "densidade": round(2 * e / (n * (n - 1)), 3),
            "grau_medio": round(2 * e / n, 1),
            "componentes": len(componentes), "isolados": isolados,
            "maior_componente_pct": round(100 * maior / n),
            "comunidades": ncom,
            "modularidade": round(q, 3) if e else np.nan,
            "ari_segmento": round(a, 3) if e else np.nan}


# ------------------------------------------------- camada A antes/depois
def _atrib_legado(atrib):
    """
    Reconstroi a Camada A como estava no frente4.py, com `tipo_fundo`
    derivado do segmento, para medir o efeito da remocao.
    """
    tipo = {"Papel": "Papel", "Fiagro": "Papel", "FoF": "FoF",
            "Híbrido": "Híbrido"}
    legado = atrib.copy()
    legado["tipo_fundo"] = atrib["segmento"].map(lambda s: tipo.get(s, "Tijolo"))
    legado["indexador"] = "n/a"
    legado["tipo_imovel"] = "n/a"
    return legado


def evolucao_camada_a(atrib):
    """Uma decisao por linha, para medir o efeito de cada uma."""
    com = gr.grafo_estrutural(_atrib_legado(atrib), limiar=0.0)
    soma = cam.grafo_estrutural(atrib, peso="soma")
    jac = cam.grafo_estrutural(atrib, peso="jaccard")
    return pd.DataFrame([
        metricas(com, atrib, "1. com tipo_fundo, soma do idf"),
        metricas(soma, atrib, "2. sem tipo_fundo, soma do idf"),
        metricas(jac, atrib, "3. sem tipo_fundo, Jaccard ponderado"),
        metricas(cam.backbone_knn(jac, cam.K_BACKBONE_A), atrib,
                 f"4. Jaccard + backbone k={cam.K_BACKBONE_A} (final)"),
    ]).set_index("configuracao")


# --------------------------------------- camada A: formulas de peso
def _cosseno(I, idf, a, b):
    num = sum(idf[x] ** 2 for x in I[a] & I[b])
    return num / np.sqrt(sum(idf[x] ** 2 for x in I[a]) *
                         sum(idf[x] ** 2 for x in I[b]))


def _gower(atrib, a, b):
    """Media por atributo; inquilino so entra se os dois tiverem lista."""
    s = [float(atrib.loc[a, c] == atrib.loc[b, c]) for c in cam.ATRIBUTOS_A]
    qa, qb = set(atrib.loc[a, "inquilinos"]), set(atrib.loc[b, "inquilinos"])
    if qa and qb:
        s.append(len(qa & qb) / len(qa | qb))
    return float(np.mean(s))


def comparacao_peso_a(atrib):
    """
    Mesmas regras (inquilino so de tijolo, backbone k=3 com empates),
    mudando so a formula do peso. vies_cobertura = correlacao entre o nº
    de itens de um fundo e a forca media das suas arestas: positivo favorece
    quem tem mais atributos, negativo penaliza.
    """
    I = cam.itens_de(atrib)
    freq = collections.Counter(x for s in I.values() for x in s)
    idf = {x: np.log(len(I) / c) for x, c in freq.items()}

    def monta(f):
        G = nx.Graph()
        G.add_nodes_from(atrib.index)
        for a, b in itertools.combinations(atrib.index, 2):
            if I[a] & I[b]:
                G.add_edge(a, b, weight=f(a, b))
        return G

    grafos = {"soma do idf": cam.grafo_estrutural(atrib, peso="soma"),
              "Jaccard ponderado": cam.grafo_estrutural(atrib, peso="jaccard"),
              "cosseno (TF-IDF)": monta(lambda a, b: _cosseno(I, idf, a, b)),
              "Gower": monta(lambda a, b: _gower(atrib, a, b))}
    seg = atrib["segmento"]
    n_itens = pd.Series({t: len(I[t]) for t in I})
    linhas = []
    for nome, G in grafos.items():
        B = cam.backbone_knn(G, cam.K_BACKBONE_A)
        forca = pd.Series({t: np.mean([d["weight"] for d in G[t].values()])
                           for t in G})
        intra = {s: np.mean([B[a][b]["weight"] for a, b in B.edges()
                             if seg[a] == seg[b] == s])
                 for s in ["Logística", "Papel"]}
        linha = metricas(B, atrib, nome)
        linha["pesos_distintos"] = len({round(d["weight"], 6)
                                        for _, _, d in G.edges(data=True)})
        linha["vies_cobertura"] = round(np.corrcoef(n_itens, forca)[0, 1], 2)
        linha["razao_intra_log_papel"] = round(intra["Logística"] / intra["Papel"], 2)
        linhas.append(linha)
    return pd.DataFrame(linhas).set_index("configuracao")


# ------------------------------------------------------------ varreduras
def sweep_a(atrib):
    G = cam.grafo_estrutural(atrib)
    linhas = [metricas(G, atrib, "completa (sem backbone)")]
    for k in GRADE_K_A:
        linhas.append(metricas(cam.backbone_knn(G, k), atrib, f"k = {k}"))
    return pd.DataFrame(linhas).set_index("configuracao")


def sweep_b(corr, atrib):
    linhas = [metricas(gr.grafo_mst(corr), atrib, "só MST")]
    for r in GRADE_RHO:
        linhas.append(metricas(gr.grafo_limiar(corr, rho_min=r), atrib,
                               f"só limiar ρ ≥ {r:.2f}"))
    for r in GRADE_RHO:
        U, _, _ = cam.camada_b(corr, rho_min=r)
        linhas.append(metricas(U, atrib, f"MST ∪ ρ ≥ {r:.2f}"))
    return pd.DataFrame(linhas).set_index("configuracao")


def sweep_c(cont, atrib):
    linhas = [metricas(cam.camada_c(cont, k=k), atrib, f"k = {k}")
              for k in GRADE_K_C]
    return pd.DataFrame(linhas).set_index("configuracao")


def figura_sensibilidade(sa, sb, sc, corr):
    fig, eixos = plt.subplots(1, 3, figsize=(15, 4.2))

    ka = [int(i.split("=")[1]) for i in sa.index if i.startswith("k =")]
    la = sa[sa.index.str.startswith("k =")]
    _curva(eixos[0], ka, la, cam.K_BACKBONE_A,
           "Camada A — backbone kNN", "k (arestas por fundo)")

    lb = sb[sb.index.str.startswith("MST")]
    _curva(eixos[1], GRADE_RHO, lb, cam.RHO_MIN_B,
           "Camada B — MST ∪ limiar", "ρ mínimo")
    p95 = np.quantile(corr.values[np.triu_indices(len(corr), 1)], 0.95)
    eixos[1].axvline(p95, color="#64748b", ls=":", lw=1)

    _curva(eixos[2], GRADE_K_C, sc, cam.K_KNN_C,
           "Camada C — kNN", "k (vizinhos por fundo)")

    salva_figura("10_sensibilidade.png")


def _curva(ax, xs, tabela, escolhido, titulo, xlabel):
    ax.plot(xs, tabela["grau_medio"], "o-", color="#2563eb", label="grau médio")
    ax.set_xlabel(xlabel)
    ax.set_ylabel("grau médio", color="#2563eb")
    ax.tick_params(axis="y", labelcolor="#2563eb")
    ax.axvline(escolhido, color="#dc2626", ls="--", lw=1.2)
    ax.set_title(titulo, fontsize=11)

    ax2 = ax.twinx()
    ax2.plot(xs, tabela["modularidade"], "s-", color="#059669",
             label="modularidade")
    ax2.set_ylabel("modularidade", color="#059669")
    ax2.tick_params(axis="y", labelcolor="#059669")
    ax.grid(alpha=0.25)


# -------------------------------------------------------------- desenhos
def diagnostico_limitacoes(corr, ret, cont):
    """
    Mede as limitações das Camadas B e C que o relatório precisa declarar,
    para que os números citados no texto sejam reproduzíveis.

    Fator de mercado: compara o espectro da matriz de correlação com o limite
    de ruído de Marchenko-Pastur, (1 + sqrt(N/T))^2. Autovalor abaixo desse
    limite é indistinguível do que se obteria com séries aleatórias.

    Regime: a matriz de 2023 contra a de 2024.

    Frequência: a correlação diária subestima o co-movimento de ativo pouco
    negociado, porque o preço não se move todo dia.

    Colinearidade da Camada C: dois indicadores muito correlacionados fazem a
    mesma dimensão pesar duas vezes na distância euclidiana.
    """
    N, T = len(corr), len(ret)
    iu = np.triu_indices(N, 1)
    ev = np.sort(np.linalg.eigvalsh(corr.values))[::-1]
    limite = (1 + np.sqrt(N / T)) ** 2

    r23 = ret[ret.index.year == 2023]
    r24 = ret[ret.index.year == 2024]
    m23 = gr.matriz_correlacao(r23).values[iu]
    m24 = gr.matriz_correlacao(r24).values[iu]
    semanal = gr.matriz_correlacao(ret.resample("W").sum()).values[iu]

    c = cont.corr().abs().to_numpy(copy=True)
    np.fill_diagonal(c, 0.0)
    i, j = np.unravel_index(np.argmax(c), c.shape)

    linhas = [
        ("fator de mercado", "1º autovalor", round(ev[0], 2),
         f"{ev[0] / N:.1%} da variância total"),
        ("fator de mercado", "limite de ruído (Marchenko-Pastur)",
         round(limite, 2), f"N={N}, T={T}"),
        ("fator de mercado", "autovalores acima do ruído", int((ev > limite).sum()),
         f"o 2º é {ev[1]:.2f}, logo acima do limite"),
        ("regime", "ρ médio em 2023", round(m23.mean(), 2), f"{len(r23)} pregões"),
        ("regime", "ρ médio em 2024", round(m24.mean(), 2), f"{len(r24)} pregões"),
        ("regime", "correlação entre as matrizes de 2023 e 2024",
         round(np.corrcoef(m23, m24)[0, 1], 2), "sobre os pares"),
        ("frequência", "mediana de ρ, retorno diário",
         round(np.median(corr.values[iu]), 2), f"{T} pregões"),
        ("frequência", "mediana de ρ, retorno semanal",
         round(np.median(semanal), 2), "agregando os retornos por semana"),
        ("camada C", f"maior correlação entre indicadores "
         f"({cont.columns[i]} × {cont.columns[j]})",
         round(c[i, j], 2), "mede a mesma dimensão duas vezes"),
    ]
    return pd.DataFrame(linhas, columns=["tema", "medida", "valor", "observação"]
                        ).set_index(["tema", "medida"])


N_EXECUCOES = 200   # sementes do Louvain na medida de estabilidade do ARI


def estabilidade_ari(grafos, atrib):
    """
    O Louvain é estocástico: cada semente pode dar uma partição diferente.
    A tabela 06 usa uma semente só (a de gr.comunidades); aqui o Louvain roda
    com N_EXECUCOES sementes em cada camada, para mostrar o valor típico do
    ARI com o segmento e o quanto ele varia. A coluna da semente única é a
    mesma da tabela 06.
    """
    import community as community_louvain
    linhas = []
    for nome, G in grafos.items():
        unica, _ = gr.comunidades(G)
        aris, qs = [], []
        for s in range(N_EXECUCOES):
            part = community_louvain.best_partition(G, weight="weight", random_state=s)
            aris.append(gr.concorda_com_segmento(part, atrib))
            qs.append(community_louvain.modularity(part, G, weight="weight"))
        linhas.append({"camada": nome,
                       "ari_semente_unica": round(gr.concorda_com_segmento(unica, atrib), 3),
                       f"ari_media_{N_EXECUCOES}": round(float(np.mean(aris)), 3),
                       "ari_desvio": round(float(np.std(aris)), 3),
                       "ari_min": round(float(np.min(aris)), 3),
                       "ari_max": round(float(np.max(aris)), 3),
                       "modularidade_media": round(float(np.mean(qs)), 3)})
    return pd.DataFrame(linhas).set_index("camada")


def _cores(G, atrib):
    return [cam.PALETA.get(atrib.loc[n, "segmento"], "#94a3b8") for n in G]


def _legenda(G, atrib):
    segs = sorted({atrib.loc[n, "segmento"] for n in G})
    return [Patch(facecolor=cam.PALETA.get(s, "#94a3b8"), label=s) for s in segs]


def desenha(G, atrib, titulo, nome, tracejadas=()):
    # Kamada-Kawai pela distancia em saltos: nao depende da escala dos pesos
    # (o spring_layout usa o peso como atracao e, com pesos entre 0 e 1 do
    # Jaccard, espalhava os segmentos)
    pos = nx.kamada_kawai_layout(G, weight=None)
    pesos = [d["weight"] for _, _, d in G.edges(data=True)]
    faixa = np.ptp(pesos) or 1.0
    larguras = [0.4 + 2.2 * (w - min(pesos)) / faixa for w in pesos]

    plt.figure(figsize=(10, 8))
    cheias = [(a, b) for a, b in G.edges() if (a, b) not in tracejadas
              and (b, a) not in tracejadas]
    nx.draw_networkx_edges(G, pos, edgelist=cheias, width=[
        larguras[i] for i, (a, b) in enumerate(G.edges())
        if (a, b) not in tracejadas and (b, a) not in tracejadas],
        alpha=0.55, edge_color="#475569")
    if tracejadas:
        nx.draw_networkx_edges(G, pos, edgelist=list(tracejadas), width=0.8,
                               style="dashed", alpha=0.5, edge_color="#94a3b8")
    nx.draw_networkx_nodes(G, pos, node_size=640,
                           node_color=_cores(G, atrib), linewidths=0.4,
                           edgecolors="white")
    nx.draw_networkx_labels(G, pos, font_size=6, font_color="white",
                            clip_on=False)

    handles = _legenda(G, atrib)
    if tracejadas:
        handles.append(Line2D([0], [0], color="#94a3b8", ls="--",
                              label="aresta só da MST"))
    plt.legend(handles=handles, loc="upper left", fontsize=8, frameon=False)
    plt.title(titulo, fontsize=12)
    plt.axis("off")
    salva_figura(nome)


# ------------------------------------------------------------------ main
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--so-final", action="store_true",
                    help="pula a varredura de sensibilidade")
    args = ap.parse_args()
    os.makedirs(PASTA, exist_ok=True)

    atrib, cont, ret, removidos = cam.carregar_dados()
    corr = gr.matriz_correlacao(ret)
    n = len(atrib)
    print(f"[frente2] {n} fundos | {len(ret)} pregões | saída em {PASTA}/")

    salva_tabela(removidos.set_index("ticker"), "00_fundos_removidos")
    pares = corr.values[np.triu_indices(n, 1)]
    dist = pd.DataFrame({"correlação entre pares": np.quantile(
        pares, [0, .25, .5, .75, .9, .95, 1])},
        index=["mínimo", "p25", "mediana", "p75", "p90", "p95", "máximo"])
    salva_tabela(dist.round(3), "01_distribuicao_correlacao")
    print(f"   p95 da correlação = {np.quantile(pares, 0.95):.3f} "
          f"(mediana {np.median(pares):.3f}, máximo {pares.max():.3f})")

    if not args.so_final:
        print("[1/3] evolução da Camada A e comparação das fórmulas de peso")
        salva_tabela(evolucao_camada_a(atrib), "02_evolucao_camada_a")
        comp = comparacao_peso_a(atrib)
        salva_tabela(comp, "08_comparacao_peso_a")
        print(comp.to_string())
        print("[2/3] varredura das três camadas")
        sa, sb, sc = sweep_a(atrib), sweep_b(corr, atrib), sweep_c(cont, atrib)
        salva_tabela(sa, "03_sensibilidade_camada_a")
        salva_tabela(sb, "04_sensibilidade_camada_b")
        salva_tabela(sc, "05_sensibilidade_camada_c")
        print("[3/3] figura de sensibilidade")
        figura_sensibilidade(sa, sb, sc, corr)

    GA_completa, GA = cam.camada_a(atrib)
    GB, MST, GL = cam.camada_b(corr)
    GC = cam.camada_c(cont)

    final = pd.DataFrame([
        metricas(GA, atrib, f"A — backbone k={cam.K_BACKBONE_A}"),
        metricas(GB, atrib, f"B — MST ∪ ρ ≥ {cam.RHO_MIN_B}"),
        metricas(GC, atrib, f"C — kNN k={cam.K_KNN_C}"),
    ]).set_index("configuracao")
    salva_tabela(final, "06_camadas_calibradas")
    print("\n" + final.to_string())

    escolhidos = pd.DataFrame([
        {"limiar": "COBERTURA_MIN", "valor": cam.COBERTURA_MIN,
         "camada": "dados", "critério": "fundo precisa de cotação real em "
         "90% do período; abaixo disso a série é cópia da coleta"},
        {"limiar": "ZEROS_MAX", "valor": cam.ZEROS_MAX, "camada": "dados",
         "critério": "mais de 30% de pregões parados indica iliquidez ou "
         "falha da fonte, não ausência de co-movimento"},
        {"limiar": "K_BACKBONE_A", "valor": cam.K_BACKBONE_A, "camada": "A",
         "critério": "menor k que deixa A e C com grau médio acima de 3, "
         "alinhado à Camada B (com k=2 a C fica em 2,9); na A a modularidade "
         "é máxima até k=3 e cai a partir de k=4. Empates com a k-ésima "
         "aresta são mantidos; corte por peso seria enviesado pelo tamanho "
         "do segmento"},
        {"limiar": "RHO_MIN_B", "valor": cam.RHO_MIN_B, "camada": "B",
         "critério": "percentil 95 da distribuição de correlação entre pares "
         "(0,315, arredondado para 0,32)"},
        {"limiar": "K_KNN_C", "valor": cam.K_KNN_C, "camada": "C",
         "critério": "mesmo k da Camada A, pela mesma regra; deixa as três "
         "camadas conexas, com grau médio entre 3,0 e 5,3"},
    ]).set_index("limiar")
    salva_tabela(escolhidos, "07_limiares_escolhidos")
    salva_tabela(diagnostico_limitacoes(corr, ret, cont), "09_diagnostico_limitacoes")

    estab = estabilidade_ari({"A": GA, "B": GB, "C": GC}, atrib)
    salva_tabela(estab, "10_estabilidade_ari")
    print(f"\n   ARI com o segmento em {N_EXECUCOES} execuções do Louvain:\n" + estab.to_string())

    so_mst = {(a, b) for a, b, d in GB.edges(data=True) if d["origem"] == "mst"}
    desenha(GA, atrib, f"Camada A — estrutural, backbone k={cam.K_BACKBONE_A}",
            "11_camada_a.png")
    desenha(GB, atrib, f"Camada B — MST ∪ ρ ≥ {cam.RHO_MIN_B}",
            "12_camada_b.png", tracejadas=so_mst)
    desenha(GC, atrib, f"Camada C — perfil fundamentalista, kNN k={cam.K_KNN_C}",
            "13_camada_c.png")

    print(f"\n   Camada A completa tinha {GA_completa.number_of_edges()} arestas; "
          f"o backbone ficou com {GA.number_of_edges()}")
    print(f"   Camada B: {len(so_mst)} arestas vêm só da MST, "
          f"{GL.number_of_edges()} vêm do limiar")
    print(f"\n[ok] tabelas e figuras em {PASTA}/")


if __name__ == "__main__":
    main()
