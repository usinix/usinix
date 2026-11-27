# SPDX-License-Identifier: LGPL-2.1-or-later
"""Mangueira: liga duas pontas (tubulação ou máquina, em qualquer combinação) com uma mangueira flexível e terminais.

Cada ponta é uma aresta circular (boca de tubo, furo roscado da máquina) ou uma face plana redonda: o centro e o
eixo dela dão o lugar e a direção de saída (para fora da peça). Em cada ponta entra um terminal (reto, 45° ou 90°,
com a rosca escolhida, girado em torno do eixo); da capa de um terminal à capa do outro passa a mangueira, uma
curva suave (B-spline) que sai alinhada com os terminais e passa pelos pontos de controle, que se arrastam na vista.

O resultado confere o raio mínimo de curvatura do tipo escolhido (os trechos mais apertados ficam marcados) e dá o
comprimento de corte (curva livre + a parte da mangueira que entra nas duas capas + folga), que vai para a lista de
materiais com os terminais.

Catálogo: valores das fichas citadas em cada tipo. A geometria dos terminais (sextavado, capa, curva) é
representativa, proporcional à rosca e à mangueira: o comprimento exato da capa e do terminal muda de fabricante
para fabricante (pode ser ajustado nas propriedades).
"""

import math

import FreeCAD

V = FreeCAD.Vector

# ---------------------------------------------------------------------------------------------- catálogo
# Hidráulica: Tubes International, fichas HW-1SN e HW-2SN (EN 853 1SN/2SN, ISO 1436, SAE 100 R1AT/R2AT), consultadas
# em 27/11/2026; -20, -24 e -32 do 2SN pela série PERFORMER 2SN da mesma ficha.
# Pneumática: Festo, tubo PUN-H (documento PUN-H, versão 2026/07); raio = raio mínimo de curvatura.
# di/de em mm, pt = pressão de trabalho em bar, rmin em mm, kgm = massa em kg/m (None = a ficha não traz).
TIPOS = {
    "Hidráulica 1SN (EN 853)": {
        "fonte": "Tubes International, ficha HW-1SN (EN 853 1SN / SAE 100 R1AT)",
        "familia": "hidraulica",
        "tamanhos": {
            "-4 (1/4\")": dict(dash=4, di=6.4, de=13.1, pt=225, rmin=100, kgm=0.22),
            "-5 (5/16\")": dict(dash=5, di=8.1, de=14.7, pt=215, rmin=115, kgm=0.26),
            "-6 (3/8\")": dict(dash=6, di=9.7, de=17.0, pt=180, rmin=130, kgm=0.33),
            "-8 (1/2\")": dict(dash=8, di=13.0, de=20.3, pt=160, rmin=180, kgm=0.41),
            "-10 (5/8\")": dict(dash=10, di=16.1, de=23.4, pt=130, rmin=200, kgm=0.47),
            "-12 (3/4\")": dict(dash=12, di=19.2, de=27.4, pt=105, rmin=240, kgm=0.59),
            "-16 (1\")": dict(dash=16, di=25.4, de=35.3, pt=88, rmin=300, kgm=0.87),
            "-20 (1 1/4\")": dict(dash=20, di=32.0, de=42.5, pt=63, rmin=420, kgm=1.21),
            "-24 (1 1/2\")": dict(dash=24, di=38.2, de=50.1, pt=50, rmin=500, kgm=1.40),
            "-32 (2\")": dict(dash=32, di=51.0, de=64.0, pt=40, rmin=630, kgm=1.91),
        },
    },
    "Hidráulica 2SN (EN 853)": {
        "fonte": "Tubes International, ficha HW-2SN (EN 853 2SN / SAE 100 R2AT)",
        "familia": "hidraulica",
        "tamanhos": {
            "-4 (1/4\")": dict(dash=4, di=6.4, de=14.7, pt=400, rmin=100, kgm=0.35),
            "-5 (5/16\")": dict(dash=5, di=8.1, de=16.2, pt=350, rmin=115, kgm=0.40),
            "-6 (3/8\")": dict(dash=6, di=9.7, de=18.6, pt=330, rmin=130, kgm=0.51),
            "-8 (1/2\")": dict(dash=8, di=13.0, de=21.7, pt=275, rmin=180, kgm=0.63),
            "-10 (5/8\")": dict(dash=10, di=16.1, de=24.9, pt=250, rmin=200, kgm=0.76),
            "-12 (3/4\")": dict(dash=12, di=19.2, de=28.9, pt=215, rmin=240, kgm=0.96),
            "-16 (1\")": dict(dash=16, di=25.4, de=37.2, pt=165, rmin=300, kgm=1.39),
            "-20 (1 1/4\")": dict(dash=20, di=31.8, de=47.7, pt=125, rmin=420, kgm=2.12),
            "-24 (1 1/2\")": dict(dash=24, di=38.1, de=54.0, pt=90, rmin=500, kgm=2.55),
            "-32 (2\")": dict(dash=32, di=50.8, de=67.5, pt=80, rmin=630, kgm=3.20),
        },
    },
    "Pneumática PU (tubo)": {
        "fonte": "Festo, tubo PUN-H (documento 2026/07)",
        "familia": "pneumatica",
        "tamanhos": {
            "Ø4": dict(dash=0, di=2.6, de=4.0, pt=6, rmin=8, kgm=None),
            "Ø6": dict(dash=0, di=4.0, de=6.0, pt=6, rmin=10, kgm=None),
            "Ø8": dict(dash=0, di=5.7, de=8.0, pt=6, rmin=21, kgm=None),
            "Ø10": dict(dash=0, di=7.0, de=10.0, pt=6, rmin=28, kgm=None),
            "Ø12": dict(dash=0, di=8.0, de=12.0, pt=6, rmin=33, kgm=None),
            "Ø14": dict(dash=0, di=9.8, de=14.0, pt=6, rmin=38, kgm=None),
        },
    },
}
TIPO_PADRAO = "Hidráulica 2SN (EN 853)"
TAMANHO_PADRAO = "-8 (1/2\")"

