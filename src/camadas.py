"""
Frente 2 — modelagem formal das tres camadas e limiares calibrados.

Este modulo e a versao 2 da construcao dos grafos e a fonte unica das
camadas usadas pelo projeto (frente2.py e frente4.py importam daqui).
Reaproveita as funcoes de `grafos.py` onde elas servem e redefine so o que a
calibragem mudou.

Cinco limiares, todos justificados em docs/frente2-thresholds.md:

  COBERTURA_MIN   fracao minima do periodo com cotacao real
  ZEROS_MAX       fracao maxima de pregoes com retorno exatamente zero
  K_BACKBONE_A    arestas mais fortes que cada fundo guarda na Camada A
  RHO_MIN_B       correlacao minima na Camada B (percentil 95 dos pares)
  K_KNN_C         vizinhos por fundo na Camada C

O que mudou em relacao a versao do frente4.py:

  Camada A  o atributo `tipo_fundo` saiu. Ele era funcao deterministica do
            segmento (todo segmento mapeava para um unico tipo), entao
            duplicava o peso do setor e ligava qualquer par de fundos de
            tijolo: 200 das 433 arestas existiam so por causa dele.
            Inquilino so conta para fundos de tijolo (em Papel, FoF e
            Fiagro o campo descreve o lastro, nao locatarios).
            O peso passou da soma do idf para o Jaccard ponderado pelo idf
            (fracao do perfil compartilhada, entre 0 e 1): a soma favorecia
            quem tem mais atributos e empatava quase tudo.
            O corte por peso saiu, porque apaga primeiro os segmentos
            maiores, que sao justamente os de maior risco de concentracao.
            No lugar entrou o backbone kNN, em que cada fundo guarda as suas
            k arestas mais fortes (e as que empatam com a k-esima) --
            invariante ao tamanho do grupo e a mesma regra da Camada C.

  Camada B  o grafo analisado passa a ser a uniao da MST com o grafo por
            limiar, em vez do grafo por limiar sozinho. Com ρ ≥ 0,30 havia
            18 fundos de grau zero e 19 componentes, o que tira do ar
            intermediacao, caminho medio, diametro e o teste de robustez.
            A MST garante conectividade; o limiar traz as ligacoes fortes.
            Cada aresta carrega `origem`: "limiar", "mst" ou "ambos".

  Camada C  inalterada na forma, so recalibrada (k de 4 para 3).

Uso (a partir da raiz do repositorio):
    import camadas
    atrib, cont, ret, removidos = camadas.carregar_dados()
"""
import collections
import itertools
import os

import networkx as nx
import numpy as np
import pandas as pd

import grafos as gr

# ------------------------------------------------------------- limiares
COBERTURA_MIN = 0.90
ZEROS_MAX = 0.30
K_BACKBONE_A = 3
RHO_MIN_B = 0.32
K_KNN_C = 3

PASTA_DADOS = os.path.join("docs", "1. Dados Reais", "Tabelas - Dados")
ARQ_PRECOS = os.path.join(PASTA_DADOS, "precos_diarios_FIIs_1_excel.csv")
ARQ_ATRIB = os.path.join(PASTA_DADOS, "atributos_fiis_v2.xlsx")

# Atributos categoricos da Camada A. `tipo_fundo` saiu (ver cabecalho);
# `indexador` e `tipo_imovel` nunca foram coletados.
ATRIBUTOS_A = ["segmento", "gestora"]

# Inquilino so existe em fundo de tijolo. Em Papel, FoF e Fiagro a planilha
# traz uma descricao do lastro ("cotas de outros FIIs...", "CRAs de
# produtores rurais..."), que o split por virgula quebraria em itens falsos.
SEGMENTOS_COM_INQUILINO = {"Logística", "Shoppings", "Lajes", "Renda Urbana",
                           "Híbrido"}

# A mesma lista de inquilinos aparece copiada em varios fundos do mesmo
# segmento (ex.: 8 shoppings): e generica, nao especifica do fundo. Listas
# repetidas em mais de REPETICAO_MAX fundos sao ignoradas.
REPETICAO_MAX = 4
CORRECOES_INQ = {"petrobas": "petrobras", "carregour": "carrefour"}

PALETA = {"Logística": "#2563eb", "Shoppings": "#db2777", "Lajes": "#059669",
          "Papel": "#d97706", "Renda Urbana": "#7c3aed", "FoF": "#0891b2",
          "Híbrido": "#64748b", "Fiagro": "#65a30d", "Desenvolvimento": "#92400e"}


# ----------------------------------------------------------------- dados
def carregar_precos():
    """Separador ';', decimal ',' e data DD/MM/AAAA."""
    px = pd.read_csv(ARQ_PRECOS, sep=";", decimal=",", index_col=0)
    px.index = pd.to_datetime(px.index, dayfirst=True)
    px.columns = [c.replace(".SA", "") for c in px.columns]
    return px.sort_index()


