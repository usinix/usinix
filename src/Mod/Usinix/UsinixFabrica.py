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

import UsinixUtil


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


_SINAIS = ((1, 1), (-1, -1), (1, -1), (-1, 1))


def _mesmos_pontos(pa, pb, tol):
    """Cada ponto de pa tem um de pb a menos de tol (e vice-versa, pela contagem igual)? Grade de tol."""
    if len(pa) != len(pb) or not pa:
        return False
    grade = {}
    for p in pb:
        grade.setdefault((round(p[0] / tol), round(p[1] / tol), round(p[2] / tol)), []).append(p)
    for p in pa:
        i, j, k = round(p[0] / tol), round(p[1] / tol), round(p[2] / tol)
        achou = False
        for di in (-1, 0, 1):
            for dj in (-1, 0, 1):
                for dk in (-1, 0, 1):
                    for q in grade.get((i + di, j + dj, k + dk), ()):
                        if abs(q[0] - p[0]) <= tol and abs(q[1] - p[1]) <= tol and abs(q[2] - p[2]) <= tol:
                            achou = True
                            break
                    if achou:
                        break
                if achou:
                    break
            if achou:
                break
        if not achou:
            return False
    return True


def referencial(sh):
    """(forma no referencial principal, pontos dos vértices, momentos em X, Y, Z) para congruentes(ref_a=...)."""
    r = _no_referencial(sh)
    try:
        s = r.Solids[0] if len(r.Solids) == 1 else r
        m = s.MatrixOfInertia
        mom = (m.A11, m.A22, m.A33)
    except Exception:
        mom = None
    return r, [(v.X, v.Y, v.Z) for v in r.Vertexes], mom


def _eixo_de_simetria(mom):
    """Índice (0 = X, 1 = Y, 2 = Z) do eixo de revolução quando dois momentos são iguais e o terceiro não;
    None se os três são diferentes; -1 se os três são iguais (cubo, esfera: sem eixo definido)."""
    if not mom:
        return -1
    esc = max(abs(x) for x in mom) or 1.0
    ig = [abs(mom[i] - mom[j]) <= 1e-6 * esc for i, j in ((1, 2), (0, 2), (0, 1))]
    if all(ig):
        return -1
    for k in range(3):
        if ig[k]:
            return k
    return None


def _girar(pts, k, ang):
    c, s = math.cos(ang), math.sin(ang)
    i, j = [x for x in range(3) if x != k]
    out = []
    for p in pts:
        q = list(p)
        q[i], q[j] = c * p[i] - s * p[j], s * p[i] + c * p[j]
        out.append(tuple(q))
    return out


def _bate_girando(pa, pb, k, tol):
    """Peça de revolução (eixos principais indefinidos em volta do eixo k): procura o giro em torno de k (e o
    meio giro que inverte o eixo) que leva os vértices de b nos de a."""
    i, j = [x for x in range(3) if x != k]
    ref = max(pa, key=lambda p: p[i] * p[i] + p[j] * p[j])
    rr = math.hypot(ref[i], ref[j])
    if rr < tol:
        return _mesmos_pontos(pa, pb, tol)
    ang_a = math.atan2(ref[j], ref[i])
    for vira in (False, True):
        qb = [(p[0], -p[1], -p[2]) if k == 0 else (-p[0], p[1], -p[2]) if k == 1 else (p[0], -p[1], -p[2])
              for p in pb] if vira else pb
        tentativas = 0
        for q in qb:
            if abs(q[k] - ref[k]) > tol or abs(math.hypot(q[i], q[j]) - rr) > tol:
                continue
            tentativas += 1
            if tentativas > 64:
                break
            if _mesmos_pontos(pa, _girar(qb, k, ang_a - math.atan2(q[j], q[i])), tol):
                return True
    return False