# Roscas por tamanho (dash) do terminal: Titan Fittings, "Fitting Thread Charts" (JIC 37° SAE J514, BSPP, NPTF,
# ORFS SAE J1453), consultada em 27/11/2026.
ROSCAS = {
    "JIC 37°": {4: "7/16-20 UNF", 5: "1/2-20 UNF", 6: "9/16-18 UNF", 8: "3/4-16 UNF", 10: "7/8-14 UNF",
                12: "1 1/16-12 UN", 16: "1 5/16-12 UN", 20: "1 5/8-12 UN", 24: "1 7/8-12 UN", 32: "2 1/2-12 UN"},
    "BSP (G)": {4: "G 1/4", 6: "G 3/8", 8: "G 1/2", 10: "G 5/8", 12: "G 3/4", 16: "G 1", 20: "G 1 1/4",
                24: "G 1 1/2", 32: "G 2"},
    "NPT": {4: "1/4 NPT", 6: "3/8 NPT", 8: "1/2 NPT", 12: "3/4 NPT", 16: "1 NPT", 20: "1 1/4 NPT",
            24: "1 1/2 NPT", 32: "2 NPT"},
    "ORFS": {4: "9/16-18 UNF", 6: "11/16-16 UN", 8: "13/16-16 UN", 10: "1-14 UNS", 12: "1 3/16-12 UN",
             16: "1 7/16-12 UN", 20: "1 11/16-12 UN", 24: "2-12 UN"},
}
# diâmetro externo da rosca (mm), só para dar tamanho ao desenho do terminal
_D_BSP = {"1/4": 13.157, "3/8": 16.662, "1/2": 20.955, "5/8": 22.911, "3/4": 26.441, "1": 33.249,
          "1 1/4": 41.910, "1 1/2": 47.803, "2": 59.614}
_D_NPT = {"1/4": 13.7, "3/8": 17.1, "1/2": 21.3, "3/4": 26.7, "1": 33.4, "1 1/4": 42.2, "1 1/2": 48.3, "2": 60.3}

