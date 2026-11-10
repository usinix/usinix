# SPDX-License-Identifier: LGPL-2.1-or-later
# Usinix - do modelo para a fábrica: DXF de todas as chapas, planilha Excel e resumo para orçamento.
"""Do modelo para a fábrica.

- DXF de todas as chapas: um arquivo por chapa diferente (iguais contadas juntas), camadas CONTORNO, FUROS,
  DOBRAS e TEXTO (peça, espessura, material e quantidade), nome do arquivo com espessura e quantidade.
- Exportar para Excel (.xlsx, sem pacote extra): abas Lista de materiais, Lista de corte, Lista de soldas e
  Resumo (massa por material, área externa para pintura, comprimento de solda modelado).
- Peças iguais pela geometria: volume, área e momentos de inércia iguais e a forma de uma coincide com a da
  outra depois de alinhadas (peça espelhada não é igual).
"""

import math
import os
import zipfile
from xml.sax.saxutils import escape

import FreeCAD

import PrumoUtil


# ============================================================================ peças iguais pela geometria
def assinatura(sh):
    """Chave que não muda com a posição: volume, área, nº de faces e momentos principais (arredondados)."""
    vol = sum(s.Volume for s in sh.Solids) if sh.Solids else sh.Volume
    mom = []
    for s in sh.Solids or [sh]:
        try:
            mom += sorted(s.PrincipalProperties["Moments"])
        except Exception:
            pass
    escala = max(vol, 1e-9) ** (5.0 / 3.0)            # momentos crescem com massa × comprimento²
    return (round(vol, 1), round(sh.Area, 1), len(sh.Faces),
            tuple(round(m / escala, 4) for m in sorted(mom)))


def _no_referencial(sh):
    """Cópia da forma com o centro de massa na origem e os eixos principais em X, Y, Z."""
    s = sh.Solids[0] if len(sh.Solids) == 1 else sh
    pp = s.PrincipalProperties
    a1 = FreeCAD.Vector(pp["FirstAxisOfInertia"])
    a2 = FreeCAD.Vector(pp["SecondAxisOfInertia"])
    a3 = a1.cross(a2)
    c = s.CenterOfMass
    m = FreeCAD.Matrix(a1.x, a1.y, a1.z, 0, a2.x, a2.y, a2.z, 0, a3.x, a3.y, a3.z, 0, 0, 0, 0, 1)
    out = sh.copy()
    out.translate(c.negative())
    out.transformShape(m)
    return out


def congruentes(sa, sb, tol=1e-3):
    """As duas formas são a mesma peça (uma rotação leva uma na outra)? Peça espelhada dá False."""
    if assinatura(sa) != assinatura(sb):
        return False
    try:
        a = _no_referencial(sa)
        b = _no_referencial(sb)
    except Exception:
        return False
    vol = max(a.Volume, 1e-9)
    # eixos principais têm sinal livre: as 4 rotações próprias (det = +1) que trocam sinais
    for sx, sy in ((1, 1), (-1, -1), (1, -1), (-1, 1)):
        sz = sx * sy
        m = FreeCAD.Matrix(sx, 0, 0, 0, 0, sy, 0, 0, 0, 0, sz, 0, 0, 0, 0, 1)
        bb = b.copy()
        bb.transformShape(m)
        try:
            if a.common(bb).Volume >= (1.0 - tol) * vol:
                return True
        except Exception:
            continue
    return False


# ============================================================================ chapas
def espessura_de(obj, sh):
    """Espessura da chapa (mm) ou None se a peça não for chapa."""
    import PrumoChapa
    import PrumoFolhaPeca as FP
    t, _r = PrumoChapa.espessura_raio(obj)
    if t:
        return t
    if "Espessura" in obj.PropertiesList:
        try:
            v = obj.Espessura
            return float(v.Value if hasattr(v, "Value") else v)
        except Exception:
            pass
    try:
        t = FP.espessura(obj)
    except Exception:
        return None
    if not t:
        return None
    bb = sh.BoundBox
    lados = sorted([bb.XLength, bb.YLength, bb.ZLength])
    # chapa: fina perto das outras medidas (dobrada, a caixa cresce; vale a soma das duas maiores)
    if t <= 25.0 and t <= 0.15 * lados[1] + 1e-9:
        return t
    return None


