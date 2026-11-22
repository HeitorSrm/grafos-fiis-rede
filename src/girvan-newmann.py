# função girvanNewman(Grafo G):
#     enquanto quantidade_componentes_conectados(G) == 1, faça
#         # Calcula a centralidade de intermediação (edge betweenness) de todas as arestas
#         intermediacao <- calcularIntermediacaoArestas(G)
#
#         # Encontra a aresta que faz parte do maior número de caminhos mais curtos
#         e_max <- argmax(intermediacao)
#
#         remover e_max de E(G)
#     fim enquanto
#     P <- componentes_conectados(G)
#     retornar P
# função final

# função calcularIntermediacaoArestas(Grafo G):
#     intermediacao[e] <- 0 para todo e em E(G)
#     para v em V(G), faça
#         # Executa busca em largura (BFS) a partir de v para encontrar caminhos mais curtos
#         caminhos <- caminhosMaisCurtos(G, v)
#         para cada aresta e utilizada em caminhos, faça
#             intermediacao[e] <- intermediacao[e] + fracao_caminhos(e)
#         fim para
#     fim para
#     retornar intermediacao
# função final

#------------------------------------------------------------------------------------------------------------------------------------------------

# import networkx as nx

# def girvan_newman(G):
#     criar_grafo(G, "Grafo Completo")
#     passo = 1
    
#     while len(list(nx.connected_components(G))) == 1:
#         betw = nx.edge_betweenness_centrality(G)
#         maiorAresta = max(betw, key=betw.get)
        
#         print(f"Passo {passo}: Remover {maiorAresta}")
#         G.remove_edge(*maiorAresta)
#         criar_grafo(G, f"Passo {passo}: Remover {maiorAresta}")
        
#         passo += 1

#     return list(nx.connected_components(G))

# G = nx.Graph()
# G.add_edges_from([
#     ('A', 'B'), ('B', 'C'), ('C', 'D'), ('D', 'E'), ('E', 'F'),
#     ('F', 'G'), ('G', 'H'), ('H', 'A'), ('B', 'H'), ('C', 'G'),
#     ('D', 'F')
# ])

# comunidades = girvan_newman(G)

# print("\nComunidades Finais: ")
# for i, c in enumerate(comunidades, 1):
#     print(f"Comunidade {i}: {c}")

#------------------------------------------------------------------------------------------------------------------------------------------------

import networkx as nx
import matplotlib.pyplot as plt

CORES = ["#4C78A8", "#F58518", "#54A24B", "#E45756", "#B279A2"]


def girvan_newman(G):
    G = G.copy()  # não mexe no grafo original
    passos = []
    while nx.number_connected_components(G) == 1:
        betw = nx.edge_betweenness_centrality(G)
        aresta = max(betw, key=betw.get)
        passos.append((G.copy(), betw, aresta))
        G.remove_edge(*aresta)
    return passos, G, list(nx.connected_components(G))


def desenhar(ax, G, pos, titulo, betw=None, removida=None, comunidades=None):
    ax.clear()
    ax.set_title(titulo, fontsize=14, fontweight="bold")
    ax.axis("off")

    if comunidades:
        cor_de = {n: CORES[i % len(CORES)] for i, c in enumerate(comunidades) for n in c}
        cores = [cor_de[n] for n in G.nodes]
    else:
        cores = CORES[0]

    nx.draw_networkx_edges(G, pos, ax=ax, edge_color="#BBBBBB", width=2)
    if removida:  # aresta que vai ser removida, em vermelho
        nx.draw_networkx_edges(G, pos, ax=ax, edgelist=[removida], edge_color="#E45756", width=4)
    nx.draw_networkx_nodes(G, pos, ax=ax, node_color=cores, node_size=800)
    nx.draw_networkx_labels(G, pos, ax=ax, font_color="white", font_weight="bold")
    if betw:
        labels = {e: f"{v:.2f}" for e, v in betw.items()}
        nx.draw_networkx_edge_labels(G, pos, ax=ax, edge_labels=labels, font_size=9)


G = nx.Graph()
G.add_edges_from([
    ('A', 'B'), ('B', 'C'), ('C', 'D'), ('D', 'E'), ('E', 'F'),
    ('F', 'G'), ('G', 'H'), ('H', 'A'), ('B', 'H'), ('C', 'G'),
    ('D', 'F')
])

passos, G_final, comunidades = girvan_newman(G)
pos = nx.spring_layout(G, seed=42)  # layout fixo pra todos os passos

# monta os "quadros" da animação
frames = [
    dict(G=g, titulo=f"Passo {i}/{len(passos)}: remover {a}", betw=b, removida=a)
    for i, (g, b, a) in enumerate(passos, 1)
]
frames.append(dict(G=G_final, titulo="Comunidades finais", comunidades=comunidades))

# janela única com navegação por setas
fig, ax = plt.subplots(figsize=(8, 6))
fig.text(0.5, 0.02, "← → para navegar entre os passos", ha="center", color="gray")
estado = {"i": 0}


def mostrar():
    desenhar(ax, pos=pos, **frames[estado["i"]])
    fig.canvas.draw_idle()


def tecla(event):
    if event.key == "right":
        estado["i"] = min(estado["i"] + 1, len(frames) - 1)
    elif event.key == "left":
        estado["i"] = max(estado["i"] - 1, 0)
    else:
        return
    mostrar()


fig.canvas.mpl_connect("key_press_event", tecla)
mostrar()

print("Comunidades finais:")
for i, c in enumerate(comunidades, 1):
    print(f"Comunidade {i}: {c}")

plt.show()  # já bloqueia até fechar a janela, não precisa do input()