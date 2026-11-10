# SPDX-License-Identifier: LGPL-2.1-or-later
# Usinix - folhas de fabricação com um clique: uma folha por barra da estrutura e a folha da chapa planificada.
"""Folhas de fabricação.

Folhas das barras: uma folha ABNT por barra diferente da estrutura (barras iguais, como na lista de corte,
saem numa folha só com a quantidade). A barra aparece deitada, vista pela alma e por cima, com a seção do
perfil ampliada ao lado; cotas de comprimento e da furação; tabela com perfil, comprimento de corte, ângulos
das pontas, furação, quantidade e massa.

Folha da chapa: a chapa planificada (ou a chapa plana, vista de frente) com as cotas gerais e da furação, as
linhas de dobra e a tabela das dobras. A planificação fica num objeto que acompanha a peça.
"""

import math

import FreeCAD

import PrumoUtil

GRUPO = "DadosDasFolhas"
ESPACO = 22.0            # mm de papel entre vistas (cabem as cotas)


# ============================================================================ apoio
def _grupo_dados(doc):
    g = doc.getObject(GRUPO)
    if g is None:
        g = doc.addObject("App::DocumentObjectGroup", GRUPO)
        g.Label = "Dados das folhas"
    return g


def _area_util(page):
    """(x0, x1, y0, y1) em mm da faixa livre acima da legenda (Y a partir da borda de baixo)."""
    import PrumoBOM
    import PrumoFolhas
    larg, alt = PrumoFolhas._tamanho_folha(page)
    e, d, s, i = PrumoBOM.margens_da_folha(page)
    h_leg = PrumoBOM.altura_legenda(page) or 55.0
    return e + 8.0, larg - d - 8.0, i + h_leg + 12.0, alt - s - 10.0


def _escala_normal(maxima):
    """Maior escala normalizada (série 1-2-5) que não passa de `maxima`."""
    import PrumoFolhas
    for e in PrumoFolhas.ESCALAS_NORMAIS:
        if e <= maxima + 1e-12:
            return e
    return PrumoFolhas.ESCALAS_NORMAIS[-1]


def _vista(doc, page, fontes, direcao, xdir, nome, rotulo, escala=None):
    v = doc.addObject("TechDraw::DrawViewPart", nome)
    v.Label = rotulo
    page.addView(v)
    v.Source = fontes
    v.Direction = direcao
    v.XDirection = xdir
    if escala is None:
        v.ScaleType = "Page"
    else:
        v.ScaleType = "Custom"
        v.Scale = escala
    return v


def esperar_geometria(vistas, segundos=30.0):
    """Espera o desenho (linha oculta) de vistas novas ficar pronto."""
    import time
    import PrumoVistas
    try:
        from PySide import QtWidgets
    except ImportError:
        QtWidgets = None
    fim = time.time() + segundos
    tocar = time.time() + 2.0
    while time.time() < fim:
        if all(PrumoVistas._vertices(v) for v in vistas):
            return True
        if time.time() > tocar:
            for v in vistas:
                if not PrumoVistas._vertices(v):
                    v.touch()
            vistas[0].Document.recompute()
            tocar = time.time() + 3.0
        if QtWidgets is not None:
            QtWidgets.QApplication.processEvents()
        time.sleep(0.05)
    return False


def _refazer_na_escala(vista, segundos=15.0):
    """A geometria da vista é calculada já na escala: depois de mudar a escala, refaz e espera o desenho novo
    (largura dos vértices proporcional à escala)."""
    import time
    import PrumoVistas
    try:
        from PySide import QtWidgets
    except ImportError:
        QtWidgets = None

    def largura():
        vs = PrumoVistas._vertices(vista)
        return (max(t[1] for t in vs) - min(t[1] for t in vs)) if vs else 0.0
    antes = largura()
    vista.touch()
    vista.Document.recompute()
    fim = time.time() + segundos
    while time.time() < fim:
        agora = largura()
        if agora and abs(agora - antes) > 1e-6:
            return True
        if QtWidgets is not None:
            QtWidgets.QApplication.processEvents()
        time.sleep(0.05)
    return False


