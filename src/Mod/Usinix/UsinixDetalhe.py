# -*- coding: utf-8 -*-
# Usinix: vista de detalhe em um clique e texto da cota como modelo ({valor})
#
# Vista de detalhe: um trecho da vista desenhado maior ao lado dela, com o círculo e a letra na vista de
# origem. A letra (A, B, C...) segue as que já existem no documento, a escala é uma escala normal pelo
# menos 2× a da vista, e o detalhe vai para o lado que tem espaço na folha.
#
# Texto da cota: "4× {valor}", "{valor} (ref.)", "{valor} ±0,1"... O {valor} continua sendo o número medido
# (acompanha a peça); o formato original fica guardado na cota para trocar ou tirar o modelo depois.


import FreeCAD

import UsinixUtil

MODELOS_COTA = ("{valor}", "2× {valor}", "4× {valor}", "{valor} (ref.)", "{valor} ±0,1", "{valor} típ.",
                "{valor} h7", "{valor} H7")


# ---------------------------------------------------------------------------------------------- detalhe
def letras_usadas(doc):
    return {str(getattr(o, "Reference", "")).strip().upper() for o in doc.Objects
            if o.TypeId == "TechDraw::DrawViewDetail"}


def proxima_letra(doc):
    """Próxima letra livre (A, B, ... Z, AA, AB...); pula I e O, que se confundem com 1 e 0."""
    usadas = letras_usadas(doc)
    alfabeto = [c for c in "ABCDEFGHJKLMNPQRSTUVWXYZ"]
    k = 0
    while True:
        n, txt = k, ""
        while True:
            txt = alfabeto[n % len(alfabeto)] + txt
            n = n // len(alfabeto) - 1
            if n < 0:
                break
        if txt not in usadas:
            return txt
        k += 1


def escala_do_detalhe(escala_vista, fator=2.0):
    """Menor escala normal (1:1, 2:1, 1:2...) que amplia pelo menos `fator` vezes a da vista."""
    alvo = escala_vista * fator
    normais = sorted({e * m for e in (1.0, 2.0, 5.0) for m in (0.001, 0.01, 0.1, 1.0, 10.0, 100.0)})
    for e in normais:
        if e >= alvo - 1e-9:
            return e
    return normais[-1]


def _caixa_da_vista(vista):
    """(xmin, xmax, ymin, ymax) das arestas visíveis da vista, sem escala, em coordenadas da vista."""
    xs, ys = [], []
    try:
        arestas = vista.getVisibleEdges()
    except Exception:
        arestas = []
    for e in arestas:
        bb = e.BoundBox
        xs += [bb.XMin, bb.XMax]
        ys += [bb.YMin, bb.YMax]
    if not xs:
        return -10.0, 10.0, -10.0, 10.0
    return min(xs), max(xs), min(ys), max(ys)


def _pagina(vista):
    import UsinixAnotacoes
    return UsinixAnotacoes.pagina_de(vista)


def _xy_na_folha(vista):
    """Centro da vista na folha (vista dentro de grupo de projeção: soma a posição do grupo)."""
    x, y = float(vista.X), float(vista.Y)
    for o in vista.InList:
        if o.TypeId == "TechDraw::DrawProjGroup":
            # a frontal aparece duas vezes no InList do grupo (âncora e vista): soma a posição uma vez só
            return x + float(o.X), y + float(o.Y)
    return x, y


DIAMETRO_MAX_PAPEL = 70.0     # mm: maior detalhe que o raio padrão gera


