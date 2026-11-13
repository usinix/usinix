# SPDX-License-Identifier: LGPL-2.1-or-later
# Usinix - trabalhos na barra da estrutura: corte das pontas soltas e furos, sem a barra virar corpo.
"""Trabalhos na barra (1.5.0).

A barra continua sendo barra da estrutura (lista de corte, cantos, análise): os trabalhos ficam
guardados na própria estrutura e entram no cálculo da barra (PrumoEstrutura.calcular_barra).

- Corte da ponta solta: reto (normal), horizontal, vertical ou pela face escolhida (aparar ou prolongar
  até ela). Ex.: banzo de escada a 45° com apoio no piso e chegada no topo cortados na horizontal.
- Furos: na alma ou nas mesas, a uma distância da ponta, em fila (quantidade e espaçamento), uma ou
  duas filas, para as barras escolhidas. A lista de corte mostra a furação de cada barra.
"""

import uuid

import FreeCAD
import FreeCADGui

import PrumoEstrutura as E
import PrumoPainel as P
import PrumoUtil
from PrumoUtil import fmt

try:
    from PySide import QtCore, QtWidgets
except ImportError:  # pragma: no cover
    from PySide2 import QtCore, QtWidgets

PARAM = "User parameter:BaseApp/Preferences/Mod/Prumo3D"
PARAFUSOS = ["Sem parafuso", "M8", "M10", "M12", "M16", "M20", "M22", "M24", "M27", "M30"]
OPCOES_PONTA = [
    (E.PONTA_RETO, "Reto", "ponta_reta", "Corte reto, a 90° da barra (como sempre foi)."),
    (E.PONTA_HORIZONTAL, "Horizontal", "ponta_horizontal", "Corte horizontal na ponta da linha: apoio no "
     "piso, chegada numa laje."),
    (E.PONTA_VERTICAL, "Vertical", "ponta_vertical", "Corte vertical na ponta da linha: encosto numa parede "
     "ou coluna."),
    ("face", "Pela face", "ponta_face", "Apara ou prolonga a barra até a face escolhida (selecione uma face "
     "plana de outra peça)."),
]
REFS = ["Início", "Fim", "As duas pontas"]


def folga_furo():
    """Folga entre o furo e o parafuso (mm), nas preferências; o padrão é 1,5 mm."""
    return FreeCAD.ParamGet(PARAM).GetFloat("FolgaFuroParafuso", 1.5)


def diametro_para(parafuso):
    """Diâmetro do furo para o parafuso (ex.: "M12" → 13,5 com folga 1,5) ou None."""
    if not parafuso or not parafuso.startswith("M"):
        return None
    try:
        return float(parafuso[1:]) + folga_furo()
    except ValueError:
        return None


def pontas_livres(barra):
    """Pontas (0 início, 1 fim) que não encostam em outra barra."""
    est = barra.Estrutura
    eds = E.arestas_ativas(est, E.arestas(est.Esqueleto))
    return [k for k, lig in enumerate(E.ligacoes(eds, barra.Indice)) if lig.tipo == "livre"]


def plano_da_face(obj, sub):
    """(ponto, normal) globais de uma face plana, ou None."""
    if not sub or not sub.startswith("Face"):
        return None
    try:
        f = PrumoUtil.forma_global(obj).Faces[int(sub[4:]) - 1]
    except Exception:
        return None
    if f.Surface.__class__.__name__ != "Plane":
        return None
    u0, u1, v0, v1 = f.ParameterRange
    n = f.normalAt((u0 + u1) / 2.0, (v0 + v1) / 2.0)
    return f.CenterOfMass, FreeCAD.Vector(n)


def _filtro_barras(obj, subs):
    return [(b.Label, b) for b in E.barras_do_item(obj, subs)]


def _filtro_face(obj, subs):
    res = []
    for o, els in E.resolver_item(obj, subs):
        if E.eh_barra(o) or E.eh_estrutura(o):
            continue
        for el in els:
            pl = plano_da_face(o, el)
            if pl is not None:
                res.append(("%s · %s" % (o.Label, el), (pl[0], pl[1], o, el)))
    return res


