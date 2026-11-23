# PSEUDOCÓDIGO DE ESTUDO — Louvain. NÃO é executado pelo projeto.
# A implementação que roda está em src/comunidades.py (e, para a Tabela 1 do
# relatório, em src/grafos.py via python-louvain). Ver src/README.md.
#
#Pseudocodigo

# função moverNós(Grafo G, Partição P):
#     fazer 
#         modularidade_antiga <- modularidade_atual_da_partição
#         para v em V(G), faça
#             # Encontre a comunidade que causa o maior aumento na modularidade quando v é movido para ela.
#             C' <- argmax(delta_Q) # delta_Q é a mudança na modularidade
#             Se delta_Q > 0, então
#                 mover v para C'
#             fim se 
#         fim para
#     atualizar modularidade_atual_da_partição
#     enquanto a modularidade_atual_da_partição for maior que a modularidade_antiga
#     retornar P 
# função final

# função aggregateGraph(Grafo G, Partição P):
#     V <- P 
#     E <- [(A,B) | (x,y) está em E(G), x está em A e A está em P, y está em B e B está em P]
#     retornar Graph(V,E)
# função final

# função louvain(Grafo G, Partição P):
#     fazer
#         P <- moverNós(G, P)
#         feito <- comprimento(P) == comprimento(V(G)) # cada comunidade é um único nó, apesar de executar moveNodes
#         Caso contrário, faça o seguinte:
#             G <- aggregateGraph(G, P)
#             P <- singletonPartition(G)
#         fim se
#     enquanto não estiver concluído
# função final

# função singletonPartition(Graph G):
#     retornar [{v} | v está em V(G)] # cada nó é colocado em sua própria comunidade
# função final

#------------------------------------------------------------------------------------------------------------------------------------------------


#Codigo louvain sem as bibliotecas da comunidade
# import networkx as nx


# # 1. Começa colocando cada pessoa/nó sozinho em seu próprio grupo
# def gruposIniciais(grafo):
#   return [{no} for no in grafo.nodes]


# # 2. Mede o quão boa está a divisão atual (nota de -0.5 até 1.0)
# def modularidade(grafo, grupos):
#   pesoTotal = grafo.size(weight="weight")
#   deltaQ = 0

#   for grupo in grupos:

#     # Soma o peso das conexões que ficam DENTRO do mesmo grupo
#     ligacoesInt = sum(
#         peso
#         for u, v, peso in grafo.edges(data="weight")
#         if u in grupo and v in grupo
#     )
    
#     # Soma o total de conexões de todos os integrantes do grupo
#     ligacoesTotais = sum(
#         grafo.degree(no, weight="weight") for no in grupo
#     )

#     deltaQ += (ligacoesInt / pesoTotal) - (
#         ligacoesTotais / (2 * pesoTotal)
#     ) ** 2

#   return deltaQ


# # 3. Calcula se vale a pena tirar um nó do 'grupo_atual' e colocar no 'grupo_destino'
# def moverNo(grafo, no, atual, destino, pesoTotal):
  
#   ligacoesNo = grafo.degree(no, weight="weight")

#   # Função auxiliar que calcula o benefício de um nó entrar em um grupo
#   def beneficio(grupo):
#     grupoSemNo = grupo - {no}
#     ligacoesGrupo = sum(
#         grafo[no][vizinho]["weight"]
#         for vizinho in grupoSemNo
#         if vizinho in grafo[no]
#     )
#     ligacoesTotalGrupo = sum(
#         grafo.degree(u, weight="weight") for u in grupoSemNo
#     )
#     return ligacoesGrupo - (
#         ligacoesTotalGrupo * ligacoesNo / (2 * pesoTotal)
#     )

#   return (beneficio(destino) - beneficio(atual)) / pesoTotal


# # 4. Fase 1 do Louvain: Move cada nó para o grupo vizinho que der mais lucro na modularidade
# def otimizarGrupo(grafo, grupos):
#   pesoTotal = grafo.size(weight="weight")

#   while True:
#     notaAnt = modularidade(grafo, grupos)