def tabela_na_folha(page, nome, titulo, linhas, larguras=(200, 290)):
    """Tabela de duas colunas (rótulo, valor) no canto de baixo à esquerda da folha, ao lado da legenda.
    Devolve a vista da tabela."""
    import PrumoBOM
    doc = page.Document
    sh = doc.getObject(nome)
    if sh is None:
        sh = doc.addObject("Spreadsheet::Sheet", nome)
        _grupo_dados(doc).addObject(sh)
    else:
        sh.clearAll()
    sh.Label = titulo
    sh.set("A1", "'" + titulo)
    sh.mergeCells("A1:B1")
    sh.setStyle("A1:B1", "bold")
    sh.setBackground("A1:B1", (0.0, 0.227, 0.439))
    sh.setForeground("A1:B1", (1.0, 1.0, 1.0))
    sh.setAlignment("A1:B1", "center|vcenter")
    for c, w in zip("AB", larguras):
        sh.setColumnWidth(c, w)
    for r, (rot, val) in enumerate(linhas, 2):
        sh.set("A%d" % r, "'" + str(rot))
        sh.set("B%d" % r, "'" + str(val))
    sh.setStyle("A2:A%d" % (len(linhas) + 1), "bold")
    doc.recompute()
    vista = None
    for v in page.Views:
        if v.TypeId == "TechDraw::DrawViewSpreadsheet" and v.Source == sh:
            vista = v
    if vista is None:
        vista = doc.addObject("TechDraw::DrawViewSpreadsheet", "Tabela")
        vista.Label = titulo
        vista.Source = sh
        page.addView(vista)
    vista.CellStart = "A1"
    vista.CellEnd = "B%d" % (len(linhas) + 1)
    alt_px = float(sh.getRowHeight("1")) or 30.0
    escala = PrumoBOM.ALTURA_LINHA_MM / (alt_px * PrumoBOM.PX_MM)
    try:
        vista.ScaleType = "Custom"
    except Exception:
        pass
    vista.Scale = escala
    vista.TextSize = PrumoBOM.TEXTO_MM / (PrumoBOM.PX_MM * escala)
    vista.LineWidth = 0.35 / PrumoBOM.PX_MM
    e, _d, _s, i = PrumoBOM.margens_da_folha(page)
    w = sum(larguras) * PrumoBOM.PX_MM * escala
    h = sum(sh.getRowHeight(str(r)) for r in range(1, len(linhas) + 2)) * PrumoBOM.PX_MM * escala
    vista.X = e + 6.0 + w / 2.0
    vista.Y = i + 6.0 + h / 2.0
    doc.recompute()
    return vista


def _f(v, casas=1):
    return PrumoUtil.fmt_dim(round(v, casas))


def _ang(a):
    a = float(a)
    return "reto (90°)" if abs(a - 90.0) < 0.05 or abs(a) < 0.05 else "%s°" % PrumoUtil.fmt_dim(round(a, 1))


# ============================================================================ barras
def _eixo_e_alma(barra):
    """(eixo da barra, normal da alma) no espaço: o eixo pela linha do esqueleto; a alma é a maior face plana
    paralela ao eixo (para cantoneira e tubo, uma das faces)."""
    import PrumoEstrutura as E
    sh = barra.Shape
    t = None
    try:
        e = E.arestas(barra.Estrutura.Esqueleto)[barra.Indice]
        t = (e.Vertexes[-1].Point - e.Vertexes[0].Point)
        t.normalize()
    except Exception:
        pass
    if t is None or t.Length < 1e-9:
        bb = sh.BoundBox
        lados = [(bb.XLength, FreeCAD.Vector(1, 0, 0)), (bb.YLength, FreeCAD.Vector(0, 1, 0)),
                 (bb.ZLength, FreeCAD.Vector(0, 0, 1))]
        t = max(lados, key=lambda x: x[0])[1]
    melhor, area = None, -1.0
    for f in sh.Faces:
        if "Plane" not in type(f.Surface).__name__:
            continue
        try:
            n = f.normalAt(0, 0)
        except Exception:
            continue
        if abs(n.dot(t)) > 1e-3:
            continue
        if f.Area > area:
            melhor, area = n, f.Area
    if melhor is None:      # perfil redondo: qualquer direção perpendicular
        melhor = t.cross(FreeCAD.Vector(0, 0, 1))
        if melhor.Length < 1e-6:
            melhor = t.cross(FreeCAD.Vector(1, 0, 0))
    melhor = FreeCAD.Vector(melhor)
    melhor.normalize()
    if melhor.dot(FreeCAD.Vector(0, -1, 0)) + 1e-3 * melhor.dot(FreeCAD.Vector(0, 0, 1)) < 0:
        melhor = melhor.negative()          # a alma vista do mesmo lado em todas as folhas
    return t, melhor