def aplicar(barras, pontas=None, furos=None, id_grupo=None, plano_face=None):
    """Grava os trabalhos nas barras (todas da mesma estrutura).

    pontas: {0: valor, 1: valor} (valor: reto, horizontal, vertical ou "face"; só pontas soltas mudam).
    furos: dicionário do grupo de furos (sem "barras"), lista desses ou None para tirar os furos do grupo.
    id_grupo: grupos de furos com esse id são trocados (o painel refaz sem duplicar)."""
    if not barras:
        return None
    est = barras[0].Estrutura
    if any(b.Estrutura is not est for b in barras):
        raise ValueError("as barras precisam ser da mesma estrutura")
    for b in barras:
        livres = pontas_livres(b)
        for k, valor in (pontas or {}).items():
            if k not in livres:
                continue
            if valor == "face":
                if plano_face is None:
                    continue
                if len(plano_face) >= 4 and plano_face[2] is not None:
                    valor = E.valor_face(plano_face[2], plano_face[3], plano_face[0], plano_face[1])
                else:
                    valor = E.valor_plano(plano_face[0], plano_face[1])
            E.definir_ponta(est, b.Indice, k, valor)
    if id_grupo is not None:
        lista = [f for f in E.furos_de(est) if f.get("id") != id_grupo]
        novos = furos if isinstance(furos, list) else ([furos] if furos else [])
        for f in novos:
            d = dict(f)
            d["barras"] = sorted(b.Indice for b in barras)
            d["id"] = id_grupo
            lista.append(d)
        E.gravar_furos(est, lista)
    return est


# ============================================================================ parafusos nos furos
def furos_na_barra(barra, diam=None):
    """Furos da barra já cortada: [(entrada, direção, saída)] pelas faces cilíndricas da forma.

    Entrada e saída são os pontos do eixo nas faces externas do material furado (alma, mesa, as duas
    paredes do tubo); a direção vai da entrada para a saída. diam filtra pelo diâmetro (mm)."""
    grupos = []
    for f in barra.Shape.Faces:
        sf = f.Surface
        if sf.__class__.__name__ != "Cylinder":
            continue
        if diam is not None and abs(2.0 * sf.Radius - diam) > 1e-3:
            continue
        if f.Area > 2.0 * 3.141593 * sf.Radius * 2000.0:      # não é furo (ex.: tubo redondo inteiro)
            continue
        eixo = FreeCAD.Vector(sf.Axis).normalize()
        c = sf.Center
        for g in grupos:
            d = c - g["c"]
            if abs(abs(eixo.dot(g["eixo"])) - 1) < 1e-6 and (d - g["eixo"] * d.dot(g["eixo"])).Length < 1e-3:
                g["faces"].append(f)
                break
        else:
            grupos.append({"c": c, "eixo": eixo, "faces": [f], "r": sf.Radius})
    res = []
    for g in grupos:
        proj = [(v.Point - g["c"]).dot(g["eixo"]) for f in g["faces"] for v in f.Vertexes]
        if not proj:
            continue
        a, b = min(proj), max(proj)
        ent, sai = g["c"] + g["eixo"] * a, g["c"] + g["eixo"] * b
        res.append((ent, (sai - ent).normalize() if (sai - ent).Length > 1e-9 else g["eixo"], sai, 2 * g["r"]))
    return res


def comprimento_parafuso(m, aperto):
    """Menor comprimento de catálogo (ISO 4017) que passa o aperto, a arruela e a porca com 2 fios de sobra."""
    import PrumoFixadores as F
    arr = F.medidas("arruela", m)["h"]
    porca = F.medidas("porca", m)["m"]
    precisa = aperto + arr + porca + 2 * (F.passo(m) or 1.5)
    lst = [float(x) for x in F.comprimentos("sextavado", m)]
    for c in lst:
        if c >= precisa - 1e-6:
            return c, precisa
    return (lst[-1] if lst else precisa), precisa