LIGACOES_HIDRAULICA = ("Fêmea giratória", "Macho")
ROSCAS_PNEUMATICA = ("G 1/8", "G 1/4", "G 3/8", "G 1/2")
FORMAS = ("Reto", "45°", "90°")


def tipo(nome):
    return TIPOS.get(nome) or TIPOS[TIPO_PADRAO]


def dados(nome_tipo, tamanho):
    t = tipo(nome_tipo)
    return t["tamanhos"].get(tamanho) or next(iter(t["tamanhos"].values()))


def roscas_para(nome_tipo, tamanho):
    """Roscas que existem para esse tamanho: [(sistema, designação)]."""
    t = tipo(nome_tipo)
    if t["familia"] == "pneumatica":
        return [("Instantânea", g) for g in ROSCAS_PNEUMATICA]
    dash = dados(nome_tipo, tamanho)["dash"]
    return [(s, tab[dash]) for s, tab in ROSCAS.items() if dash in tab]


def _polegadas(txt):
    """'1 1/16-12 UN' → 1.0625 (pol)."""
    num = txt.split("-")[0].strip()
    total = 0.0
    for parte in num.split():
        if "/" in parte:
            a, b = parte.split("/")
            total += float(a) / float(b)
        else:
            total += float(parte)
    return total


def diametro_rosca(sistema, rosca):
    """Diâmetro externo aproximado da rosca (mm), para desenhar o terminal."""
    try:
        if sistema in ("JIC 37°", "ORFS"):
            return _polegadas(rosca) * 25.4
        if sistema in ("BSP (G)", "Instantânea"):
            return {"1/8": 9.728}.get(rosca.replace("G", "").strip()) or _D_BSP[rosca.replace("G", "").strip()]
        if sistema == "NPT":
            return _D_NPT[rosca.replace("NPT", "").strip()]
    except (KeyError, ValueError):
        pass
    return 20.0


def medidas_terminal(nome_tipo, tamanho, sistema, rosca):
    """Proporções representativas do terminal (mm): sextavado (entre faces e altura), pescoço, raio da curva,
    capa (diâmetro, comprimento) e quanto da mangueira entra na capa."""
    de = dados(nome_tipo, tamanho)["de"]
    d = diametro_rosca(sistema, rosca)
    if tipo(nome_tipo)["familia"] == "pneumatica":
        return dict(d=d, s=d + 4.0, hs=8.0, dp=max(de + 2.0, 0.7 * d), lp=4.0, rc=de + 6.0,
                    dc=de + 6.0, lc=de + 12.0, entra=0.6 * (de + 12.0))
    return dict(d=d, s=1.15 * d + 4.0, hs=0.55 * d + 6.0, dp=0.75 * d, lp=0.4 * d + 8.0, rc=0.9 * d + 12.0,
                dc=1.25 * de + 4.0, lc=1.4 * de + 22.0, entra=1.4 * de + 18.0)


# ---------------------------------------------------------------------------------------------- pontas
def _forma_global(obj, sub):
    """Elemento `sub` de obj em coordenadas globais (obj dentro de Parte/Montagem também)."""
    import Part
    el = Part.getShape(obj, sub, needSubElement=True, transform=False)
    try:
        pl = obj.getGlobalPlacement()
    except Exception:
        pl = obj.Placement
    el = el.copy()
    el.transformShape(pl.toMatrix(), True)
    return el


def _centro_da_peca(obj):
    try:
        sh = obj.Shape.copy()
        try:
            pai = obj.getGlobalPlacement().multiply(obj.Placement.inverse())
            sh.transformShape(pai.toMatrix(), True)
        except Exception:
            pass
        if sh.Solids:
            return sh.Solids[0].CenterOfMass if len(sh.Solids) == 1 else sh.BoundBox.Center
        return sh.BoundBox.Center
    except Exception:
        return None


