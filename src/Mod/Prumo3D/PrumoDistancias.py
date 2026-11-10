# SPDX-License-Identifier: LGPL-2.1-or-later
# Usinix - distâncias de segurança da ABNT NBR ISO 13857:2021 para proteções de máquina (NR-12).
"""Distâncias de segurança (ABNT NBR ISO 13857:2021).

Valores conferidos no texto da ABNT NBR ISO 13857:2021 (1ª edição, 12/03/2021, idêntica à ISO 13857:2019),
consultada no catálogo ABNT/Confea em 10/11/2026 (situação: em vigor). Só os números das tabelas entram aqui.

- Alcance por cima (4.2.1.2): zona de perigo a 2 700 mm ou mais; 2 500 mm quando a lesão é leve e pouco provável.
- Alcance sobre a proteção: Tabela 1 (lesão leve e pouco provável) e Tabela 2 (demais casos). Sem interpolação
  (4.2.2.1): entre dois valores, vale o mais seguro — aqui, a linha de h que pede mais distância e a coluna de
  altura da proteção imediatamente abaixo. Proteção com menos de 1 000 mm não entra nas tabelas; com menos de
  1 400 mm, a norma pede medidas adicionais.
- Alcance através de aberturas: Tabela 4 (14 anos ou mais) e Tabela 5 (3 anos ou mais), com as notas de fenda curta.
- Membros inferiores: Tabela 7.
"""

NORMA = "ABNT NBR ISO 13857:2021"
CONFERIDA = "catálogo ABNT/Confea, 10/11/2026"

ALCANCE_SUPERIOR = {"alto": 2700.0, "baixo": 2500.0}

# Tabelas 1 e 2: colunas = altura da estrutura de proteção (hps); linhas = altura da zona de perigo (h) -> s
HPS_BAIXO = (1000, 1200, 1400, 1600, 1800, 2000, 2200, 2400, 2500)
TAB_BAIXO = {  # Tabela 1 — lesão leve e baixa probabilidade
    2500: (0, 0, 0, 0, 0, 0, 0, 0, 0),
    2400: (100, 100, 100, 100, 100, 100, 100, 100, 0),
    2200: (600, 600, 500, 500, 400, 350, 250, 0, 0),
    2000: (1100, 900, 700, 600, 500, 350, 0, 0, 0),
    1800: (1100, 1000, 900, 900, 600, 0, 0, 0, 0),
    1600: (1300, 1000, 900, 900, 500, 0, 0, 0, 0),
    1400: (1300, 1000, 900, 800, 100, 0, 0, 0, 0),
    1200: (1400, 1000, 900, 500, 0, 0, 0, 0, 0),
    1000: (1400, 1000, 900, 300, 0, 0, 0, 0, 0),
    800: (1300, 900, 600, 0, 0, 0, 0, 0, 0),
    600: (1200, 500, 0, 0, 0, 0, 0, 0, 0),
    400: (1200, 300, 0, 0, 0, 0, 0, 0, 0),
    200: (1100, 200, 0, 0, 0, 0, 0, 0, 0),
    0: (1100, 200, 0, 0, 0, 0, 0, 0, 0)}
HPS_ALTO = (1000, 1200, 1400, 1600, 1800, 2000, 2200, 2400, 2500, 2700)
TAB_ALTO = {  # Tabela 2
    2700: (0, 0, 0, 0, 0, 0, 0, 0, 0, 0),
    2600: (900, 800, 700, 600, 600, 500, 400, 300, 100, 0),
    2400: (1100, 1000, 900, 800, 700, 600, 400, 300, 100, 0),
    2200: (1300, 1200, 1000, 900, 800, 600, 400, 300, 0, 0),
    2000: (1400, 1300, 1100, 900, 800, 600, 400, 0, 0, 0),
    1800: (1500, 1400, 1100, 900, 800, 600, 0, 0, 0, 0),
    1600: (1500, 1400, 1100, 900, 800, 500, 0, 0, 0, 0),
    1400: (1500, 1400, 1100, 900, 800, 0, 0, 0, 0, 0),
    1200: (1500, 1400, 1100, 900, 700, 0, 0, 0, 0, 0),
    1000: (1500, 1400, 1000, 800, 0, 0, 0, 0, 0, 0),
    800: (1500, 1300, 900, 600, 0, 0, 0, 0, 0, 0),
    600: (1400, 1300, 800, 0, 0, 0, 0, 0, 0, 0),
    400: (1400, 1200, 400, 0, 0, 0, 0, 0, 0, 0),
    200: (1200, 900, 0, 0, 0, 0, 0, 0, 0, 0),
    0: (1100, 500, 0, 0, 0, 0, 0, 0, 0, 0)}

