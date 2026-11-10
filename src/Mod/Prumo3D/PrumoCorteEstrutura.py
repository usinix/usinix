# SPDX-License-Identifier: LGPL-2.1-or-later
# Usinix - corte ou furo feito uma vez e aplicado em várias barras da estrutura (como o "escopo" do SolidWorks).
"""Cortar barras.

Um corte da estrutura usa uma ferramenta — um sólido qualquer (extrusão, cilindro, caixa, peça) ou um esboço
fechado, que vira uma extrusão que atravessa a estrutura — e tira esse volume de todas as barras do escopo.
O escopo é a lista de barras que o corte atinge: escolhida à mão ou, se nenhuma for escolhida, todas as barras
que a ferramenta atravessa. Tudo fica ligado: mexeu no esboço ou moveu a ferramenta, as barras se refazem; a
folha de cada barra e a lista de materiais já saem com o recorte.

Cada barra guarda os cortes que a atingem (propriedade CortesEstrutura): a barra depende do corte, e o corte da
ferramenta, sem ciclo. A ferramenta fica escondida e aparece na árvore dentro do corte.
"""

import os

import FreeCAD

AQUI = os.path.dirname(os.path.abspath(__file__))


def _e_esboco(o):
    try:
        return o.isDerivedFrom("Sketcher::SketchObject") or (
            not getattr(o, "Shape", None) is None and not o.Shape.Solids and o.Shape.Wires
            and all(w.isClosed() for w in o.Shape.Wires))
    except Exception:
        return False


def forma_ferramenta(corte):
    """Sólido da ferramenta, no espaço global."""
    import PrumoUtil
    f = corte.Ferramenta
    if f is None:
        return None
    sh = PrumoUtil.forma_global(f)
    if sh.isNull() or not sh.Solids:
        return None
    return sh


def barras_do_documento(doc):
    import PrumoEstrutura as E
    return [o for o in doc.Objects if E.eh_barra(o)]


def barras_atingidas(ferramenta_sh, barras):
    """Barras que a ferramenta atravessa (volume em comum)."""
    res = []
    for b in barras:
        try:
            sh = b.Shape
            if sh.isNull() or not ferramenta_sh.BoundBox.intersect(sh.BoundBox):
                continue
            if sh.common(ferramenta_sh).Volume > 1e-3:
                res.append(b)
        except Exception:
            continue
    return res


def _sem_este_corte(b, corte):
    return [c for c in (b.CortesEstrutura or []) if c is not None and c != corte]


def definir_escopo(corte, barras):
    """Liga o corte às barras dadas e desliga das que saíram do escopo."""
    doc = corte.Document
    novas = {b.Name for b in barras}
    for b in barras_do_documento(doc):
        tem = corte in (b.CortesEstrutura or [])
        if b.Name in novas and not tem:
            b.CortesEstrutura = _sem_este_corte(b, corte) + [corte]
            b.touch()
        elif b.Name not in novas and tem:
            b.CortesEstrutura = _sem_este_corte(b, corte)
            b.touch()
    corte.Escopo = sorted(novas)


def barras_do_corte(corte):
    doc = corte.Document
    return [b for b in barras_do_documento(doc) if corte in (b.CortesEstrutura or [])]


def ferramenta_de_esboco(doc, esboco, barras=()):
    """Extrusão que atravessa a estrutura: o esboço puxado para os dois lados, pela normal dele."""
    diag = 1000.0
    bb = FreeCAD.BoundBox()
    for b in barras or barras_do_documento(doc):
        try:
            bb.add(b.Shape.BoundBox)
        except Exception:
            pass
    if bb.isValid():
        diag = max(diag, bb.DiagonalLength * 1.2)
    ex = doc.addObject("Part::Extrusion", "FerramentaCorte")
    ex.Base = esboco
    ex.DirMode = "Normal"
    ex.Symmetric = True
    ex.LengthFwd = diag
    ex.Solid = True
    ex.Label = "Ferramenta (%s)" % esboco.Label
    return ex