def congruentes(sa, sb, tol=1e-3, sig_a=None, sig_b=None, ref_a=None, ref_b=None):
    """As duas formas são a mesma peça (uma rotação leva uma na outra)? Peça espelhada dá False.

    Primeiro compara os vértices no referencial principal (rápido: cópias da mesma peça batem aí); só quando não
    batem (eixos principais indefinidos, como em peça redonda ou cubo) faz a interseção dos sólidos, que é a
    conta que pesava na lista de materiais com centenas de peças. sig_*/ref_*: valores já calculados."""
    if (sig_a or assinatura(sa)) != (sig_b or assinatura(sb)):
        return False
    try:
        a, pa, ma = ref_a or referencial(sa)
        b, pb, _mb = ref_b or referencial(sb)
    except Exception:
        return False
    tam = max(a.BoundBox.DiagonalLength, 1.0)
    tolp = max(1e-4 * tam, 1e-3)
    eixo = _eixo_de_simetria(ma)
    if eixo is None:
        for sx, sy in _SINAIS:
            sz = sx * sy
            if _mesmos_pontos(pa, [(sx * x, sy * y, sz * z) for x, y, z in pb], tolp):
                return True
    elif eixo >= 0 and _bate_girando(pa, pb, eixo, tolp):
        return True
    vol = max(a.Volume, 1e-9)
    # eixos principais têm sinal livre: as 4 rotações próprias (det = +1) que trocam sinais
    for sx, sy in _SINAIS:
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
    import UsinixChapa
    import UsinixFolhaPeca as FP
    t, _r = UsinixChapa.espessura_raio(obj)
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
    import UsinixBOM
    try:
        import UsinixEstrutura as E
    except Exception:
        E = None
    grupos = []
    for obj, sh, _comprado in UsinixBOM.itens(objs):
        base = UsinixBOM._alvo(obj)
        if E is not None and E.eh_barra(base):
            continue
        if "Perna" in base.PropertiesList and "Pecas" in base.PropertiesList:
            continue
        t = espessura_de(base, sh)
        if not t:
            continue
        mat = str(UsinixBOM._prop(base, "Material") or UsinixUtil.material(base)[0] or "")
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
    import UsinixChapa
    import UsinixFolhaPeca as FP
    os.makedirs(pasta, exist_ok=True)
    feitos = []
    for k, (obj, qtd, t, mat) in enumerate(chapas(objs), 1):
        try:
            fam = UsinixChapa.familia_do_material(mat or UsinixUtil.material(obj)[0])
        except Exception:
            fam = "Aço carbono"
        try:
            face, dobras = FP.forma_plana(obj, fam)
        except Exception as exc:
            FreeCAD.Console.PrintWarning("Usinix: %s não planificou (%s); ficou fora do lote.\n" % (obj.Label, exc))
            continue
        externas, internas = UsinixChapa.separar_furos(face)
        marca = "%s%02d" % (prefixo, k) if prefixo else obj.Label
        texto = "%s - CH %s mm - %s - %d pc" % (marca, UsinixUtil.fmt_dim(t), mat or "material a definir", qtd)
        bb = face.BoundBox
        alt = max(2.5, min(10.0, bb.YLength * 0.06))
        nome = "%s_esp%smm_q%d.dxf" % (_nome_arquivo(marca), UsinixUtil.fmt_dim(t).replace(",", "-"), qtd)
        caminho = os.path.join(pasta, nome)
        textos = [(bb.XMin, bb.YMin - 2.0 * alt, alt, texto)]
        nota = UsinixChapa._nota_piso(obj, bool(internas))
        if nota:
            textos.append((bb.XMin, bb.YMin - 3.6 * alt, alt, nota))
        UsinixChapa.escrever_dxf(caminho, externas, dobras, internas, textos)
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
def resumo_orcamento(objs, linhas=None):
    """{"materiais": [(material, massa kg)], "massa_total", "area_pintura_m2", "solda_mm" (None se não há
    cordões modelados), "pecas"}. linhas: as da lista de materiais, se já coletadas (são a conta pesada)."""
    import UsinixBOM
    if linhas is None:
        linhas = UsinixBOM.coletar(objs)
    por_mat = {}
    for ln in linhas:
        if ln.massa_total is None:
            continue
        m = ln.material if ln.material not in ("", "—") else "material a definir"
        por_mat[m] = por_mat.get(m, 0.0) + ln.massa_total
    area = 0.0
    for _o, sh, _c in UsinixBOM.itens(objs):
        base = UsinixBOM._alvo(_o)
        if "Perna" in base.PropertiesList and "Pecas" in base.PropertiesList:
            continue
        area += sh.Area
    solda = None
    try:
        import UsinixEstruturaExtras as X
        cord = X.lista_de_soldas(_tudo(objs))
        if cord:
            solda = sum(s.ComprimentoTotal.Value for s in cord)
    except Exception:
        pass
    tub = None
    try:
        import UsinixTubulacao as T
        linhas_tubo = [o for o in _tudo(objs) if T.e_tubulacao(o)]
        if linhas_tubo:
            tub = sum(T.massa_instalada(o) for o in linhas_tubo)
    except Exception:
        tub = None
    return {"materiais": sorted(por_mat.items(), key=lambda t: -t[1]), "massa_total": sum(por_mat.values()),
            "area_pintura_m2": area / 1e6, "solda_mm": solda, "pecas": sum(ln.qtd for ln in linhas),
            "massa_tubulacao_instalada": tub}