def barras_para_folhas(objs):
    """[(barra modelo, quantidade, [barras])] agrupando como a lista de corte (perfil, comprimento, ângulos e
    furação), na ordem da lista de corte."""
    import PrumoEstrutura as E
    barras = []
    for o in objs:
        if E.eh_estrutura(o):
            barras += E.barras_de(o)
        elif E.eh_barra(o):
            barras.append(o)
        elif hasattr(o, "Group"):
            barras += [b for b in o.Group if E.eh_barra(b)]
    grupos, ordem = {}, []
    for b in barras:
        comp = round(b.ComprimentoCorte.Value, 1)
        a0, a1 = sorted([round(b.CorteInicio.Value, 1), round(b.CorteFim.Value, 1)])
        chave = (b.Perfil, comp, a0, a1, getattr(b, "Furacao", "") or "")
        if chave not in grupos:
            grupos[chave] = []
            ordem.append(chave)
        grupos[chave].append(b)
    ordem.sort(key=lambda k: (k[0], -k[1]))
    return [(grupos[k][0], len(grupos[k]), grupos[k]) for k in ordem]


class BarraReta:
    """Cópia da barra deitada no eixo X (alma virada para -Y, "cima" em +Z, ponta inicial em x = 0), para a
    folha: o TechDraw só interrompe vistas ao longo de X, Y ou Z. Acompanha a barra quando ela muda."""

    def __init__(self, obj, barra=None):
        obj.Proxy = self
        obj.addProperty("App::PropertyLink", "Barra", "Folha", "Barra da estrutura desenhada na folha")
        obj.Barra = barra

    def onDocumentRestored(self, obj):
        obj.Proxy = self

    def execute(self, obj):
        if obj.Barra is not None:
            import Part
            # num composto: a posição de dentro (a rotação) não é trocada pela Placement do objeto
            obj.Shape = Part.makeCompound([barra_deitada(obj.Barra)])

    def dumps(self):
        return None

    def loads(self, state):
        return None


def barra_deitada(barra):
    t, n = _eixo_e_alma(barra)
    cima = n.cross(t)
    cima.normalize()
    m = FreeCAD.Matrix(t.x, t.y, t.z, 0, -n.x, -n.y, -n.z, 0, cima.x, cima.y, cima.z, 0, 0, 0, 0, 1)
    sh = barra.Shape.copy()
    sh.transformShape(m)          # rígida: furos continuam círculos
    bb = sh.BoundBox
    sh.translate(FreeCAD.Vector(-bb.XMin, -(bb.YMin + bb.YMax) / 2.0, -(bb.ZMin + bb.ZMax) / 2.0))
    return sh


def _trechos_livres(sh, folga):
    """[(x0, x1)] trechos ao longo de X sem furo, recorte nem canto (com `folga` mm de cada lado), onde a vista
    pode ser interrompida."""
    L = sh.BoundBox.XLength
    ocupado = []
    for e in sh.Edges:
        bb = e.BoundBox
        if bb.XLength > 0.5 * L:
            continue               # aresta corrida ao longo da barra
        ocupado.append((bb.XMin - folga, bb.XMax + folga))
    ocupado.sort()
    juntos = []
    for a, b in ocupado:
        if juntos and a <= juntos[-1][1]:
            juntos[-1][1] = max(juntos[-1][1], b)
        else:
            juntos.append([a, b])
    livres = []
    for (a0, b0), (a1, _b1) in zip(juntos, juntos[1:]):
        if a1 - b0 > 1e-6:
            livres.append((b0, a1))
    return livres


