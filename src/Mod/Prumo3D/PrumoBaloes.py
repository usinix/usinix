# SPDX-License-Identifier: LGPL-2.1-or-later
# Usinix - balões numerados ligados à lista de materiais.
"""Balões da montagem.

Um balão por item da lista de materiais, na vista escolhida (a isométrica, se houver; senão a frontal).
O número do balão é o número do item na lista: cada balão guarda a peça que aponta (propriedade PecaUsinix),
e "Atualizar balões" — chamado também pela Lista de materiais — refaz os números quando a lista muda.
Os balões ficam num anel em volta da vista, sem se sobrepor, com a seta numa face da peça virada para quem olha.
"""

import math

import FreeCAD

import PrumoUtil

PROP = "PecaUsinix"
AFASTAR_MM = 14.0          # do contorno da vista até o centro do balão, em mm de papel
ESPACO_MM = 11.0           # distância mínima entre dois balões, em mm de papel


def _escala(vista):
    try:
        return float(vista.getScale())
    except Exception:
        return float(getattr(vista, "Scale", 1.0) or 1.0)


def vista_padrao(page):
    """A isométrica da folha, se houver; senão a frontal do primeiro grupo; senão a primeira vista de peça."""
    partes = [v for v in page.Views if v.TypeId == "TechDraw::DrawViewPart"]
    for v in partes:
        d = v.Direction
        if abs(abs(d.x) - abs(d.y)) < 1e-6 and abs(abs(d.y) - abs(d.z)) < 1e-6:
            return v
    for g in page.Views:
        if g.isDerivedFrom("TechDraw::DrawProjGroup"):
            for v in g.Views:
                if v.Type == "Front":
                    return v
    return partes[0] if partes else None


def baloes_da_vista(vista):
    page = vista.findParentPage()
    return [b for b in (page.Views if page else []) if b.TypeId == "TechDraw::DrawViewBalloon"
            and b.SourceView == vista and PROP in b.PropertiesList]


def _escondido(p, direcao, outras):
    """O ponto p fica atrás de outra peça para quem olha de `direcao`?"""
    import Part
    tam = 1e5
    ini = p + direcao * 0.05
    raio = Part.LineSegment(ini, p + direcao * tam).toShape()
    bb = raio.BoundBox
    for sh in outras:
        if not sh.BoundBox.intersect(bb):
            continue
        try:
            if sh.distToShape(raio)[0] < 1e-4:
                return True
        except Exception:
            continue
    return False


def _ponto_na_peca(sh, direcao, outras=()):
    """Ponto de uma face da peça virada para quem olha e não escondida pelas outras peças (nem por ela
    mesma): é onde a seta do balão vai. Prefere faces grandes e bem de frente; amostra cada face numa grade
    para achar um pedaço à vista."""
    candidatos = []
    for f in sh.Faces:
        try:
            u0, u1, v0, v1 = f.ParameterRange
        except Exception:
            continue
        for fu, fv in ((0.5, 0.5), (0.3, 0.3), (0.7, 0.3), (0.3, 0.7), (0.7, 0.7), (0.5, 0.15), (0.5, 0.85),
                       (0.15, 0.5), (0.85, 0.5)):
            u, v = u0 + (u1 - u0) * fu, v0 + (v1 - v0) * fv
            try:
                p = f.valueAt(u, v)
                if not f.isInside(p, 1e-4, True):
                    continue
                n = f.normalAt(u, v)
            except Exception:
                continue
            if f.Orientation == "Reversed":
                n = n.negative()
            frente = n.dot(direcao)
            if frente <= 0.2:
                continue
            # o centro da face vale um pouco mais (a seta fica no meio da face, não na beira)
            candidatos.append((frente * f.Area * (1.15 if (fu, fv) == (0.5, 0.5) else 1.0), p))
    candidatos.sort(key=lambda t: -t[0])
    tapam = list(outras) + [sh]
    for _nota, p in candidatos[:40]:
        if not _escondido(p, direcao, tapam):
            return p
    return candidatos[0][1] if candidatos else sh.BoundBox.Center


