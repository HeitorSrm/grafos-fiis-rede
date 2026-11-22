"""
Análise da base ampliada (156 FIIs) e comparação com a base de 46.

Pergunta: as conclusões das perguntas (b) e (c) se mantêm num universo real
3,4 vezes maior? Usa as mesmas funções da Frente 4 e do teste sintético.

Diferenças em relação à base de 46, todas pela regra da Frente 2:
  - limiar da Camada B = percentil 95 da correlação DESTA amostra;
  - k da Camada C = menor k com grafo conexo e grau médio acima de 3.
A Camada A não é construída: gestora e inquilinos só existem para os 46
fundos revisados, e para os outros 110 ela se reduziria ao segmento.

Uso (a partir da raiz do repositório, depois de coleta_ampliada.py):
    python src/analise_ampliada.py
Saída: out/ampliada/
"""
import os

import networkx as nx
import numpy as np
import pandas as pd
from sklearn.metrics import adjusted_rand_score as ari

import camadas as cm
import frente4 as f4
import grafos as gr
import teste_sintetico as ts

PASTA = os.path.join("out", "ampliada")
ARQ_PRECOS = os.path.join("dados", "ampliado", "precos.csv")
ARQ_UNIVERSO = os.path.join("dados", "ampliado", "universo.csv")
MIN_FUNDOS_SEGMENTO = 3      # segmentos menores ficam fora das carteiras
N_BOOT = 100                 # reamostragens dos pregões para as pontes
N_ACASO = 2000               # carteiras sorteadas
SEMENTE = 42
PONTES_BASE = ["RECR11", "VRTA11", "SNCI11"]   # pontes mais recorrentes na base de 46


# ---------------------------------------------------------------- dados

def carregar_ampliada():
    """Mesma limpeza do projeto; atributos e indicadores vêm do universo."""
    px = pd.read_csv(ARQ_PRECOS, sep=";", decimal=",", index_col=0)
    px.index = pd.to_datetime(px.index, dayfirst=True)
    px, removidos = cm.limpar_precos(px.dropna(axis=1, how="all"))
    ret = cm.retornos_log(px)
    u = pd.read_csv(ARQ_UNIVERSO).set_index("ticker").loc[ret.columns]
    atrib = pd.DataFrame({"segmento": u["segmento"], "origem_segmento": u["origem_segmento"]})
    cont = pd.DataFrame({
        "dividend_yield": u["dy"].replace(0, np.nan),               # DY 0 = faltando
        "pvp": u["pvp"],
        "patrimonio_liquido": np.log10(u["patrimonio_liquido"]),
        "liquidez": np.log10(u["liquidez"]),
        "num_ativos": u["num_imoveis"].replace(0, np.nan),         # 0 = não se aplica
    }).astype(float)
    return atrib, cont, ret, removidos


def carregar_base46():
    atrib, cont, ret, _ = cm.carregar_dados(verbose=False)
    return atrib, cont, ret


# ---------------------------------------------------------------- camadas

def k_camada_c(cont):
    """Regra da Frente 2: menor k com grafo conexo e grau médio acima de 3."""
    for k in range(2, 21):
        G = cm.camada_c(cont, k=k)
        if nx.is_connected(G) and 2 * G.number_of_edges() / len(G) > 3:
            return k, G
    return k, G


def camada_b_p95(ret):
    """Limiar = p95 da correlação arredondado a 2 casas, como na Frente 2
    (na base de 46: 0,315 -> 0,32, o valor oficial)."""
    corr = ret.corr()
    p95 = round(float(np.quantile(corr.values[np.triu_indices(len(corr), 1)], 0.95)), 2)
    GB, MST, _ = cm.camada_b(corr, rho_min=p95)
    return corr, p95, GB, MST


# ---------------------------------------------------------------- análises

def resumo_base(nome, atrib, cont, ret):
    """Uma coluna da tabela de comparação entre as bases."""
    seg = atrib["segmento"]
    corr, p95, GB, MST = camada_b_p95(ret)
    k, GC = k_camada_c(cont)
    iu = np.triu_indices(len(corr), 1)
    part, q = gr.comunidades(GB)
    btw = pd.Series(nx.betweenness_centrality(GB)).sort_values(ascending=False)
    top10 = list(btw.index[:10])
    linha = {
        "fundos": len(seg), "retornos": len(ret),
        "inicio_janela": str(ret.index[0].date()),
        "rho_mediana": np.median(corr.values[iu]), "rho_p95": p95,
        "arestas_B": GB.number_of_edges(), "densidade_B": nx.density(GB),
        "modularidade_B": q, "comunidades_B": len(set(part.values())),
        "ari_B_segmento": ari(seg.loc[list(part)], [part[n] for n in part]),
        "k_C": k, "arestas_C": GC.number_of_edges(),
        "top10_pontes": " ".join(top10),
        "papel_no_top10": int((seg[top10] == "Papel").sum()),
    }
    for t in PONTES_BASE:
        linha[f"posicao_{t}"] = int(list(btw.index).index(t)) + 1 if t in btw else np.nan
    return pd.Series(linha, name=nome), corr, GB, MST, GC


