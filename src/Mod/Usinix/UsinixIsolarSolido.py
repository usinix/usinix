# -*- coding: utf-8 -*-
# Usinix: isolar um sólido de um corpo com vários (3 suportes iguais modelados num corpo só) para desenhar só ele.
#
# O filtro de sólidos do FreeCAD "adota" o corpo de origem na árvore e o corpo parece ter sumido. Este objeto só
# aponta para o corpo (não o contém) e escolhe o sólido pelo ponto de referência (o centro de massa guardado), não
# pela ordem dentro do corpo: incluir ou apagar outro sólido antes dele não troca a peça desenhada.
import FreeCAD

import UsinixUtil


class SolidoIsolado:
    Type = "SolidoIsolado"
    AUXILIAR = True          # cópia para o desenho: a peça da lista de materiais continua sendo o corpo

    def __init__(self, obj):
        obj.addProperty("App::PropertyLink", "Base", "Sólido isolado", "Corpo ou peça com vários sólidos")
        obj.addProperty("App::PropertyVector", "PontoReferencia", "Sólido isolado",
                        "Centro de massa do sólido escolhido (o mais próximo é o desenhado)")
        obj.addProperty("App::PropertyInteger", "Indice", "Sólido isolado", "Posição atual do sólido na peça")
        obj.addProperty("App::PropertyInteger", "Iguais", "Sólido isolado",
                        "Quantos sólidos da peça têm o mesmo volume (para a quantidade no desenho)")
        for p in ("Indice", "Iguais"):
            obj.setEditorMode(p, 1)
        obj.Proxy = self

    def execute(self, obj):
        if obj.Base is None:
            return
        sols = obj.Base.Shape.Solids
        if not sols:
            raise ValueError("%s não tem sólido" % obj.Base.Label)
        ref = obj.PontoReferencia
        k = min(range(len(sols)), key=lambda i: (sols[i].CenterOfMass - ref).Length)
        s = sols[k]
        obj.Shape = s.copy()
        obj.Indice = k
        v = s.Volume
        obj.Iguais = sum(1 for x in sols if abs(x.Volume - v) <= 1e-6 * max(1.0, v))

    def onDocumentRestored(self, obj):
        obj.Proxy = self

    def dumps(self):
        return None

    def loads(self, _estado):
        return None


class VPSolidoIsolado:
    def __init__(self, vobj):
        vobj.Proxy = self

    def attach(self, vobj):
        self.Object = vobj.Object

    def getIcon(self):
        return UsinixUtil.icone("isolar_solido.svg")

    def claimChildren(self):
        return []                # não adota o corpo: ele continua onde está na árvore

    def dumps(self):
        return None

    def loads(self, _estado):
        return None


def isolar(base, indice=None, ponto=None, rotulo=None):
    """Objeto com um sólido de `base`: pelo índice (0 = primeiro) ou pelo sólido mais perto de `ponto`."""
    sols = base.Shape.Solids
    if len(sols) < 1:
        raise ValueError("%s não tem sólido" % base.Label)
    if ponto is None:
        if indice is None:
            raise ValueError("informe o sólido (índice ou um ponto dele)")
        if not 0 <= int(indice) < len(sols):
            raise ValueError("%s tem %d sólido(s): índice de 0 a %d" % (base.Label, len(sols), len(sols) - 1))
        ponto = sols[int(indice)].CenterOfMass
    doc = base.Document
    o = doc.addObject("Part::FeaturePython", "SolidoIsolado")
    SolidoIsolado(o)
    o.Base = base
    o.PontoReferencia = FreeCAD.Vector(ponto)
    if FreeCAD.GuiUp:
        VPSolidoIsolado(o.ViewObject)
    doc.recompute()
    o.Label = rotulo or UsinixUtil.rotulo_unico(doc, "%s – sólido %d de %d" % (base.Label, o.Indice + 1, len(sols)))
    if FreeCAD.GuiUp:
        try:
            o.ViewObject.Visibility = False      # para o desenho; o corpo continua aparecendo na tela
        except Exception:
            pass
    return o


def _selecao():
    """(objeto, ponto) da seleção: o sólido que contém a face/aresta/vértice escolhido."""
    import FreeCADGui
    for s in FreeCADGui.Selection.getSelectionEx():
        o = s.Object
        try:
            if len(o.Shape.Solids) < 2:
                continue
        except Exception:
            continue
        if s.SubObjects:
            sub = s.SubObjects[0]
            c = sub.CenterOfMass if hasattr(sub, "CenterOfMass") else sub.Point
            for sol in o.Shape.Solids:
                if sol.isInside(c, 1e-6, True) or sol.distToShape(sub)[0] < 1e-6:
                    return o, sol.CenterOfMass
        return o, None
    return None, None


class CmdIsolarSolido:
    def GetResources(self):
        return {"Pixmap": UsinixUtil.icone("isolar_solido.svg"), "MenuText": "Isolar sólido para desenho",
                "ToolTip": "Num corpo com vários sólidos (peças iguais modeladas juntas), escolha uma face de um "
                           "deles: o Usinix cria uma cópia ligada só daquele sólido para pôr na folha. O corpo "
                           "continua na árvore e na lista de materiais; a cópia acompanha as mudanças nele."}

    def IsActive(self):
        try:
            o, _p = _selecao()
            return o is not None
        except Exception:
            return False

    def Activated(self):
        import FreeCADGui
        from PySide import QtWidgets
        o, ponto = _selecao()
        if o is None:
            return
        if ponto is None:
            QtWidgets.QMessageBox.information(FreeCADGui.getMainWindow(), "Isolar sólido",
                                              "Escolha uma face, aresta ou vértice do sólido que vai para o desenho.")
            return
        doc = o.Document
        doc.openTransaction("Isolar sólido")
        try:
            n = isolar(o, ponto=ponto)
            doc.commitTransaction()
        except Exception as exc:
            doc.abortTransaction()
            QtWidgets.QMessageBox.warning(FreeCADGui.getMainWindow(), "Isolar sólido", str(exc))
            return
        FreeCADGui.Selection.clearSelection()
        FreeCADGui.Selection.addSelection(n)


def registrar_comandos():
    import FreeCADGui
    FreeCADGui.addCommand("Usinix_IsolarSolido", CmdIsolarSolido())