def ponta_de(obj, sub):
    """(centro, eixo para fora, diâmetro) da ponta escolhida: aresta circular, face plana com borda redonda ou face
    cilíndrica (furo/boca de tubo). O eixo aponta para longe do centro da peça (sai da máquina ou do tubo)."""
    el = _forma_global(obj, sub)
    centro = eixo = None
    diam = 0.0
    if el.ShapeType == "Edge" and hasattr(el.Curve, "Center") and hasattr(el.Curve, "Radius"):
        centro, eixo, diam = el.Curve.Center, el.Curve.Axis, 2 * el.Curve.Radius
    elif el.ShapeType == "Face":
        sup = el.Surface
        if hasattr(sup, "Axis") and hasattr(sup, "Radius") and not hasattr(sup, "MajorRadius"):   # cilindro
            bordas = [e for e in el.Edges if hasattr(e.Curve, "Center") and hasattr(e.Curve, "Radius")]
            eixo, diam = sup.Axis, 2 * sup.Radius
            if bordas:
                ref = _centro_da_peca(obj)
                bordas.sort(key=lambda e: -(e.Curve.Center - ref).Length if ref is not None else 0)
                centro = bordas[0].Curve.Center
            else:
                centro = el.CenterOfMass
        else:                                                                                  # face plana
            redondas = [e for e in el.Edges if hasattr(e.Curve, "Radius")]
            u0, u1, v0, v1 = el.ParameterRange
            eixo = el.normalAt((u0 + u1) / 2, (v0 + v1) / 2)
            if redondas:
                menor = min(redondas, key=lambda e: e.Curve.Radius)
                centro, diam = menor.Curve.Center, 2 * menor.Curve.Radius
            else:
                centro = el.CenterOfMass
    elif el.ShapeType == "Vertex":
        centro, eixo = el.Point, V(0, 0, 1)
    if centro is None:
        raise ValueError("Escolha uma aresta redonda (boca do tubo, furo da máquina) ou uma face plana.")
    eixo = V(eixo).normalize()
    ref = _centro_da_peca(obj)
    if ref is not None and (centro - ref).dot(eixo) < 0:
        eixo = eixo * -1
    return V(centro), eixo, diam


def filtro_ponta(obj, subs):
    """Para a caixa de seleção do painel: aceita aresta redonda, face ou vértice."""
    res = []
    for s in subs or ():
        if s.startswith(("Edge", "Face", "Vertex")):
            try:
                ponta_de(obj, s)
            except Exception:
                continue
            res.append(("%s · %s" % (obj.Label, s), (obj, s)))
    return res


# ---------------------------------------------------------------------------------------------- geometria
def _perpendicular(n):
    ref = V(0, 0, 1) if abs(n.z) < 0.95 else V(1, 0, 0)
    u = ref - n * ref.dot(n)
    return u.normalize()


def _girar(v, eixo, graus):
    return FreeCAD.Rotation(eixo, graus).multVec(v)


def giro_para(p, n, alvo):
    """Giro (graus) que faz o terminal curvo virar para o alvo (a outra ponta ou o primeiro ponto de passagem)."""
    u0 = _perpendicular(n)
    w = V(alvo) - p
    w = w - n * w.dot(n)
    if w.Length < 1e-6:
        return 0.0
    return math.degrees(math.atan2(u0.cross(w).dot(n), u0.dot(w)))


def terminal(p, n, forma, giro, m):
    """Sólidos do terminal na ponta p (eixo n para fora) e onde a mangueira começa: (sólidos, ponto, direção)."""
    import Part
    u = _girar(_perpendicular(n), n, giro)
    solidos = []
    # sextavado (porca giratória ou sextavado do macho), com a face na ponta
    s = m["s"]
    r_hex = s / math.sqrt(3.0)
    v_perp = n.cross(u)
    pts = [p + (u * math.cos(math.radians(60 * k + 30)) + v_perp * math.sin(math.radians(60 * k + 30))) * r_hex
           for k in range(6)]
    hexf = Part.Face(Part.makePolygon(pts + [pts[0]]))
    solidos.append(hexf.extrude(n * m["hs"]))
    a = p + n * m["hs"]
    solidos.append(Part.makeCylinder(m["dp"] / 2, m["lp"], a, n))
    a = a + n * m["lp"]
    graus = {"45°": 45.0, "90°": 90.0}.get(forma, 0.0)
    d = V(n)
    if graus:
        centro = a + u * m["rc"]
        eixo = n.cross(u)
        circ = Part.Face(Part.Wire(Part.makeCircle(m["dp"] / 2, a, n)))
        solidos.append(circ.revolve(centro, eixo, graus))
        a = centro + _girar(a - centro, eixo, graus)
        d = _girar(n, eixo, graus).normalize()
    solidos.append(Part.makeCylinder(m["dc"] / 2, m["lc"], a, d))
    return solidos, a + d * m["lc"], d