def chapas(objs):
    """[(peça modelo, quantidade, espessura mm, material)] das chapas da seleção (abre montagens; barras de
    estrutura ficam de fora). Chapas iguais (mesma geometria, espessura e material) contam juntas."""
    import PrumoBOM
    try:
        import PrumoEstrutura as E
    except Exception:
        E = None
    grupos = []
    for obj, sh, _comprado in PrumoBOM.itens(objs):
        base = PrumoBOM._alvo(obj)
        if E is not None and E.eh_barra(base):
            continue
        if "Perna" in base.PropertiesList and "Pecas" in base.PropertiesList:
            continue
        t = espessura_de(base, sh)
        if not t:
            continue
        mat = str(PrumoBOM._prop(base, "Material") or PrumoUtil.material(base)[0] or "")
        if mat.lower().startswith("não definido"):
            mat = ""
        for g in grupos:
            if abs(g[2] - t) < 1e-6 and g[3] == mat and congruentes(g[4], sh):
                g[1] += 1
                break
        else:
            grupos.append([base, 1, t, mat, sh])
    return [(o, q, t, m) for o, q, t, m, _s in grupos]


def _nome_arquivo(txt):
    import re
    return re.sub(r'[<>:"/\\|?*\s]+', "_", txt).strip("_") or "chapa"


def exportar_dxf_lote(objs, pasta, prefixo=""):
    """Um DXF por chapa diferente na pasta. Devolve [(arquivo, peça, quantidade, espessura)]."""
    import PrumoChapa
    import PrumoFolhaPeca as FP
    os.makedirs(pasta, exist_ok=True)
    feitos = []
    for k, (obj, qtd, t, mat) in enumerate(chapas(objs), 1):
        try:
            fam = PrumoChapa.familia_do_material(mat or PrumoUtil.material(obj)[0])
        except Exception:
            fam = "Aço carbono"
        try:
            face, dobras = FP.forma_plana(obj, fam)
        except Exception as exc:
            FreeCAD.Console.PrintWarning("Usinix: %s não planificou (%s); ficou fora do lote.\n" % (obj.Label, exc))
            continue
        externas, internas = PrumoChapa.separar_furos(face)
        marca = "%s%02d" % (prefixo, k) if prefixo else obj.Label
        texto = "%s - CH %s mm - %s - %d pc" % (marca, PrumoUtil.fmt_dim(t), mat or "material a definir", qtd)
        bb = face.BoundBox
        alt = max(2.5, min(10.0, bb.YLength * 0.06))
        nome = "%s_esp%smm_q%d.dxf" % (_nome_arquivo(marca), PrumoUtil.fmt_dim(t).replace(",", "-"), qtd)
        caminho = os.path.join(pasta, nome)
        PrumoChapa.escrever_dxf(caminho, externas, dobras, internas, [(bb.XMin, bb.YMin - 2.0 * alt, alt, texto)])
        feitos.append((caminho, obj, qtd, t))
    return feitos


# ============================================================================ Excel (.xlsx sem dependência)
def _col(i):
    s = ""
    i += 1
    while i:
        i, r = divmod(i - 1, 26)
        s = chr(65 + r) + s
    return s


def _nome_aba(txt, usados):
    import re
    base = re.sub(r"[\[\]:*?/\\]", "-", txt)[:31] or "Aba"
    nome, n = base, 2
    while nome.lower() in usados:
        nome = "%s (%d)" % (base[:26], n)
        n += 1
    usados.add(nome.lower())
    return nome