def estabilidade_pontes(ret, atrib):
    """Frequência no top-10 da intermediação em reamostragens dos pregões
    (blocos de 5 dias, para preservar a dependência de curto prazo)."""
    rng = np.random.default_rng(SEMENTE)
    blocos = [ret.iloc[i:i + 5] for i in range(0, len(ret), 5)]
    cont = pd.Series(0, index=ret.columns)
    for _ in range(N_BOOT):
        r = pd.concat([blocos[i] for i in rng.integers(0, len(blocos), len(blocos))])
        _, _, GB, _ = camada_b_p95(r)
        btw = pd.Series(nx.betweenness_centrality(GB)).sort_values(ascending=False)
        cont[btw.index[:10]] += 1
    t = (cont / N_BOOT).sort_values(ascending=False).head(15).rename("freq_top10").to_frame()
    t.insert(0, "segmento", atrib.loc[t.index, "segmento"])
    return t


def carteiras(ret, seg, nome):
    """Escolha com o 1º período, medida no 2º; só segmentos com
    MIN_FUNDOS_SEGMENTO fundos ou mais."""
    grandes = seg.value_counts()
    seg = seg[seg.isin(grandes[grandes >= MIN_FUNDOS_SEGMENTO].index)]
    r = ret[seg.index]
    meio = len(r) // 2
    c1, c2 = r.iloc[:meio].corr(), r.iloc[meio:].corr()
    ap, ef = ts.carteiras_por_rede(c1, seg)
    ap_rho, ef_rho = ts.carteiras_so_correlacao(c1, seg)
    rng = np.random.default_rng(SEMENTE)
    grupos = [seg.index[seg == s] for s in sorted(seg.unique())]
    acaso = np.array([ts.rho_medio_carteira(c2, [rng.choice(g) for g in grupos])
                      for _ in range(N_ACASO)])
    rho = lambda f: ts.rho_medio_carteira(c2, f)
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
    return tab


# ---------------------------------------------------------------- execução

def main():
    os.makedirs(PASTA, exist_ok=True)
    a46, c46, r46 = carregar_base46()
    aA, cA, rA, rem = carregar_ampliada()
    print(f"[ampliada] {len(aA)} fundos, {len(rA)} retornos ({len(rem)} removidos na limpeza)")

    s46, *_ = resumo_base("base 46", a46, c46, r46)
    sA, corrA, GB, MST, GC = resumo_base("ampliada", aA, cA, rA)
    comp = pd.concat([s46, sA], axis=1)
    f4.salva_tabela(comp, PASTA, "01_comparacao_bases")
    print("\n[01] comparação entre as bases\n" + comp.to_string())

    print("\n[02] pontes na base ampliada (Camada B)")
    print(f4.tabela_pontes(GB, MST, aA, PASTA).to_string())
    est = estabilidade_pontes(rA, aA)
    f4.salva_tabela(est, PASTA, "02_pontes_estabilidade")
    print(f"\n   frequência no top-10 em {N_BOOT} reamostragens\n" + est.to_string())

    print("\n[03] correlação segmento × segmento e pares cruzados")
    print(f4.correlacao_segmentos(corrA, aA, PASTA).to_string())
    seg = aA["segmento"]
    iu = np.triu_indices(len(corrA), 1)
    cruz = sorted(((corrA.iat[i, j], corrA.index[i], corrA.index[j]) for i, j in zip(*iu)
                   if seg.iat[i] != seg.iat[j]), reverse=True)[:15]
    pc = pd.DataFrame([{"fundo_1": a, "segmento_1": seg[a], "fundo_2": b, "segmento_2": seg[b],
                        "rho": round(r, 3)} for r, a, b in cruz], index=range(1, 16))
    f4.salva_tabela(pc, PASTA, "03_pares_cruzados")
    print(pc.to_string())
    f4.figura_matriz_correlacao(corrA, aA, PASTA)

    print("\n[04] carteiras: escolha no 1º período, medida no 2º")
    cart = pd.concat([carteiras(r46, a46["segmento"], "base 46"),
                      carteiras(rA, aA["segmento"], "ampliada")], ignore_index=True).round(3)
    f4.salva_tabela(cart, PASTA, "04_carteiras", index=False)
    print(cart.drop(columns="fundos").to_string(index=False))

    print("\n[05] figuras")
    so_mst = {frozenset((a, b)) for a, b, d in GB.edges(data=True) if d["origem"] == "mst"}
    f4.desenha_grafo(GB, aA, f"Base ampliada — Camada B ({len(aA)} FIIs)", PASTA,
                     "05_grafo_B.png", nx.kamada_kawai_layout(GB, weight=None), tracejadas=so_mst)
    print(f"\n[ok] resultados em {PASTA}/")


if __name__ == "__main__":
    main()