def _plano_da_quebra(doc, plano, x0, x1, meia):
    """Esboço com as duas linhas de quebra (em x0 e x1), atravessando a barra (± meia)."""
    import Part
    sk = doc.addObject("Sketcher::SketchObject", "Quebra")
    sk.Label = "Quebra da folha"
    if plano == "XZ":
        sk.Placement = FreeCAD.Placement(FreeCAD.Vector(), FreeCAD.Rotation(FreeCAD.Vector(1, 0, 0), 90))
    for x in (x0, x1):
        sk.addGeometry(Part.LineSegment(FreeCAD.Vector(x, -meia, 0), FreeCAD.Vector(x, meia, 0)))
    _grupo_dados(doc).addObject(sk)
    try:
        sk.ViewObject.Visibility = False
    except Exception:
        pass
    return sk


def escolher_escala_e_quebras(sh, largura, altura, alvo_perfil=45.0):
    """(escala, [(x0, x1) removidos]) para a barra deitada caber em largura × altura (mm de papel): a maior
    escala normalizada em que o perfil não passa de `alvo_perfil` mm e a barra cabe, interrompendo os trechos
    livres se preciso."""
    import PrumoFolhas
    bb = sh.BoundBox
    L, alt, larg = bb.XLength, bb.ZLength, bb.YLength
    for e in PrumoFolhas.ESCALAS_NORMAIS:
        if max(alt, larg) * e > alvo_perfil or (alt + larg) * e + ESPACO > altura:
            continue
        if L * e <= largura:
            return e, []
        manter = 12.0 / e                      # pedaço de barra que fica à vista de cada lado da quebra
        vao = 8.0 / e                          # espaço da quebra no papel: 8 mm
        tiradas, comprimido = [], L
        for a, b in sorted(_trechos_livres(sh, 25.0 / e), key=lambda t: -(t[1] - t[0])):
            if comprimido * e <= largura:
                break
            corte = (b - a) - 2 * manter
            if corte <= vao:
                continue
            tiradas.append((a + manter, b - manter))
            comprimido -= corte - vao
        if comprimido * e <= largura and len(tiradas) <= 3:
            return e, sorted(tiradas)
    e = PrumoFolhas.ESCALAS_NORMAIS[-1]
    for x in PrumoFolhas.ESCALAS_NORMAIS:
        if L * x <= largura and (alt + larg) * x + ESPACO <= altura:
            return x, []
    return e, []


def _vista_quebrada(doc, page, fonte, direcao, xdir, nome, rotulo, quebras):
    if not quebras:
        return _vista(doc, page, [fonte], direcao, xdir, nome, rotulo)
    v = doc.addObject("TechDraw::DrawBrokenView", nome)
    v.Label = rotulo
    page.addView(v)
    v.Source = [fonte]
    v.Direction = direcao
    v.XDirection = xdir
    v.ScaleType = "Page"
    v.Breaks = quebras
    return v


