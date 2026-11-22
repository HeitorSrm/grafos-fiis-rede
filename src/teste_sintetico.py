"""
Teste de carga e de correção com 500 fundos sintéticos de estrutura conhecida.

Diferente do --simular do frente4.py (que só mede escala), aqui a resposta
certa é plantada no gerador, e o teste verifica se o pipeline a recupera:

  - segmentos (Camada A deve agrupá-los);
  - pontes: fundos cujo preço segue dois segmentos (Camada B, intermediação);
  - pares de segmentos com fator oculto comum, sem gestora nem inquilino em
    comum (diversificação aparente);
  - perfis financeiros independentes do segmento (Camada C);
  - carteiras aparente (fundo mais central da MST em cada segmento) e efetiva
    (o mais periférico), escolhidas no 1º período e medidas no 2º.

Três cenários: "forte" (estrutura nítida), "realista" (correlação fraca como
nos FIIs reais) e "regime" (realista + mudança de regime entre os períodos,
como a observada entre 2023 e 2024). Várias sementes por cenário.

As carteiras também são comparadas com a regra sem grafo (maior/menor
correlação média), para separar o que vem da rede do que vem só da exposição
ao mercado.

Uso (a partir da raiz do repositório):
    python src/teste_sintetico.py            # 5 sementes por cenário
    python src/teste_sintetico.py --sementes 2
Saída: out/teste_sintetico/
"""
import argparse
import itertools
import os
import time

import networkx as nx
import numpy as np
import pandas as pd
from sklearn.metrics import adjusted_rand_score as ari

import camadas as cm
import grafos as gr

PASTA = os.path.join("out", "teste_sintetico")
DIAS = 500                       # metade = período de escolha, metade = teste

TAMANHOS = {"Papel": 150, "Logística": 80, "Shoppings": 70, "Lajes": 60,
            "Renda Urbana": 40, "Híbrido": 40, "FoF": 35, "Fiagro": 25}
PARES_OCULTOS = [("Renda Urbana", "Lajes"), ("Fiagro", "Shoppings")]
N_PONTES = 12
PERFIS = {  # DY, P/VP, log10 PL, log10 liquidez, nº de ativos
    "grande_liquido": (9.0, 0.95, 9.6, 7.3, 30),
    "medio": (11.0, 0.85, 9.0, 6.6, 12),
    "pequeno_iliquido": (13.0, 0.70, 8.4, 5.6, 4),
    "alto_yield_descontado": (16.0, 0.55, 8.8, 6.2, 8),
}

# força dos fatores: beta de mercado (mín, máx), segmento, oculto, ponte, ruído;
# persist = fração das cargas do 1º período que continua no 2º (1 = estrutura estável)
CENARIOS = {
    "forte":    dict(bm=(0.3, 0.9), seg=0.9, oculto=0.8, ponte=0.9, ruido=0.7, persist=1.0),
    # calibrado para a correlação dos FIIs reais (mediana ~0,19, p95 ~0,32)
    "realista": dict(bm=(0.3, 0.85), seg=0.42, oculto=0.42, ponte=0.42, ruido=1.15, persist=1.0),
    # como o realista, mas com mudança de regime entre os períodos: a correlação
    # entre as matrizes de 2023 e 2024 fica ~0,2, como nos FIIs reais (0,17)
    "regime":   dict(bm=(0.3, 0.85), seg=0.36, oculto=0.36, ponte=0.36, ruido=1.15, persist=0.25),
}
# desvio dentro de cada perfil da Camada C: perfis se sobrepõem, como nos dados reais
RUIDO_PERFIL = (1.5, 0.10, 0.30, 0.40, 5)
GRADE_K = range(2, 31)


# ---------------------------------------------------------------- gerador