FATORES_TANGENTE = (0.6, 0.8, 1.0, 1.3, 1.6, 2.0, 2.5, 3.0)


def _interpolar(pts, d0, d1, k):
    import Part
    tans = [d0 * k] + [V(0, 0, 0)] * (len(pts) - 2) + [d1 * (-k)]
    flags = [True] + [False] * (len(pts) - 2) + [True]
    c = Part.BSplineCurve()
    # Scale=False: a tangente vale por unidade de parâmetro (comprimento da corda), então k é adimensional
    c.interpolate(Points=pts, Tangents=tans, TangentFlags=flags, Scale=False)
    return c


def curva(p0, d0, p1, d1, pontos=()):
    """B-spline da capa A à capa B, saindo na direção d0 e chegando na direção -d1, pelos pontos de controle.
    Entre alguns tamanhos de tangente, fica o que dá o maior raio mínimo (a mangueira "folgada", como fica na
    montagem); empate: a mais curta."""
    pts = [V(p0)] + [V(q) for q in pontos] + [V(p1)]
    melhor = None
    for k in FATORES_TANGENTE:
        try:
            c = _interpolar(pts, V(d0).normalize(), V(d1).normalize(), k)
        except Exception:
            continue
        r = min(r for _t, _p, r in raios(c, 120))
        chave = (round(r, 1), -c.length())
        if melhor is None or chave > melhor[0]:
            melhor = (chave, c)
    if melhor is None:
        raise ValueError("Não foi possível passar a mangueira por esses pontos.")
    return melhor[1]


def raios(c, n=240):
    """[(parâmetro, ponto, raio)] amostrados ao longo da curva."""
    a, b = c.FirstParameter, c.LastParameter
    res = []
    for i in range(n + 1):
        t = a + (b - a) * i / n
        k = c.curvature(t)
        res.append((t, c.value(t), 1.0 / k if k > 1e-12 else float("inf")))
    return res


def trechos_apertados(amostras, rmin):
    """Pontos da curva onde o raio fica abaixo do mínimo (para marcar na vista)."""
    return [p for _t, p, r in amostras if r < rmin * 0.999]


def _corte(livre, entra_a, entra_b, folga):
    total = livre + entra_a + entra_b + folga
    return math.ceil(total / 5.0) * 5.0          # arredondado para cima, de 5 em 5 mm


def montar(pa, na, pb, nb, nome_tipo, tamanho, term_a, term_b, pontos=(), folga=0.0):
    """Tudo da mangueira. term_x = (sistema, rosca, ligação, forma, giro); giro None = o terminal curvo vira sozinho
    para a outra ponta (ou para o ponto de passagem mais perto). Devolve dicionário com forma, curva,
    comprimentos, raio mínimo medido, pontos apertados e as medidas usadas."""
    import Part
    pontos = [V(q) for q in pontos]
    if term_a[4] is None:
        term_a = tuple(term_a[:4]) + (giro_para(pa, na, pontos[0] if pontos else pb),)
    if term_b[4] is None:
        term_b = tuple(term_b[:4]) + (giro_para(pb, nb, pontos[-1] if pontos else pa),)
    dd = dados(nome_tipo, tamanho)
    ma = medidas_terminal(nome_tipo, tamanho, term_a[0], term_a[1])
    mb = medidas_terminal(nome_tipo, tamanho, term_b[0], term_b[1])
    sa, ha, da = terminal(pa, na, term_a[3], term_a[4], ma)
    sb, hb, db = terminal(pb, nb, term_b[3], term_b[4], mb)
    c = curva(ha, da, hb, db, pontos)
    mang = varrer(c, dd["de"] / 2)
    am = raios(c)
    rmed = min(r for _t, _p, r in am)
    livre = c.length()
    return {
        "forma": Part.makeCompound([mang] + sa + sb),
        "faces_mangueira": len(mang.Faces),
        "curva": c,
        "livre": livre,
        "corte": _corte(livre, ma["entra"], mb["entra"], folga),
        "raio_medido": rmed,
        "raio_minimo": dd["rmin"],
        "apertados": trechos_apertados(am, dd["rmin"]),
        "inicio": ha, "fim": hb,
        "dados": dd,
    }