# Tabela 4 (14 anos ou mais): (e máximo, fenda, quadrada, circular, parte do corpo)
ABERTURAS_14 = ((4, 2, 2, 2, "ponta dos dedos"), (6, 10, 5, 5, "ponta dos dedos"),
                (8, 20, 15, 5, "dedo até a junta"), (10, 80, 25, 20, "dedo até a junta"),
                (12, 100, 80, 80, "mão"), (20, 120, 120, 120, "mão"),
                (30, 850, 120, 120, "braço até o ombro"), (40, 850, 200, 120, "braço até o ombro"),
                (120, 850, 850, 850, "braço até o ombro"))
NOTA_FENDA_14 = (20, 30, 65, 200)    # fenda 20 < e ≤ 30 com comprimento ≤ 65 mm: s ≥ 200 (nota a)
# Tabela 5 (3 anos ou mais)
ABERTURAS_3 = ((4, 2, 2, 2, "ponta dos dedos"), (6, 20, 10, 10, "ponta dos dedos"),
               (8, 40, 30, 20, "dedo até a junta"), (10, 80, 60, 60, "dedo até a junta"),
               (12, 100, 80, 80, "mão"), (20, 900, 120, 120, "mão"),
               (30, 900, 550, 120, "braço até o ombro"), (100, 900, 900, 900, "braço até o ombro"))
NOTA_FENDA_3 = (12, 20, 40, 120)     # fenda 12 < e ≤ 20 com comprimento ≤ 40 mm: s ≥ 120 (nota a)
# Tabela 7 (membros inferiores, 14 anos ou mais): (e máximo, fenda, quadrada ou circular); None = não admissível
INFERIORES = ((5, 0, 0), (15, 10, 0), (35, 80, 25), (60, 180, 80), (80, 650, 180), (95, 1100, 650),
              (180, 1100, 1100), (240, None, 1100))
NOTA_FENDA_INF = (15, 35, 75, 50)    # fenda 15 < e ≤ 35 com comprimento ≤ 75 mm: s > 50 (nota a)

TIPOS = ("quadrada", "fenda", "circular")
TIPO_ROTULO = {"quadrada": "Malha quadrada", "fenda": "Fenda (malha retangular)", "circular": "Furo redondo"}


def _risco(risco):
    return "baixo" if str(risco).lower().startswith("b") else "alto"


def _publico(publico):
    return "3" if str(publico).strip().startswith("3") else "14"


def altura_fora_de_alcance(risco="alto"):
    """Altura mínima (mm) da zona de perigo para ficar fora do alcance por cima (4.2.1.2)."""
    return ALCANCE_SUPERIOR[_risco(risco)]


def alcance_sobre(h, hps, risco="alto"):
    """Distância horizontal mínima s (mm) da proteção à zona de perigo, para alcance sobre a proteção.

    Devolve (s, aviso). s = None quando a tabela não se aplica (proteção com menos de 1 000 mm)."""
    r = _risco(risco)
    colunas, tab = (HPS_BAIXO, TAB_BAIXO) if r == "baixo" else (HPS_ALTO, TAB_ALTO)
    h, hps = float(h), float(hps)
    topo = ALCANCE_SUPERIOR[r]
    if h >= topo:
        return 0.0, ""
    if hps < colunas[0]:
        return None, ("Proteção com menos de 1 000 mm de altura não restringe o movimento do corpo e não entra "
                      "nas Tabelas 1 e 2.")
    # coluna: a altura de proteção tabelada imediatamente abaixo (mais segura)
    j = max(i for i, c in enumerate(colunas) if c <= hps + 1e-9)
    # linhas: as duas alturas tabeladas em volta de h; vale a que pede mais distância
    alturas = sorted(tab)
    abaixo = max(a for a in alturas if a <= h + 1e-9)
    acima = [a for a in alturas if a >= h - 1e-9]
    acima = min(acima) if acima else abaixo
    s = max(tab[abaixo][j], tab[acima][j])
    aviso = ""
    if hps < 1400:
        aviso = "Proteção com menos de 1 400 mm: a norma pede medidas de proteção adicionais."
    return float(s), aviso