def folha_da_barra(doc, barra, qtd=1, formato="A3", norma=None, campos=None, marca=None):
    """Folha ABNT de uma barra: vista pela alma, vista de cima (interrompidas se a barra for longa), seção
    ampliada, cotas de comprimento e da furação e tabela. Devolve a folha."""
    import PrumoFolhas
    import PrumoVistas
    norma = norma or PrumoFolhas.NORMA_PADRAO
    marca = marca or barra.Label
    valores = {"titulo": ("BARRA %s — %s" % (marca, barra.Perfil)).upper(),
               "material": barra.Material or "", "massa": PrumoUtil.fmt(float(barra.Massa or 0.0), 3)}
    if campos:
        valores.update(campos)
    page = PrumoFolhas.nova_folha(doc, formato, norma, False, valores, None)
    page.Label = "Barra %s" % marca
    try:
        import PrumoPropriedades
        PrumoPropriedades.vincular_folha(page, barra)
        page.LegendaAutomatica = False          # a legenda da barra é a desta folha (marca e perfil)
    except Exception:
        pass
    reta = doc.addObject("Part::FeaturePython", "BarraReta")
    BarraReta(reta, barra)
    reta.Label = "Barra %s deitada" % marca
    _grupo_dados(doc).addObject(reta)
    doc.recompute()
    try:
        reta.ViewObject.Visibility = False
    except Exception:
        pass
    sh = reta.Shape
    bb = sh.BoundBox
    alt, larg = bb.ZLength, bb.YLength
    x0, x1, y0, y1 = _area_util(page)
    lado_secao = 62.0                            # faixa da direita para a seção ampliada
    largura_vistas = (x1 - x0) - lado_secao - 2 * ESPACO
    altura_vistas = (y1 - y0) - 3 * ESPACO
    e, tiradas = escolher_escala_e_quebras(sh, largura_vistas, altura_vistas)
    page.Scale = e
    PrumoFolhas.escrever_escala(page)
    q_frente = [_plano_da_quebra(doc, "XZ", a, b, alt / 2.0 + 5.0) for a, b in tiradas]
    q_topo = [_plano_da_quebra(doc, "XY", a, b, larg / 2.0 + 5.0) for a, b in tiradas]
    X, Y, Z = FreeCAD.Vector(1, 0, 0), FreeCAD.Vector(0, 1, 0), FreeCAD.Vector(0, 0, 1)
    frente = _vista_quebrada(doc, page, reta, Y.negative(), X, "VistaAlma", "Vista pela alma", q_frente)
    topo = _vista_quebrada(doc, page, reta, Z, X, "VistaTopo", "Vista de cima", q_topo)
    for v in (frente, topo):
        if tiradas:
            v.Gap = 8.0 / e
    # seção: olhando a ponta inicial, ampliada até ~45 mm de papel (nunca menor que a da folha)
    es = max(e, _escala_normal(45.0 / max(alt, larg, 1.0)))
    secao = _vista(doc, page, [reta], X.negative(), Y.negative(), "VistaSecao", "Seção", es)
    try:
        secao.Caption = "SEÇÃO — %s" % PrumoFolhas._texto_escala(es)
    except Exception:
        pass
    # 1º diedro: a vista de cima fica embaixo da vista pela alma
    cx = x0 + ESPACO + largura_vistas / 2.0
    meio = (y0 + y1) / 2.0
    bloco = (alt + larg) * e + ESPACO
    frente.X, frente.Y = cx, meio + bloco / 2.0 - alt * e / 2.0
    topo.X, topo.Y = cx, meio - bloco / 2.0 + larg * e / 2.0
    secao.X, secao.Y = x1 - lado_secao / 2.0, frente.Y
    doc.recompute()
    esperar_geometria([frente, topo, secao])
    # cotas: comprimento (em cima da vista pela alma) e furação nas duas vistas
    ex = PrumoVistas._extremos(frente, "x")
    if ex:
        PrumoVistas._cota(page, frente, "DistanceX", ex[0], ex[1], "Comprimento", "cima")
    for v in (frente, topo):
        try:
            PrumoVistas.cotas_de_furos(page, v)
        except Exception as exc:
            FreeCAD.Console.PrintLog("Usinix: furos na folha da barra: %s\n" % exc)
    massa = float(barra.Massa or 0.0)
    linhas = [("Marca", marca), ("Perfil", barra.Perfil), ("Material", barra.Material or "—"),
              ("Comprimento de corte", "%s mm" % _f(barra.ComprimentoCorte.Value)),
              ("Corte no início", _ang(barra.CorteInicio.Value)), ("Corte no fim", _ang(barra.CorteFim.Value)),
              ("Furação", getattr(barra, "Furacao", "") or "sem furos"), ("Quantidade", str(qtd)),
              ("Massa unitária", "%s kg" % PrumoUtil.fmt(massa, 2)),
              ("Massa total", "%s kg" % PrumoUtil.fmt(massa * qtd, 2))]
    if tiradas:
        linhas.append(("Vista", "interrompida (cotas em medida real)"))
    if (barra.SituacaoDados or "") not in ("", "confirmado"):
        linhas.append(("Observação", "perfil a conferir no catálogo"))
    tabela_na_folha(page, "DadosBarra_%s" % page.Name, "Barra %s" % marca, linhas)
    doc.recompute()
    return page