def _retangulos(page, ignorar=()):
    """Retângulos ocupados na folha (x0, y0, x1, y1), em mm: vistas (com folga para as cotas) e legenda."""
    rets = []
    try:
        larg = float(page.Template.Width)
    except Exception:
        larg = 420.0
    rets.append((larg - 10.0 - 180.0, 10.0, larg - 10.0, 10.0 + 62.0))      # legenda ABNT
    vistas = []
    for v in page.Views:
        if v.TypeId == "TechDraw::DrawProjGroup":
            vistas += list(v.Views)            # as vistas do grupo de projeção ficam dentro dele
        else:
            vistas.append(v)
    cotas = {}
    for v in page.Views:
        if v.TypeId == "TechDraw::DrawViewDimension":
            try:
                cotas.setdefault(v.References2D[0][0].Name, []).append(v)
            except Exception:
                pass
    for v in vistas:
        if v in ignorar:
            continue
        if v.TypeId == "TechDraw::DrawViewAnnotation":
            rets.append((float(v.X) - 25.0, float(v.Y) - 6.0, float(v.X) + 25.0, float(v.Y) + 6.0))
            continue
        if not v.isDerivedFrom("TechDraw::DrawViewPart"):
            continue
        try:
            cx, cy = _xy_na_folha(v)
            e = float(v.getScale())
            if v.TypeId == "TechDraw::DrawViewDetail":
                r = float(getattr(v.Radius, "Value", v.Radius)) * e + 3.0
                rets.append((cx - r, cy - r - 12.0, cx + r, cy + r))       # círculo e a legenda embaixo
                continue
            x0, x1, y0, y1 = _caixa_da_vista(v)
        except Exception:
            continue
        a, b, c, d = cx + x0 * e - 6.0, cy + y0 * e - 6.0, cx + x1 * e + 6.0, cy + y1 * e + 6.0
        for cota in cotas.get(v.Name, []):           # as cotas da vista também ocupam
            px, py = cx + float(cota.X), cy + float(cota.Y)
            a, b, c, d = min(a, px - 8.0), min(b, py - 8.0), max(c, px + 8.0), max(d, py + 8.0)
        rets.append((a, b, c, d))
    return rets


RESERVA = object()


def lugar_livre(page, meia, perto, ignorar=(), reserva=RESERVA):
    """Centro de um quadrado de meio-lado `meia` dentro da moldura que não cruza nada ocupado, o mais perto
    possível de `perto`. Sem lugar livre: o canto de cima à esquerda da área útil (ou `reserva`)."""
    try:
        larg, alt = float(page.Template.Width), float(page.Template.Height)
    except Exception:
        larg, alt = 420.0, 297.0
    xmin, xmax, ymin, ymax = 25.0 + meia, larg - 10.0 - meia, 10.0 + meia, alt - 10.0 - meia
    rets = _retangulos(page, ignorar)
    melhor = None
    passo = 4.0
    y = ymin
    while y <= ymax:
        x = xmin
        while x <= xmax:
            livre = all(x + meia <= a or x - meia >= c or y + meia <= b or y - meia >= dd for a, b, c, dd in rets)
            if livre:
                dist = (x - perto[0]) ** 2 + (y - perto[1]) ** 2
                if melhor is None or dist < melhor[0]:
                    melhor = (dist, x, y)
            x += passo
        y += passo
    if melhor is None:
        return (xmin, ymax) if reserva is RESERVA else reserva
    return melhor[1], melhor[2]