class Parafusamento:
    """Parafuso, arruela e porca em cada furo de um grupo de furos de uma barra (uma forma só; a lista de
    materiais conta as peças pela propriedade Itens)."""

    def __init__(self, obj):
        obj.Proxy = self
        self._props(obj)

    def _props(self, obj):
        def add(tipo, nome, grupo, dica, ro=False):
            if nome not in obj.PropertiesList:
                obj.addProperty(tipo, nome, grupo, dica)
            if ro:
                obj.setEditorMode(nome, 1)
        add("App::PropertyLink", "Barra", "Parafusos", "Barra furada")
        add("App::PropertyString", "Grupo", "Parafusos", "Grupo de furos (id) desta barra")
        add("App::PropertyString", "Diametro", "Parafusos", "Rosca (M12...)")
        add("App::PropertyLength", "Aperto", "Parafusos", "Espessura da peça presa além da barra (chapa, cantoneira)")
        add("App::PropertyString", "Material", "Parafusos", "Material / classe (ex.: aço classe 8.8)")
        add("App::PropertyLength", "Comprimento", "Parafusos", "Comprimento do parafuso escolhido", True)
        add("App::PropertyInteger", "Quantidade", "Parafusos", "Furos com parafuso", True)
        add("App::PropertyStringList", "ItensParafusos", "Parafusos", "Peças para a lista de materiais "
            "(quantidade|tipo|rosca|comprimento)", True)

    def onDocumentRestored(self, obj):
        obj.Proxy = self
        self._props(obj)

    def execute(self, obj):
        import Part
        import PrumoFixadores as F
        b, m = obj.Barra, obj.Diametro
        if b is None or not m or m not in F.diametros("sextavado"):
            obj.Shape = Part.Shape()
            obj.ItensParafusos = []
            obj.Quantidade = 0
            return
        est = b.Estrutura
        gs = [f for f in E.furos_da_barra(est, b.Indice) if f.get("id") == obj.Grupo] if est else []
        diams = {round(float(f.get("diam", 0)), 3) for f in gs}
        pecas, n, comp = [], 0, 0.0
        md_arr = F.medidas("arruela", m)
        eds = E.arestas(est.Esqueleto)
        e = eds[b.Indice]
        p0, t = e.valueAt(e.FirstParameter), E._dir(e, True)
        xs = [x for f in gs for x in E._pos_furos(e, f)]
        for d in diams:
            for ent, dirc, sai, _dd in furos_na_barra(b, d):
                if not any(abs((ent - p0).dot(t) - x) < 1e-3 for x in xs):
                    continue                     # furo de outro grupo com o mesmo diâmetro
                aperto_barra = (sai - ent).Length
                comp, _p = comprimento_parafuso(m, aperto_barra + obj.Aperto.Value)
                cabeca = ent - dirc * obj.Aperto.Value
                pl = FreeCAD.Placement(cabeca, FreeCAD.Rotation(FreeCAD.Vector(0, 0, 1), dirc * -1))
                par = F.forma("sextavado", m, comp)
                par.Placement = pl
                arr = F.forma("arruela", m)
                arr.Placement = FreeCAD.Placement(sai, FreeCAD.Rotation(FreeCAD.Vector(0, 0, 1), dirc))
                porca = F.forma("porca", m)
                porca.Placement = FreeCAD.Placement(sai + dirc * md_arr["h"],
                                                    FreeCAD.Rotation(FreeCAD.Vector(0, 0, 1), dirc))
                pecas += [par, arr, porca]
                n += 1
        obj.Shape = Part.makeCompound(pecas) if pecas else Part.Shape()
        obj.Quantidade = n
        obj.Comprimento = comp
        obj.ItensParafusos = (["%d|sextavado|%s|%s" % (n, m, fmt(comp, 0)), "%d|arruela|%s|" % (n, m),
                               "%d|porca|%s|" % (n, m)] if n else [])
        if n:
            obj.Label = "Parafusos %s × %s (%d) — %s" % (m, fmt(comp, 0), n, b.Label)

    def dumps(self):
        return None

    def loads(self, state):
        return None


class VPParafusamento:
    def __init__(self, vobj):
        vobj.Proxy = self

    def attach(self, vobj):
        self.Object = vobj.Object

    def getIcon(self):
        return PrumoUtil.icone("fixador.svg")

    def dumps(self):
        return None

    def loads(self, state):
        return None


def parafusamentos(doc, barra=None, grupo=None):
    return [o for o in doc.Objects if "ItensParafusos" in o.PropertiesList
            and (barra is None or o.Barra == barra) and (grupo is None or o.Grupo == grupo)]


def por_parafusos(barras, grupo, m, aperto=0.0, material=""):
    """Um parafusamento por barra para o grupo de furos (cria ou atualiza). Devolve os objetos."""
    res = []
    for b in barras:
        doc = b.Document
        ex = parafusamentos(doc, b, grupo)
        o = ex[0] if ex else doc.addObject("Part::FeaturePython", "Parafusos")
        if not ex:
            Parafusamento(o)
            o.Barra, o.Grupo = b, grupo
            if FreeCAD.GuiUp:
                VPParafusamento(o.ViewObject)
                try:
                    mat = FreeCAD.Material()
                    mat.DiffuseColor = (0.62, 0.64, 0.66)
                    o.ViewObject.ShapeAppearance = [mat]
                except Exception:
                    pass
            est = b.Estrutura
            try:
                est.addObject(o)
            except Exception:
                pass
        o.Diametro, o.Aperto, o.Material = m, aperto, material
        res.append(o)
    return res


def tirar_parafusos(doc, grupo, barras=None):
    for o in parafusamentos(doc, grupo=grupo):
        if barras is None or o.Barra in barras:
            doc.removeObject(o.Name)


def itens_bom(obj):
    """[(quantidade, tipo, rosca, comprimento)] de um parafusamento, para a lista de materiais."""
    res = []
    for l in obj.ItensParafusos:
        q, t, m, c = (l.split("|") + ["", "", "", ""])[:4]
        try:
            res.append((int(q), t, m, float(c.replace(",", ".")) if c else 0.0))
        except ValueError:
            continue
    return res