def _ancora(vista, ponto):
    """Ponto 3D -> coordenadas da vista (sem escala), como o TechDraw centra a peça."""
    c = vista.getGeometricCenter()
    a = vista.projectPoint(ponto)
    b = vista.projectPoint(c)
    return FreeCAD.Vector(a.x - b.x, a.y - b.y, 0)


def _espalhar(angulos, minimo):
    """Afasta ângulos (em radianos, num círculo) para que dois vizinhos fiquem a pelo menos `minimo`."""
    n = len(angulos)
    if n < 2:
        return list(angulos)
    if minimo * n >= 2 * math.pi:            # não cabe: distribui por igual, na ordem dos ângulos
        ordem = sorted(range(n), key=lambda i: angulos[i])
        r = [0.0] * n
        for k, i in enumerate(ordem):
            r[i] = angulos[ordem[0]] + 2 * math.pi * k / n
        return r
    ordem = sorted(range(n), key=lambda i: angulos[i])
    a = [angulos[i] for i in ordem]
    for _ in range(200):
        mexeu = False
        for i in range(n):
            j = (i + 1) % n
            gap = (a[j] - a[i]) % (2 * math.pi)
            if gap < minimo - 1e-9:
                falta = (minimo - gap) / 2.0
                a[i] -= falta
                a[j] += falta
                mexeu = True
        if not mexeu:
            break
    r = [0.0] * n
    for k, i in enumerate(ordem):
        r[i] = a[k]
    return r


def criar_baloes(page, vista=None, objs=None):
    """Um balão por item da lista de materiais das peças da vista. Refaz os balões que o Usinix já tinha
    posto nessa vista. Devolve [(balão, nº do item)]."""
    import PrumoBOM
    vista = vista or vista_padrao(page)
    if vista is None:
        raise ValueError("A folha não tem vista de peça para os balões. Ponha a montagem na folha primeiro.")
    objs = list(objs or vista.Source)
    mapa = {}
    linhas = PrumoBOM.coletar(objs, mapa=mapa)
    if not linhas:
        raise ValueError("Nenhuma peça na vista para numerar.")
    doc = page.Document
    for b in baloes_da_vista(vista):
        doc.removeObject(b.Name)
    direcao = FreeCAD.Vector(vista.Direction).normalize()
    # uma peça por item: a primeira que a lista contou
    por_item = {}
    for (dn, nome), (n, sh) in mapa.items():
        o = FreeCAD.getDocument(dn).getObject(nome)
        if o is not None and n not in por_item:
            por_item[n] = (o, sh)
    e = _escala(vista)
    todas = [sh for _o, sh in PrumoUtil.pecas(objs)]
    ancoras = {}
    for n, (o, sh) in por_item.items():
        outras = [s for s in todas if not s.isSame(sh)]
        ancoras[n] = _ancora(vista, _ponto_na_peca(sh, direcao, outras))
    # anel em volta do contorno da vista (coordenadas sem escala, como OriginX/X do balão)
    xs, ys = [], []
    i = 0
    while i < 20000:
        try:
            v = vista.getVertexByIndex(i)
        except Exception:
            break
        if v is None:
            break
        xs.append(v.Point.x)
        ys.append(v.Point.y)
        i += 1
    if xs:
        raio = math.hypot(max(abs(min(xs)), abs(max(xs))), max(abs(min(ys)), abs(max(ys)))) * 0.85
    else:
        raio = max((a.Length for a in ancoras.values()), default=20.0)
    raio += AFASTAR_MM / e
    itens = sorted(ancoras)
    angulos = [math.atan2(ancoras[n].y, ancoras[n].x) if ancoras[n].Length > 1e-6 else math.pi / 2
               for n in itens]
    angulos = _espalhar(angulos, (ESPACO_MM / e) / raio)
    feitos = []
    for n, ang in zip(itens, angulos):
        o, _sh = por_item[n]
        a = ancoras[n]
        b = doc.addObject("TechDraw::DrawViewBalloon", "Balao")
        b.addProperty("App::PropertyLinkGlobal", PROP, "Usinix", "Peça que o balão numera (item da lista de materiais)")
        setattr(b, PROP, o)
        b.SourceView = vista
        b.Text = str(n)
        b.Label = "Balão %d" % n
        b.OriginX, b.OriginY = a.x, a.y
        b.X, b.Y = raio * math.cos(ang), raio * math.sin(ang)
        try:
            b.BubbleShape = "Circular"
            b.EndType = "Dot"
        except Exception:
            pass
        page.addView(b)
        feitos.append((b, n))
    doc.recompute()
    return feitos