def gerar_universo(cenario, seed):
    """Devolve (atrib, cont, ret, gabarito)."""
    p = CENARIOS[cenario]
    rng = np.random.default_rng(seed)
    fundos, seg_de = [], {}
    for s, n in TAMANHOS.items():
        for i in range(n):
            t = f"{s[:3].upper()}{i:03d}"
            fundos.append(t)
            seg_de[t] = s
    seg = pd.Series(seg_de)
    segs = list(TAMANHOS)

    # pontes: fundos de um segmento cujo preço também segue outro
    pontes = {}
    for t in rng.choice(fundos, N_PONTES, replace=False):
        outro = rng.choice([s for s in segs if s != seg[t]])
        pontes[t] = outro

    f_mkt = rng.normal(size=DIAS)
    f_seg = {s: rng.normal(size=DIAS) for s in segs}
    f_oculto = {par: rng.normal(size=DIAS) for par in PARES_OCULTOS}
    segundo = np.arange(DIAS) >= DIAS // 2      # dias do 2º período
    q = p["persist"]
    ret = {}
    for t in fundos:
        s = seg[t]
        # cargas do 2º período: parte herdada do 1º, parte nova (mudança de regime)
        bm1 = rng.uniform(*p["bm"])
        bm = np.where(segundo, q * bm1 + (1 - q) * rng.uniform(*p["bm"]), bm1)
        mult = np.where(segundo, q + (1 - q) * rng.uniform(0, 2), 1.0)
        r = bm * f_mkt + p["ruido"] * rng.normal(size=DIAS)
        if t in pontes:   # metade do fator de cada um dos dois segmentos
            r += mult * p["ponte"] * (f_seg[s] + f_seg[pontes[t]]) / np.sqrt(2)
        else:
            r += mult * p["seg"] * f_seg[s]
        for par, f in f_oculto.items():
            if s in par:
                r += mult * p["oculto"] * f
        ret[t] = 0.01 * r
    ret = pd.DataFrame(ret, index=pd.bdate_range("2023-01-02", periods=DIAS))

    # gestoras: quase todas dentro de um segmento; 5 atuam em vários
    gest_seg = {s: [f"G_{s[:3]}{j}" for j in range(max(2, TAMANHOS[s] // 6))] for s in segs}
    multi = [f"G_multi{j}" for j in range(5)]
    gestora = {t: (rng.choice(multi) if rng.random() < 0.08 else rng.choice(gest_seg[seg[t]]))
               for t in fundos}

    # inquilinos: só tijolo, pool por segmento, cobertura desigual (0 a 5 nomes)
    pool = {s: [f"empresa_{s[:3]}{j}" for j in range(30)] for s in cm.SEGMENTOS_COM_INQUILINO}
    inquilinos = {t: (list(rng.choice(pool[seg[t]], rng.integers(0, 6), replace=False))
                      if seg[t] in pool else []) for t in fundos}

    atrib = pd.DataFrame({"segmento": seg, "gestora": pd.Series(gestora),
                          "inquilinos": pd.Series(inquilinos)}).loc[fundos]

    # Camada C: perfil plantado, independente do segmento
    nomes = list(PERFIS)
    perfil = pd.Series({t: rng.choice(nomes) for t in fundos})
    linhas = {}
    for t in fundos:
        dy, pvp, pl, liq, nat = PERFIS[perfil[t]]
        sd = RUIDO_PERFIL
        linhas[t] = dict(dividend_yield=rng.normal(dy, sd[0]), pvp=rng.normal(pvp, sd[1]),
                         patrimonio_liquido=rng.normal(pl, sd[2]), liquidez=rng.normal(liq, sd[3]),
                         num_ativos=(max(1.0, rng.normal(nat, sd[4])) if seg[t] in pool else np.nan))
    cont = pd.DataFrame(linhas).T.loc[fundos].astype(float)

    # pontes: fundo -> o 2º segmento que ele segue
    gabarito = {"pontes": pontes, "pares_ocultos": {frozenset(p) for p in PARES_OCULTOS},
                "perfil": perfil}
    return atrib, cont, ret, gabarito


# ---------------------------------------------------------------- carteiras

def carteiras_por_rede(corr, seg):
    """Uma carteira por regra, com 1 fundo por segmento, a partir da MST:
    aparente = o mais central (maior intermediação) de cada segmento;
    efetiva = o mais periférico (menor intermediação).
    Desempate pela correlação média com o resto do mercado, para não
    depender da ordem dos fundos."""
    mst = gr.grafo_mst(corr)
    btw = pd.Series(nx.betweenness_centrality(mst))
    rho_medio = (corr.sum() - 1) / (len(corr) - 1)
    aparente, efetiva = [], []
    for s in sorted(seg.unique()):
        f = seg.index[seg == s]
        chave = pd.DataFrame({"btw": btw[f], "rho": rho_medio[f]})
        aparente.append(chave.sort_values(["btw", "rho"], ascending=False).index[0])
        efetiva.append(chave.sort_values(["btw", "rho"]).index[0])
    return aparente, efetiva


def carteiras_so_correlacao(corr, seg):
    """Comparação sem grafo: maior e menor correlação média de cada segmento.
    Mostra o quanto da regra da rede vem só da exposição ao mercado."""
    rho_medio = (corr.sum() - 1) / (len(corr) - 1)
    grupos = [rho_medio[seg.index[seg == s]] for s in sorted(seg.unique())]
    return [g.idxmax() for g in grupos], [g.idxmin() for g in grupos]


def rho_medio_carteira(corr, fundos):
    sub = corr.loc[fundos, fundos].values
    return sub[np.triu_indices(len(fundos), 1)].mean()


# ---------------------------------------------------------------- avaliação

def calibrar_k(GA_completo, cont):
    """Regra da Frente 2 aplicada a esta amostra: menor k que deixa A e C
    conexas e com grau médio acima de 3. Com k fixo em 3, grupos de mais de
    3 fundos com o mesmo perfil na Camada A (mesmo segmento e mesma gestora,
    Jaccard = 1) ficam fechados em si e o grafo se parte.
    Se o grafo completo da Camada A já é desconexo (um segmento sem gestora
    nem inquilino em comum com os outros), nenhum k o conecta: a meta passa a
    ser preservar os componentes do grafo completo."""
    meta_A = nx.number_connected_components(GA_completo)
    for k in GRADE_K:
        GA, GC = cm.backbone_knn(GA_completo, k), cm.camada_c(cont, k=k)
        ok_A = nx.number_connected_components(GA) == meta_A
        ok_C = nx.is_connected(GC)
        grau_ok = all(2 * G.number_of_edges() / len(G) > 3 for G in (GA, GC))
        if ok_A and ok_C and grau_ok:
            return k, GA, GC
    print(f"   [aviso] nenhum k até {k} atingiu a meta de conectividade")
    return k, GA, GC


def pureza(part, rotulo):
    """Fração dos fundos que estão numa comunidade cujo rótulo dominante é o
    deles. 1 = nenhuma comunidade mistura rótulos (ainda que um rótulo possa
    estar partido em várias)."""
    df = pd.DataFrame({"c": pd.Series(part), "r": rotulo.loc[list(part)]})
    return df.groupby("c")["r"].agg(lambda s: s.value_counts().iloc[0]).sum() / len(df)


def avaliar(cenario, seed):
    t0 = time.time()
    atrib, cont, ret, gab = gerar_universo(cenario, seed)
    seg = atrib["segmento"]
    corr = ret.corr()
    iu = np.triu_indices(len(corr), 1)
    p95 = float(np.quantile(corr.values[iu], 0.95))

    GA_c, GA3 = cm.camada_a(atrib)                 # k = 3 fixo, só para comparar
    k, GA, GC = calibrar_k(GA_c, cont)
    GB, MST, _ = cm.camada_b(corr, rho_min=p95)   # mesmo critério da Frente 2: p95
    t_grafos = time.time() - t0

    def comunidades_vs(G, rotulo):
        part, _ = gr.comunidades(G)
        nos = list(part)
        return ari(rotulo.loc[nos], [part[n] for n in nos]), pureza(part, rotulo)

    ari_A, pur_A = comunidades_vs(GA, seg)
    ari_B, pur_B = comunidades_vs(GB, seg)
    ari_C, pur_C = comunidades_vs(GC, gab["perfil"])
    ari_C_seg, _ = comunidades_vs(GC, seg)

    # pontes plantadas no topo da intermediação (Camada B e, para comparar, MST)
    def acerto(G):
        btw = pd.Series(nx.betweenness_centrality(G)).sort_values(ascending=False)
        return len(set(btw.index[:N_PONTES]) & set(gab["pontes"])) / N_PONTES
    acerto_pontes, acerto_pontes_mst = acerto(GB), acerto(MST)

    # pares cruzados mais correlacionados: vêm dos pares ocultos? têm peso_A = 0?
    cruz = sorted(((corr.iat[i, j], corr.index[i], corr.index[j]) for i, j in zip(*iu)
                   if seg.iat[i] != seg.iat[j]), reverse=True)[:50]
    pontes = gab["pontes"]
    plantado = lambda a, b: (frozenset((seg[a], seg[b])) in gab["pares_ocultos"]
                             or pontes.get(a) == seg[b] or pontes.get(b) == seg[a])
    de_oculto = np.mean([plantado(a, b) for _, a, b in cruz])
    # acaso: fração de TODOS os pares cruzados que são plantados
    acaso_pares = np.mean([plantado(corr.index[i], corr.index[j]) for i, j in zip(*iu)
                           if seg.iat[i] != seg.iat[j]])
    peso_zero = np.mean([not GA_c.has_edge(a, b) for _, a, b in cruz])

    # carteiras: escolhidas no 1º período, medidas no 2º
    meio = DIAS // 2
    c1, c2 = ret.iloc[:meio].corr(), ret.iloc[meio:].corr()
    aparente, efetiva = carteiras_por_rede(c1, seg)
    ap_rho, ef_rho = carteiras_so_correlacao(c1, seg)
    rng = np.random.default_rng(seed + 1000)
    grupos = [seg.index[seg == s] for s in sorted(seg.unique())]
    acaso = np.array([rho_medio_carteira(c2, [rng.choice(g) for g in grupos])
                      for _ in range(2000)])
    r_ap, r_ef = rho_medio_carteira(c2, aparente), rho_medio_carteira(c2, efetiva)
    iu2 = np.triu_indices(len(c1), 1)

    return {
        "cenario": cenario, "semente": seed,
        "rho_mediana": round(float(np.median(corr.values[iu])), 3), "rho_p95": round(p95, 3),
        "k_calibrado": k,
        "componentes_A_com_k3": nx.number_connected_components(GA3),
        "componentes_A_completo": nx.number_connected_components(GA_c),
        "componentes_A": nx.number_connected_components(GA),
        "conexas": (nx.number_connected_components(GA) == nx.number_connected_components(GA_c)
                    and nx.is_connected(GB) and nx.is_connected(GC)),
        "arestas_A": GA.number_of_edges(), "arestas_B": GB.number_of_edges(),
        "arestas_C": GC.number_of_edges(),
        "ari_A_segmento": round(ari_A, 3), "pureza_A_segmento": round(pur_A, 3),
        "ari_B_segmento": round(ari_B, 3), "pureza_B_segmento": round(pur_B, 3),
        "ari_C_perfil": round(ari_C, 3), "pureza_C_perfil": round(pur_C, 3),
        "ari_C_segmento": round(ari_C_seg, 3),
        "acerto_pontes": round(acerto_pontes, 3),
        "acerto_pontes_mst": round(acerto_pontes_mst, 3),
        "pares_cruzados_plantados": round(float(de_oculto), 3),
        "pares_cruzados_acaso": round(float(acaso_pares), 3),
        "pares_cruzados_peso_A_zero": round(float(peso_zero), 3),
        "corr_entre_periodos": round(float(np.corrcoef(c1.values[iu2], c2.values[iu2])[0, 1]), 3),
        "rho_aparente_2o": round(r_ap, 3), "rho_acaso_2o": round(float(acaso.mean()), 3),
        "rho_efetiva_2o": round(r_ef, 3),
        "rho_aparente_so_corr_2o": round(rho_medio_carteira(c2, ap_rho), 3),
        "rho_efetiva_so_corr_2o": round(rho_medio_carteira(c2, ef_rho), 3),
        "efetiva_igual_so_corr": sum(a == b for a, b in zip(efetiva, ef_rho)),
        "pct_acaso_abaixo_da_efetiva": round(100 * float((acaso < r_ef).mean()), 1),
        "pct_acaso_abaixo_da_aparente": round(100 * float((acaso < r_ap).mean()), 1),
        "tempo_grafos_s": round(t_grafos, 1), "tempo_total_s": round(time.time() - t0, 1),
    }


# ---------------------------------------------------------------- critérios

CRITERIOS = {
    "B e C conexas; A com os mesmos componentes do grafo completo": lambda r: r.conexas,
    "A não mistura segmentos (pureza > 0,9)": lambda r: r.pureza_A_segmento > 0.9,
    "C não mistura perfis (pureza > 0,8) e ignora o segmento (ARI < 0,1)":
        lambda r: r.pureza_C_perfil > 0.8 and r.ari_C_segmento < 0.1,
    "pontes plantadas no topo (> 10x o acaso de 2,4%)": lambda r: r.acerto_pontes > 0.24,
    "pares cruzados vêm da estrutura plantada (> 5x o acaso)":
        lambda r: r.pares_cruzados_plantados > 5 * r.pares_cruzados_acaso,
    "pares cruzados sem vínculo na Camada A (> 80%)": lambda r: r.pares_cruzados_peso_A_zero > 0.8,
    "carteiras fora da amostra: aparente > acaso > efetiva":
        lambda r: r.rho_aparente_2o > r.rho_acaso_2o > r.rho_efetiva_2o,
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sementes", type=int, default=5)
    args = ap.parse_args()
    os.makedirs(PASTA, exist_ok=True)

    linhas = []
    for cenario in CENARIOS:
        for seed in range(args.sementes):
            r = avaliar(cenario, seed)
            linhas.append(r)
            print(f"[{cenario} {seed}] {r['tempo_total_s']}s | k={r['k_calibrado']} | "
                  f"pureza A {r['pureza_A_segmento']} | pontes B {r['acerto_pontes']:.0%} "
                  f"MST {r['acerto_pontes_mst']:.0%} | carteiras {r['rho_aparente_2o']} > "
                  f"{r['rho_acaso_2o']} > {r['rho_efetiva_2o']}")
    df = pd.DataFrame(linhas)
    df.to_csv(os.path.join(PASTA, "resultados_por_semente.csv"), index=False)

    resumo = df.drop(columns=["semente", "conexas"]).groupby("cenario").agg(["mean", "min", "max"]).round(3).T
    resumo.to_csv(os.path.join(PASTA, "resumo.csv"))

    print("\n=== critérios de aceite (todas as sementes)")
    tabela = []
    for nome, f in CRITERIOS.items():
        for cenario, g in df.groupby("cenario", sort=False):
            ok = sum(bool(f(r)) for r in g.itertuples())
            tabela.append({"criterio": nome, "cenario": cenario, "passou": f"{ok}/{len(g)}"})
    crit = pd.DataFrame(tabela).pivot(index="criterio", columns="cenario", values="passou")
    crit = crit.loc[list(CRITERIOS), list(CENARIOS)]
    crit.to_csv(os.path.join(PASTA, "criterios.csv"))
    print(crit.to_string())
    print(f"\n[ok] resultados em {PASTA}/")


if __name__ == "__main__":
    main()