# ============================================================================ tabela de furos (desenho)
NOME_TABELA = "TabelaFuros"
COLS_TABELA = ["Barra", "Furo", "Onde", "Medido de", "Distância (mm)", "Transversal (mm)", "Ø (mm)",
               "Parafuso / origem"]
LARG_TABELA = [120, 45, 110, 80, 100, 110, 100, 170]


def linhas_furos(objs):
    """Uma linha por furo das barras: (barra, nº, onde, medido de, distância da ponta, transversal, Ø, parafuso).

    A distância vale da ponta da linha indicada (início ou fim), como a oficina marca; a transversal, do
    centro da face (alma: na altura; mesas: na largura)."""
    barras = []
    for o in objs:
        if E.eh_estrutura(o):
            barras += E.barras_de(o)
        elif E.eh_barra(o):
            barras.append(o)
    vistos, res = set(), []
    for b in barras:
        if b.Name in vistos or b.Estrutura is None:
            continue
        vistos.add(b.Name)
        est = b.Estrutura
        e = E.arestas(est.Esqueleto)[b.Indice]
        n = 0
        for f in E.furos_da_barra(est, b.Indice):
            filas = 2 if int(f.get("filas", 1)) >= 2 else 1
            gab, desloc = float(f.get("gab", 0)), float(f.get("desloc", 0))
            transv = [desloc] if filas == 1 else [desloc - gab / 2.0, desloc + gab / 2.0]
            lados = {"Mesa de cima": ["mesa de cima"], "Mesa de baixo": ["mesa de baixo"],
                     "As duas mesas": ["mesa de cima", "mesa de baixo"]}.get(f.get("face"), ["alma"])
            ref = f.get("ref", "inicio")
            for x in E._pos_furos(e, f):
                if x < -1e-6 or x > e.Length + 1e-6:
                    continue
                d = x if ref == "inicio" else e.Length - x
                for lado in lados:
                    for w in transv:
                        n += 1
                        res.append((b.Label, n, lado, "início" if ref == "inicio" else "fim", d, w,
                                    float(f.get("diam", 0)), f.get("parafuso") or "—"))
        for linha in _furos_dos_cortes(b, e):
            n += 1
            res.append((b.Label, n) + linha)
    return res


def _furos_dos_cortes(b, e):
    """Furos e recortes que os cortes da estrutura (Cortar barras) fazem na barra: (onde, medido de, distância,
    transversal, Ø ou medidas do recorte, origem). Cada sólido separado da ferramenta conta como um furo."""
    cortes = [c for c in (getattr(b, "CortesEstrutura", None) or []) if c is not None]
    if not cortes:
        return []
    import Part
    import PrumoCorteEstrutura as C
    import PrumoEstruturaExtras as X
    try:
        _est, _eds, _n, sec = X._contexto(b)
    except Exception:
        return []
    p0 = e.valueAt(e.FirstParameter)
    t = E._dir(e, True)
    u, v = sec.u, sec.v
    caixa = b.Shape.BoundBox
    bloco = Part.makeBox(caixa.XLength + 2, caixa.YLength + 2, caixa.ZLength + 2,
                         FreeCAD.Vector(caixa.XMin - 1, caixa.YMin - 1, caixa.ZMin - 1))
    res = []
    for c in cortes:
        try:
            ferr = C.forma_ferramenta(c)
        except Exception:
            ferr = None
        if ferr is None or not ferr.BoundBox.intersect(caixa):
            continue
        for sol in ferr.Solids:
            if not sol.BoundBox.intersect(caixa):
                continue
            pedaco = sol.common(bloco)
            if pedaco.Solids:
                pedaco = pedaco.Solids[0] if len(pedaco.Solids) == 1 else Part.makeCompound(pedaco.Solids)
            if pedaco.Volume < 1e-3 or b.Shape.distToShape(pedaco)[0] > 0.5:
                continue
            centro = pedaco.CenterOfMass if hasattr(pedaco, "CenterOfMass") else pedaco.BoundBox.Center
            x = (centro - p0).dot(t)
            if x < -1e-6 or x > e.Length + 1e-6:
                continue
            eixo_meio = p0 + t * x + u * sec.du + v * sec.dv
            cil = [f for f in sol.Faces if f.Surface.TypeId == "Part::GeomCylinder"]
            if cil:
                a = FreeCAD.Vector(cil[0].Surface.Axis).normalize()
                medida = 2.0 * cil[0].Surface.Radius
            else:
                # recorte: atravessa na direção em que o pedaço ocupa toda a seção
                dims = {k: _extensao(pedaco, d) for k, d in (("u", u), ("v", v))}
                a = u if dims["u"] >= sec.larg - 1e-3 else v
                medida = None
            if abs(a.dot(t)) > 0.9:
                onde = "na ponta (ao longo da barra)"
                transv = 0.0
            elif abs(a.dot(u)) >= abs(a.dot(v)):
                onde = "alma" if (sec.it or {}).get("tipo") in ("W", "I", "U", "HP") else "lado"
                transv = (centro - eixo_meio).dot(v)
            else:
                onde = "mesas" if (sec.it or {}).get("tipo") in ("W", "I", "U", "HP") else "topo e fundo"
                transv = (centro - eixo_meio).dot(u)
            if medida is None:
                perp = v if a is u else u
                medida_txt = "recorte %s × %s" % (fmt(_extensao(pedaco, t), 0), fmt(_extensao(pedaco, perp), 0))
            else:
                medida_txt = medida
            res.append((onde, "início", x, transv, medida_txt, "Cortar barras: %s" % c.Label))
    res.sort(key=lambda r: r[2])
    return res