def atualizar_baloes(doc):
    """Refaz o número de cada balão do Usinix pela lista de materiais atual. Devolve quantos mudaram."""
    import PrumoBOM
    mudou = 0
    por_vista = {}
    for b in doc.Objects:
        if b.TypeId == "TechDraw::DrawViewBalloon" and PROP in b.PropertiesList and b.SourceView is not None:
            por_vista.setdefault(b.SourceView.Name, []).append(b)
    for nome, bs in por_vista.items():
        vista = doc.getObject(nome)
        mapa = {}
        try:
            PrumoBOM.coletar(list(vista.Source), mapa=mapa)
        except Exception:
            continue
        for b in bs:
            o = getattr(b, PROP)
            if o is None:
                continue
            n = mapa.get((o.Document.Name, o.Name), (None, None))[0]
            texto = str(n) if n is not None else "?"
            if b.Text != texto:
                b.Text = texto
                mudou += 1
    if mudou:
        doc.recompute()
    return mudou


# ============================================================================ interface
try:
    import FreeCADGui
    from PySide import QtWidgets
except ImportError:      # sem interface
    FreeCADGui = None


class CmdBaloes:
    def GetResources(self):
        return {"Pixmap": PrumoUtil.icone("baloes.svg"), "MenuText": "Balões da lista",
                "ToolTip": "Põe um balão numerado em cada peça da vista (a isométrica, ou a selecionada), com o "
                           "número do item da lista de materiais. Os números se atualizam com a lista."}

    def IsActive(self):
        doc = FreeCAD.ActiveDocument
        return doc is not None and any(o.isDerivedFrom("TechDraw::DrawPage") for o in doc.Objects)

    def Activated(self):
        import PrumoVistas
        sel = [s.Object for s in FreeCADGui.Selection.getSelectionEx()]
        vista = next((o for o in sel if o.isDerivedFrom("TechDraw::DrawViewPart")), None)
        page = vista.findParentPage() if vista is not None else PrumoVistas.folha_ativa()
        if page is None:
            fs = PrumoVistas.folhas(FreeCAD.ActiveDocument)
            page = fs[0] if len(fs) == 1 else None
        if page is None:
            QtWidgets.QMessageBox.information(FreeCADGui.getMainWindow(), "Balões",
                                              "Abra a folha da montagem (clique na aba dela, embaixo da tela).")
            return None
        doc = page.Document
        doc.openTransaction("Balões")
        try:
            feitos = criar_baloes(page, vista)
        except ValueError as ex:
            doc.abortTransaction()
            QtWidgets.QMessageBox.information(FreeCADGui.getMainWindow(), "Balões", str(ex))
            return None
        doc.commitTransaction()
        FreeCAD.Console.PrintMessage("Usinix: %d balão(ões) na folha %s.\n" % (len(feitos), page.Label))
        return feitos


def registrar_comandos():
    if FreeCADGui is not None:
        FreeCADGui.addCommand("Prumo_Baloes", CmdBaloes())