def abertura(e, tipo="quadrada", publico="14", comprimento_fenda=None):
    """Distância mínima sr (mm) da abertura à zona de perigo (Tabela 4 ou 5).

    Devolve dict: s (None se a abertura não protege — maior que a da tabela), parte do corpo, nota."""
    tipo = tipo if tipo in TIPOS else "quadrada"
    pub = _publico(publico)
    linhas, nota = (ABERTURAS_3, NOTA_FENDA_3) if pub == "3" else (ABERTURAS_14, NOTA_FENDA_14)
    e = float(e)
    tab = "Tabela 5" if pub == "3" else "Tabela 4"
    if e <= 0:
        return {"s": 0.0, "parte": "", "nota": "", "tabela": tab}
    for emax, sf, sq, sc, parte in linhas:
        if e <= emax + 1e-9:
            s = {"fenda": sf, "quadrada": sq, "circular": sc}[tipo]
            txt = ""
            if (tipo == "fenda" and comprimento_fenda and nota[0] < e <= nota[1] + 1e-9
                    and float(comprimento_fenda) <= nota[2] + 1e-9):
                s = min(s, nota[3])
                txt = "fenda curta (comprimento ≤ %d mm): o polegar limita o acesso" % nota[2]
            return {"s": float(s), "parte": parte, "nota": txt, "tabela": tab}
    return {"s": None, "parte": "corpo inteiro ou braço", "tabela": tab,
            "nota": "abertura maior que %d mm: não protege; use as distâncias de alcance sobre a proteção (4.2.2)"
                    % linhas[-1][0]}


def membros_inferiores(e, tipo="fenda", comprimento_fenda=None):
    """Distância mínima (mm) para aberturas ao alcance dos pés e pernas (Tabela 7). s None = não admissível."""
    e = float(e)
    fenda = tipo == "fenda"
    if e <= 0:
        return {"s": 0.0, "nota": ""}
    for emax, sf, sq in INFERIORES:
        if e <= emax + 1e-9:
            s = sf if fenda else sq
            txt = ""
            if (fenda and comprimento_fenda and NOTA_FENDA_INF[0] < e <= NOTA_FENDA_INF[1] + 1e-9
                    and float(comprimento_fenda) <= NOTA_FENDA_INF[2] + 1e-9):
                s = NOTA_FENDA_INF[3]
                txt = "fenda curta (comprimento ≤ 75 mm)"
            if s is None:
                return {"s": None, "nota": "fenda acima de 180 mm: não admissível"}
            return {"s": float(s), "nota": txt}
    return {"s": None, "nota": "abertura acima de 240 mm: permite o acesso do corpo inteiro"}