def _extensao(sh, d):
    vs = [p.Point.dot(d) for p in sh.Vertexes] or [0.0]
    return max(vs) - min(vs)


def gravar_tabela(doc, linhas):
    sheet = doc.getObject(NOME_TABELA)
    if sheet is None:
        sheet = doc.addObject("Spreadsheet::Sheet", NOME_TABELA)
        sheet.Label = "Tabela de furos"
    else:
        sheet.clearAll()
    letras = "ABCDEFGH"
    for i, (c, w) in enumerate(zip(COLS_TABELA, LARG_TABELA)):
        sheet.set("%s1" % letras[i], c)
        sheet.setColumnWidth(letras[i], w)
    sheet.setStyle("A1:H1", "bold")
    sheet.setBackground("A1:H1", (0.0, 0.227, 0.439))
    sheet.setForeground("A1:H1", (1.0, 1.0, 1.0))
    sheet.setAlignment("A1:H1", "center|vcenter")
    for r, (bl, n, onde, ref, d, w, diam, par) in enumerate(linhas, 2):
        sheet.set("A%d" % r, "'" + bl)
        sheet.set("B%d" % r, str(n))
        sheet.set("C%d" % r, "'" + onde)
        sheet.set("D%d" % r, "'" + ref)
        sheet.set("E%d" % r, "'" + fmt(d, 1))
        sheet.set("F%d" % r, "'" + fmt(w, 1))
        if isinstance(diam, str):
            sheet.set("G%d" % r, "'" + diam)
        else:
            sheet.set("G%d" % r, "'" + (fmt(diam, 0) if abs(diam - round(diam)) < 1e-6 else fmt(diam, 1)))
        sheet.set("H%d" % r, "'" + par)
    if linhas:
        sheet.setAlignment("B2:H%d" % (len(linhas) + 1), "center|vcenter")
    doc.recompute()
    return sheet


def inserir_tabela_na_folha(page, sheet, n_linhas):
    """Tabela de furos no canto superior esquerdo do quadro (a lista de materiais fica embaixo, à direita)."""
    import PrumoBOM as B
    doc = page.Document
    vista = next((v for v in page.Views if v.TypeId == "TechDraw::DrawViewSpreadsheet" and v.Source == sheet),
                 None)
    if vista is None:
        vista = doc.addObject("TechDraw::DrawViewSpreadsheet", "VistaTabelaFuros")
        vista.Label = "Tabela de furos"
        vista.Source = sheet
        page.addView(vista)
    vista.CellStart = "A1"
    vista.CellEnd = "H%d" % (n_linhas + 1)
    alt_px = float(sheet.getRowHeight("1")) or 30.0
    escala = B.ALTURA_LINHA_MM / (alt_px * B.PX_MM)
    try:
        vista.ScaleType = "Custom"
    except Exception:
        pass
    vista.Scale = escala
    vista.TextSize = B.TEXTO_MM / (B.PX_MM * escala)
    vista.LineWidth = 0.35 / B.PX_MM
    try:
        alt = float(page.Template.Height)
        esq, _d, sup, _inf = B.margens_da_folha(page)
        w = sum(LARG_TABELA) * B.PX_MM * escala
        h = sum(sheet.getRowHeight(str(r)) for r in range(1, n_linhas + 2)) * B.PX_MM * escala
        vista.X = esq + 5.0 + w / 2.0
        vista.Y = alt - sup - 5.0 - h / 2.0
    except Exception as exc:
        FreeCAD.Console.PrintLog("Usinix: posição da tabela de furos: %s\n" % exc)
    doc.recompute()
    return vista