def varrer(c, raio):
    """Sólido da mangueira ao longo da curva. Frenet puro torce a superfície e a vista desenha a mangueira com
    falhas; o Frenet corrigido falha em curvas planas, que vão com a binormal fixa (normal do plano). makePipe
    não serve: derruba o programa em alguns caminhos (falha dentro do OCC)."""
    import Part
    caminho = Part.Wire(c.toShape())
    circ = Part.Wire(Part.makeCircle(raio, c.value(c.FirstParameter), c.tangent(c.FirstParameter)[0]))

    def corrigido():
        return caminho.makePipeShell([circ], True, False)

    def binormal():
        pl = caminho.findPlane()
        if pl is None:
            raise ValueError("curva não plana")
        sw = Part.BRepOffsetAPI.MakePipeShell(caminho)
        sw.setBiNormalMode(pl.Axis)
        sw.add(circ, False, True)
        sw.build()
        sw.makeSolid()
        return sw.shape()

    def frenet():
        return caminho.makePipeShell([circ], True, True)

    erro = None
    for modo in (corrigido, binormal, frenet):
        try:
            s = modo()
            if not s.isNull() and s.isValid() and s.Solids:
                return s
        except Exception as exc:
            erro = exc
    raise ValueError("Não foi possível desenhar a mangueira nesse caminho (%s)." % erro)


def ponto_novo(c, pontos):
    """Onde entra um ponto de controle novo: no meio do maior vão da curva entre os pontos que ela já tem."""
    a, b = c.FirstParameter, c.LastParameter
    nos = [a] + sorted(c.parameter(V(q)) for q in pontos) + [b]
    i = max(range(len(nos) - 1), key=lambda k: nos[k + 1] - nos[k])
    t = (nos[i] + nos[i + 1]) / 2
    novos = list(pontos)
    novos.insert(i, c.value(t))
    return novos


# ---------------------------------------------------------------------------------------------- objeto
def _rotulo_terminal(familia, sistema, rosca, ligacao, forma):
    if familia == "pneumatica":
        return "Conexão instantânea %s %s" % (forma.lower() if forma != "Reto" else "reta", rosca)
    lig = "fêmea giratória" if ligacao.startswith("Fêmea") else "macho"
    return "Terminal prensado %s %s %s (%s)" % (sistema, lig, forma.lower() if forma != "Reto" else "reto", rosca)