class CorteEstrutura:
    def __init__(self, obj):
        obj.Proxy = self
        self._props(obj)

    def _props(self, obj):
        if "Ferramenta" not in obj.PropertiesList:
            obj.addProperty("App::PropertyLink", "Ferramenta", "Corte", "Sólido que é tirado das barras")
        if "Escopo" not in obj.PropertiesList:
            obj.addProperty("App::PropertyStringList", "Escopo", "Corte", "Barras atingidas (nomes)")
            obj.setEditorMode("Escopo", 1)
        if "Automatico" not in obj.PropertiesList:
            obj.addProperty("App::PropertyBool", "Automatico", "Corte",
                            "Escopo = todas as barras que a ferramenta atravessa (refeito ao editar)")
        if "Resumo" not in obj.PropertiesList:
            obj.addProperty("App::PropertyString", "Resumo", "Corte", "Quantas barras o corte atinge")
            obj.setEditorMode("Resumo", 1)

    def onDocumentRestored(self, obj):
        obj.Proxy = self
        self._props(obj)

    def execute(self, obj):
        n = len(obj.Escopo)
        obj.Resumo = "%d barra%s" % (n, "" if n == 1 else "s")


def criar(doc, ferramenta, barras=None, automatico=None):
    """Cria o corte. ferramenta: sólido ou esboço fechado; barras: escopo (None = as que a ferramenta atravessa)."""
    if ferramenta is None:
        raise ValueError("Escolha a ferramenta do corte: um sólido ou um esboço fechado.")
    if _e_esboco(ferramenta):
        ferramenta = ferramenta_de_esboco(doc, ferramenta, barras or ())
        doc.recompute()
    import PrumoUtil
    sh = PrumoUtil.forma_global(ferramenta)
    if sh.isNull() or not sh.Solids:
        raise ValueError("A ferramenta \"%s\" não é um sólido." % ferramenta.Label)
    automatico = (not barras) if automatico is None else bool(automatico)
    alvo = barras_atingidas(sh, barras if barras else barras_do_documento(doc))
    if not alvo:
        raise ValueError("A ferramenta não atravessa nenhuma barra%s." % (" escolhida" if barras else ""))
    c = doc.addObject("App::FeaturePython", "CorteBarras")
    CorteEstrutura(c)
    c.Ferramenta = ferramenta
    c.Automatico = automatico
    c.Label = "Corte em %d barra%s" % (len(alvo), "" if len(alvo) == 1 else "s")
    if FreeCAD.GuiUp:
        VistaCorte(c.ViewObject)
        try:
            ferramenta.ViewObject.Visibility = False
            if getattr(ferramenta, "Base", None) is not None:
                ferramenta.Base.ViewObject.Visibility = False
        except Exception:
            pass
    definir_escopo(c, alvo)
    doc.recompute()
    return c


def editar(corte, ferramenta=None, barras=None):
    """Troca a ferramenta e/ou refaz o escopo (automático: as barras que a ferramenta atravessa agora)."""
    doc = corte.Document
    if ferramenta is not None and ferramenta != corte.Ferramenta:
        if _e_esboco(ferramenta):
            ferramenta = ferramenta_de_esboco(doc, ferramenta, barras or ())
            doc.recompute()
        corte.Ferramenta = ferramenta
    sh = forma_ferramenta(corte)
    if sh is None:
        raise ValueError("A ferramenta do corte não é um sólido.")
    # para achar as barras atingidas, a forma das barras sem este corte
    base = barras if barras else barras_do_documento(doc)
    for b in barras_do_corte(corte):
        b.CortesEstrutura = _sem_este_corte(b, corte)
        b.touch()
    doc.recompute()
    alvo = barras_atingidas(sh, base)
    corte.Automatico = not barras
    definir_escopo(corte, alvo)
    corte.Label = "Corte em %d barra%s" % (len(alvo), "" if len(alvo) == 1 else "s")
    doc.recompute()
    return corte


def remover(corte):
    for b in barras_do_corte(corte):
        b.CortesEstrutura = _sem_este_corte(b, corte)
        b.touch()


def e_corte(o):
    return o is not None and isinstance(getattr(o, "Proxy", None), CorteEstrutura)


# ============================================================================ interface
try:
    import FreeCADGui
    import PrumoPainel as P
except ImportError:
    FreeCADGui = None
    P = None