class CmdTabelaFuros:
    def GetResources(self):
        return {"Pixmap": PrumoUtil.icone("lista_corte.svg"), "MenuText": "Tabela de furos",
                "ToolTip": "Planilha com cada furo das barras — os de Trabalhos na barra e os furos e recortes de "
                           "Cortar barras — (onde, distância da ponta, transversal, Ø e parafuso ou origem). Com "
                           "uma folha de desenho aberta, coloca a tabela na folha."}

    def IsActive(self):
        return FreeCAD.ActiveDocument is not None

    def Activated(self):
        doc = FreeCAD.ActiveDocument
        objs = FreeCADGui.Selection.getSelection() or doc.Objects
        linhas = linhas_furos(objs)
        if not linhas:
            QtWidgets.QMessageBox.information(FreeCADGui.getMainWindow(), "Tabela de furos",
                                              "Nenhuma barra com furos. Use Trabalhos na barra ou Cortar barras "
                                              "para furar.")
            return
        doc.openTransaction("Tabela de furos")
        sheet = gravar_tabela(doc, linhas)
        page = None
        try:
            mdi = FreeCADGui.getMainWindow().centralWidget().activeSubWindow()
            titulo = mdi.windowTitle() if mdi else ""
            page = next((p for p in doc.Objects if p.isDerivedFrom("TechDraw::DrawPage") and p.Label in titulo),
                        None)
        except Exception:
            page = None
        if page is not None:
            inserir_tabela_na_folha(page, sheet, len(linhas))
        doc.commitTransaction()


