# -*- coding: utf-8 -*-
# Usinix: esqueleto de barras para a simulação (MEF com vigas), ligado à estrutura soldada.
#
# Antes o esqueleto do estudo de vigas era uma geometria fixa: mudar a estrutura (os vãos das travessas da Grade,
# por exemplo) deixava o MEF com as barras na posição antiga, sem aviso. Este objeto refaz as linhas a partir da
# estrutura a cada recálculo; a bancada e o assistente avisam que a malha e o resultado ficaram velhos.
import FreeCAD

import UsinixUtil

ROTULO = "Esqueleto MEF"


def _offset_centroide(est, ativas, i, normal):
    """Vetor da linha do esboço até o centroide da seção da barra i (fixação, giro e espelhamento já aplicados)."""
    import UsinixEstrutura as E
    sec = E.Secao(est, ativas, i, normal)
    cu, cv = E.deslocamento(sec.it, "Centroide", sec.espelhar)     # centro da caixa em relação ao centroide
    return sec.u * (sec.du - cu) + sec.v * (sec.dv - cv)


def _intersecao_no_plano(p0, d0, p1, d1, normal):
    """Ponto da reta (p0, d0) onde ela cruza a reta (p1, d1), as duas vistas no plano de normal `normal`."""
    n = FreeCAD.Vector(normal)
    w = p1 - p0
    a, b = d0 - n * d0.dot(n), d1 - n * d1.dot(n)
    w = w - n * w.dot(n)
    cr = a.cross(b)
    den = cr.dot(n)
    if abs(den) < 1e-9 * max(1.0, a.Length * b.Length):
        return None
    t = w.cross(b).dot(n) / den
    return p0 + d0 * t


def linhas(est, eixo_real=True):
    """Linhas das barras da estrutura, partidas nos cruzamentos para os nós ligarem.

    eixo_real: cada barra vai para o eixo do centroide da seção (no contorno com fixação "Meio direito" o tubo
    fica 20 mm para dentro da linha do esboço); nas ligações a ponta encontra o eixo da barra vizinha no plano.
    Diferença de altura entre os eixos (excentricidade fora do plano) não é modelada: fica em Excentricidades."""
    import Part
    import UsinixEstrutura as E
    ativas = E.arestas_ativas(est)
    idx = [i for i, e in enumerate(ativas) if e is not None]
    if not idx:
        return Part.Shape(), []
    normal = E._normal_esqueleto(ativas)
    segs = []
    excent = []
    if eixo_real and normal is not None:
        off = {}
        for i in idx:
            try:
                off[i] = _offset_centroide(est, ativas, i, normal)
            except Exception:
                off[i] = FreeCAD.Vector()
        n = FreeCAD.Vector(normal).normalize()
        for i in idx:
            e = ativas[i]
            p0, p1 = e.Vertexes[0].Point, e.Vertexes[-1].Point
            d = p1 - p0
            if d.Length < E.TOL:
                continue
            d.normalize()
            o = off[i]
            novos = []
            for p in (p0, p1):
                q = p + o
                vizinhas = [j for j in idx if j != i and
                            ativas[j].distToShape(Part.Vertex(p))[0] < 1e-6]
                melhor = None
                for j in vizinhas:
                    ej = ativas[j]
                    dj = ej.Vertexes[-1].Point - ej.Vertexes[0].Point
                    if dj.Length < E.TOL or abs(dj.normalize().dot(d)) > 0.999:
                        continue                          # colinear: não define a ponta
                    x = _intersecao_no_plano(p + o, d, ej.Vertexes[0].Point + off[j], dj, n)
                    if x is not None and (melhor is None or (x - q).Length < (melhor - q).Length):
                        melhor = x
                novos.append(melhor if melhor is not None else q)
            segs.append(Part.makeLine(novos[0], novos[1]))
            h = o.dot(n)
            if abs(h) > 0.5:
                excent.append("Linha %d: %s mm fora do plano" % (i + 1, ("%.1f" % h).replace(".", ",")))
    else:
        segs = [ativas[i] for i in idx]
    alturas = {round(s.Vertexes[0].Point.dot(FreeCAD.Vector(normal).normalize()), 1) for s in segs} \
        if normal is not None else set()
    if len(alturas) > 1:
        # eixos em alturas diferentes não se cruzam: leva tudo para o plano do primeiro (a excentricidade fica
        # registrada) para os nós ligarem
        n = FreeCAD.Vector(normal).normalize()
        h0 = segs[0].Vertexes[0].Point.dot(n)
        segs = [Part.makeLine(sg.Vertexes[0].Point - n * (sg.Vertexes[0].Point.dot(n) - h0),
                              sg.Vertexes[-1].Point - n * (sg.Vertexes[-1].Point.dot(n) - h0)) for sg in segs]
    if len(segs) == 1:
        return Part.Compound(segs), excent
    try:
        partes = segs[0].generalFuse(segs[1:], 1e-3)[0]
        return Part.Compound([e for e in partes.Edges if e.Length > E.TOL]), excent
    except Exception:
        return Part.Compound(segs), excent