def verificar(abertura_mm, tipo="quadrada", dist_abertura=0.0, altura_protecao=0.0, altura_perigo=0.0,
              dist_perigo=None, folga_inferior=0.0, risco="alto", publico="14", comprimento_fenda=None,
              dist_folga=None):
    """Verifica uma proteção fixa (grade ou enclausuramento) contra as tabelas da norma.

    abertura_mm: abertura da tela (lado, diâmetro ou largura da fenda); dist_abertura: da tela até o ponto de
    perigo mais próximo; altura_protecao: do piso ao topo da proteção; altura_perigo: altura do ponto de perigo;
    dist_perigo: distância horizontal da proteção ao perigo (padrão: a mesma da tela); folga_inferior: vão entre o
    piso e a proteção; dist_folga: da folga até o perigo que os pés alcançam (padrão: dist_perigo).
    Devolve (ok, itens), itens = [{"nome", "exigido", "atual", "ok", "ref", "texto"}]."""
    itens = []
    dist_perigo = dist_abertura if dist_perigo is None else dist_perigo
    dist_folga = dist_perigo if dist_folga is None else dist_folga
    a = abertura(abertura_mm, tipo, publico, comprimento_fenda)
    if a["s"] is None:
        itens.append({"nome": "Abertura da tela", "exigido": None, "atual": dist_abertura, "ok": False,
                      "ref": "%s, %s" % (NORMA, a["tabela"]), "texto": a["nota"]})
    else:
        ok = dist_abertura + 1e-9 >= a["s"]
        txt = a["nota"]
        itens.append({"nome": "Abertura da tela (%s %s mm)" % (TIPO_ROTULO[tipo].lower(), _n(abertura_mm)),
                      "exigido": a["s"], "atual": dist_abertura, "ok": ok,
                      "ref": "%s, %s" % (NORMA, a["tabela"]), "texto": txt})
    topo = altura_fora_de_alcance(risco)
    if altura_perigo >= topo:
        itens.append({"nome": "Alcance por cima", "exigido": None, "atual": altura_perigo, "ok": True,
                      "ref": "%s, 4.2.1" % NORMA,
                      "texto": "perigo a %s mm ou mais do piso: fora do alcance por cima" % _n(topo)})
    else:
        s, aviso = alcance_sobre(altura_perigo, altura_protecao, risco)
        tab = "Tabela 1" if _risco(risco) == "baixo" else "Tabela 2"
        if s is None:
            itens.append({"nome": "Alcance sobre a proteção", "exigido": None, "atual": dist_perigo, "ok": False,
                          "ref": "%s, %s" % (NORMA, tab), "texto": aviso})
        else:
            itens.append({"nome": "Alcance sobre a proteção (altura %s mm, perigo a %s mm)" % (
                _n(altura_protecao), _n(altura_perigo)), "exigido": s, "atual": dist_perigo,
                "ok": dist_perigo + 1e-9 >= s, "ref": "%s, %s" % (NORMA, tab), "texto": aviso})
    if folga_inferior > 0:
        m = membros_inferiores(folga_inferior, "fenda")
        if m["s"] is None:
            itens.append({"nome": "Folga inferior (%s mm)" % _n(folga_inferior), "exigido": None,
                          "atual": dist_folga, "ok": False, "ref": "%s, Tabela 7" % NORMA, "texto": m["nota"]})
        else:
            txt = m["nota"]
            if folga_inferior > 120:
                txt = ((txt + "; ") if txt else "") + ("pela folga passa o braço: avalie também o alcance por "
                                                       "baixo (fora das tabelas)")
            itens.append({"nome": "Folga inferior (%s mm) — pés e pernas" % _n(folga_inferior), "exigido": m["s"],
                          "atual": dist_folga, "ok": dist_folga + 1e-9 >= m["s"],
                          "ref": "%s, Tabela 7" % NORMA, "texto": txt})
    return all(i["ok"] for i in itens), itens


def maior_abertura(dist, tipo="quadrada", publico="14"):
    """Maior abertura da tabela (mm) que ainda atende à distância dada (para sugerir a malha)."""
    linhas = ABERTURAS_3 if _publico(publico) == "3" else ABERTURAS_14
    col = {"fenda": 1, "quadrada": 2, "circular": 3}.get(tipo, 2)
    melhor = 0.0
    for lin in linhas:
        if lin[col] <= dist + 1e-9:
            melhor = float(lin[0])
    return melhor


def _n(v):
    v = float(v)
    return ("%d" % round(v)) if abs(v - round(v)) < 1e-6 else ("%.1f" % v).replace(".", ",")


def linha(i):
    """Um item da verificação em uma linha: ✓/✗, nome, exigido × atual, observação e referência."""
    ex = "—" if i["exigido"] is None else "%s mm" % _n(i["exigido"])
    return "%s %s: exigido %s, atual %s mm%s  [%s]" % (
        "✓" if i["ok"] else "✗", i["nome"], ex, _n(i["atual"]), (" — " + i["texto"]) if i["texto"] else "",
        i["ref"])


def texto(ok, itens):
    """Resumo em texto para a janela e para o relatório."""
    topo = "Proteção %s — %s" % ("CONFORME" if ok else "NÃO CONFORME", NORMA)
    return "\n".join([topo] + [linha(i) for i in itens])