def _tudo(objs):
    r, pilha = [], list(objs)
    while pilha:
        o = pilha.pop(0)
        if o in r:
            continue
        r.append(o)
        pilha += list(getattr(o, "Group", []) or [])
    return r


def exportar_excel(objs, caminho, linhas=None):
    """Planilha com a lista de materiais, a lista de corte, a lista de soldas e o resumo. Devolve o caminho.
    linhas: as da lista de materiais, se já coletadas."""
    import UsinixBOM
    abas = []
    if linhas is None:
        linhas = UsinixBOM.coletar(objs)
    total = sum(ln.massa_total or 0.0 for ln in linhas)
    abas.append(("Lista de materiais", UsinixBOM.COLUNAS,
                 [[n, ln.qtd, ln.codigo, ln.denominacao, ln.material, ln.dimensoes, ln.massa, ln.massa_total, ln.obs]
                  for n, ln in enumerate(linhas, 1)] + [["Total", None, None, None, None, None, None, total, None]],
                 [6, 6, 14, 34, 22, 28, 15, 15, 24]))
    try:
        import UsinixEstrutura as E
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
        import UsinixEstruturaExtras as X
        soldas = X.lista_de_soldas(_tudo(objs))
    except Exception:
        soldas = []
    if soldas:
        abas.append(("Lista de soldas", ["Item", "Junta", "Perna z (mm)", "Comprimento (mm)", "Processo", "Eletrodo",
                                         "Volume (cm³)", "Massa (kg)", "Observação"],
                     [[n, s.Juntas or s.Label, s.Perna.Value, s.ComprimentoTotal.Value, s.Processo, s.Eletrodo or None,
                       s.VolumeDepositado, s.MassaDepositada, s.Observacao or None] for n, s in enumerate(soldas, 1)],
                     [6, 34, 12, 16, 22, 12, 12, 11, 24]))
    r = resumo_orcamento(objs, linhas)
    res = [["Peças (unidades)", r["pecas"]]]
    res += [["Massa — %s (kg)" % m, kg] for m, kg in r["materiais"]]
    res += [["Total — massa (kg)", r["massa_total"]]]
    if r.get("massa_tubulacao_instalada") is not None:
        # a lista conta os tubos em barras inteiras (compra); montada, a linha pesa menos
        res += [["Tubulação montada — massa (kg, tubos pelo comprimento cortado)", r["massa_tubulacao_instalada"]]]
    res += [["Área externa para pintura (m²)", r["area_pintura_m2"]],
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
    import UsinixBOM
    return UsinixBOM._objetos_alvo()


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
        return {"Pixmap": UsinixUtil.icone("dxf_lote.svg"), "MenuText": "DXF de todas as chapas",
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
        return {"Pixmap": UsinixUtil.icone("exportar_excel.svg"), "MenuText": "Exportar para Excel",
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
        FreeCADGui.addCommand("Usinix_DXFLote", CmdDXFLote())
        FreeCADGui.addCommand("Usinix_ExportarExcel", CmdExportarExcel())