def escrever_xlsx(caminho, abas):
    """Grava um .xlsx. abas: [(nome, cabeçalho [str], linhas [[str | número | None]], larguras [car.] ou None)].
    Números ficam números (somáveis no Excel); o cabeçalho sai em negrito, branco no azul, e fica congelado."""
    usados = set()
    nomes = [_nome_aba(a[0], usados) for a in abas]
    ct = ['<?xml version="1.0" encoding="UTF-8" standalone="yes"?>',
          '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">',
          '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>',
          '<Default Extension="xml" ContentType="application/xml"/>',
          '<Override PartName="/xl/workbook.xml" '
          'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>',
          '<Override PartName="/xl/styles.xml" '
          'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>']
    for i in range(len(abas)):
        ct.append('<Override PartName="/xl/worksheets/sheet%d.xml" '
                  'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>' % (i + 1))
    ct.append("</Types>")
    rels = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/'
            'officeDocument" Target="xl/workbook.xml"/></Relationships>')
    wb = ['<?xml version="1.0" encoding="UTF-8" standalone="yes"?>',
          '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
          'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets>']
    wbr = ['<?xml version="1.0" encoding="UTF-8" standalone="yes"?>',
           '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">']
    for i, n in enumerate(nomes, 1):
        wb.append('<sheet name="%s" sheetId="%d" r:id="rId%d"/>' % (escape(n, {'"': "&quot;"}), i, i))
        wbr.append('<Relationship Id="rId%d" Type="http://schemas.openxmlformats.org/officeDocument/2006/'
                   'relationships/worksheet" Target="worksheets/sheet%d.xml"/>' % (i, i))
    wb.append("</sheets></workbook>")
    wbr.append('<Relationship Id="rId%d" Type="http://schemas.openxmlformats.org/officeDocument/2006/'
               'relationships/styles" Target="styles.xml"/></Relationships>' % (len(nomes) + 1))
    # estilos: 0 normal, 1 cabeçalho, 2 número 0,000, 3 negrito, 4 número 0,000 em negrito
    estilos = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
               '<styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
               '<numFmts count="1"><numFmt numFmtId="164" formatCode="0.000"/></numFmts>'
               '<fonts count="3"><font><sz val="10"/><name val="Arial"/></font>'
               '<font><b/><sz val="10"/><color rgb="FFFFFFFF"/><name val="Arial"/></font>'
               '<font><b/><sz val="10"/><name val="Arial"/></font></fonts>'
               '<fills count="3"><fill><patternFill patternType="none"/></fill>'
               '<fill><patternFill patternType="gray125"/></fill>'
               '<fill><patternFill patternType="solid"><fgColor rgb="FF003A70"/></patternFill></fill></fills>'
               '<borders count="1"><border><left/><right/><top/><bottom/><diagonal/></border></borders>'
               '<cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs>'
               '<cellXfs count="5"><xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0"/>'
               '<xf numFmtId="0" fontId="1" fillId="2" borderId="0" xfId="0" applyFont="1" applyFill="1"/>'
               '<xf numFmtId="164" fontId="0" fillId="0" borderId="0" xfId="0" applyNumberFormat="1"/>'
               '<xf numFmtId="0" fontId="2" fillId="0" borderId="0" xfId="0" applyFont="1"/>'
               '<xf numFmtId="164" fontId="2" fillId="0" borderId="0" xfId="0" applyFont="1" '
               'applyNumberFormat="1"/></cellXfs>'
               '<cellStyles count="1"><cellStyle name="Normal" xfId="0" builtinId="0"/></cellStyles>'
               '</styleSheet>')

    def celula(ref, v, negrito=False):
        if v is None or v == "":
            return ""
        if isinstance(v, bool):
            v = "sim" if v else "não"
        if isinstance(v, (int, float)) and not (isinstance(v, float) and (math.isnan(v) or math.isinf(v))):
            est = (4 if negrito else 2) if isinstance(v, float) else (3 if negrito else 0)
            return '<c r="%s" s="%d"><v>%s</v></c>' % (ref, est, repr(float(v)) if isinstance(v, float) else v)
        return '<c r="%s" t="inlineStr"%s><is><t xml:space="preserve">%s</t></is></c>' % (
            ref, ' s="3"' if negrito else "", escape(str(v)))

    with zipfile.ZipFile(caminho, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", "".join(ct))
        z.writestr("_rels/.rels", rels)
        z.writestr("xl/workbook.xml", "".join(wb))
        z.writestr("xl/_rels/workbook.xml.rels", "".join(wbr))
        z.writestr("xl/styles.xml", estilos)
        for i, aba in enumerate(abas, 1):
            _nome, cab, linhas, larguras = (list(aba) + [None])[:4]
            larguras = larguras or [max(10, min(60, max([len(str(cab[c]))] + [len(str(l[c])) for l in linhas
                                                                                  if c < len(l) and l[c] is not None])
                                               + 2)) for c in range(len(cab))]
            x = ['<?xml version="1.0" encoding="UTF-8" standalone="yes"?>',
                 '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">',
                 '<sheetViews><sheetView workbookViewId="0"><pane ySplit="1" topLeftCell="A2" activePane="bottomLeft" '
                 'state="frozen"/></sheetView></sheetViews><cols>']
            for c, w in enumerate(larguras, 1):
                x.append('<col min="%d" max="%d" width="%.1f" customWidth="1"/>' % (c, c, w))
            x.append("</cols><sheetData>")
            x.append('<row r="1">' + "".join('<c r="%s1" t="inlineStr" s="1"><is><t>%s</t></is></c>'
                                             % (_col(c), escape(str(t))) for c, t in enumerate(cab)) + "</row>")
            for r, linha in enumerate(linhas, 2):
                negrito = bool(linha) and isinstance(linha[0], str) and linha[0].startswith("Total")
                x.append('<row r="%d">' % r + "".join(celula("%s%d" % (_col(c), r), v, negrito)
                                                      for c, v in enumerate(linha)) + "</row>")
            x.append("</sheetData></worksheet>")
            z.writestr("xl/worksheets/sheet%d.xml" % i, "".join(x))
    return caminho


# ============================================================================ resumo para orçamento
def resumo_orcamento(objs):
    """{"materiais": [(material, massa kg)], "massa_total", "area_pintura_m2", "solda_mm" (None se não há
    cordões modelados), "pecas"}."""
    import PrumoBOM
    linhas = PrumoBOM.coletar(objs)
    por_mat = {}
    for ln in linhas:
        if ln.massa_total is None:
            continue
        m = ln.material if ln.material not in ("", "—") else "material a definir"
        por_mat[m] = por_mat.get(m, 0.0) + ln.massa_total
    area = 0.0
    for _o, sh, _c in PrumoBOM.itens(objs):
        base = PrumoBOM._alvo(_o)
        if "Perna" in base.PropertiesList and "Pecas" in base.PropertiesList:
            continue
        area += sh.Area
    solda = None
    try:
        import PrumoEstruturaExtras as X
        cord = X.lista_de_soldas(_tudo(objs))
        if cord:
            solda = sum(s.ComprimentoTotal.Value for s in cord)
    except Exception:
        pass
    return {"materiais": sorted(por_mat.items(), key=lambda t: -t[1]), "massa_total": sum(por_mat.values()),
            "area_pintura_m2": area / 1e6, "solda_mm": solda, "pecas": sum(ln.qtd for ln in linhas)}


def _tudo(objs):
    r, pilha = [], list(objs)
    while pilha:
        o = pilha.pop(0)
        if o in r:
            continue
        r.append(o)
        pilha += list(getattr(o, "Group", []) or [])
    return r


def exportar_excel(objs, caminho):
    """Planilha com a lista de materiais, a lista de corte, a lista de soldas e o resumo. Devolve o caminho."""
    import PrumoBOM
    abas = []
    linhas = PrumoBOM.coletar(objs)
    total = sum(ln.massa_total or 0.0 for ln in linhas)
    abas.append(("Lista de materiais", PrumoBOM.COLUNAS,
                 [[n, ln.qtd, ln.codigo, ln.denominacao, ln.material, ln.dimensoes, ln.massa, ln.massa_total, ln.obs]
                  for n, ln in enumerate(linhas, 1)] + [["Total", None, None, None, None, None, None, total, None]],
                 [6, 6, 14, 34, 22, 28, 15, 15, 24]))
    try:
        import PrumoEstrutura as E
        # só as estruturas: as barras de dentro já vêm com elas (passar as duas contaria cada barra duas vezes)
        corte = E.lista_de_corte([o for o in _tudo(objs) if E.eh_estrutura(o)])
    except Exception:
        corte = []
    if corte:
        abas.append(("Lista de corte", ["Item", "Perfil", "Comprimento (mm)", "Corte início (°)", "Corte fim (°)",
                                        "Qtd.", "Massa unit. (kg)", "Massa total (kg)", "Material", "Furação",
                                        "Situação"],
                     [[n, l[0], l[1], l[2], l[3], l[4], l[5], l[5] * l[4], l[7] or None, l[8] or None, l[6]]
                      for n, l in enumerate(corte, 1)] +
                     [["Total", None, None, None, None, sum(l[4] for l in corte), None,
                       sum(l[5] * l[4] for l in corte), None, None, None]],
                     [6, 18, 16, 14, 14, 6, 15, 15, 18, 16, 12]))
    try:
        import PrumoEstruturaExtras as X
        soldas = X.lista_de_soldas(_tudo(objs))
    except Exception:
        soldas = []
    if soldas:
        abas.append(("Lista de soldas", ["Item", "Junta", "Perna z (mm)", "Comprimento (mm)", "Processo", "Eletrodo",
                                         "Volume (cm³)", "Massa (kg)", "Observação"],
                     [[n, s.Juntas or s.Label, s.Perna.Value, s.ComprimentoTotal.Value, s.Processo, s.Eletrodo or None,
                       s.VolumeDepositado, s.MassaDepositada, s.Observacao or None] for n, s in enumerate(soldas, 1)],
                     [6, 34, 12, 16, 22, 12, 12, 11, 24]))
    r = resumo_orcamento(objs)
    res = [["Peças (unidades)", r["pecas"]]]
    res += [["Massa — %s (kg)" % m, kg] for m, kg in r["materiais"]]
    res += [["Total — massa (kg)", r["massa_total"]],
            ["Área externa para pintura (m²)", r["area_pintura_m2"]],
            ["Comprimento de solda (mm)", r["solda_mm"] if r["solda_mm"] is not None else "sem cordões modelados"]]
    abas.append(("Resumo", ["Item", "Valor"], res, [40, 24]))
    return escrever_xlsx(caminho, abas)


# ============================================================================ interface
try:
    import FreeCADGui
    from PySide import QtCore, QtGui, QtWidgets
except ImportError:      # sem interface
    FreeCADGui = None


def _alvo():
    import PrumoBOM
    return PrumoBOM._objetos_alvo()


def _pasta_projeto(doc):
    return os.path.dirname(doc.FileName) if doc.FileName else os.path.expanduser("~")


def _avisar(titulo, texto, pasta):
    mb = QtWidgets.QMessageBox(FreeCADGui.getMainWindow())
    mb.setWindowTitle(titulo)
    mb.setText(texto)
    abrir = mb.addButton("Abrir a pasta", QtWidgets.QMessageBox.ActionRole)
    mb.addButton("OK", QtWidgets.QMessageBox.AcceptRole)
    mb.setAttribute(QtCore.Qt.WA_DeleteOnClose)
    mb.buttonClicked.connect(lambda b: b is abrir and QtGui.QDesktopServices.openUrl(
        QtCore.QUrl.fromLocalFile(pasta)))
    mb.show()
    return mb


class CmdDXFLote:
    def GetResources(self):
        return {"Pixmap": PrumoUtil.icone("dxf_lote.svg"), "MenuText": "DXF de todas as chapas",
                "ToolTip": "Planifica todas as chapas da montagem (ou da seleção) e grava um DXF por chapa "
                           "diferente, com contorno, furos, dobras e o texto da peça (espessura, material e "
                           "quantidade), para o corte a laser ou plasma."}

    def IsActive(self):
        return FreeCAD.ActiveDocument is not None

    def Activated(self):
        doc = FreeCAD.ActiveDocument
        objs = _alvo()
        pasta = QtWidgets.QFileDialog.getExistingDirectory(
            FreeCADGui.getMainWindow(), "Pasta para os DXF", os.path.join(_pasta_projeto(doc), "DXF"))
        if not pasta:
            return None
        feitos = exportar_dxf_lote(objs, pasta)
        if not feitos:
            QtWidgets.QMessageBox.information(FreeCADGui.getMainWindow(), "DXF de todas as chapas",
                                              "Nenhuma chapa encontrada na seleção.")
            return None
        n = sum(q for _c, _o, q, _t in feitos)
        return _avisar("DXF de todas as chapas", "%d arquivo(s) DXF (%d chapa(s) no total) em:\n%s"
                       % (len(feitos), n, pasta), pasta)


class CmdExportarExcel:
    def GetResources(self):
        return {"Pixmap": PrumoUtil.icone("exportar_excel.svg"), "MenuText": "Exportar para Excel",
                "ToolTip": "Grava uma planilha .xlsx com a lista de materiais, a lista de corte, a lista de "
                           "soldas e o resumo para orçamento (massa por material, área de pintura e solda)."}

    def IsActive(self):
        return FreeCAD.ActiveDocument is not None

    def Activated(self):
        doc = FreeCAD.ActiveDocument
        nome = os.path.splitext(os.path.basename(doc.FileName))[0] if doc.FileName else doc.Label
        caminho, _f = QtWidgets.QFileDialog.getSaveFileName(
            FreeCADGui.getMainWindow(), "Exportar para Excel",
            os.path.join(_pasta_projeto(doc), "%s - listas.xlsx" % nome), "Planilha do Excel (*.xlsx)")
        if not caminho:
            return None
        if not caminho.lower().endswith(".xlsx"):
            caminho += ".xlsx"
        exportar_excel(_alvo(), caminho)
        return _avisar("Exportar para Excel", "Planilha salva em:\n%s" % caminho, os.path.dirname(caminho))


def registrar_comandos():
    if FreeCADGui is not None:
        FreeCADGui.addCommand("Prumo_DXFLote", CmdDXFLote())
        FreeCADGui.addCommand("Prumo_ExportarExcel", CmdExportarExcel())