def folhas_das_barras(doc, objs, formato="A3", norma=None, prefixo=""):
    """Uma folha por barra diferente (marcas B01, B02…). Devolve [(folha, barra, quantidade)]."""
    lista = barras_para_folhas(objs)
    if not lista:
        raise ValueError("Escolha uma estrutura ou barras da estrutura.")
    n = len(lista)
    feitas = []
    for k, (b, q, _todas) in enumerate(lista, 1):
        marca = "B%02d" % k
        campos = {"folha": "%d / %d" % (k, n)}
        if prefixo:
            campos["numero"] = "%s-%s" % (prefixo.rstrip("-"), marca)
        page = folha_da_barra(doc, b, q, formato, norma, campos, marca)
        feitas.append((page, b, q))
    return feitas


# ============================================================================ chapa
def dobras_da_chapa(sh):
    """[(ângulo °, raio interno mm)] das dobras: pares de faces cilíndricas coaxiais (interna e externa)."""
    cil = []
    for f in sh.Faces:
        s = f.Surface
        if "Cylinder" not in type(s).__name__:
            continue
        try:
            u0, u1, _v0, _v1 = f.ParameterRange
        except Exception:
            continue
        ang = math.degrees(abs(u1 - u0))
        if ang >= 359.0:
            continue                      # furo ou eixo, não dobra
        cil.append((FreeCAD.Vector(s.Center), FreeCAD.Vector(s.Axis), float(s.Radius), ang))
    usados, dobras = set(), []
    for i, (c, a, r, ang) in enumerate(cil):
        if i in usados:
            continue
        par = [i]
        for j in range(i + 1, len(cil)):
            c2, a2, r2, ang2 = cil[j]
            if j in usados or abs(abs(a.dot(a2)) - 1.0) > 1e-6:
                continue
            d = c2 - c
            if (d - a * d.dot(a)).Length < 1e-4 and abs(ang - ang2) < 0.5:
                par.append(j)
        usados.update(par)
        dobras.append((round(ang, 1), round(min(cil[k][2] for k in par), 2)))
    return dobras


class Planificacao:
    """Planificação de uma peça de chapa, para a folha: acompanha a peça (recalcula quando ela muda)."""

    def __init__(self, obj, chapa=None, material="Aço carbono"):
        obj.Proxy = self
        obj.addProperty("App::PropertyLink", "Chapa", "Planificação", "Peça de chapa planificada")
        obj.addProperty("App::PropertyString", "MaterialK", "Planificação", "Tabela de fator K usada")
        obj.addProperty("App::PropertyInteger", "Dobras", "Planificação", "Quantidade de dobras")
        obj.setEditorMode("Dobras", 1)
        obj.Chapa = chapa
        obj.MaterialK = material

    def onDocumentRestored(self, obj):
        obj.Proxy = self

    def execute(self, obj):
        import Part
        face, linhas = forma_plana(obj.Chapa, obj.MaterialK)
        obj.Shape = Part.makeCompound([face] + list(linhas))
        obj.Dobras = len(linhas)

    def dumps(self):
        return None

    def loads(self, state):
        return None


def forma_plana(chapa, material="Aço carbono"):
    """(face no plano XY a partir de z = 0, linhas de dobra). Chapa sem dobra: a maior face plana, de frente."""
    import PrumoChapa
    sh = chapa.Shape
    if dobras_da_chapa(sh):
        forma, dobras, normal = PrumoChapa.planificar(chapa, material)
        return PrumoChapa._no_plano_xy(forma, dobras, normal)
    faces = [f for f in sh.Faces if "Plane" in type(f.Surface).__name__]
    if not faces:
        raise ValueError("%s não tem face plana." % chapa.Label)
    alvo = max(faces, key=lambda f: f.Area)
    normal = alvo.normalAt(0, 0)
    return PrumoChapa._no_plano_xy(sh, None, normal)