def criar_detalhe(vista, centro=None, raio=None, fator=2.0, letra=None):
    """Vista de detalhe de `vista`. centro: ponto (x, y) da vista, sem escala (ex.: de uma aresta escolhida);
    sem ele, o centro da vista. raio: sem escala; sem ele, 10% do maior lado da vista (no máximo 70 mm de
    diâmetro no papel). Vai para o lugar livre da folha mais perto da vista. Devolve o detalhe."""
    doc = vista.Document
    page = _pagina(vista)
    if page is None:
        raise ValueError("a vista não está numa folha")
    x0, x1, y0, y1 = _caixa_da_vista(vista)
    if centro is None:
        centro = FreeCAD.Vector((x0 + x1) / 2.0, (y0 + y1) / 2.0, 0)
    centro = FreeCAD.Vector(centro.x, centro.y, 0)
    esc_vista = float(vista.getScale())
    padrao = not raio
    if padrao:
        raio = max(0.10 * max(x1 - x0, y1 - y0), 1.0)
    esc = escala_do_detalhe(esc_vista, fator)
    if padrao and raio * esc > DIAMETRO_MAX_PAPEL / 2.0:
        raio = DIAMETRO_MAX_PAPEL / 2.0 / esc          # detalhe com no máximo 70 mm no papel
    letra = (letra or proxima_letra(doc)).upper()
    d = doc.addObject("TechDraw::DrawViewDetail", "Detalhe")
    d.BaseView = vista
    d.Source = vista.Source
    try:
        d.XSource = vista.XSource
    except Exception:
        pass
    d.Direction = vista.Direction
    d.XDirection = vista.XDirection
    d.AnchorPoint = centro
    d.Radius = raio
    d.Reference = letra
    d.ScaleType = "Custom"
    d.Scale = esc
    d.Label = "Detalhe %s" % letra
    page.addView(d)
    # no lugar livre da folha mais perto da vista (fora das vistas, das cotas e da legenda)
    vx, vy = _xy_na_folha(vista)
    for _k in range(8):
        achou = lugar_livre(page, raio * esc + 12.0, (vx, vy), ignorar=(d,), reserva=None)
        if achou is not None or not padrao or raio * esc < 12.0:
            break
        raio *= 0.8                                       # sem lugar na folha: um detalhe menor
        d.Radius = raio
    px, py = achou if achou is not None else lugar_livre(page, raio * esc + 12.0, (vx, vy), ignorar=(d,))
    py += 9.0                                             # espaço para a legenda embaixo
    d.X, d.Y = px, py
    # legenda do detalhe (NBR 10067): letra e escala embaixo do círculo
    leg = doc.addObject("TechDraw::DrawViewAnnotation", "LegendaDetalhe")
    leg.Label = "Legenda do detalhe %s" % letra
    leg.Text = ["DETALHE %s" % letra, "ESC. %s" % texto_escala(esc)]
    leg.TextSize = 3.5
    page.addView(leg)
    leg.X, leg.Y = px, py - raio * esc - 8.0           # duas linhas de 3,5 mm sem encostar no círculo
    if "UsinixLegenda" not in d.PropertiesList:
        d.addProperty("App::PropertyLink", "UsinixLegenda", "Usinix", "Legenda do detalhe (letra e escala)")
    d.UsinixLegenda = leg
    d.recompute()
    doc.recompute()
    return d


def texto_escala(e):
    """2.0 → "2:1"; 0.5 → "1:2"."""
    if e >= 1:
        return "%s:1" % UsinixUtil.fmt(e, 0 if abs(e - round(e)) < 1e-9 else 1)
    return "1:%s" % UsinixUtil.fmt(1.0 / e, 0 if abs(1.0 / e - round(1.0 / e)) < 1e-9 else 1)


def centro_da_selecao(vista, subelementos):
    """Ponto da vista (sem escala) do primeiro vértice ou aresta escolhidos; None se não houver."""
    for s in subelementos or []:
        try:
            if s.startswith("Vertex"):
                p = vista.getVertexBySelection(s).Point
                return FreeCAD.Vector(p.x, p.y, 0)
            if s.startswith("Edge"):
                e = vista.getEdgeBySelection(s)
                p = e.valueAt((e.FirstParameter + e.LastParameter) / 2.0)
                return FreeCAD.Vector(p.x, p.y, 0)
        except Exception:
            continue
    return None


# ------------------------------------------------------------------------------------ texto da cota
def _escapar(txt):
    return txt.replace("%", "%%")


def formato_base(cota):
    """Formato do número da cota antes de qualquer modelo (guardado na primeira aplicação)."""
    if "UsinixFormatoBase" in cota.PropertiesList and cota.UsinixFormatoBase:
        return cota.UsinixFormatoBase
    return cota.FormatSpec


def aplicar_modelo(cotas, modelo):
    """Texto das cotas pelo modelo: "{valor}" é o número medido, no formato que a cota já tinha
    ("4× {valor}" → "4× 25"). "{valor}" sozinho volta ao original. Devolve as cotas alteradas."""
    modelo = (modelo or "{valor}").strip()
    if "{valor}" not in modelo:
        raise ValueError("o modelo precisa ter {valor}, onde entra o número medido")
    feitas = []
    for c in cotas:
        if c.TypeId != "TechDraw::DrawViewDimension":
            continue
        base = formato_base(c)
        if "UsinixFormatoBase" not in c.PropertiesList:
            c.addProperty("App::PropertyString", "UsinixFormatoBase", "Usinix",
                          "Formato do número antes do modelo de texto (Texto da cota)")
            c.setPropertyStatus("UsinixFormatoBase", "Hidden")
        c.UsinixFormatoBase = base
        antes, depois = modelo.split("{valor}", 1)
        c.FormatSpec = _escapar(antes) + base + _escapar(depois.replace("{valor}", ""))
        c.recompute()
        feitas.append(c)
    return feitas


