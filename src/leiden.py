#Pseudocodigo de Leiden

# função leiden(Grafo G):
#     P <- particaoSingleton(G) # Cada nó começa em sua própria comunidade
#     enquanto verdadeiro, faça
#         # 1. Fase de movimentação local rápida
#         P <- moverNosRapido(G, P)
#
#         # Se nenhum nó se juntou a outro (cada comunidade tem apenas 1 nó), encerra
#         se tamanho(P) == tamanho(V(G)), então
#             interromper
#         fim se
#
#         # 2. Fase de refinamento (diferencial do Leiden para garantir comunidades bem conectadas)
#         P_refinada <- refinarParticao(G, P)
#
#         # 3. Fase de agregação (compacta o grafo com base na partição refinada, mantendo a estrutura de P)
#         G <- aggregateGraph(G, P_refinada)
#         P <- projetarParticao(P, P_refinada)
#     fim enquanto
#     retornar P
# função final

# função moverNosRapido(Grafo G, Partição P):
#     fila <- criarFilaComTodosOsNos(V(G))
#     enquanto fila não estiver vazia, faça
#         v <- removerPrimeiro(fila)
#         # Encontra a comunidade vizinha que gera o maior ganho na qualidade (modularidade ou CPM)
#         C' <- argmax(delta_H)
#         se delta_H > 0, então
#             mover v para C'
#             # Adiciona à fila apenas os vizinhos de v que ainda não estão em C' e não estão na fila
#             adicionarVizinhosNaFila(fila, v, C')
#         fim se
#     fim enquanto
#     retornar P
# função final

# função refinarParticao(Grafo G, Partição P):
#     P_refinada <- particaoSingleton(G)
#     para cada comunidade C em P, faça
#         # Avalia os nós apenas dentro dos limites da comunidade C
#         para cada nó v em C que esteja bem conectado internamente, faça
#             se v ainda estiver sozinho em P_refinada, então
#                 # Escolhe aleatoriamente uma subcomunidade bem conectada dentro de C que aumente a qualidade
#                 C_sub <- escolherSubcomunidadeAleatoria(G, v, C, P_refinada)
#                 se C_sub existir, então
#                     mover v para C_sub em P_refinada
#                 fim se
#             fim se
#         fim para
#     fim para
#     retornar P_refinada
# função final

# função aggregateGraph(Grafo G, Partição P_refinada):
#     V <- P_refinada
#     E <- [(A,B) | (x,y) está em E(G), x está em A e A está em P_refinada, y está em B e B está em P_refinada]
#     retornar Graph(V,E)
# função final

#-------------------------------------------------------------------------------------------------------------------------------------------------

#Codigo Leiden sem a biblioteca da comunidade

# from collections import deque
# import random
# import networkx as nx


# # 1. Função de qualidade: Modularidade calculada manualmente (sem biblioteca de comunidade)
# def calcular_modularidade(G, P):
#   m = G.size(weight="weight")
#   if m == 0:
#     return 0.0
#   Q = 0.0
#   for c in P:
#     L_c = sum(
#         d.get("weight", 1) for u, v, d in G.edges(data=True) if u in c and v in c
#     )
#     d_c = sum(G.degree(u, weight="weight") for u in c)
#     Q += (L_c / m) - (d_c / (2 * m)) ** 2
#   return Q


# # 2. Calcula a variação (ganho) na modularidade ao mover o nó 'v' para a comunidade 'C'
# def ganho_modularidade(G, v, A, C, m):
#   kv = G.degree(v, weight="weight")

#   def beneficio(S):
#     S_sem_v = S - {v}
#     k_in = sum(
#         G[v][u].get("weight", 1) for u in S_sem_v if u in G[v]
#     )
#     tot = sum(G.degree(u, weight="weight") for u in S_sem_v)
#     return k_in - (tot * kv) / (2 * m)

#   return (beneficio(C) - beneficio(A)) / m