#     for no in grafo.nodes:
#       # Descobre em qual grupo o nó está agora
#       atual = next(g for g in grupos if no in g)

#       # Olha apenas para os grupos onde ele tem amigos/vizinhos conectados
#       vizinho = [
#           g
#           for g in grupos
#           if g is not atual and any(vizinho in g for vizinho in grafo[no])
#       ]
#       if not vizinho:
#         continue

#       # Escolhe o grupo vizinho que dá o maior aumento de pontuação
#       melhorGrupo = max(
#           vizinho,
#           key=lambda g: moverNo(
#               grafo, no, atual, g, pesoTotal
#           ),
#       )

#       # Só muda de grupo se o ganho for positivo
#       if (
#           moverNo(
#               grafo, no, atual, melhorGrupo, pesoTotal
#           )
#           > 1e-12
#       ):
#         atual.remove(no)
#         melhorGrupo.add(no)

#     # Remove grupos que ficaram vazios depois das mudanças
#     grupos = [g for g in grupos if g]

#     # Se a nota geral parou de subir, encerra essa fase
#     if modularidade(grafo, grupos) <= notaAnt + 1e-12:
#       return grupos


# # 5. Fase 2 do Louvain: Encolhe o grafo, transformando cada grupo inteiro em um único "Super Nó"
# def superNo(grafo, grupos):
#   mapa_no_para_grupo = {no: i for i, grupo in enumerate(grupos) for no in grupo}

#   novoGrafo = nx.Graph()
#   novoGrafo.add_nodes_from(range(len(grupos)))

#   for u, v, peso in grafo.edges(data="weight"):
#     grupo_u = mapa_no_para_grupo[u]
#     grupo_v = mapa_no_para_grupo[v]

#     # Soma os pesos das conexões entre os grupos (ou dentro do mesmo grupo)
#     if novoGrafo.has_edge(grupo_u, grupo_v):
#       novoGrafo[grupo_u][grupo_v]["weight"] += peso
#     else:
#       novoGrafo.add_edge(grupo_u, grupo_v, weight=peso)

#   return novoGrafo


# # 6. Algoritmo Principal: Repete a Fase 1 e a Fase 2 até ninguém mais querer mudar de grupo
# def louvain(grafo_original):
#   # Cria uma cópia garantindo que todas as conexões tenham peso 1
#   grafo_atual = nx.Graph()
#   grafo_atual.add_nodes_from(grafo_original.nodes)
#   grafo_atual.add_weighted_edges_from(
#       grafo_original.edges(data="weight", default=1)
#   )

#   # Guarda quem são os nós originais dentro de cada "Super Nó"
#   historico_membros = {no: {no} for no in grafo_atual.nodes}
#   grupos = gruposIniciais(grafo_atual)

#   while True:
#     grupos = otimizarGrupo(grafo_atual, grupos)

#     # Se ninguém se juntou a ninguém (cada nó continua sozinho), o algoritmo acabou
#     ninguem_mudou = len(grupos) == grafo_atual.number_of_nodes()
#     if ninguem_mudou:
#       break

#     # Atualiza a lista de quem está dentro de cada novo grupo
#     historico_membros = {
#         i: set().union(*(historico_membros[no] for no in grupo))
#         for i, grupo in enumerate(grupos)
#     }

#     # Compacta o grafo e recomeça o processo no nível superior
#     grafo_atual = superNo(grafo_atual, grupos)
#     grupos = gruposIniciais(grafo_atual)

#   return list(historico_membros.values())


# # --- TESTANDO O CÓDIGO ---
# G = nx.Graph()
# G.add_edges_from([
#     ("A", "B"),
#     ("B", "C"),
#     ("C", "D"),
#     ("D", "E"),
#     ("E", "F"),
#     ("F", "G"),
#     ("G", "H"),
#     ("H", "A"),
#     ("B", "H"),
#     ("C", "G"),
#     ("D", "F"),
# ])

# comunidades = louvain(G)

# print("Comunidades finais:")
# for i, comunidade in enumerate(comunidades, 1):
#   print(f"Comunidade {i}: {sorted(list(comunidade))}")