class VistaCorte:
    def __init__(self, vobj):
        vobj.Proxy = self

    def attach(self, vobj):
        self.vobj = vobj

    def getIcon(self):
        return os.path.join(AQUI, "Resources", "icons", "corte_estrutura.svg")

    def claimChildren(self):
        f = self.vobj.Object.Ferramenta
        return [f] if f is not None else []

    def doubleClicked(self, vobj):
        if P is not None:
            PainelCorte().editar_objeto(vobj.Object).mostrar()
            return True
        return False

    def onDelete(self, vobj, subelements):
        remover(vobj.Object)
        f = vobj.Object.Ferramenta
        try:
            if f is not None:
                f.ViewObject.Visibility = True
        except Exception:
            pass
        return True

    def dumps(self):
        return None

    def loads(self, state):
        return None


def _filtro_ferramenta(obj, subs):
    import PrumoEstrutura as E
    if E.eh_barra(obj) or E.eh_estrutura(obj) or e_corte(obj):
        return []
    try:
        sh = obj.Shape
    except Exception:
        return []
    if sh.isNull():
        return []
    if sh.Solids or _e_esboco(obj):
        return [(obj.Label, obj)]
    return []


def _filtro_barra(obj, subs):
    import PrumoEstrutura as E
    if E.eh_barra(obj):
        return [(obj.Label, obj)]
    if E.eh_estrutura(obj):
        return [(b.Label, b) for b in E.barras_de(obj)]
    return []


if P is not None:
    class PainelCorte(P.PainelTarefa):
        titulo = "Cortar barras"
        ajuda = ("Corte ou furo feito uma vez e aplicado em várias barras. Escolha a ferramenta (um sólido ou um "
                 "esboço fechado, que atravessa a estrutura) e, se quiser, as barras; sem barras escolhidas, o corte "
                 "pega todas que a ferramenta atravessa.")
        previa = True

        def montar(self):
            f = self.form
            s0 = f.secao("Ferramenta", "selecao")
            self.ferr = f.caixa(s0, "Ferramenta", _filtro_ferramenta, minimo=1, maximo=1,
                                dica="Sólido (extrusão, cilindro, caixa…) ou esboço fechado.")
            s1 = f.secao("Barras (escopo)", "estrutura")
            self.barras = f.caixa(s1, "Barras", _filtro_barra, minimo=0, maximo=500,
                                  dica="Vazio = todas as barras que a ferramenta atravessa. Clicar numa estrutura "
                                       "pega todas as barras dela.")

        def pendencia(self):
            if not self.ferr.valores():
                return "Escolha a ferramenta: um sólido ou um esboço fechado."
            return None

        def pronto_texto(self):
            return "OK grava o corte." if self.editando is not None else "OK corta as barras."

        def _barras(self):
            vistos, res = set(), []
            for b in self.barras.valores():
                if b.Name not in vistos:
                    vistos.add(b.Name)
                    res.append(b)
            return res

        def carregar(self, obj):
            if obj.Ferramenta is not None:
                self.ferr.aceitar(obj.Ferramenta, [])
            if not obj.Automatico:
                for b in barras_do_corte(obj):
                    self.barras.aceitar(b, [])

        def aplicar_edicao(self, obj):
            editar(obj, self.ferr.valores()[0], self._barras() or None)
            return obj

        def executar(self):
            return [criar(FreeCAD.ActiveDocument, self.ferr.valores()[0], self._barras() or None)]

    class CmdCorteEstrutura:
        def GetResources(self):
            import PrumoUtil
            return {"Pixmap": PrumoUtil.icone("corte_estrutura.svg"), "MenuText": "Cortar barras",
                    "ToolTip": "Corte ou furo feito uma vez e aplicado em várias barras da estrutura (escopo): "
                               "use um sólido ou um esboço fechado como ferramenta. Tudo fica ligado."}

        def IsActive(self):
            doc = FreeCAD.ActiveDocument
            if doc is None:
                return False
            import PrumoEstrutura as E
            return any(E.eh_barra(o) for o in doc.Objects)

        def Activated(self):
            PainelCorte().mostrar()


def registrar_comandos():
    if FreeCADGui is not None and P is not None and "Prumo_CorteEstrutura" not in FreeCADGui.listCommands():
        FreeCADGui.addCommand("Prumo_CorteEstrutura", CmdCorteEstrutura())