class PainelTrabalhos(P.PainelTarefa):
    titulo = "Trabalhos na barra"
    ajuda = ("Corte das pontas soltas e furos nas barras da estrutura. A barra continua barra: a lista de "
             "corte sai com o comprimento, o ângulo das pontas e a furação.")
    previa = True

    def montar(self):
        f = self.form
        s1 = f.secao("Barras", "selecao")
        self.barras = f.caixa(s1, "Barras", _filtro_barras, minimo=1,
                              dica="Clique nas barras na tela ou na árvore (várias de uma vez valem para todas).")
        s2 = f.secao("Pontas soltas", "ponta")
        self.p0 = P.Opcoes(OPCOES_PONTA, E.PONTA_RETO, colunas=4)
        self.p1 = P.Opcoes(OPCOES_PONTA, E.PONTA_RETO, colunas=4)
        s2.linha("ponta", self.p0, "Corte da ponta inicial da barra (onde a linha começa).", "Ponta inicial")
        s2.linha("ponta", self.p1, "Corte da ponta final da barra (onde a linha termina).", "Ponta final")
        self.face = f.caixa(s2, "Face para o corte (Pela face)", _filtro_face, minimo=0, maximo=1,
                            dica="Face plana de outra peça (piso, laje, chapa) onde a barra é aparada ou "
                                 "prolongada.")
        self.nota_pontas = s2.texto("")
        self.p0.mudou.connect(self._mostrar_face)
        self.p1.mudou.connect(self._mostrar_face)
        self._mostrar_face()
        s3 = f.secao("Furos", "furo")
        self.furar = P.marcar("Furar as barras", False)
        s3.widget(self.furar)
        self.face_furo = s3.linha("tipo", P.lista(E.FACES_FURO), "Alma: furo atravessa na largura. Mesas: "
                                  "furo em cima, embaixo ou nas duas.", "Onde")
        self.parafuso = s3.linha("parafuso", P.lista(PARAFUSOS, "M12"), "O diâmetro do furo sai do parafuso "
                                 "mais a folga (preferência do Usinix).", "Parafuso")
        self.diam = s3.linha("furo", P.numero(13.5, 1.0, 200.0), "Diâmetro do furo.", "Diâmetro do furo")
        self.ref = s3.linha("ponta", P.lista(REFS), "De qual ponta da linha medir a distância.", "Medir de")
        self.dist = s3.linha("comprimento", P.numero(50.0, 0.0, 50000.0), "Da ponta da linha até o primeiro "
                             "furo.", "Distância da ponta")
        self.qtd = QtWidgets.QSpinBox()
        self.qtd.setRange(1, 200)
        self.qtd.setValue(2)
        s3.linha("quantidade", self.qtd, "Furos ao longo da barra.", "Quantidade")
        self.passo = s3.linha("comprimento", P.numero(80.0, 0.0, 50000.0), "Distância entre os furos ao longo "
                              "da barra.", "Espaçamento")
        self.filas = s3.linha("quantidade", P.lista(["1 fila", "2 filas"]), "Duas filas: lado a lado na face "
                              "(nas mesas, uma de cada lado da alma).", "Filas")
        self.gab = s3.linha("largura", P.numero(60.0, 0.0, 2000.0), "Distância entre as duas filas "
                            "(gabarito).", "Entre filas")
        self.desloc = s3.linha("posicao", P.numero(0.0, -2000.0, 2000.0), "Desloca as filas em relação ao "
                               "centro da face.", "Deslocamento")
        self.por_parafuso = P.marcar("Pôr parafuso, arruela e porca nos furos", False)
        s3.widget(self.por_parafuso)
        self.aperto = s3.linha("espessura", P.numero(0.0, 0.0, 500.0), "Espessura da peça presa junto com a "
                               "barra (chapa, cantoneira); entra no comprimento do parafuso.", "Peça presa")
        self.mat_paraf = s3.linha("material", QtWidgets.QLineEdit("Aço classe 8.8"), "Material / classe dos "
                                  "parafusos para a lista de materiais.", "Classe do parafuso")
        self.parafuso.currentIndexChanged.connect(self._parafuso_mudou)
        self.face_furo.currentIndexChanged.connect(self._face_mudou)
        self.furar.toggled.connect(self._habilitar)
        self.por_parafuso.toggled.connect(self._habilitar)
        self.parafuso.currentIndexChanged.connect(self._habilitar)
        self.id_grupo = "tb-" + uuid.uuid4().hex[:8]
        self._carregado = False
        self._habilitar()

    # ---- campos
    def _mostrar_face(self, *_a):
        """A caixa da face só aparece quando uma das pontas é "Pela face"."""
        self.face.setVisible("face" in (self.p0.valor(), self.p1.valor()))

    def _parafuso_mudou(self, *_a):
        d = diametro_para(self.parafuso.currentText())
        if d is not None:
            self.diam.setValue(d)

    def _face_mudou(self, *_a):
        mesas = self.face_furo.currentText() != "Alma"
        if mesas and self.filas.currentIndex() == 0:
            self.filas.setCurrentIndex(1)     # nas mesas, normalmente um furo de cada lado da alma
        bs = self.barras.valores()
        if mesas and bs:
            try:
                it = E.PrumoPerfis.perfil(bs[0].Perfil)
                self.gab.setValue(round(it.get("bf", 0) / 2.0) or self.gab.value())
            except Exception:
                pass

    def _habilitar(self, *_a):
        on = self.furar.isChecked()
        for w in (self.face_furo, self.parafuso, self.diam, self.ref, self.dist, self.qtd, self.passo,
                  self.filas, self.gab, self.desloc, self.por_parafuso):
            w.setEnabled(on)
        com = on and self.por_parafuso.isChecked() and self.parafuso.currentText() != "Sem parafuso"
        self.aperto.setEnabled(com)
        self.mat_paraf.setEnabled(com)

    # ---- o que já está gravado nas barras
    def _carregar_da_barra(self, b):
        est = b.Estrutura
        for k, w in ((0, self.p0), (1, self.p1)):
            v = E.ponta(est, b.Indice, k)
            if v.startswith(E.PONTA_FACE):
                # a face gravada volta para a caixa: OK de novo não pede para escolher a face
                nome, sub = v[len(E.PONTA_FACE):].split(":")[:2]
                o = est.Document.getObject(nome)
                if o is not None and not self.face.valores():
                    try:
                        self.face.aceitar(o, [sub])
                    except Exception:
                        pass
            w.definir("face" if v.startswith((E.PONTA_PLANO, E.PONTA_FACE)) else v)
        fs = E.furos_da_barra(est, b.Indice)
        if fs:
            g = fs[0]
            self.id_grupo = g.get("id") or self.id_grupo
            mesmos = [f for f in fs if f.get("id") == g.get("id")]
            self.furar.setChecked(True)
            self.face_furo.setCurrentText(g.get("face", "Alma"))
            self.parafuso.setCurrentText(g.get("parafuso") or "Sem parafuso")
            self.diam.setValue(float(g.get("diam", 13.5)))
            refs = {f.get("ref", "inicio") for f in mesmos}
            self.ref.setCurrentText("As duas pontas" if len(refs) > 1 else
                                    ("Fim" if g.get("ref") == "fim" else "Início"))
            self.dist.setValue(float(g.get("dist", 50)))
            self.qtd.setValue(int(g.get("qtd", 1)))
            self.passo.setValue(float(g.get("passo", 0)))
            self.filas.setCurrentIndex(1 if int(g.get("filas", 1)) >= 2 else 0)
            self.gab.setValue(float(g.get("gab", 0)))
            self.desloc.setValue(float(g.get("desloc", 0)))
            ps = parafusamentos(b.Document, b, self.id_grupo)
            self.por_parafuso.setChecked(bool(ps))
            if ps:
                self.aperto.setValue(ps[0].Aperto.Value)
                self.mat_paraf.setText(ps[0].Material)

    def atualizar(self):
        bs = self.barras.valores()
        if bs and not self._carregado:
            self._carregado = True
            try:
                self._carregar_da_barra(bs[0])
            except Exception:
                pass
        self._nota()
        super().atualizar()

    def _nota(self):
        presas = []
        for b in self.barras.valores():
            try:
                livres = pontas_livres(b)
            except Exception:
                continue
            for k, nome in ((0, "início"), (1, "fim")):
                if k not in livres:
                    presas.append("%s (%s)" % (b.Label, nome))
        txt = ("Pontas presas em outra barra seguem o tratamento do canto: %s." % ", ".join(presas)) if presas \
            else "O corte vale só para as pontas soltas (que não encostam em outra barra)."
        try:
            self.nota_pontas.setText(txt)
        except Exception:
            pass

    # ---- o trabalho
    def grupo_furos(self):
        if not self.furar.isChecked():
            return None
        par = self.parafuso.currentText()
        base = {"face": self.face_furo.currentText(), "diam": round(self.diam.value(), 3),
                "dist": self.dist.value(), "qtd": self.qtd.value(), "passo": self.passo.value(),
                "filas": 2 if self.filas.currentIndex() == 1 else 1, "gab": self.gab.value(),
                "desloc": self.desloc.value(), "parafuso": "" if par == "Sem parafuso" else par}
        ref = self.ref.currentText()
        if ref == "As duas pontas":
            return [dict(base, ref="inicio"), dict(base, ref="fim")]
        return [dict(base, ref="fim" if ref == "Fim" else "inicio")]

    def pendencia(self):
        falta = super().pendencia()
        if falta:
            return falta
        bs = self.barras.valores()
        if len({b.Estrutura.Name for b in bs if b.Estrutura is not None}) > 1:
            return "Escolha barras de uma estrutura só."
        if "face" in (self.p0.valor(), self.p1.valor()) and not self.face.valores():
            return "Pela face: selecione a face plana (piso, laje, chapa) onde a barra é cortada."
        g = self.grupo_furos()
        if g and self.por_parafuso.isChecked() and not g[0]["parafuso"]:
            return "Para pôr parafusos, escolha o parafuso (M12, M16...)."
        if g and g[0]["parafuso"] and self.por_parafuso.isChecked() and g[0]["diam"] < float(g[0]["parafuso"][1:]):
            return "O furo é menor que o parafuso: aumente o diâmetro do furo."
        if g and g[0]["qtd"] > 1 and g[0]["passo"] <= 0:
            return "Furos: informe o espaçamento entre os furos."
        return None

    def executar(self):
        bs = self.barras.valores()
        pl = self.face.valores()[0] if self.face.valores() else None
        g = self.grupo_furos()
        est = aplicar(bs, {0: self.p0.valor(), 1: self.p1.valor()}, g, self.id_grupo, pl)
        if est is not None:
            for b in E.barras_de(est):
                b.touch()
            doc = est.Document
            if g and self.por_parafuso.isChecked() and g[0]["parafuso"]:
                tirar_parafusos(doc, self.id_grupo, [o for o in E.barras_de(est) if o not in bs])
                por_parafusos(bs, self.id_grupo, g[0]["parafuso"], self.aperto.value(),
                              self.mat_paraf.text().strip())
            else:
                tirar_parafusos(doc, self.id_grupo)
        return bs

    def pronto_texto(self):
        bs = self.barras.valores()
        partes = []
        for b in bs[:4]:
            fu = getattr(b, "Furacao", "") or "sem furos"
            partes.append("%s: %s mm, pontas %s° / %s°, %s" % (b.Label, fmt(b.ComprimentoCorte.Value, 1),
                                                               fmt(b.CorteInicio.Value, 0),
                                                               fmt(b.CorteFim.Value, 0), fu))
        return ("; ".join(partes) + ". OK grava.") if partes else super().pronto_texto()


class CmdTrabalhosBarra:
    def GetResources(self):
        return {"Pixmap": PrumoUtil.icone("trabalhos_barra.svg"), "MenuText": "Trabalhos na barra",
                "ToolTip": "Corte das pontas soltas (horizontal, vertical ou pela face) e furos na alma ou nas "
                           "mesas das barras da estrutura. A barra continua na lista de corte, com a furação."}

    def IsActive(self):
        return FreeCAD.ActiveDocument is not None

    def Activated(self):
        PainelTrabalhos().mostrar()


def registrar_comandos():
    FreeCADGui.addCommand("Prumo_TrabalhosBarra", CmdTrabalhosBarra())
    FreeCADGui.addCommand("Prumo_TabelaFuros", CmdTabelaFuros())