def limpar_precos(px, cobertura_min=COBERTURA_MIN, zeros_max=ZEROS_MAX):
    """
    O CSV nao tem nenhum NaN, mas isso e artificial: a coleta aplicou
    ffill().bfill(), entao fundo sem historico no inicio da janela recebeu
    o primeiro preco real copiado para tras (GARE11 fica com o mesmo preco
    por 292 pregoes). Preco parado vira retorno zero, e dois fundos parados
    na mesma janela aparecem como perfeitamente concordantes.

    1) apaga o trecho inicial copiado;
    2) remove fundo com cotacao real em menos de `cobertura_min` do periodo
       (nao era negociado no inicio da janela);
    3) remove fundo com mais de `zeros_max` de pregoes parados
       (iliquidez ou falha da fonte).

    Devolve (precos limpos, tabela dos removidos).
    """
    px = px.copy()
    for c in px.columns:
        s = px[c]
        mudou = (s != s.iloc[0]).values
        inicio = mudou.argmax() if mudou.any() else len(s)
        # o pregao anterior a 1a mudanca e a 1a cotacao real; antes dele e copia
        if inicio > 1:
            px.iloc[:inicio - 1, px.columns.get_loc(c)] = np.nan

    cobertura = px.notna().mean()
    ret = np.log(px).diff()
    zeros = (ret == 0).sum() / ret.notna().sum()

    saidas = []
    for t in px.columns:
        motivos = []
        if cobertura[t] < cobertura_min:
            motivos.append(f"cotação real em só {cobertura[t]:.0%} do período")
        if zeros[t] > zeros_max:
            motivos.append(f"{zeros[t]:.0%} dos pregões com retorno zero")
        if motivos:
            saidas.append({"ticker": t, "cobertura": round(cobertura[t], 3),
                           "frac_retorno_zero": round(zeros[t], 3),
                           "motivo": "; ".join(motivos)})
    removidos = pd.DataFrame(saidas, columns=["ticker", "cobertura",
                                              "frac_retorno_zero", "motivo"])
    return px.drop(columns=removidos["ticker"]), removidos


def retornos_log(px):
    """Retorno log diario, so nas datas em que todos os fundos tem cotacao."""
    return np.log(px).diff().dropna(how="any")


def _separa_inquilinos(texto):
    """'A, B e C.' -> ['a', 'b', 'c']"""
    texto = texto.strip().rstrip(".").lower().replace(" e ", ",")
    nomes = [n.strip().rstrip(".") for n in texto.split(",")]
    return [CORRECOES_INQ.get(n, n) for n in nomes if n]


def carregar_atributos(tickers):
    """Le a base v2 e devolve (categoricos, continuos)."""
    A = pd.read_excel(ARQ_ATRIB, sheet_name="Planilha A").set_index("ticker").loc[tickers]
    C = pd.read_excel(ARQ_ATRIB, sheet_name="Planilha C").set_index("ticker").loc[tickers]

    atrib = pd.DataFrame(index=A.index)
    atrib["segmento"] = A["segmento"]
    atrib["segmento_planilha"] = A["segmento_planilha"]
    atrib["gestora"] = A["gestora"].str.strip()

    texto = A["inquilinos"].fillna("").str.strip().str.lower()
    repeticoes = texto.map(texto.value_counts())
    tem_inquilino = atrib["segmento"].isin(SEGMENTOS_COM_INQUILINO)
    atrib["inquilinos"] = [
        _separa_inquilinos(txt)
        if tem_inquilino[t] and txt and repeticoes[t] <= REPETICAO_MAX else []
        for t, txt in texto.items()]

    cont = pd.DataFrame(index=C.index)
    cont["dividend_yield"] = C["dy_12m"].replace(0, np.nan)   # DY 0 = faltando
    cont["pvp"] = C["p_vp"]
    # PL e liquidez vao de milhoes a bilhoes: log10 antes do z-score
    cont["patrimonio_liquido"] = np.log10(C["patrimonio_liquido"])
    cont["liquidez"] = np.log10(C["liquidez_diaria"])
    # num_ativos = 0 em fundo de papel e FoF: e "nao se aplica", nao zero
    cont["num_ativos"] = C["num_ativos"].replace(0, np.nan)
    return atrib, cont.astype(float)


def carregar_dados(verbose=True):
    """Devolve (atrib, cont, retornos, removidos)."""
    px, removidos = limpar_precos(carregar_precos())
    if verbose:
        print(f"[dados] {px.shape[1] + len(removidos)} FIIs no CSV, "
              f"{len(removidos)} removidos na limpeza")
    ret = retornos_log(px)
    atrib, cont = carregar_atributos(list(ret.columns))
    return atrib, cont, ret, removidos