# grafo_com_pesos = nx.Graph()
# grafo_com_pesos.add_weighted_edges_from(G.edges(data="weight", default=1))
# print(
#     "Modularidade:",
#     round(modularidade(grafo_com_pesos, comunidades), 4))

#-------------------------------------------------------------------------------------------------------------------------------------------------

#codigo louvain com as bibliotecas da comunidade

# import networkx as nx
# from networkx.algorithms.community import modularity


# def mover_nos(G, P):
#   while True:
#     Q_antiga = modularity(G, P)
#     for no in G.nodes:
#       atual = next(c for c in P if no in c)
#       vizinhos = [
#           c for c in P if c is not atual and any(v in c for v in G[no])
#       ]
#       if not vizinhos:
#         continue

#       # Testa mover o nó para cada grupo vizinho e pega o de maior modularidade
#       melhor = max(
#           vizinhos,
#           key=lambda c: modularity(
#               G,
#               [
#                   x - {no} if x is atual else (x | {no} if x is c else x)
#                   for x in P
#               ],
#           ),
#       )

#       nova_P = [
#           x - {no} if x is atual else (x | {no} if x is melhor else x)
#           for x in P
#       ]
#       if modularity(G, nova_P) > modularity(G, P) + 1e-12:
#         atual.remove(no)
#         melhor.add(no)

#     P = [c for c in P if c]
#     if modularity(G, P) <= Q_antiga + 1e-12:
#       return P


# def compactar_grafo(G, P):
#   mapa = {no: i for i, c in enumerate(P) for no in c}
#   H = nx.Graph()
#   H.add_nodes_from(range(len(P)))
#   for u, v, d in G.edges(data=True):
#     a, b, w = mapa[u], mapa[v], d.get("weight", 1)
#     H.add_edge(a, b, weight=H[a][b]["weight"] + w if H.has_edge(a, b) else w)
#   return H


# def louvain(G):
#   H = G.copy()
#   membros = {v: {v} for v in H.nodes}
#   P = [{v} for v in H.nodes]

#   while True:
#     P = mover_nos(H, P)
#     if len(P) == H.number_of_nodes():
#       break

#     membros = {
#         i: set().union(*(membros[v] for v in c)) for i, c in enumerate(P)
#     }
#     H = compactar_grafo(H, P)
#     P = [{v} for v in H.nodes]

#   return list(membros.values())


# # --- EXECUÇÃO ---
# G = nx.Graph([
#     ("A", "B"),
#     ("B", "C"),
#     ("C", "D"),
#     ("D", "E"),
#     ("E", "F"),
#     ("F", "G"),
#     ("G", "H"),
#     ("H", "A"),
#     ("B", "H"),
#     ("C", "G"),
#     ("D", "F"),
# ])

# comunidades = louvain(G)
# print("Comunidades:", [sorted(list(c)) for c in comunidades])
# print("Modularidade:", round(modularity(G, comunidades), 4))

#------------------------------------------------------------------------------------------------------------------------------------------------

#Codigo Louvain visual com as bibliotecas da comunidade

import matplotlib.pyplot as plt
import networkx as nx
from networkx.algorithms.community import modularity

CORES = ["#4C78A8", "#F58518", "#54A24B", "#E45756", "#B279A2", "#72B7B2", "#FF9DA6", "#9D755D"]


def expandir(P, membros):
    """Traduz os grupos atuais (mesmo após compactar) de volta para os nós originais."""
    return [set().union(*(membros[v] for v in c)) for c in P]