def espessura(chapa):
    import PrumoChapa
    t, _r = PrumoChapa.espessura_raio(chapa)
    if t:
        return t
    sh = chapa.Shape
    faces = [f for f in sh.Faces if "Plane" in type(f.Surface).__name__]
    if len(faces) >= 2:
        # distância da maior face à face paralela de frente para ela (o outro lado da chapa)
        a = max(faces, key=lambda f: f.Area)
        n = a.normalAt(0, 0)
        p = a.Vertexes[0].Point
        ds = []
        for f in faces:
            if f.isSame(a) or abs(abs(f.normalAt(0, 0).dot(n)) - 1.0) > 1e-6:
                continue
            d = abs((f.Vertexes[0].Point - p).dot(n))
            if d > 1e-4 and f.Area > 0.2 * a.Area:
                ds.append(d)
        if ds:
            return min(ds)
    return None


def folha_da_chapa(doc, chapa, formato="A3", norma=None, campos=None, material=None):
    """Folha ABNT da chapa planificada: vista de frente cotada (geral e furação), linhas de dobra, isométrica
    da peça e tabela (espessura, desenvolvimento, dobras). Devolve a folha."""
    import PrumoChapa
    import PrumoFolhas
    import PrumoVistas
    norma = norma or PrumoFolhas.NORMA_PADRAO
    if material is None:
        try:
            material = PrumoChapa.familia_do_material(PrumoUtil.material(chapa)[0])
        except Exception:
            material = "Aço carbono"
    pl = doc.addObject("Part::FeaturePython", "Planificacao")
    Planificacao(pl, chapa, material)
    pl.Label = "Planificação de %s" % chapa.Label
    _grupo_dados(doc).addObject(pl)
    doc.recompute()
    try:
        pl.ViewObject.Visibility = False
    except Exception:
        pass
    if pl.Shape.isNull():
        doc.removeObject(pl.Name)
        raise ValueError("Não foi possível planificar %s." % chapa.Label)
    page = PrumoFolhas.nova_folha(doc, formato, norma, False, campos, [chapa], arranjo="so_iso")
    page.Label = "Chapa %s" % chapa.Label
    bb = pl.Shape.BoundBox
    x0, x1, y0, y1 = _area_util(page)
    iso = PrumoVistas.iso_da_peca(page, [chapa])
    lado_iso = 95.0
    e = _escala_normal(min(((x1 - x0) - lado_iso - 2 * ESPACO) / max(bb.XLength, 1.0),
                           ((y1 - y0) - 2 * ESPACO) / max(bb.YLength, 1.0)))
    page.Scale = e
    PrumoFolhas.escrever_escala(page)
    plana = _vista(doc, page, [pl], FreeCAD.Vector(0, 0, 1), FreeCAD.Vector(1, 0, 0), "VistaPlanificada",
                   "Planificação")
    plana.X = x0 + ESPACO + ((x1 - x0) - lado_iso - 2 * ESPACO) / 2.0
    plana.Y = (y0 + y1) / 2.0
    if iso is not None:
        iso.ScaleType = "Custom"
        ib = chapa.Shape.BoundBox
        iso.Scale = _escala_normal(70.0 / max(ib.DiagonalLength, 1.0))
        iso.X, iso.Y = x1 - lado_iso / 2.0, y1 - 45.0
        iso.touch()                 # sem tocar, a vista fica com o desenho da escala antiga
    doc.recompute()
    esperar_geometria([plana])
    if iso is not None:
        _refazer_na_escala(iso)
    for eixo, lado, rot in (("x", "cima", "Largura"), ("y", "esq", "Altura")):
        ex = PrumoVistas._extremos(plana, eixo)
        if ex:
            PrumoVistas._cota(page, plana, "DistanceX" if eixo == "x" else "DistanceY", ex[0], ex[1],
                              "%s planificada" % rot, lado)
    try:
        PrumoVistas.cotas_de_furos(page, plana)
    except Exception as exc:
        FreeCAD.Console.PrintLog("Usinix: furos na folha da chapa: %s\n" % exc)
    t = espessura(chapa)
    dobras = dobras_da_chapa(chapa.Shape)
    linhas = [("Peça", chapa.Label), ("Material", PrumoUtil.material(chapa)[0] or "—"),
              ("Espessura", "%s mm" % _f(t, 2) if t else "—"),
              ("Desenvolvimento", "%s × %s mm" % (_f(bb.XLength), _f(bb.YLength))),
              ("Dobras", str(len(dobras)) if dobras else "sem dobras")]
    for k, (ang, r) in enumerate(dobras, 1):
        linhas.append(("Dobra %d" % k, "%s° · raio interno %s mm" % (PrumoUtil.fmt_dim(ang), _f(r, 2))))
    if dobras:
        _t, r = PrumoChapa.espessura_raio(chapa)
        if t and r is not None:
            linhas.append(("Fator K (%s)" % material, PrumoUtil.fmt(PrumoChapa.k_fator(material, r, t), 3)))
        linhas.append(("Linhas de dobra", "traço fino na planificação"))
    tabela_na_folha(page, "DadosChapa_%s" % page.Name, "Chapa %s" % chapa.Label, linhas)
    doc.recompute()
    return page