class Mangueira:
    """Objeto paramétrico (Part::FeaturePython)."""

    def __init__(self, obj):
        obj.Proxy = self
        self._props(obj)

    def _props(self, obj):
        def add(tp, nome, grupo, dica, valor=None, modo=None):
            if nome not in obj.PropertiesList:
                obj.addProperty(tp, nome, grupo, dica)
                if valor is not None:
                    setattr(obj, nome, valor)
            if modo is not None:
                obj.setEditorMode(nome, modo)
        add("App::PropertyLinkSubGlobal", "PontaA", "Pontas", "Ponta A: aresta redonda, face ou vértice (tubo ou máquina)")
        add("App::PropertyLinkSubGlobal", "PontaB", "Pontas", "Ponta B: aresta redonda, face ou vértice (tubo ou máquina)")
        add("App::PropertyBool", "InverterA", "Pontas", "Inverte a direção de saída da ponta A", False)
        add("App::PropertyBool", "InverterB", "Pontas", "Inverte a direção de saída da ponta B", False)
        if "Tipo" not in obj.PropertiesList:
            obj.addProperty("App::PropertyEnumeration", "Tipo", "Mangueira", "Tipo de mangueira (catálogo)")
            obj.Tipo = list(TIPOS)
            obj.Tipo = TIPO_PADRAO
        add("App::PropertyString", "Tamanho", "Mangueira", "Tamanho (dash/polegada ou diâmetro externo)", TAMANHO_PADRAO)
        add("App::PropertyLength", "Folga", "Mangueira", "Acrescentado ao comprimento de corte", 0.0)
        add("App::PropertyVectorList", "Pontos", "Mangueira", "Pontos de controle por onde a mangueira passa")
        for lado in ("A", "B"):
            add("App::PropertyString", "Rosca" + lado, "Terminal " + lado, "Sistema e rosca do terminal (ex.: JIC 37° | 3/4-16 UNF)", "")
            add("App::PropertyString", "Ligacao" + lado, "Terminal " + lado, "Fêmea giratória ou Macho", "Fêmea giratória")
            add("App::PropertyString", "Forma" + lado, "Terminal " + lado, "Reto, 45° ou 90°", "Reto")
            add("App::PropertyBool", "GiroAuto" + lado, "Terminal " + lado, "O terminal curvo vira sozinho para a outra ponta", True)
            add("App::PropertyAngle", "Giro" + lado, "Terminal " + lado, "Giro do terminal curvo em torno do eixo da ponta (sem giro automático)", 0.0)
        add("App::PropertyLength", "Corte", "Resultado", "Comprimento de corte da mangueira", 0.0, 1)
        add("App::PropertyLength", "Livre", "Resultado", "Comprimento livre (entre as capas)", 0.0, 1)
        add("App::PropertyLength", "RaioMedido", "Resultado", "Menor raio de curvatura da mangueira", 0.0, 1)
        add("App::PropertyLength", "RaioMinimo", "Resultado", "Raio mínimo do catálogo", 0.0, 1)
        add("App::PropertyString", "Aviso", "Resultado", "Aviso do raio mínimo", "", 1)
        add("App::PropertyVectorList", "Apertados", "Resultado", "Pontos abaixo do raio mínimo", None, 2)
        add("App::PropertyInteger", "FacesMangueira", "Resultado", "Faces da mangueira (cor)", 0, 2)
        add("App::PropertyIntegerList", "Itens", "Resultado", "Itens na lista de materiais", None, 2)

    def onDocumentRestored(self, obj):
        self._props(obj)

    def _term(self, obj, lado):
        txt = getattr(obj, "Rosca" + lado) or ""
        if "|" in txt:
            sistema, rosca = [x.strip() for x in txt.split("|", 1)]
        else:
            ops = roscas_para(obj.Tipo, obj.Tamanho)
            sistema, rosca = ops[0] if ops else ("JIC 37°", "3/4-16 UNF")
        giro = None if getattr(obj, "GiroAuto" + lado, False) else float(getattr(obj, "Giro" + lado))
        return (sistema, rosca, getattr(obj, "Ligacao" + lado), getattr(obj, "Forma" + lado), giro)

    def _ponta(self, obj, lado):
        link = getattr(obj, "Ponta" + lado)
        if not link or not link[1]:
            raise ValueError("Falta a ponta %s." % lado)
        p, n, _d = ponta_de(link[0], link[1][0])
        if getattr(obj, "Inverter" + lado):
            n = n * -1
        return p, n

    def execute(self, obj):
        import Part
        try:
            pa, na = self._ponta(obj, "A")
            pb, nb = self._ponta(obj, "B")
            r = montar(pa, na, pb, nb, obj.Tipo, obj.Tamanho, self._term(obj, "A"), self._term(obj, "B"),
                       list(obj.Pontos), float(obj.Folga))
        except Exception as exc:
            FreeCAD.Console.PrintWarning("Usinix: mangueira: %s\n" % exc)
            obj.Shape = Part.Shape()
            obj.Aviso = str(exc)
            return
        self.curva = r["curva"]      # para o painel pôr pontos novos (não vai para o arquivo)
        obj.Shape = r["forma"]
        obj.FacesMangueira = r["faces_mangueira"]
        obj.Corte = r["corte"]
        obj.Livre = r["livre"]
        obj.RaioMedido = min(r["raio_medido"], 1e7)
        obj.RaioMinimo = r["raio_minimo"]
        obj.Apertados = r["apertados"]
        if r["apertados"]:
            obj.Aviso = ("Raio de %.0f mm, abaixo do mínimo de %.0f mm: afaste os pontos ou mude o terminal."
                         % (r["raio_medido"], r["raio_minimo"]))
        else:
            obj.Aviso = ""

    def linhas_bom(self, obj):
        """Para a lista de materiais: [(chave, denominação, material, dimensões, qtd, massa, obs)]."""
        t = tipo(obj.Tipo)
        dd = dados(obj.Tipo, obj.Tamanho)
        corte = float(obj.Corte)
        massa = dd["kgm"] * corte / 1000.0 if dd.get("kgm") else None
        linhas = [(("mangueira", obj.Tipo, obj.Tamanho, round(corte)),
                   "Mangueira %s %s" % (obj.Tipo, obj.Tamanho), "—", "L = %.0f mm (corte)" % corte, 1, massa,
                   "%.0f bar; raio mín. %.0f mm" % (dd["pt"], dd["rmin"]))]
        for lado in ("A", "B"):
            sistema, rosca, lig, forma, _g = self._term(obj, lado)
            den = _rotulo_terminal(t["familia"], sistema, rosca, lig, forma)
            mat = "Latão niquelado" if t["familia"] == "pneumatica" else "Aço"
            linhas.append((("terminal", den, obj.Tamanho), "%s, mangueira %s" % (den, obj.Tamanho), mat, "", 1,
                           None, "geometria representativa"))
        return linhas

    def dumps(self):
        return None

    def loads(self, state):
        return None