def mover_nos(H, P, G_orig, membros, nivel, frames):
    while True:
        Q_antiga = modularity(H, P)
        for no in H.nodes:
            atual = next(c for c in P if no in c)
            vizinhos = [c for c in P if c is not atual and any(v in c for v in H[no])]
            if not vizinhos:
                continue

            melhor = max(
                vizinhos,
                key=lambda c: modularity(
                    H, [x - {no} if x is atual else (x | {no} if x is c else x) for x in P]
                ),
            )
            nova_P = [x - {no} if x is atual else (x | {no} if x is melhor else x) for x in P]

            if modularity(H, nova_P) > modularity(H, P) + 1e-12:
                atual.remove(no)
                melhor.add(no)

                # Salva o quadro toda vez que um nó muda de comunidade
                com_orig = expandir([c for c in P if c], membros)
                q_atual = modularity(G_orig, com_orig)
                frames.append(dict(
                    titulo=f"Nível {nivel}: mover {sorted(list(membros[no]))} (Q = {q_atual:.3f})",
                    comunidades=com_orig,
                    destaque=membros[no],
                ))

        P = [c for c in P if c]
        if modularity(H, P) <= Q_antiga + 1e-12:
            return P


def compactar_grafo(G, P):
    mapa = {no: i for i, c in enumerate(P) for no in c}
    H = nx.Graph()
    H.add_nodes_from(range(len(P)))
    for u, v, d in G.edges(data=True):
        a, b, w = mapa[u], mapa[v], d.get("weight", 1)
        H.add_edge(a, b, weight=H[a][b]["weight"] + w if H.has_edge(a, b) else w)
    return H


def louvain_visual(G):
    H = G.copy()
    membros = {v: {v} for v in H.nodes}
    P = [{v} for v in H.nodes]
    nivel = 1

    # Quadro inicial: cada nó com sua própria cor
    frames = [dict(
        titulo=f"Início: cada nó isolado (Q = {modularity(G, P):.3f})",
        comunidades=P,
        destaque=None,
    )]

    while True:
        P = mover_nos(H, P, G, membros, nivel, frames)
        if len(P) == H.number_of_nodes():
            break

        membros = {i: set().union(*(membros[v] for v in c)) for i, c in enumerate(P)}
        H = compactar_grafo(H, P)
        P = [{v} for v in H.nodes]
        nivel += 1

        com_orig = list(membros.values())
        frames.append(dict(
            titulo=f"Compactação -> Início do Nível {nivel} (Q = {modularity(G, com_orig):.3f})",
            comunidades=com_orig,
            destaque=None,
        ))

    comunidades_finais = list(membros.values())
    frames.append(dict(
        titulo=f"Comunidades finais (Q = {modularity(G, comunidades_finais):.3f})",
        comunidades=comunidades_finais,
        destaque=None,
    ))
    return frames, comunidades_finais


def desenhar(ax, G, pos, titulo, comunidades, destaque=None):
    ax.clear()
    ax.set_title(titulo, fontsize=13, fontweight="bold")
    ax.axis("off")

    cor_de = {n: CORES[i % len(CORES)] for i, c in enumerate(comunidades) for n in c}
    cores = [cor_de[n] for n in G.nodes]

    # Destaca com borda preta grossa os nós que acabaram de ser movidos
    bordas = ["#111111" if (destaque and n in destaque) else "white" for n in G.nodes]
    larguras = [3.5 if (destaque and n in destaque) else 1.5 for n in G.nodes]

    nx.draw_networkx_edges(G, pos, ax=ax, edge_color="#BBBBBB", width=2)
    nx.draw_networkx_nodes(
        G, pos, ax=ax, node_color=cores, node_size=800,
        edgecolors=bordas, linewidths=larguras
    )
    nx.draw_networkx_labels(G, pos, ax=ax, font_color="white", font_weight="bold")


# --- EXECUÇÃO ---
G = nx.Graph([
    ("A", "B"), ("B", "C"), ("C", "D"), ("D", "E"), ("E", "F"),
    ("F", "G"), ("G", "H"), ("H", "A"), ("B", "H"), ("C", "G"), ("D", "F"),
])

frames, comunidades = louvain_visual(G)
pos = nx.spring_layout(G, seed=42)

fig, ax = plt.subplots(figsize=(8, 6))
fig.text(0.5, 0.02, "← → para navegar entre os passos", ha="center", color="gray")
estado = {"i": 0}


def mostrar():
    desenhar(ax, G, pos, **frames[estado["i"]])
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
    print(f"Comunidade {i}: {sorted(list(c))}")
print("Modularidade:", round(modularity(G, comunidades), 4))

plt.show()