# -------------------------------------------------------------- camada A
def itens_de(atrib):
    """Cada fundo vira um conjunto de itens 'atributo=valor'."""
    I = {}
    for t in atrib.index:
        s = set()
        for col in ATRIBUTOS_A:
            v = str(atrib.loc[t, col]).strip()
            if v and v.lower() != "n/a":
                s.add(f"{col}={v}")
        for q in atrib.loc[t, "inquilinos"]:
            s.add(f"inquilino={q}")
        I[t] = s
    return I


def grafo_estrutural(atrib, peso="jaccard"):
    """
    Projecao bipartida FII x caracteristica, valorada por raridade,
    com idf(item) = ln(N / nº de fundos que tem o item).

    peso="jaccard" (padrao): Jaccard ponderado pelo idf,
        w = soma idf(itens em comum) / soma idf(itens da uniao), entre 0 e 1.
        E a fracao do perfil dos dois fundos que e compartilhada.
    peso="soma": soma do idf dos itens em comum (versao anterior, mantida
        so para comparacao). Favorecia quem tem mais atributos e gerava
        muitos empates, porque so dependia de QUAIS itens coincidem.
    """
    N = len(atrib)
    I = itens_de(atrib)
    freq = collections.Counter(it for s in I.values() for it in s)
    idf = {it: np.log(N / c) for it, c in freq.items()}

    G = nx.Graph()
    G.add_nodes_from(atrib.index)
    for a, b in itertools.combinations(atrib.index, 2):
        comuns = I[a] & I[b]
        if not comuns:
            continue
        # soma em ordem fixa: a ordem de um set muda a cada execução e, em
        # ponto flutuante, mudaria o último dígito do peso (e desempates)
        w = sum(idf[it] for it in sorted(comuns))
        if peso == "jaccard":
            w /= sum(idf[it] for it in sorted(I[a] | I[b]))
        if w > 0:
            G.add_edge(a, b, weight=w, itens=len(comuns))
    return G


def backbone_knn(G, k):
    """
    Cada vertice guarda as suas k arestas de maior peso; o grafo final e a
    uniao dessas escolhas. Um vertice pode terminar com mais de k arestas,
    se outros tambem o escolherem, mas nunca com menos -- nenhum fundo fica
    isolado, e a selecao nao depende do tamanho do grupo a que ele pertence.
    """
    H = nx.Graph()
    H.add_nodes_from(G.nodes(data=True))
    for n in G:
        pesos = sorted((d["weight"] for d in G[n].values()), reverse=True)
        if not pesos:
            continue
        # empates com a k-esima aresta tambem ficam: sem isso, entre fundos
        # com o mesmo peso (ex.: so o segmento em comum) quem decidiria
        # seria a ordem das linhas da planilha
        corte = pesos[min(k, len(pesos)) - 1]
        for v, d in G[n].items():
            if d["weight"] >= corte - 1e-9:
                H.add_edge(n, v, **d)
    return H


def camada_a(atrib, k=K_BACKBONE_A):
    """Devolve (grafo completo, backbone kNN)."""
    G = grafo_estrutural(atrib)
    return G, backbone_knn(G, k)


# -------------------------------------------------------------- camada B
def camada_b(corr, rho_min=RHO_MIN_B):
    """
    Uniao da MST de Mantegna com o grafo por limiar.

    A MST e construida sobre a distancia d = sqrt(2*(1 - rho)) e garante que
    os N fundos fiquem em um unico componente. O limiar acrescenta os pares
    de correlacao alta que a arvore nao contem.

    Cada aresta recebe `origem`: "limiar", "mst" ou "ambos".
    Devolve (uniao, mst, grafo por limiar).
    """
    MST = gr.grafo_mst(corr)
    GL = gr.grafo_limiar(corr, rho_min=rho_min)

    U = nx.Graph()
    U.add_nodes_from(corr.index)
    for a, b, d in MST.edges(data=True):
        U.add_edge(a, b, **d, origem="mst")
    for a, b, d in GL.edges(data=True):
        if U.has_edge(a, b):
            U[a][b]["origem"] = "ambos"
        else:
            U.add_edge(a, b, **d, origem="limiar")
    # peso comparavel entre as duas origens: a correlacao do par
    for a, b in U.edges():
        U[a][b]["rho"] = float(corr.loc[a, b])
    return U, MST, GL


def camada_c(cont, k=K_KNN_C):
    """Grafo kNN sobre o perfil fundamentalista (delega para grafos.py)."""
    return gr.grafo_fundamentalista(cont, k=k)