# ------------------------------------------------------------------------------------------- comandos
try:
    import FreeCADGui
    from PySide import QtWidgets
except ImportError:
    FreeCADGui = None


def _sel_vista():
    for s in FreeCADGui.Selection.getSelectionEx():
        o = s.Object
        if o.isDerivedFrom("TechDraw::DrawViewPart") and o.TypeId != "TechDraw::DrawViewDetail":
            return o, list(s.SubElementNames)
    return None, []


class CmdDetalhe:
    def GetResources(self):
        return {"Pixmap": UsinixUtil.icone("detalhe.svg"), "MenuText": "Vista de detalhe",
                "ToolTip": "Trecho da vista desenhado maior ao lado dela, com o círculo e a letra na vista. "
                           "Escolha a vista (e, se quiser, uma aresta ou um vértice no centro do detalhe). "
                           "Letra, escala e posição saem sozinhas; o raio e a escala se ajustam nas "
                           "propriedades do detalhe."}

    def IsActive(self):
        return FreeCAD.ActiveDocument is not None and _sel_vista()[0] is not None

    def Activated(self):
        vista, subs = _sel_vista()
        if vista is None:
            return
        doc = vista.Document
        doc.openTransaction("Vista de detalhe")
        try:
            d = criar_detalhe(vista, centro_da_selecao(vista, subs))
            doc.commitTransaction()
        except Exception as exc:
            doc.abortTransaction()
            QtWidgets.QMessageBox.warning(FreeCADGui.getMainWindow(), "Vista de detalhe", str(exc))
            return
        FreeCADGui.Selection.clearSelection()
        FreeCADGui.Selection.addSelection(d)


class CmdTextoCota:
    def GetResources(self):
        return {"Pixmap": UsinixUtil.icone("texto_cota.svg"), "MenuText": "Texto da cota",
                "ToolTip": "Texto das cotas escolhidas por um modelo: {valor} é o número medido (continua "
                           "acompanhando a peça). Ex.: 4× {valor}, {valor} (ref.), {valor} ±0,1. "
                           "\"{valor}\" sozinho volta ao texto original."}

    def IsActive(self):
        return any(o.TypeId == "TechDraw::DrawViewDimension" for o in FreeCADGui.Selection.getSelection())

    def Activated(self):
        cotas = [o for o in FreeCADGui.Selection.getSelection() if o.TypeId == "TechDraw::DrawViewDimension"]
        if not cotas:
            return
        atual = cotas[0].FormatSpec.replace(formato_base(cotas[0]), "{valor}", 1).replace("%%", "%")
        itens = list(MODELOS_COTA)
        if atual not in itens:
            itens.insert(0, atual)
        txt, ok = QtWidgets.QInputDialog.getItem(
            FreeCADGui.getMainWindow(), "Texto da cota",
            "Modelo do texto ({valor} = número medido) para %d cota(s):" % len(cotas), itens,
            itens.index(atual), True)
        if not ok:
            return
        doc = cotas[0].Document
        doc.openTransaction("Texto da cota")
        try:
            aplicar_modelo(cotas, txt)
            doc.commitTransaction()
        except Exception as exc:
            doc.abortTransaction()
            QtWidgets.QMessageBox.warning(FreeCADGui.getMainWindow(), "Texto da cota", str(exc))
        doc.recompute()


def registrar_comandos():
    if FreeCADGui is not None:
        FreeCADGui.addCommand("Usinix_VistaDetalhe", CmdDetalhe())
        FreeCADGui.addCommand("Usinix_TextoCota", CmdTextoCota())