class EsqueletoMEF:
    Type = "EsqueletoMEF"
    AUXILIAR = True          # objeto de apoio: fora da lista de materiais e das folhas

    def __init__(self, obj):
        obj.addProperty("App::PropertyLink", "Estrutura", "Esqueleto MEF",
                        "Estrutura soldada de onde saem as linhas (acompanha as mudanças dela)")
        obj.addProperty("App::PropertyInteger", "Barras", "Esqueleto MEF", "Linhas depois de partir nos cruzamentos")
        obj.setEditorMode("Barras", 1)
        self._props(obj)
        obj.Proxy = self

    def _props(self, obj):
        if "EixoReal" not in obj.PropertiesList:
            obj.addProperty("App::PropertyBool", "EixoReal", "Esqueleto MEF",
                            "Linhas no eixo do centroide de cada barra (desligado: as linhas do esboço)")
            obj.EixoReal = True
        if "Excentricidades" not in obj.PropertiesList:
            obj.addProperty("App::PropertyStringList", "Excentricidades", "Esqueleto MEF",
                            "Barras com o eixo fora do plano das outras (não modelado: confira)")
            obj.setEditorMode("Excentricidades", 1)

    def execute(self, obj):
        est = obj.Estrutura
        if est is None:
            return
        self._props(obj)
        forma, exc = linhas(est, bool(obj.EixoReal))
        obj.Shape = forma
        obj.Barras = len(obj.Shape.Edges)
        if list(obj.Excentricidades) != exc:
            obj.Excentricidades = exc

    def onDocumentRestored(self, obj):
        obj.Proxy = self
        self._props(obj)

    def dumps(self):
        return None

    def loads(self, _estado):
        return None


class VPEsqueletoMEF:
    def __init__(self, vobj):
        vobj.Proxy = self

    def attach(self, vobj):
        self.Object = vobj.Object

    def getIcon(self):
        return UsinixUtil.icone("esqueleto_mef.svg")

    def claimChildren(self):
        return []

    def dumps(self):
        return None

    def loads(self, _estado):
        return None


def de(est):
    """Esqueleto MEF já ligado a esta estrutura, ou None."""
    for o in est.InList:
        if getattr(getattr(o, "Proxy", None), "Type", "") == EsqueletoMEF.Type and o.Estrutura == est:
            return o
    return None


def criar(est):
    """Esqueleto MEF da estrutura (reaproveita o que já existe)."""
    import UsinixEstrutura as E
    if not E.eh_estrutura(est):
        raise ValueError("escolha uma estrutura soldada")
    o = de(est)
    if o is not None:
        o.touch()
        est.Document.recompute()
        return o
    doc = est.Document
    o = doc.addObject("Part::FeaturePython", "EsqueletoMEF")
    EsqueletoMEF(o)
    o.Estrutura = est
    o.Label = "%s – %s" % (ROTULO, est.Label)
    if FreeCAD.GuiUp:
        VPEsqueletoMEF(o.ViewObject)
        try:
            o.ViewObject.LineWidth = 3.0
            o.ViewObject.LineColor = (0.0, 0.227, 0.439)
            o.ViewObject.PointSize = 6.0
        except Exception:
            pass
    doc.recompute()
    return o


class CmdEsqueletoMEF:
    def GetResources(self):
        return {"Pixmap": UsinixUtil.icone("esqueleto_mef.svg"), "MenuText": "Esqueleto da estrutura",
                "ToolTip": "Linhas das barras da estrutura soldada para o estudo de vigas (MEF), partidas nos "
                           "cruzamentos. Ficam ligadas à estrutura: mudou a estrutura, o esqueleto acompanha e a "
                           "bancada avisa que a malha e o resultado precisam ser refeitos."}

    def IsActive(self):
        return _estrutura_selecionada() is not None

    def Activated(self):
        est = _estrutura_selecionada()
        if est is None:
            return
        doc = est.Document
        doc.openTransaction("Esqueleto MEF")
        try:
            o = criar(est)
            doc.commitTransaction()
        except Exception as exc:
            doc.abortTransaction()
            from PySide import QtWidgets
            import FreeCADGui
            QtWidgets.QMessageBox.warning(FreeCADGui.getMainWindow(), "Esqueleto da estrutura", str(exc))
            return
        import FreeCADGui
        FreeCADGui.Selection.clearSelection()
        FreeCADGui.Selection.addSelection(o)


def _estrutura_selecionada():
    try:
        import FreeCADGui
        import UsinixEstrutura as E
        for o in FreeCADGui.Selection.getSelection():
            est = E.estrutura_de(o)
            if est is not None:
                return est
        doc = FreeCAD.ActiveDocument
        ests = [o for o in (doc.Objects if doc else []) if E.eh_estrutura(o)]
        return ests[0] if len(ests) == 1 else None
    except Exception:
        return None


def registrar_comandos():
    import FreeCADGui
    FreeCADGui.addCommand("Usinix_EsqueletoMEF", CmdEsqueletoMEF())