# ============================================================================ interface
try:
    import FreeCADGui
    from PySide import QtWidgets
except ImportError:      # sem interface
    FreeCADGui = None


def _sel():
    return [s.Object for s in FreeCADGui.Selection.getSelectionEx()]


def _aviso(titulo, texto):
    QtWidgets.QMessageBox.information(FreeCADGui.getMainWindow(), titulo, texto)


def _abrir(page):
    try:
        from PySide import QtCore
        import PrumoFolhas
        QtCore.QTimer.singleShot(0, lambda: PrumoFolhas._abrir_folha(page))
    except Exception:
        pass


class CmdFolhasBarras:
    def GetResources(self):
        return {"Pixmap": PrumoUtil.icone("folha_barra.svg"), "MenuText": "Folhas das barras",
                "ToolTip": "Uma folha ABNT por barra diferente da estrutura selecionada: barra deitada, seção "
                           "ampliada, comprimento, ângulos das pontas, furação cotada, quantidade e massa."}

    def IsActive(self):
        return FreeCAD.ActiveDocument is not None

    def Activated(self):
        import PrumoEstrutura as E
        doc = FreeCAD.ActiveDocument
        objs = _sel() or [o for o in doc.Objects if E.eh_estrutura(o)]
        if not barras_para_folhas(objs):
            _aviso("Folhas das barras", "Selecione a estrutura (ou as barras) para fazer as folhas.")
            return None
        doc.openTransaction("Folhas das barras")
        try:
            feitas = folhas_das_barras(doc, objs)
        except ValueError as ex:
            doc.abortTransaction()
            _aviso("Folhas das barras", str(ex))
            return None
        doc.commitTransaction()
        if feitas:
            _abrir(feitas[0][0])
        FreeCAD.Console.PrintMessage("Usinix: %d folha(s) de barra.\n" % len(feitas))
        return feitas


class CmdFolhaChapa:
    def GetResources(self):
        return {"Pixmap": PrumoUtil.icone("folha_chapa.svg"), "MenuText": "Folha da chapa",
                "ToolTip": "Folha ABNT da peça de chapa selecionada: planificação cotada com a furação, linhas "
                           "de dobra, isométrica e tabela com espessura, desenvolvimento e dobras."}

    def IsActive(self):
        return FreeCAD.ActiveDocument is not None

    def Activated(self):
        doc = FreeCAD.ActiveDocument
        sel = [o for o in _sel() if getattr(o, "Shape", None) is not None and o.Shape.Solids]
        if not sel:
            _aviso("Folha da chapa", "Selecione a peça de chapa (dobrada ou plana).")
            return None
        doc.openTransaction("Folha da chapa")
        try:
            pages = [folha_da_chapa(doc, o) for o in sel]
        except Exception as ex:
            doc.abortTransaction()
            _aviso("Folha da chapa", str(ex))
            return None
        doc.commitTransaction()
        _abrir(pages[0])
        return pages


def registrar_comandos():
    if FreeCADGui is not None:
        FreeCADGui.addCommand("Prumo_FolhasBarras", CmdFolhasBarras())
        FreeCADGui.addCommand("Prumo_FolhaChapa", CmdFolhaChapa())