def e_mangueira(obj):
    return obj is not None and isinstance(getattr(obj, "Proxy", None), Mangueira)


def criar(ponta_a, ponta_b, nome_tipo=TIPO_PADRAO, tamanho=TAMANHO_PADRAO, term_a=None, term_b=None, pontos=(),
          folga=0.0, doc=None):
    """ponta_x = (objeto, subelemento). term_x = (sistema, rosca, ligação, forma, giro) ou None (padrão);
    giro None = automático (o terminal curvo vira para a outra ponta)."""
    doc = doc or FreeCAD.ActiveDocument
    obj = doc.addObject("Part::FeaturePython", "Mangueira")
    Mangueira(obj)
    obj.Label = "Mangueira"
    definir(obj, ponta_a, ponta_b, nome_tipo, tamanho, term_a, term_b, pontos, folga)
    if FreeCAD.GuiUp:
        try:
            import UsinixMangueiraGui
            UsinixMangueiraGui.VPMangueira(obj.ViewObject)
        except Exception as exc:
            FreeCAD.Console.PrintLog("Usinix: mangueira (vista): %s\n" % exc)
    doc.recompute()
    return obj


def definir(obj, ponta_a, ponta_b, nome_tipo, tamanho, term_a, term_b, pontos, folga):
    obj.PontaA = (ponta_a[0], [ponta_a[1]])
    obj.PontaB = (ponta_b[0], [ponta_b[1]])
    obj.Tipo = nome_tipo
    obj.Tamanho = tamanho
    ops = roscas_para(nome_tipo, tamanho)
    padrao = ops[0] if ops else ("JIC 37°", "3/4-16 UNF")
    for lado, term in (("A", term_a), ("B", term_b)):
        sistema, rosca, lig, forma, giro = term or (padrao[0], padrao[1], "Fêmea giratória", "Reto", None)
        setattr(obj, "Rosca" + lado, "%s | %s" % (sistema, rosca))
        setattr(obj, "Ligacao" + lado, lig)
        setattr(obj, "Forma" + lado, forma)
        setattr(obj, "GiroAuto" + lado, giro is None)
        setattr(obj, "Giro" + lado, giro or 0.0)
    obj.Pontos = [V(p) for p in pontos]
    obj.Folga = folga