# # 3. Fase 1: Movimentação local rápida usando fila (Otimização clássica do Leiden)
# def mover_nos_rapido(G, P):
#   m = G.size(weight="weight")
#   nos = list(G.nodes)
#   random.shuffle(nos)
#   fila = deque(nos)
#   na_fila = set(nos)

#   while fila:
#     v = fila.popleft()
#     na_fila.remove(v)

#     A = next(c for c in P if v in c)
#     vizinhas = [c for c in P if c is not A and any(u in c for u in G[v])]
#     if not vizinhas:
#       continue

#     # Escolhe a comunidade vizinha que dá o maior ganho
#     melhor_C = max(vizinhas, key=lambda c: ganho_modularidade(G, v, A, c, m))
#     if ganho_modularidade(G, v, A, melhor_C, m) > 1e-12:
#       A.remove(v)
#       melhor_C.add(v)

#       # Adiciona na fila apenas os vizinhos de 'v' que não estão na nova comunidade
#       for u in G[v]:
#         if u not in melhor_C and u not in na_fila:
#           fila.append(u)
#           na_fila.add(u)

#   return [c for c in P if c]


# # 4. Fase 2: Refinamento (Garante que todas as subcomunidades sejam bem conectadas)
# def refinar_particao(G, P, gama=1.0, theta=0.01):
#   m = G.size(weight="weight")
#   P_refinada = [{v} for v in G.nodes]

#   for C in P:
#     # Avalia apenas nós bem conectados dentro da comunidade C
#     nos_C = list(C)
#     random.shuffle(nos_C)

#     for v in nos_C:
#       sub_atual = next(s for s in P_refinada if v in s)
#       # Só avalia se o nó ainda estiver isolado na partição refinada
#       if len(sub_atual) > 1:
#         continue

#       # Busca subcomunidades vizinhas que estão dentro da mesma comunidade C
#       candidatas = [
#           s
#           for s in P_refinada
#           if s is not sub_atual and s.issubset(C) and any(u in s for u in G[v])
#       ]

#       # Filtra apenas as que aumentam a modularidade
#       boas = [
#           s
#           for s in candidatas
#           if ganho_modularidade(G, v, sub_atual, s, m) > 1e-12
#       ]

#       if boas:
#         # Escolhe uma subcomunidade boa (com aleatoriedade controlada por theta)
#         pesos = [
#             pow(2.71828, ganho_modularidade(G, v, sub_atual, s, m) / theta)
#             for s in boas
#         ]
#         escolhida = random.choices(boas, weights=pesos, k=1)[0]
#         sub_atual.remove(v)
#         escolhida.add(v)

#   return [s for s in P_refinada if s]


# # 5. Fase 3: Agregação (Compacta o grafo com base na partição refinada)
# def compactar_grafo(G, P_refinada, P_original):
#   mapa = {no: i for i, s in enumerate(P_refinada) for no in s}
#   H = nx.Graph()
#   H.add_nodes_from(range(len(P_refinada)))

#   for u, v, d in G.edges(data=True):
#     a, b = mapa[u], mapa[v]
#     w = d.get("weight", 1)
#     if H.has_edge(a, b):
#       H[a][b]["weight"] += w
#     else:
#       H.add_edge(a, b, weight=w)

#   # Projeta a partição P original sobre os novos super-nós refinados
#   P_projetada = []
#   for C in P_original:
#     novos_nos = {mapa[v] for v in C}
#     P_projetada.append(novos_nos)

#   return H, P_projetada


# # 6. Algoritmo Principal de Leiden
# def leiden(G, seed=42):
#   random.seed(seed)
#   H = nx.Graph()
#   H.add_nodes_from(G.nodes)
#   H.add_weighted_edges_from(G.edges(data="weight", default=1))

#   membros = {v: {v} for v in H.nodes}
#   P = [{v} for v in H.nodes]

#   while True:
#     P = mover_nos_rapido(H, P)

#     # Se cada nó ficou sozinho, o algoritmo convergiu
#     if len(P) == H.number_of_nodes():
#       break

#     # Refina a partição antes de compactar
#     P_refinada = refinar_particao(H, P)

