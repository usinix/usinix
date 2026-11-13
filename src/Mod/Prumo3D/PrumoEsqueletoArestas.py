# SPDX-License-Identifier: LGPL-2.1-or-later
# Usinix - esqueleto da estrutura soldada tirado das arestas de um corpo (ligado a elas).
"""Esqueleto a partir de arestas.

Para a estrutura que segue um corpo — o quadro em volta de uma máquina, a moldura de uma base, o reforço ao longo
das arestas de uma caixa — as linhas de centro já existem: são arestas do corpo. Este objeto junta as arestas
escolhidas (de um ou mais corpos) e serve de esqueleto para a Estrutura soldada. É ligado às arestas: o corpo
mudou de medida, o esqueleto e as barras acompanham.

Uso: selecione as arestas na vista (Ctrl + clique) e clique em Estrutura soldada; o esqueleto é criado sozinho.
"""

import FreeCAD

try:
    import FreeCADGui
except ImportError:
    FreeCADGui = None


class EsqueletoArestas:
    def __init__(self, obj):
        obj.Proxy = self
        self._props(obj)

    def _props(self, obj):
        if "Arestas" not in obj.PropertiesList:
            obj.addProperty("App::PropertyLinkSubList", "Arestas", "Esqueleto",
                            "Arestas dos corpos que formam as linhas de centro")
        if "EsqueletoUsinix" not in obj.PropertiesList:
            obj.addProperty("App::PropertyBool", "EsqueletoUsinix", "Esqueleto", "Marca do objeto")
            obj.EsqueletoUsinix = True
            obj.setEditorMode("EsqueletoUsinix", 2)

    def onDocumentRestored(self, obj):
        obj.Proxy = self
        self._props(obj)

    def execute(self, obj):
        obj.Shape = forma(obj.Arestas)
        obj.Placement = FreeCAD.Placement()

    def dumps(self):
        return None

    def loads(self, state):
        return None


def forma(refs):
    """Compound das arestas referenciadas, no espaço global."""
    import Part
    eds = []
    for o, subs in refs or []:
        for sub in subs:
            if not sub.split(".")[-1].startswith("Edge"):
                continue
            try:
                e = Part.getShape(o, sub, needSubElement=True, transform=True)
            except Exception:
                e = o.Shape.getElement(sub.split(".")[-1])
            if not e.isNull() and e.Edges:
                eds.append(e.Edges[0].copy())
    if not eds:
        return Part.Shape()
    return Part.makeCompound(eds)


class VistaEsqueleto:
    def __init__(self, vobj):
        vobj.Proxy = self

    def attach(self, vobj):
        self.Object = vobj.Object

    def getIcon(self):
        import PrumoUtil
        return PrumoUtil.icone("estrutura.svg")

    def dumps(self):
        return None

    def loads(self, state):
        return None


def criar(refs, doc=None):
    """Esqueleto ligado às arestas `refs` = [(objeto, ("Edge1", ...)), ...]."""
    doc = doc or refs[0][0].Document
    o = doc.addObject("Part::FeaturePython", "EsqueletoArestas")
    EsqueletoArestas(o)
    o.Arestas = [(ob, tuple(subs)) for ob, subs in refs]
    o.Label = "Esqueleto (arestas de %s)" % ", ".join(sorted({ob.Label for ob, _s in refs}))
    if FreeCAD.GuiUp:
        VistaEsqueleto(o.ViewObject)
        try:
            o.ViewObject.LineWidth = 3
            o.ViewObject.LineColor = (0.97, 0.75, 0.0)
        except Exception:
            pass
    doc.recompute()
    return o


def arestas_selecionadas():
    """[(objeto, (EdgeN, ...))] das arestas selecionadas em sólidos (não em esboços nem em barras)."""
    if FreeCADGui is None:
        return []
    import PrumoEstrutura as E
    res = []
    for s in FreeCADGui.Selection.getSelectionEx("", 0):
        obj = s.Object
        subs = [n for n in s.SubElementNames if n.split(".")[-1].startswith("Edge")]
        if not subs or E.eh_estrutura(obj) or E.eh_barra(obj):
            continue
        # seleção dentro de contêiner (Body/Part): o objeto que tem a aresta, com o nome curto
        por_obj = {}
        for sub in subs:
            alvo, nome = obj, sub
            if "." in sub:
                try:
                    o2 = obj.getSubObject(sub, retType=1)
                    if o2 is not None:
                        alvo, nome = o2, sub.split(".")[-1]
                except Exception:
                    pass
            if E.eh_barra(alvo) or E.eh_estrutura(alvo):
                continue
            por_obj.setdefault(alvo, []).append(nome)
        res.extend((o, tuple(ns)) for o, ns in por_obj.items())
    return res
