# -*- coding: utf-8 -*-
# Usinix: esqueleto de barras para a simulação (MEF com vigas), ligado à estrutura soldada.
#
# Antes o esqueleto do estudo de vigas era uma geometria fixa: mudar a estrutura (os vãos das travessas da Grade,
# por exemplo) deixava o MEF com as barras na posição antiga, sem aviso. Este objeto refaz as linhas a partir da
# estrutura a cada recálculo; a bancada e o assistente avisam que a malha e o resultado ficaram velhos.
import FreeCAD

import UsinixUtil

ROTULO = "Esqueleto MEF"


def linhas(est):
    """Linhas das barras da estrutura (só as que têm barra), partidas nos cruzamentos para os nós ligarem."""
    import Part
    import UsinixEstrutura as E
    eds = [e for e in E.arestas_ativas(est) if e is not None]
    if not eds:
        return Part.Shape()
    if len(eds) == 1:
        return Part.Compound(eds)
    try:
        partes = eds[0].generalFuse(eds[1:])[0]
        return Part.Compound([e for e in partes.Edges if e.Length > E.TOL])
    except Exception:
        return Part.Compound(eds)


class EsqueletoMEF:
    Type = "EsqueletoMEF"
    AUXILIAR = True          # objeto de apoio: fora da lista de materiais e das folhas

    def __init__(self, obj):
        obj.addProperty("App::PropertyLink", "Estrutura", "Esqueleto MEF",
                        "Estrutura soldada de onde saem as linhas (acompanha as mudanças dela)")
        obj.addProperty("App::PropertyInteger", "Barras", "Esqueleto MEF", "Linhas depois de partir nos cruzamentos")
        obj.setEditorMode("Barras", 1)
        obj.Proxy = self

    def execute(self, obj):
        est = obj.Estrutura
        if est is None:
            return
        obj.Shape = linhas(est)
        obj.Barras = len(obj.Shape.Edges)

    def onDocumentRestored(self, obj):
        obj.Proxy = self

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