#     # Atualiza quem são os nós originais dentro de cada grupo refinado
#     membros = {
#         i: set().union(*(membros[v] for v in s))
#         for i, s in enumerate(P_refinada)
#     }

#     # Compacta o grafo mantendo a estrutura da partição P
#     H, P = compactar_grafo(H, P_refinada, P)

#   return list(membros.values())


# # --- EXECUÇÃO ---
# G = nx.Graph([
#     ("A", "B"), ("B", "C"), ("C", "D"), ("D", "E"), ("E", "F"),
#     ("F", "G"), ("G", "H"), ("H", "A"), ("B", "H"), ("C", "G"), ("D", "F"),
# ])

# comunidades = leiden(G)

# print("Comunidades finais (Leiden):")
# for i, c in enumerate(comunidades, 1):
#   print(f"Comunidade {i}: {sorted(list(c))}")

# H_peso = nx.Graph()
# H_peso.add_weighted_edges_from(G.edges(data="weight", default=1))
# print("Modularidade:", round(calcular_modularidade(H_peso, comunidades), 4))

#-------------------------------------------------------------------------------------------------------------------------------------------------

#Leiden Visual com a biblioteca da comunidade

import matplotlib.pyplot as plt
import networkx as nx
from networkx.algorithms.community import leiden_communities, modularity

CORES = ["#4C78A8", "#F58518", "#54A24B", "#E45756", "#B279A2", "#72B7B2"]

# 1. Criação do grafo
G = nx.Graph([
    ("A", "B"), ("B", "C"), ("C", "D"), ("D", "E"), ("E", "F"),
    ("F", "G"), ("G", "H"), ("H", "A"), ("B", "H"), ("C", "G"), ("D", "F"),
])

# 2. Executa o Leiden usando a função oficial da biblioteca de comunidades
# metric="modularity" faz ele otimizar a modularidade (o padrão da função é "cpm")
comunidades = leiden_communities(G, metric="modularity", seed=42)
q_final = modularity(G, comunidades)

# 3. Prepara os quadros (Antes e Depois) com o mesmo layout
pos = nx.spring_layout(G, seed=42)
frames = [
    dict(titulo="Grafo Inicial (Sem divisão)", grupos=None),
    dict(titulo=f"Leiden Final (Modularidade Q = {q_final:.3f})", grupos=comunidades),
]

# 4. Configuração da janela interativa com setas (← →)
fig, ax = plt.subplots(figsize=(8, 6))
fig.text(0.5, 0.02, "← → para alternar entre Antes e Depois", ha="center", color="gray")
estado = {"i": 0}


def desenhar():
    ax.clear()
    frame = frames[estado["i"]]
    ax.set_title(frame["titulo"], fontsize=13, fontweight="bold")
    ax.axis("off")

    if frame["grupos"]:
        cor_de = {n: CORES[i % len(CORES)] for i, c in enumerate(frame["grupos"]) for n in c}
        cores_nos = [cor_de[n] for n in G.nodes]
    else:
        cores_nos = CORES[0]

    nx.draw_networkx_edges(G, pos, ax=ax, edge_color="#BBBBBB", width=2)
    nx.draw_networkx_nodes(
        G, pos, ax=ax, node_color=cores_nos, node_size=800,
        edgecolors="white", linewidths=2
    )
    nx.draw_networkx_labels(G, pos, ax=ax, font_color="white", font_weight="bold")
    fig.canvas.draw_idle()


def tecla(event):
    if event.key == "right":
        estado["i"] = min(estado["i"] + 1, len(frames) - 1)
    elif event.key == "left":
        estado["i"] = max(estado["i"] - 1, 0)
    else:
        return
    desenhar()


fig.canvas.mpl_connect("key_press_event", tecla)
desenhar()

print("Comunidades finais (NetworkX Leiden):")
for i, c in enumerate(comunidades, 1):
    print(f"Comunidade {i}: {sorted(list(c))}")
print("Modularidade:", round(q_final, 4))

plt.show()