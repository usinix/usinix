# SPDX-License-Identifier: LGPL-2.1-or-later
"""Relatório de uma análise MEF montada na bancada (sem o assistente).

Escolhe-se uma análise do documento (pode haver várias, como os casos A e B de uma mesma estrutura) e sai o
relatório completo no padrão do Usinix: vistas, materiais, seções das barras, apoios em palavras, cargas com a
direção em palavras, malha, resultados, reações de apoio com a conferência do equilíbrio, verificação e as
validações do modelo. Serve para modelos de vigas (elementos 1D com seção) e para sólidos.

Antes de gerar, o Usinix confere que o resultado corresponde ao modelo de agora: a assinatura de cargas, apoios,
materiais, seções e malha é gravada quando o resultado é carregado. Resultado de antes dessa conferência (ou de
um modelo que mudou depois) pede um novo cálculo.
"""

import hashlib
import math
import os
import re

import FreeCAD

import UsinixFEM as F
import UsinixUtil

try:
    import FreeCADGui
    from PySide import QtCore, QtWidgets
    import UsinixPainel as P
except Exception:                  # pragma: no cover (sem interface)
    FreeCADGui = None
    P = None

V = FreeCAD.Vector
try:
    from UsinixNBR8800 import GAMA_A1  # o mesmo γa1 da verificação das barras
except Exception:                  # pragma: no cover
    GAMA_A1 = 1.10
LIMITE_EQUILIBRIO = 1.0            # % de diferença entre reações e cargas aplicadas
E_RIGIDO = 2.0e6                   # MPa: acima disso o material é um elemento rígido auxiliar
OK, AVISO, ERRO, INFO = "ok", "aviso", "erro", "info"


# =========================================================================== leitura do modelo
def analises(doc=None):
    doc = doc or FreeCAD.ActiveDocument
    return [o for o in doc.Objects if o.isDerivedFrom("Fem::FemAnalysis")] if doc else []


def _q(v, unidade):
    try:
        return FreeCAD.Units.Quantity(v).getValueAs(unidade).Value
    except Exception:
        try:
            return float(getattr(v, "Value", v))
        except Exception:
            return None


def _itens(est, *tipos):
    return est._tipo(*tipos) if est.analise is not None else []


def _subs(o):
    out = []
    for ob, ss in getattr(o, "References", []) or []:
        for s in ss:
            out.append((ob, s))
    return out


def _fmt(v, c=2, u=""):
    if isinstance(v, (int, float)) and abs(v) < 0.5 * 10 ** -c:
        v = 0.0                      # sem "-0,0" de resíduo numérico
    return F.fmt(v, c, u)


def palavras(v):
    """Direção em palavras: 'para baixo (−Z)', 'para cima (+Z)', '+X', '−Y e para baixo'..."""
    if v is None or v.Length < 1e-12:
        return "—"
    v = V(v)
    v.normalize()
    partes = []
    nomes = {"x": ("+X", "−X"), "y": ("+Y", "−Y"), "z": ("para cima (+Z)", "para baixo (−Z)")}
    for eixo in ("z", "x", "y"):
        c = getattr(v, eixo)
        if abs(c) > 0.05:
            partes.append((abs(c), nomes[eixo][0 if c > 0 else 1]))
    partes.sort(reverse=True)
    if len(partes) == 1 or partes[0][0] > 0.995:
        return partes[0][1]
    return " e ".join(p for _c, p in partes) + " (inclinada)"


def secao(g):
    """Propriedades de uma seção de viga (Fem::ElementGeometry1D): nome, A (mm²), I1 e I2 (mm⁴)."""
    t = getattr(g, "SectionType", "")
    mm = lambda nome: _q(getattr(g, nome), "mm") or 0.0          # noqa: E731
    if t == "Rectangular":
        b, h = mm("RectWidth"), mm("RectHeight")
        return {"tipo": "Retangular maciça %s × %s mm" % (_fmt(h, 1), _fmt(b, 1)), "A": b * h,
                "I1": b * h ** 3 / 12.0, "I2": h * b ** 3 / 12.0}
    if t == "Box":
        # o CalculiX recebe as quatro paredes (BoxT1 a BoxT4), não só duas
        b, h = mm("BoxWidth"), mm("BoxHeight")
        ts = [mm("BoxT%d" % i) if hasattr(g, "BoxT%d" % i) else mm("BoxT%d" % (1 + (i - 1) % 2)) for i in (1, 2, 3, 4)]
        bi, hi = max(b - ts[1] - ts[3], 0.0), max(h - ts[0] - ts[2], 0.0)
        iguais = max(ts) - min(ts) < 1e-6
        esp = _fmt(ts[0], 2) if iguais else "/".join(_fmt(x, 2) for x in ts)
        return {"tipo": "Tubo retangular %s × %s × %s mm" % (_fmt(h, 1), _fmt(b, 1), esp), "A": b * h - bi * hi,
                "I1": (b * h ** 3 - bi * hi ** 3) / 12.0, "I2": (h * b ** 3 - hi * bi ** 3) / 12.0,
                "paredes": ts, "paredes_iguais": iguais}
    if t == "Circular":
        d = mm("CircDiameter")
        return {"tipo": "Barra redonda Ø %s mm" % _fmt(d, 2), "A": math.pi * d * d / 4.0,
                "I1": math.pi * d ** 4 / 64.0, "I2": math.pi * d ** 4 / 64.0}
    if t == "Pipe":
        d, e = mm("PipeDiameter"), mm("PipeThickness")
        di = max(d - 2 * e, 0.0)
        return {"tipo": "Tubo redondo Ø %s × %s mm" % (_fmt(d, 1), _fmt(e, 2)),
                "A": math.pi * (d * d - di * di) / 4.0, "I1": math.pi * (d ** 4 - di ** 4) / 64.0,
                "I2": math.pi * (d ** 4 - di ** 4) / 64.0}
    return {"tipo": t or "—", "A": None, "I1": None, "I2": None}


def _biblioteca_sy(nome):
    """Limite de escoamento (MPa) do material da biblioteca com o mesmo nome (ou contido no nome)."""
    if not nome:
        return None, ""
    alvo = re.sub(r"[^a-z0-9]", "", nome.lower())
    try:
        import Materials
        mm = Materials.MaterialManager()
        for d in F.materiais():
            n = re.sub(r"[^a-z0-9]", "", (d.get("nome") or "").lower())
            if n and (n == alvo or n in alvo or alvo in n):
                p = mm.getMaterial(d["uuid"]).Properties
                sy = F.props_mat(p).get("Sy")
                if sy:
                    return sy, d.get("nome")
    except Exception:
        pass
    return None, ""


def materiais(est):
    out = []
    for m in _itens(est, "Fem::MaterialCommon", "Fem::MaterialSolid"):
        pm = F.props_mat(m.Material)
        fonte = "material da análise" if pm.get("Sy") else ""
        if not pm.get("Sy"):
            sy, nome = _biblioteca_sy(m.Material.get("Name", m.Label))
            if sy:
                pm["Sy"], fonte = sy, "biblioteca do Usinix (%s)" % nome
        subs = _subs(m)
        out.append({"obj": m, "nome": m.Material.get("Name", m.Label), "rotulo": rotulo(m), "E": pm.get("E"),
                    "nu": pm.get("nu"), "rho": pm.get("rho"), "Sy": pm.get("Sy"), "fonte_sy": fonte,
                    "rigido": bool(pm.get("E") and pm["E"] >= E_RIGIDO), "subs": subs})
    return out


def _arestas_do_modelo(est):
    """[(objeto, "EdgeN")] de todas as linhas da geometria do estudo (peça ou malha)."""
    geo = est.peca
    if geo is None and est.malha is not None:
        geo = getattr(est.malha, "Shape", None)
    try:
        return [(geo, "Edge%d" % (i + 1)) for i in range(len(geo.Shape.Edges))]
    except Exception:
        return []


def secoes(est):
    out = []
    itens = _itens(est, "Fem::ElementGeometry1D")
    # seção sem linhas escolhidas vale para as linhas que nenhuma outra seção pegou (é assim que o CalculiX lê);
    # o relatório mostrava "0 trechos, 0,00 m" e a massa ficava sem conta
    com_ref = {(ob.Name, sub) for g in itens for ob, sub in _subs(g)}
    resto = [(ob, sub) for ob, sub in _arestas_do_modelo(est) if (ob.Name, sub) not in com_ref]
    for g in itens:
        sp = secao(g)
        subs = _subs(g) or resto
        comp = 0.0
        for ob, s in subs:
            try:
                comp += ob.Shape.getElement(s).Length
            except Exception:
                pass
        sp.update(obj=g, rotulo=rotulo(g), subs=subs, n=len(subs), comprimento=comp)
        out.append(sp)
    return out


def massa_vigas(est, mats=None, secs=None):
    """Massa do modelo de vigas (kg): comprimento × área × densidade de cada barra."""
    mats = mats if mats is not None else materiais(est)
    secs = secs if secs is not None else secoes(est)
    if not secs:
        return None
    dens = {}
    geral = None
    for m in mats:
        if not m["subs"]:
            geral = m["rho"]
        for ob, s in m["subs"]:
            dens[(ob.Name, s)] = m["rho"]
    total = 0.0
    for sp in secs:
        if not sp["A"]:
            continue
        for ob, s in sp["subs"]:
            rho = dens.get((ob.Name, s), geral)
            try:
                L = ob.Shape.getElement(s).Length
            except Exception:
                continue
            if rho:
                total += L * sp["A"] * rho * 1e-9
    return total


def _graus(o):
    if F._eh(o, "Fem::ConstraintFixed"):
        return "Engaste: todos os deslocamentos e rotações travados"
    trava, livre, imposto = [], [], []
    for nome, rot in (("x", "UX"), ("y", "UY"), ("z", "UZ"), ("rotx", "RX"), ("roty", "RY"), ("rotz", "RZ")):
        if getattr(o, nome + "Free", True):
            livre.append(rot)
        else:
            trava.append(rot)
            v = getattr(o, {"x": "xDisplacement", "y": "yDisplacement", "z": "zDisplacement",
                            "rotx": "xRotation", "roty": "yRotation", "rotz": "zRotation"}[nome], None)
            v = _q(v, "mm" if not nome.startswith("rot") else "deg") if v is not None else 0.0
            if v:
                imposto.append("%s = %s" % (rot, _fmt(v, 2)))
    txt = "Trava " + ", ".join(trava) if trava else "Nada travado"
    if livre:
        txt += "; livre " + ", ".join(livre)
    if imposto:
        txt += "; deslocamento imposto " + ", ".join(imposto)
    return txt


def apoios(est):
    return [{"obj": o, "rotulo": rotulo(o), "graus": _graus(o), "subs": _subs(o)} for o in est.fixacoes]


def cargas(est, massa=None):
    """[{obj, rotulo, tipo, valor, dir, vetor (N), texto}] — vetor é a resultante (None para pressão)."""
    out = []
    for o in est.cargas:
        d = {"obj": o, "rotulo": rotulo(o), "subs": _subs(o), "vetor": None}
        if F._eh(o, "Fem::ConstraintSelfWeight"):
            g = _q(getattr(o, "GravityAcceleration", 9806.65), "mm/s^2") or 9806.65
            dv = V(getattr(o, "GravityDirection", V(0, 0, -1)))
            d.update(tipo="Peso próprio", valor="%s × g" % _fmt(g / 9806.65, 3), dir=palavras(dv), fator=g / 9806.65)
            if massa:
                n = dv.Length or 1.0
                d["vetor"] = dv * (massa * g / 1000.0 / n)
                d["valor"] += " = %s" % _fmt(massa * g / 1000.0, 1, "N")
        elif F._eh(o, "Fem::ConstraintForce"):
            f = _q(o.Force, "N") or 0.0
            dv = V(getattr(o, "DirectionVector", V(0, 0, 0)))
            d.update(tipo="Força total", valor=_fmt(f, 1, "N"), dir=palavras(dv))
            if dv.Length > 1e-12:
                d["vetor"] = dv * (f / dv.Length)
        elif F._eh(o, "Fem::ConstraintPressure"):
            d.update(tipo="Pressão", valor=_fmt(_q(o.Pressure, "MPa"), 3, "MPa"),
                     dir="para dentro da face" if not o.Reversed else "para fora da face")
        else:
            d.update(tipo=rotulo(o), valor="—", dir="—")
        out.append(d)
    return out


def rotulo(o):
    """Rótulo do objeto no relatório: a cópia feita por duplicar_analise guarda o rótulo original (o FreeCAD põe
    "001" no fim do rótulo repetido, e ele aparecia no relatório)."""
    try:
        return o.UsinixRotulo if "UsinixRotulo" in o.PropertiesList and o.UsinixRotulo else o.Label
    except Exception:
        return getattr(o, "Label", "")


G = 9.80665     # m/s² (1 kgf = 9,80665 N)


def ponto_mais_distante(forma, apoios, amostras=64):
    """(ponto, distância) do ponto do modelo de barras mais longe do apoio mais próximo: nos vértices e ao longo
    das linhas (no meio de uma viga biapoiada o ponto mais distante não é nó)."""
    def dist(p):
        return min((p - q).Length for q in apoios)
    melhor = (-1.0, None)
    for v in forma.Vertexes:
        d = dist(v.Point)
        if d > melhor[0]:
            melhor = (d, v.Point)
    for e in forma.Edges:
        a, b = e.FirstParameter, e.LastParameter
        ts = [a + (b - a) * i / float(amostras) for i in range(1, amostras)]
        if not ts:
            continue
        t = max(ts, key=lambda x: dist(e.valueAt(x)))
        lo, hi = max(a, t - (b - a) / amostras), min(b, t + (b - a) / amostras)
        for _ in range(40):                     # refina (seção áurea) entre as amostras vizinhas
            m1, m2 = lo + (hi - lo) * 0.382, lo + (hi - lo) * 0.618
            if dist(e.valueAt(m1)) < dist(e.valueAt(m2)):
                lo = m1
            else:
                hi = m2
        p = e.valueAt((lo + hi) / 2.0)
        d = dist(p)
        if d > melhor[0] + 1.0:                 # 1 mm a mais que um nó: senão fica no nó
            melhor = (d, p)
    return melhor[1], melhor[0]


def _referencias(analise, peca):
    """Geometria (ponto do vértice; extremos da linha) de tudo que a análise referencia na peça."""
    out = []
    for o in analise.Group:
        if "References" not in o.PropertiesList:
            continue
        lst = []
        for ob, subs in o.References:
            if ob != peca:
                continue
            for sub in subs:
                try:
                    el = peca.Shape.getElement(sub)
                except Exception:
                    continue
                lst.append((sub[:4], [v.Point for v in el.Vertexes]))
        if lst:
            out.append((o, lst))
    return out


def _remapear(analise, peca, antes):
    """Depois de partir uma linha, aponta as referências para os novos números (vértice pelo ponto; linha pelas
    partes que ficam sobre ela)."""
    import Part
    sh = peca.Shape
    for o, lst in antes:
        novos = []
        for tipo, pts in lst:
            if tipo == "Vert":
                k = min(range(len(sh.Vertexes)), key=lambda i: (sh.Vertexes[i].Point - pts[0]).Length)
                novos.append("Vertex%d" % (k + 1))
            elif tipo == "Edge" and len(pts) >= 2:
                velha = Part.makeLine(pts[0], pts[-1])
                for i, e in enumerate(sh.Edges):
                    if all(velha.distToShape(Part.Vertex(v.Point))[0] < 1e-4 for v in e.Vertexes):
                        novos.append("Edge%d" % (i + 1))
        outros = [(ob, subs) for ob, subs in o.References if ob != peca]
        try:
            o.References = outros + ([(peca, tuple(dict.fromkeys(novos)))] if novos else [])
        except Exception as exc:
            FreeCAD.Console.PrintWarning("Usinix: referências de %s: %s\n" % (o.Label, exc))


def _pontos_dos_apoios(est):
    pts = []
    for c in est.fixacoes:
        for o, ss in c.References:
            for sub in ss:
                try:
                    el = o.Shape.getElement(sub)
                except Exception:
                    continue
                pts += [v.Point for v in el.Vertexes]
    return pts


def _linha_vertical(doc):
    """Linha vertical escondida que serve de direção para forças em vértices (uma por documento)."""
    o = doc.getObject("UsinixDirecaoVertical")
    if o is None:
        o = doc.addObject("Part::Line", "UsinixDirecaoVertical")
        o.Label = "Direção vertical (referência das cargas)"
        o.X1 = o.Y1 = o.Z1 = 0.0
        o.X2 = o.Y2 = 0.0
        o.Z2 = 100.0
        doc.recompute()
        try:
            o.ViewObject.Visibility = False
        except Exception:
            pass
    return o


def carga_no_ponto_mais_distante(analise, massa_kg, rotulo=None):
    """Força vertical para baixo de massa_kg × g no ponto do modelo mais longe dos apoios (o ponto cuja
    distância ao apoio mais próximo é a maior): o caso de uma pessoa com carga na ponta de uma plataforma, que
    antes era montado à mão e chegou a ser esquecido. Funciona no modelo de barras: o ponto pode ficar no meio
    de uma linha (meio da viga); no esqueleto MEF a linha é partida ali para virar nó."""
    import ObjectsFem
    est = F.Estudo(analise=analise)
    peca = est.peca
    if peca is None:
        raise ValueError("a análise não tem geometria")
    apoios = _pontos_dos_apoios(est)
    if not apoios:
        raise ValueError("defina os apoios antes: o ponto mais distante é medido a partir deles")
    vs = peca.Shape.Vertexes
    if not vs:
        raise ValueError("a geometria da análise não tem vértices")
    alvo, _d = ponto_mais_distante(peca.Shape, apoios)
    if not any((v.Point - alvo).Length < 1.0 for v in vs) and "PontosDeCarga" in peca.PropertiesList:
        # o ponto mais distante fica no meio de uma linha (meio da viga): vira nó do esqueleto
        antes = _referencias(analise, peca)
        peca.PontosDeCarga = list(peca.PontosDeCarga) + [alvo]
        peca.recompute()
        _remapear(analise, peca, antes)
        vs = peca.Shape.Vertexes
    k = min(range(len(vs)), key=lambda i: (vs[i].Point - alvo).Length)
    dist = min((vs[k].Point - q).Length for q in apoios)
    doc = analise.Document
    c = ObjectsFem.makeConstraintForce(doc, "CargaNaPonta")
    c.References = [(peca, ("Vertex%d" % (k + 1),))]
    c.Force = "%.3f N" % (float(massa_kg) * G)
    analise.addObject(c)
    c.Direction = (_linha_vertical(doc), ["Edge1"])     # vértice não tem normal: direção por uma linha vertical
    c.Reversed = False
    c.recompute()
    if c.DirectionVector.z > 0:
        c.Reversed = True
        c.recompute()
    if c.DirectionVector.z > -0.99:
        doc.removeObject(c.Name)
        raise ValueError("não foi possível apontar a força para baixo neste vértice (o modelo não é plano "
                         "horizontal): aplique a carga pela bancada escolhendo a direção")
    c.Label = rotulo or UsinixUtil.rotulo_unico(doc, "Carga de %s kg no ponto mais distante dos apoios" %
                                                UsinixUtil.fmt(float(massa_kg), 0))
    est.put("UsinixResultadoVelho", True, "App::PropertyBool")
    doc.recompute()
    return c, vs[k].Point, dist


def duplicar_analise(analise, rotulo_novo=None):
    """Cópia da análise com material, seções, apoios, cargas, malha e solver próprios, apontando para a mesma
    geometria (o caso B a partir do caso A, por exemplo). Os rótulos da cópia saem iguais aos do original no
    relatório. Resultados não são copiados: a cópia nasce para ser calculada."""
    doc = analise.Document
    nova = doc.addObject(analise.TypeId, analise.Name)
    nova.Label = rotulo_novo or UsinixUtil.rotulo_unico(doc, analise.Label + " (cópia)")
    mapa = {}
    # rótulos iguais aos do original: o FreeCAD põe "001" no rótulo repetido, a não ser que o documento aceite
    # rótulo duplicado (preferência "DuplicateLabels"), ligada só durante a cópia
    pref = FreeCAD.ParamGet("User parameter:BaseApp/Preferences/Document")
    dup_antes = pref.GetBool("DuplicateLabels", False)
    pref.SetBool("DuplicateLabels", True)
    try:
        _copiar_membros(analise, nova, mapa)
    finally:
        pref.SetBool("DuplicateLabels", dup_antes)
    for nome in nova.PropertiesList:
        if nome.startswith("Usinix") and nome in analise.PropertiesList and nome not in (
                "UsinixCondAssin", "UsinixCondPontos", "UsinixCalculadoEm", "UsinixConvergencia", "UsinixRelTitulo"):
            try:
                setattr(nova, nome, getattr(analise, nome))
            except Exception:
                pass
    for nome in analise.PropertiesList:
        if nome.startswith("Usinix") and nome not in nova.PropertiesList and nome not in (
                "UsinixCondAssin", "UsinixCondPontos", "UsinixCalculadoEm", "UsinixConvergencia", "UsinixRelTitulo"):
            try:
                nova.addProperty(analise.getTypeIdOfProperty(nome), nome, "Usinix")
                setattr(nova, nome, getattr(analise, nome))
            except Exception:
                pass
    doc.recompute()
    return nova


def _copiar_membros(analise, nova, mapa):
    doc = analise.Document
    for o in analise.Group:
        if o.isDerivedFrom("Fem::FemResultObject") or o.isDerivedFrom("Fem::FemPostObject") or \
                o.TypeId == "App::TextDocument" or (o.TypeId == "Fem::FemMeshObject" and o.Name.startswith("ResultMesh")):
            continue                     # resultados e arquivos do solver: a cópia nasce para ser calculada
        c = doc.copyObject(o, False)
        if "UsinixRotulo" not in c.PropertiesList:
            c.addProperty("App::PropertyString", "UsinixRotulo", "Usinix", "Rótulo no relatório (cópia de análise)")
        c.UsinixRotulo = rotulo(o)
        try:
            c.Label = o.Label
        except Exception:
            pass
        mapa[o] = c
        nova.addObject(c)


def _dat(est):
    for o in est.analise.Group if est.analise is not None else []:
        if o.TypeId == "App::TextDocument" and o.Name.startswith("ccx_dat_file"):
            return o.Text or ""
    return ""


def reacoes(est):
    """Reações por apoio lidas do arquivo .dat do CalculiX: {nome do apoio: Vector(Fx, Fy, Fz) N}."""
    txt = _dat(est)
    if not txt:
        return {}
    por_set = {}
    for m in re.finditer(r"total force \(fx,fy,fz\) for set (\S+) and time\s+\S+\s+([-+0-9.E]+)\s+([-+0-9.E]+)"
                         r"\s+([-+0-9.E]+)", txt):
        por_set[m.group(1).upper()] = V(float(m.group(2)), float(m.group(3)), float(m.group(4)))
    out = {}
    for o in est.fixacoes:
        r = por_set.get(o.Name.upper())
        if r is not None:
            out[o.Name] = r
    return out


def reacoes_por_no(est):
    """Reação de cada nó dos apoios pequenos (o .dat traz nó a nó quando o Usinix pediu TOTALS=YES):
    {nome do apoio: [(nó, Vector posição mm ou None, Vector(Fx, Fy, Fz) N)]}."""
    txt = _dat(est)
    if not txt:
        return {}
    mesh = getattr(est.malha, "FemMesh", None) if est.malha is not None else None
    nomes = {o.Name.upper(): o.Name for o in est.fixacoes}
    out = {}
    for m in re.finditer(r"^\s*forces \(fx,fy,fz\) for set (\S+) and time\s+\S+\s*$(.*?)(?=^\s*total force|\Z)",
                         txt, re.M | re.S):
        nome = nomes.get(m.group(1).upper())
        if nome is None:
            continue
        lst = []
        for ln in m.group(2).splitlines():
            p = ln.split()
            if len(p) == 4 and p[0].isdigit():
                no = int(p[0])
                try:
                    pos = V(mesh.getNodeById(no)) if mesh is not None else None
                except Exception:
                    pos = None
                lst.append((no, pos, V(float(p[1]), float(p[2]), float(p[3]))))
        if lst:
            out[nome] = lst
    return out


def equilibrio(est, cgs, reac):
    """(ok?, diferença %, soma das reações, soma das cargas) — None quando não dá para conferir.

    Tolerância: 1 % da resultante mais 5 % do peso próprio, porque o CalculiX integra a massa das vigas
    expandidas (caixa, tubo) de forma aproximada e o peso que ele aplica difere um pouco de L × A × ρ."""
    if not reac or any(c["vetor"] is None for c in cgs) or not cgs:
        return None
    soma_r = V(0, 0, 0)
    for r in reac.values():
        soma_r += r
    soma_c = V(0, 0, 0)
    for c in cgs:
        soma_c += c["vetor"]
    if soma_c.Length < 1e-9:
        return None
    dif = (soma_r + soma_c).Length / soma_c.Length * 100.0
    peso = sum(c["vetor"].Length for c in cgs if F._eh(c["obj"], "Fem::ConstraintSelfWeight"))
    tol = LIMITE_EQUILIBRIO + 5.0 * peso / soma_c.Length
    return dif <= tol, dif, soma_r, soma_c


# =========================================================================== resultado em dia
def assinatura(est):
    """Impressão digital do que define o resultado: cargas, apoios, materiais, seções e malha."""
    partes = []
    for o in sorted(est.fixacoes + est.cargas + _itens(est, "Fem::MaterialCommon", "Fem::MaterialSolid",
                                                       "Fem::ElementGeometry1D"), key=lambda x: x.Name):
        lin = [o.Name, repr([(ob.Name, tuple(ss)) for ob, ss in getattr(o, "References", []) or []])]
        for p in sorted(o.PropertiesList):
            if p in ("Label", "Label2", "Visibility", "ExpressionEngine", "Proxy", "References", "Scale",
                     "Points", "Normals", "NormalDirection", "DirectionVector"):
                continue
            try:
                v = getattr(o, p)
            except Exception:
                continue
            if isinstance(v, (dict,)):
                v = sorted(v.items())
            elif hasattr(v, "Name") and hasattr(v, "TypeId"):
                v = v.Name
            lin.append("%s=%r" % (p, str(v)))
        partes.append("|".join(lin))
    m = est.malha
    if m is not None:
        partes.append("malha|%s|%s|%s|%d" % (getattr(m, "CharacteristicLengthMax", ""), getattr(m, "ElementOrder", ""),
                                             getattr(getattr(m, "Shape", None), "Name", ""),
                                             m.FemMesh.NodeCount if getattr(m, "FemMesh", None) else 0))
        try:
            sh = m.Shape.Shape
            partes.append("geo|%.3f|%.3f|%d|%d" % (sh.Volume, sum(e.Length for e in sh.Edges), len(sh.Edges),
                                                   len(sh.Vertexes)))
        except Exception:
            pass
    s = est.solver
    if s is not None:
        partes.append("solver|%s" % getattr(s, "AnalysisType", ""))
    return hashlib.md5("\n".join(partes).encode("utf-8")).hexdigest()


def _pontos_da_malha(est):
    m = est.malha
    try:
        return F.pontos_da_forma(m.Shape.Shape)
    except Exception:
        return ""


def gravar_assinatura(est):
    if est.analise is not None:
        est.put("UsinixCondAssin", assinatura(est))
        # posição dos vértices do modelo, à parte da assinatura (para não dar por velho o que já foi conferido)
        est.put("UsinixCondPontos", _pontos_da_malha(est))


def estado(est):
    """(chave, texto): sem_resultado, atual, desatualizado ou nao_confirmado."""
    if not est.resultados:
        return "sem_resultado", "A análise ainda não tem resultado: calcule antes de gerar o relatório."
    gravada = est.get("UsinixCondAssin", "")
    if not gravada:
        return "nao_confirmado", ("Não dá para confirmar que o resultado guardado é do modelo de agora (ele foi "
                                  "calculado antes desta conferência existir): recalcule antes de gerar o relatório.")
    if gravada != assinatura(est):
        return "desatualizado", ("O resultado é de antes da última mudança em cargas, apoios, materiais, seções ou "
                                 "malha: recalcule antes de gerar o relatório.")
    pts = est.get("UsinixCondPontos", "")
    if pts and pts != _pontos_da_malha(est):
        return "desatualizado", ("A geometria mudou depois do cálculo (posição das barras ou dos vértices): gere a "
                                 "malha e recalcule antes de gerar o relatório.")
    return "atual", "O resultado corresponde ao modelo de agora."


# cores do tema Usinix nos símbolos de apoio e de carga (o FreeCAD usa verde-escuro, vermelho e azul)
COR_APOIO = (0.0, 0.227, 0.439)            # azul Usinix #003A70
COR_CARGA = (0.878, 0.631, 0.0)            # âmbar #E0A100 (o amarelo puro some no fundo claro)
TIPOS_APOIO = ("Fem::ConstraintFixed", "Fem::ConstraintDisplacement", "Fem::ConstraintSpring",
               "Fem::ConstraintPlaneRotation", "Fem::ConstraintRigidBody", "Fem::ConstraintContact",
               "Fem::ConstraintBearing", "Fem::ConstraintTransform")
TIPOS_CARGA = ("Fem::ConstraintForce", "Fem::ConstraintPressure", "Fem::ConstraintGear", "Fem::ConstraintPulley")


def cor_do_simbolo(obj):
    """Cor do tema para o símbolo da restrição, ou None se ela não tem símbolo de apoio/carga."""
    t = obj.TypeId
    if t in TIPOS_APOIO:
        return COR_APOIO
    if t in TIPOS_CARGA:
        return COR_CARGA
    return None


def pintar_simbolo(obj):
    """Aplica a cor do tema no símbolo de uma restrição nova (as de arquivos antigos ficam como estão)."""
    cor = cor_do_simbolo(obj)
    vo = getattr(obj, "ViewObject", None)
    if cor is None or vo is None or not hasattr(vo, "ShapeAppearance"):
        return False
    try:
        mats = list(vo.ShapeAppearance)
        for m in mats:
            m.DiffuseColor = cor + (1.0,) if len(m.DiffuseColor) == 4 else cor
        vo.ShapeAppearance = mats
        return True
    except Exception as exc:
        FreeCAD.Console.PrintLog("Usinix: cor da restrição %s: %s\n" % (obj.Name, exc))
        return False


# ícones da árvore dos objetos FEM em Python: o FreeCAD devolve o recurso interno (":/icons/X.svg"),
# que não passa pelo tema de ícones; troca pelo arquivo do tema Usinix quando ele existe
_VP_COM_ICONE = (("femviewprovider.view_base_femobject", "VPBaseFemObject"),
                 ("femviewprovider.view_material_common", "VPMaterialCommon"),
                 ("femviewprovider.view_mesh_gmsh", "VPMeshGmsh"),
                 ("femviewprovider.view_mesh_netgen", "VPMeshNetgen"),
                 ("femviewprovider.view_solver_ccxtools", "VPSolverCcxTools"),
                 ("femviewprovider.view_solver_calculix", "VPSolverCalculiX"))


def icone_do_tema(caminho):
    """Arquivo do tema Usinix para um ícone interno ":/icons/Nome.svg", ou o próprio caminho."""
    if not isinstance(caminho, str) or not caminho.startswith(":/"):
        return caminho
    nome = os.path.splitext(os.path.basename(caminho))[0]
    try:
        import UsinixEstilo
        f = UsinixEstilo._icon_file(nome)
    except Exception:
        f = None
    return f or caminho


def tema_icones_fem():
    """Passa os ícones da árvore dos objetos FEM em Python pelo tema (uma vez por sessão)."""
    if _obs.get("icones") or not FreeCAD.GuiUp:
        return
    import importlib
    for mod, cls in _VP_COM_ICONE:
        try:
            c = getattr(importlib.import_module(mod), cls)
        except Exception:
            continue
        orig = c.__dict__.get("getIcon")
        if orig is None or getattr(orig, "_usinix", False):
            continue

        def novo(self, _orig=orig):
            return icone_do_tema(_orig(self))
        novo._usinix = True
        c.getIcon = novo
    _obs["icones"] = True


def esconder_resultados_grandes(doc, limite=None):
    """Arquivo salvo com um resultado de malha enorme à mostra (convergência forçada): abrir já desenhando
    tudo deixava o programa parado. Esconde malha e resultados quando a malha passa do limite e avisa.
    Retorna os nomes escondidos."""
    if doc is None or not FreeCAD.GuiUp:
        return []
    limite = limite or F.LIMITE_NOS_CONVERGENCIA
    grandes = []
    for o in doc.Objects:
        try:
            if o.isDerivedFrom("Fem::FemMeshObject") and o.FemMesh.NodeCount > limite:
                grandes.append((o, o.FemMesh.NodeCount))
        except Exception:
            continue
    if not grandes:
        return []
    escondidos = []
    for o in doc.Objects:
        try:
            pesado = o.isDerivedFrom("Fem::FemMeshObject") or o.isDerivedFrom("Fem::FemPostObject") or \
                o.isDerivedFrom("Fem::FemResultObject")
            if pesado and o.ViewObject is not None and o.ViewObject.Visibility:
                o.ViewObject.Visibility = False
                escondidos.append(o.Name)
        except Exception:
            continue
    if escondidos:
        n = max(c for _o, c in grandes)
        FreeCAD.Console.PrintWarning(
            "Usinix: a malha de \"%s\" tem %s nós; o resultado foi escondido ao abrir para não travar o "
            "programa. Mostre-o pela árvore quando quiser.\n" % (grandes[0][0].Label, ("{:,}".format(n)).replace(",", ".")))
    return escondidos


class _ObservadorResultado:
    """Grava a assinatura quando um resultado termina de carregar (cálculo pela bancada ou pelo assistente)
    e pinta no tema Usinix os símbolos das restrições criadas."""

    def slotCreatedObject(self, obj):
        try:
            if obj.TypeId.startswith("Fem::") and not _obs.get("icones"):
                tema_icones_fem()
        except Exception as exc:
            FreeCAD.Console.PrintLog("Usinix: ícones FEM: %s\n" % exc)
        try:
            if not obj.TypeId.startswith("Fem::Constraint") or getattr(obj.Document, "Restoring", False):
                return
            nome, doc = obj.Name, obj.Document.Name
        except Exception:
            return

        def pinta():
            try:
                d = FreeCAD.getDocument(doc)
                o = d.getObject(nome) if d else None
                if o is not None:
                    pintar_simbolo(o)
            except Exception:
                pass
        try:
            QtCore.QTimer.singleShot(0, pinta)       # a vista do objeto ainda não existe neste instante
        except Exception:
            pass

    def slotCreatedDocument(self, doc):
        UsinixUtil.depois_de_abrir(self, doc, self._ao_abrir)

    def slotFinishRestoreDocument(self, doc):
        UsinixUtil.depois_de_abrir(self, doc, self._ao_abrir)

    def _ao_abrir(self, doc):
        # resultados escondidos no arquivo continuavam desenhando a barra de cores: refaz o hide() deles
        # (o pipeline remonta a barra depois do restauro e da 1ª pintura da vista: repete mais tarde também)
        try:
            esconder_resultados_grandes(doc)
        except Exception as exc:
            FreeCAD.Console.PrintLog("Usinix: resultado grande: %s\n" % exc)
        try:
            nome = doc.Name
            for ms in (0, 800, 2500, 6000):
                QtCore.QTimer.singleShot(ms, lambda n=nome: esconder_legendas(FreeCAD.listDocuments().get(n)))
        except Exception:
            pass

    def slotChangedObject(self, obj, prop):
        if prop != "Stats":
            return
        try:
            if not obj.isDerivedFrom("Fem::FemResultObject") or getattr(obj.Document, "Restoring", False):
                return
            if getattr(obj, "isRestoring", lambda: False)():
                return
            for a in obj.InList:
                if a.isDerivedFrom("Fem::FemAnalysis"):
                    gravar_assinatura(F.Estudo(analise=a))
            # o pipeline novo nasce sem campo e desenha a escala de −0,5 a +0,5: esconde depois de montado
            d = obj.Document
            for ms in (0, 800):
                QtCore.QTimer.singleShot(ms, lambda d=d: esconder_legendas(d))
        except Exception as exc:
            FreeCAD.Console.PrintLog("Usinix: assinatura do resultado: %s\n" % exc)


_obs = {}


def instalar():
    if "obs" not in _obs:
        _obs["obs"] = _ObservadorResultado()
        FreeCAD.addDocumentObserver(_obs["obs"])


# =========================================================================== validações e verificação
def avaliar(est, elu=True, gama=GAMA_A1, fs_min=1.5):
    """Tudo o que o relatório precisa, calculado uma vez."""
    mats = materiais(est)
    secs = secoes(est)
    vigas = bool(secs)
    massa = massa_vigas(est, mats, secs) if vigas else None
    if not vigas and est.peca is not None:
        try:
            sh = est.peca.Shape
            rho = next((m["rho"] for m in mats if m["rho"]), None)
            massa = sh.Volume * 1e-9 * rho if rho and sh.Volume > 0 else None
        except Exception:
            massa = None
    cgs = cargas(est, massa)
    reac = reacoes(est)
    eq = equilibrio(est, cgs, reac)
    e = F.estatisticas(est) or {}
    sy_mat = next((m for m in mats if m["Sy"] and not m["rigido"]), None)
    sy = sy_mat["Sy"] if sy_mat else None
    svm = e.get("svm_max")
    chave, txt_estado = estado(est)
    val = [(OK if chave == "atual" else ERRO, txt_estado)]
    if eq is None:
        if any(c["vetor"] is None for c in cgs):
            val.append((AVISO, "Equilíbrio não conferido: há carga de pressão (a resultante depende da área)."))
        elif not reac:
            val.append((AVISO, "Equilíbrio não conferido: o resultado não trouxe as reações de apoio."))
    else:
        ok, dif, sr, sc = eq
        val.append((OK if ok else ERRO, "Equilíbrio: a soma das reações (%s N) equilibra a soma das cargas (%s N), "
                    "diferença de %s." % (_vec(sr), _vec(sc), _fmt(dif, 2, "%")) if ok else
                    "Equilíbrio: a soma das reações (%s N) não equilibra a soma das cargas (%s N), diferença de %s. "
                    "Confira apoios e cargas." % (_vec(sr), _vec(sc), _fmt(dif, 2, "%"))))
    for c in cgs:
        o = c["obj"]
        if c["vetor"] is not None and F._eh(o, "Fem::ConstraintForce") and c["vetor"].z > 0.5 * c["vetor"].Length:
            val.append((AVISO, "A carga \"%s\" aponta para cima (+Z), contra a gravidade. Confira se é isso mesmo."
                        % c["rotulo"]))
        if F._eh(o, "Fem::ConstraintSelfWeight") and c["vetor"] is not None and c["vetor"].z > -0.5 * c["vetor"].Length:
            val.append((AVISO, "O peso próprio \"%s\" não aponta para baixo (−Z)." % c["rotulo"]))
    if not est.fixacoes:
        val.append((ERRO, "A análise não tem apoios."))
    if not mats:
        val.append((ERRO, "A análise não tem material."))
    elif sy is None:
        val.append((AVISO, "O material não tem limite de escoamento (nem na biblioteca do Usinix): a verificação de "
                    "tensão não foi feita."))
    elif sy_mat["fonte_sy"].startswith("biblioteca"):
        val.append((INFO, "Limite de escoamento de %s tirado da %s; confirme com o certificado do material." % (
            _fmt(sy, 0, "MPa"), sy_mat["fonte_sy"])))
    for sp in secs:
        if sp.get("paredes") and not sp.get("paredes_iguais"):
            val.append((AVISO, "Seção \"%s\": as quatro paredes do tubo têm espessuras diferentes (%s mm). O solver usa "
                        "BoxT1 a BoxT4; confira se é isso mesmo." % (sp["rotulo"], "; ".join(_fmt(x, 2) for x in
                                                                                      sp["paredes"]))))
    rig = [m for m in mats if m["rigido"]]
    if rig:
        val.append((INFO, "Elementos rígidos auxiliares (%s): servem para ligar e dar massa; as tensões neles não "
                    "têm significado físico." % ", ".join(m["rotulo"] for m in rig)))
    checar = [o.Label for o in [est.analise] + list(est.analise.Group) if "a checar" in o.Label.lower()] \
        if est.analise is not None else []
    if checar:
        val.append((AVISO, "Itens marcados \"a checar\" no próprio modelo: %s." % "; ".join(checar)))
    verif = None
    if svm and sy:
        if elu:
            lim = sy / gama
            verif = {"criterio": "σ von Mises ≤ fy / γa1 (cargas majoradas, ELU)", "limite": lim, "taxa": svm / lim,
                     "ok": svm <= lim, "texto": "%s ≤ %s / %s = %s" % (_fmt(svm, 1, "MPa"), _fmt(sy, 0), _fmt(gama, 2),
                                                                       _fmt(lim, 1, "MPa"))}
        else:
            fs = sy / svm
            verif = {"criterio": "Fator de segurança ao escoamento fy / σ ≥ %s" % _fmt(fs_min, 2), "limite": fs_min,
                     "taxa": fs_min / fs, "ok": fs >= fs_min, "fs": fs,
                     "texto": "%s / %s = %s" % (_fmt(sy, 0, "MPa"), _fmt(svm, 1, "MPa"), _fmt(fs, 2))}
        val.append((OK if verif["ok"] else ERRO, "Verificação de tensão: %s (%s)." % (
            verif["texto"], "atende" if verif["ok"] else "não atende")))
    return {"mats": mats, "secs": secs, "vigas": vigas, "massa": massa, "cargas": cgs, "reacoes": reac, "eq": eq,
            "reacoes_nos": reacoes_por_no(est),
            "est": e, "Sy": sy, "verif": verif, "val": val, "estado": chave, "elu": elu, "gama": gama,
            "fs_min": fs_min}


def _vec(v):
    return "%s; %s; %s" % (_fmt(v.x, 1), _fmt(v.y, 1), _fmt(v.z, 1))


# =========================================================================== relatório
def _texto_subs(subs, limite=8):
    nomes = [s for _o, s in subs]
    if not nomes:
        return "Modelo inteiro"
    if len(nomes) > limite:
        return "%s… (%d no total)" % (", ".join(nomes[:limite]), len(nomes))
    return ", ".join(nomes)


def corpo(est, doc, imgs, largura, a=None):
    import UsinixFEMRelatorio as R
    a = a or est._avaliacao
    e = a["est"]
    peca = est.peca
    h = []
    alvo = est.get("UsinixRelPeca", "") or (peca.Label if peca is not None else "o modelo")
    h.append("<h1>1. Objetivo</h1>")
    h.append("<p>Avaliar as tensões, os deslocamentos e as reações de apoio de <b>%s</b> na análise <b>%s</b>, por "
             "análise estática linear pelo método dos elementos finitos%s.</p>" % (
                 alvo, est.analise.Label, " com elementos de viga" if a["vigas"] else ""))

    h.append("<h1>2. Modelo</h1>")
    h.append(R._img(doc, "modelo", imgs.get("modelo"), "Figura 1 — Modelo com apoios e cargas", largura))
    lin = [R._par("Análise", est.analise.Label), R._par("Geometria do cálculo", peca.Label if peca else "—")]
    if a["vigas"]:
        n = sum(s["n"] for s in a["secs"])
        L = sum(s["comprimento"] for s in a["secs"])
        lin += [R._par("Barras (elementos de viga)", "%d trechos, %s de comprimento total" % (n, _fmt(L / 1000.0, 2, "m"))),
                R._par("Massa do modelo", _fmt(a["massa"], 1, "kg") if a["massa"] else "—")]
    else:
        try:
            bb = peca.Shape.BoundBox
            lin.append(R._par("Dimensões externas", "%s × %s × %s mm" % (_fmt(bb.XLength, 1), _fmt(bb.YLength, 1),
                                                                        _fmt(bb.ZLength, 1))))
        except Exception:
            pass
        lin.append(R._par("Massa", _fmt(a["massa"], 2, "kg") if a["massa"] else "—"))
    h.append(R._tab(lin, larguras=["40%", "60%"]))

    h.append("<h1>3. Materiais</h1>")
    h.append(R._tab([[m["rotulo"], _fmt(m["E"] / 1000.0 if m["E"] else None, 1, "GPa"), _fmt(m["nu"], 2),
                      _fmt(m["rho"], 0, "kg/m³"),
                      (_fmt(m["Sy"], 0, "MPa") + ("<br><span class='nota'>%s</span>" % m["fonte_sy"]
                                                  if m["fonte_sy"] and m["Sy"] else "")) if not m["rigido"]
                      else "rígido auxiliar", _texto_subs(m["subs"], 4)] for m in a["mats"]] or [["—"] * 6],
                    cab=["Material", "E", "ν", "ρ", "fy", "Onde"], larguras=["28%", "11%", "7%", "13%", "17%", "24%"]))
    h.append("<p class='nota'>Modelo linear elástico isotrópico. As propriedades devem ser confirmadas com o "
             "certificado do material empregado.</p>")

    num = 4
    if a["vigas"]:
        h.append("<h1>%d. Seções das barras</h1>" % num)
        h.append(R._tab([[s["rotulo"], s["tipo"], _fmt(s["A"], 1, "mm²"),
                          "%s / %s" % (_fmt(s["I1"] / 1e4 if s["I1"] else None, 2), _fmt(s["I2"] / 1e4 if s["I2"]
                                                                                       else None, 2)),
                          "%d · %s" % (s["n"], _fmt(s["comprimento"] / 1000.0, 2, "m"))] for s in a["secs"]],
                        cab=["Seção", "Tipo", "Área", "I1 / I2 (cm⁴)", "Barras"],
                        larguras=["26%", "28%", "13%", "16%", "17%"]))
        num += 1

    h.append("<h1>%d. Apoios</h1>" % num)
    h.append(R._tab([[x["rotulo"], x["graus"], _texto_subs(x["subs"])] for x in apoios(est)] or
                    [["—", "Sem apoios", "—"]], cab=["Apoio", "Graus de liberdade", "Pontos"],
                    larguras=["32%", "42%", "26%"]))
    num += 1
    h.append("<h1>%d. Cargas</h1>" % num)
    h.append(R._tab([[c["rotulo"], c["tipo"], c["valor"], c["dir"], _texto_subs(c["subs"], 5)] for c in a["cargas"]] or
                    [["—", "Sem cargas", "—", "—", "—"]], cab=["Carga", "Tipo", "Valor", "Direção", "Onde"],
                    larguras=["30%", "13%", "19%", "18%", "20%"]))
    num += 1

    h.append("<h1>%d. Malha e solução</h1>" % num)
    m = est.malha
    lin = []
    if m is not None:
        fm = m.FemMesh
        ordem2 = getattr(m, "ElementOrder", "2nd") == "2nd"
        if a["vigas"]:
            elem = "Viga de %s (%d nós), expandida pelo CalculiX" % ("2ª ordem" if ordem2 else "1ª ordem",
                                                                    3 if ordem2 else 2)
            nel = fm.EdgeCount
        else:
            elem = "Tetraédrico de %s" % ("2ª ordem" if ordem2 else "1ª ordem")
            nel = fm.VolumeCount or fm.FaceCount
        lin += [R._par("Gerador", "Gmsh"), R._par("Elemento", elem),
                R._par("Tamanho máximo do elemento", str(getattr(m, "CharacteristicLengthMax", "—"))),
                R._par("Nós / elementos", "%s / %s" % (_fmt(fm.NodeCount, 0), _fmt(nel, 0)))]
    lin += [R._par("Solver", "CalculiX" + (" " + est.get("UsinixCcxVersao") if est.get("UsinixCcxVersao") else "")),
            R._par("Tipo de análise", "Estática linear"),
            R._par("Calculado em", est.get("UsinixCalculadoEm", "") or "—")]
    h.append(R._tab(lin, larguras=["40%", "60%"]))
    num += 1

    h.append("<h1>%d. Resultados</h1>" % num)
    h.append(R._tab([R._par("Tensão máxima de von Mises", "<span class='destaque'>%s</span>" % _fmt(e.get("svm_max"), 1, "MPa")),
                     R._par("Deslocamento máximo", "<span class='destaque'>%s</span>" % _fmt(e.get("u_max"), 3, "mm"))],
                    larguras=["55%", "45%"]))
    h.append(R._img(doc, "tensao", imgs.get("tensao"), "Figura 2 — Tensão equivalente de von Mises: de 0 (azul) a %s "
                    "(vermelho)" % _fmt(e.get("svm_max"), 1, "MPa"), largura))
    h.append(R._img(doc, "deslocamento", imgs.get("deslocamento"), "Figura 3 — Deslocamento total: de 0 (azul) a %s "
                    "(vermelho)" % _fmt(e.get("u_max"), 3, "mm"), largura))
    num += 1

    h.append("<h1>%d. Reações de apoio e equilíbrio</h1>" % num)
    reac = a["reacoes"]
    if reac:
        nomes = {o.Name: rotulo(o) for o in est.fixacoes}
        lin = [[nomes.get(k, k), _fmt(r.x, 1), _fmt(r.y, 1), _fmt(r.z, 1)] for k, r in reac.items()]
        if a["eq"] is not None:
            _ok, dif, sr, sc = a["eq"]
            lin.append(["<b>Soma das reações</b>", _fmt(sr.x, 1), _fmt(sr.y, 1), _fmt(sr.z, 1)])
            lin.append(["<b>Soma das cargas aplicadas</b>", _fmt(sc.x, 1), _fmt(sc.y, 1), _fmt(sc.z, 1)])
        h.append(R._tab(lin, cab=["Apoio", "Fx (N)", "Fy (N)", "Fz (N)"], larguras=["46%", "18%", "18%", "18%"]))
        if a["eq"] is not None:
            ok, dif, _sr, _sc = a["eq"]
            h.append("<p>%s: a diferença entre as reações e as cargas aplicadas é de %s (critério adotado: até %s da "
                     "resultante, mais 5 %% do peso próprio, que o solver integra de forma aproximada nas vigas).</p>"
                     % ("O modelo está em equilíbrio" if ok else "O modelo NÃO está em equilíbrio", _fmt(dif, 2, "%"),
                        _fmt(LIMITE_EQUILIBRIO, 0, "%")))
    else:
        h.append("<p>O resultado não trouxe as reações de apoio.</p>")
    por_no = {k: v for k, v in (a.get("reacoes_nos") or {}).items() if len(v) > 1}
    if por_no:
        nomes = {o.Name: rotulo(o) for o in est.fixacoes}
        lin = []
        for k, lst in por_no.items():
            for no, pos, r in sorted(lst, key=lambda t: (t[1].x, t[1].y, t[1].z) if t[1] is not None else (t[0],)):
                lin.append([nomes.get(k, k), "%d" % no,
                            "%s; %s; %s" % (_fmt(pos.x, 0), _fmt(pos.y, 0), _fmt(pos.z, 0)) if pos is not None else "—",
                            _fmt(r.x, 1), _fmt(r.y, 1), _fmt(r.z, 1), _fmt(r.Length, 1)])
        h.append("<p>Reação em cada nó dos apoios com mais de um ponto (para dimensionar parafusos, correntes e "
                 "chumbadores):</p>")
        h.append(R._tab(lin, cab=["Apoio", "Nó", "Posição x; y; z (mm)", "Fx (N)", "Fy (N)", "Fz (N)", "|F| (N)"],
                        larguras=["22%", "7%", "21%", "12%", "12%", "12%", "14%"]))
    num += 1

    h.append("<h1>%d. Verificação e validação do modelo</h1>" % num)
    v = a["verif"]
    if v:
        h.append(R._tab([R._par("Critério", v["criterio"]), R._par("Cálculo", v["texto"]),
                         R._par("Taxa de uso", "<span class='destaque'>%s</span>" % _fmt(v["taxa"], 2)),
                         R._par("Resultado", "<span class='destaque'>%s</span>" % ("ATENDE" if v["ok"] else "NÃO ATENDE"))],
                        larguras=["35%", "65%"]))
        if a["elu"]:
            h.append("<p class='nota'>γa1 = %s (ABNT NBR 8800:2024). As cargas da análise devem estar majoradas "
                     "pelas combinações últimas.</p>" % _fmt(a["gama"], 2))
    marca = {OK: "✓", AVISO: "!", ERRO: "✗", INFO: "i"}
    cor = {OK: "#2E7D4F", AVISO: "#9A6B00", ERRO: "#B3261E", INFO: "#5B6876"}
    h.append(R._tab([["<span style='color:%s'><b>%s</b></span>" % (cor[n], marca[n]), t] for n, t in a["val"]],
                    larguras=["6%", "94%"]))
    num += 1

    h.append("<h1>%d. Premissas e limitações</h1>" % num)
    prem = ["Material linear elástico, homogêneo e isotrópico; não há plasticidade no modelo.",
            "Pequenos deslocamentos e pequenas deformações (sem não linearidade geométrica)."]
    if a["vigas"]:
        prem += ["Barras representadas por elementos de viga nas linhas de centro; ligações, soldas, furos e "
                 "excentricidades não modelados, salvo onde indicado nas seções.",
                 "Seções equivalentes e elementos rígidos auxiliares, quando houver, representam peças que não estão "
                 "no catálogo de seções do solver."]
    else:
        prem += ["Fixações ideais: as faces travadas não se deslocam, o que tende a ser mais rígido que o apoio real.",
                 "Picos de tensão em cantos vivos e nas bordas das fixações podem ser singularidades numéricas."]
    prem.append("Os resultados valem apenas para as cargas e condições descritas neste relatório.")
    h.append("<ul>" + "".join("<li style='margin-bottom:4px'>%s</li>" % p for p in prem) + "</ul>")
    num += 1

    h.append("<h1>%d. Conclusão</h1>" % num)
    if v:
        h.append("<p>%s</p>" % (
            "A tensão máxima de von Mises (%s) atende ao critério adotado (%s), com taxa de uso de %s, nas condições "
            "analisadas." % (_fmt(e.get("svm_max"), 1, "MPa"), v["criterio"], _fmt(v["taxa"], 2)) if v["ok"] else
            "A tensão máxima de von Mises (%s) não atende ao critério adotado (%s): taxa de uso de %s."
            % (_fmt(e.get("svm_max"), 1, "MPa"), v["criterio"], _fmt(v["taxa"], 2))))
    obs = (est.get("UsinixRelObs", "") or "").strip()
    if obs:
        h.append("<p>%s</p>" % obs.replace("\n", "<br>"))
    h.append("<p class='nota'>A aceitação do resultado é do responsável técnico.</p>")
    resp, crea, art = (est.get("UsinixRelResp", "") or ""), (est.get("UsinixRelCrea", "") or ""), \
        (est.get("UsinixRelArt", "") or "")
    h.append("<br><table width='100%'><tr><td width='15%'></td>"
             "<td width='70%' align='center' style='border-top:1px solid #1F2A36; padding-top:6px'>"
             "<b>{}</b><br><span class='rot'>{}{}</span></td><td width='15%'></td></tr></table>".format(
                 resp or "Responsável técnico", ("CREA " + crea) if crea else "", (" · ART " + art) if art else ""))
    return "<html><body>%s</body></html>" % "".join(h)


def capturas(est, pasta):
    """Vista do modelo, da tensão e do deslocamento, com as outras análises do documento escondidas."""
    import UsinixFEMRelatorio as R
    outros = [o for a in analises(est.doc) if a != est.analise for o in a.Group
              if getattr(o, "ViewObject", None) is not None]
    for o in outros:
        try:
            o.ViewObject.Visibility = False
        except Exception:
            pass
    esconder_legendas(est.doc)
    imgs = {"modelo": _captura_modelo(est, pasta)}
    if est.resultados:
        imgs["tensao"] = R._captura(est, "tensao", pasta)
        imgs["deslocamento"] = R._captura(est, "deslocamento", pasta)
    F.mostrar_campo(est, "modelo")
    esconder_legendas(est.doc)
    return imgs


def _captura_modelo(est, pasta):
    """Modelo com apoios e cargas. Nas vigas, as barras aparecem com a seção (a malha expandida do resultado), em
    cinza, em vez das linhas de centro."""
    import UsinixFEMRelatorio as R
    malhas = []
    if secoes(est):
        for r in est.resultados:
            m = getattr(r, "Mesh", None)
            if m is not None and getattr(m, "ViewObject", None) is not None:
                vo = m.ViewObject
                malhas.append((vo, vo.Visibility, vo.DisplayMode, vo.ShapeColor))
    if not malhas:
        return R._captura(est, "modelo", pasta)
    F.mostrar_campo(est, "modelo")
    try:
        for vo, _v, _d, _c in malhas:
            vo.Visibility = True
            vo.DisplayMode = "Faces"
            vo.ShapeColor = (0.72, 0.75, 0.79)
        if est.peca is not None:
            est.peca.ViewObject.Visibility = True
        caminho = os.path.join(pasta, "modelo.png")
        v = R._vista()
        FreeCADGui.updateGui()
        v.viewIsometric()
        v.fitAll()
        FreeCADGui.updateGui()
        v.saveImage(caminho, 1800, 1150, "White")
        return caminho if os.path.isfile(caminho) else None
    except Exception as exc:
        FreeCAD.Console.PrintWarning("Usinix: captura do modelo falhou: %s\n" % exc)
        return R._captura(est, "modelo", pasta)
    finally:
        for vo, vis, modo, cor in malhas:
            try:
                vo.DisplayMode, vo.ShapeColor, vo.Visibility = modo, cor, vis
            except Exception:
                pass


def esconder_legendas(doc):
    """A barra de cores dos resultados é compartilhada entre os resultados do documento. Ela ficava na tela, com a
    escala de −0,5 a 0,5 (sem significado), quando o resultado mostrado tinha o campo "None" ou quando um
    resultado escondido no arquivo não tinha passado pelo hide(). Esconde o que não mostra campo nenhum e repete o
    hide() de quem está escondido."""
    if doc is None or FreeCADGui is None:
        return
    for o in doc.Objects:
        try:
            if not o.isDerivedFrom("Fem::FemPostObject") or o.isDerivedFrom("Fem::FemPostDataAtPointFilter"):
                continue
            vo = o.ViewObject
            if vo.Visibility and getattr(vo, "Field", "") == "None":
                vo.Visibility = False
            if not vo.Visibility:
                vo.hide()
        except Exception:
            pass


def gerar_pdf(analise, caminho, elu=True, gama=GAMA_A1, fs_min=1.5, forcar=False):
    """Gera o relatório da análise. Recusa resultado que não corresponde ao modelo (a não ser com forcar)."""
    import UsinixFEMRelatorio as R
    est = F.Estudo(analise=analise)
    if est.tipo != "static":
        raise ValueError("O relatório da bancada é para análise estática; a análise modal sai pelo assistente.")
    chave, txt = estado(est)
    if chave != "atual" and not forcar:
        raise ValueError(txt)
    if not est.get("UsinixRelTitulo", ""):
        est.put("UsinixRelTitulo", analise.Label)
    est._avaliacao = avaliar(est, elu, gama, fs_min)
    R.gerar(est, caminho, corpo=lambda e, d, i, l: corpo(e, d, i, l), capturas=capturas)
    esconder_legendas(est.doc)
    est.put("UsinixRelatorioPDF", caminho)
    return caminho, est._avaliacao


def recalcular(analise):
    est = F.Estudo(analise=analise)
    ok, erro, dt = F.calcular(est)
    if ok:
        gravar_assinatura(est)
    return ok, erro, dt


# =========================================================================== bancada
if P is not None:
    class PainelRelatorioMEF(P.PainelTarefa):
        titulo = "Relatório da análise"
        icone_cmd = "relatorio_mef.svg"
        ajuda = ("Escolha uma análise do documento (feita na bancada ou no assistente) e gere o relatório completo: "
                 "vistas, materiais, seções, apoios, cargas, resultados, reações, equilíbrio e verificação.")

        CAMPOS = (("UsinixRelTitulo", "Título"), ("UsinixRelCliente", "Cliente"),
                  ("UsinixRelProjeto", "Equipamento / projeto"), ("UsinixRelPeca", "Peça analisada"),
                  ("UsinixRelResp", "Responsável técnico"), ("UsinixRelCrea", "CREA"), ("UsinixRelArt", "ART nº"))

        def montar(self):
            f = self.form
            s1 = f.secao("Análise", "comando")
            self.lista_an = analises()
            self.combo = QtWidgets.QComboBox()
            self.combo.addItems([a.Label for a in self.lista_an])
            ativa = self._analise_inicial()
            if ativa in self.lista_an:
                self.combo.setCurrentIndex(self.lista_an.index(ativa))
            s1.linha("selecao", self.combo, "A análise que vai para o relatório.", "Análise")
            self.situacao = QtWidgets.QLabel("—")
            self.situacao.setWordWrap(True)
            self.situacao.setTextFormat(QtCore.Qt.RichText)
            s1.widget(self.situacao)
            self.bt_calc = QtWidgets.QPushButton("Recalcular esta análise")
            self.bt_calc.clicked.connect(self._recalcular)
            s1.widget(self.bt_calc)
            s2 = f.secao("Verificação", "info")
            self.elu = P.marcar("Cargas majoradas (ELU): comparar com fy / γa1", True)
            self.gama = P.numero(GAMA_A1, 1.0, 2.0, "", 2)
            self.fs = P.numero(1.5, 1.0, 10.0, "", 2)
            s2.linha("tipo", self.elu, "")
            self.l_gama = s2.widget(self._campo("γa1", self.gama,
                                                "Coeficiente de ponderação da resistência (NBR 8800:2024)."))
            self.l_fs = s2.widget(self._campo("FS mínimo", self.fs,
                                              "Fator de segurança mínimo exigido, definido pelo responsável técnico."))
            self.elu.toggled.connect(self._modo)
            s3 = f.secao("Capa e assinatura", "texto", aberta=False)
            self.campos = {}
            for chave, rot in self.CAMPOS:
                e = QtWidgets.QLineEdit()
                s3.linha("texto", e, "", rot)
                self.campos[chave] = e
            self.obs = QtWidgets.QPlainTextEdit()
            self.obs.setPlaceholderText("Observações e conclusão do responsável")
            self.obs.setMaximumHeight(90)
            s3.widget(self.obs)
            self.combo.currentIndexChanged.connect(self._carregar)
            self._carregar()

        def _campo(self, rotulo, w, dica):
            caixa = QtWidgets.QWidget()
            lay = QtWidgets.QHBoxLayout(caixa)
            lay.setContentsMargins(28, 0, 0, 0)
            lb = QtWidgets.QLabel(rotulo)
            lb.setToolTip(dica)
            w.setToolTip(dica)
            lay.addWidget(lb)
            lay.addStretch(1)
            w.setMaximumWidth(110)
            lay.addWidget(w)
            return caixa

        def _analise_inicial(self):
            sel = FreeCADGui.Selection.getSelection()
            for o in sel:
                if o.isDerivedFrom("Fem::FemAnalysis"):
                    return o
                for a in o.InList:
                    if a.isDerivedFrom("Fem::FemAnalysis"):
                        return a
            try:
                import FemGui
                return FemGui.getActiveAnalysis()
            except Exception:
                return None

        def analise(self):
            i = self.combo.currentIndex()
            return self.lista_an[i] if 0 <= i < len(self.lista_an) else None

        def _modo(self, *_a):
            for w, v in ((self.l_gama, self.elu.isChecked()), (self.l_fs, not self.elu.isChecked())):
                try:
                    w.setVisible(v)
                except Exception:
                    pass

        def _carregar(self, *_a):
            a = self.analise()
            if a is None:
                self.situacao.setText("O documento não tem análise.")
                return
            est = F.Estudo(analise=a)
            for chave, e in self.campos.items():
                e.setText(est.get(chave, "") or (a.Label if chave == "UsinixRelTitulo" else ""))
            self.obs.setPlainText(est.get("UsinixRelObs", "") or "")
            self.elu.setChecked("elu" in a.Label.lower() or bool(est.get("UsinixRelELU", True)))
            self._modo()
            self._situacao()

        def _situacao(self):
            a = self.analise()
            if a is None:
                return
            est = F.Estudo(analise=a)
            chave, txt = estado(est)
            cor = {"atual": "#2E7D4F"}.get(chave, "#B3261E")
            linhas = ["<span style='color:%s'><b>%s</b></span>" % (cor, txt)]
            if chave == "atual":
                av = avaliar(est, self.elu.isChecked(), self.gama.value(), self.fs.value())
                for n, t in av["val"][1:]:
                    c = {OK: "#2E7D4F", ERRO: "#B3261E", AVISO: "#9A6B00"}.get(n, "#5B6876")
                    linhas.append("<span style='color:%s'>%s</span>" % (c, t.replace("<", "&lt;")))
            self.situacao.setText("<br>".join(linhas))
            self.bt_calc.setVisible(est.tipo == "static")

        def _recalcular(self):
            a = self.analise()
            if a is None:
                return
            QtWidgets.QApplication.setOverrideCursor(QtCore.Qt.WaitCursor)
            try:
                ok, erro, dt = recalcular(a)
            finally:
                QtWidgets.QApplication.restoreOverrideCursor()
            if ok:
                self.form.mensagem.mostrar("Recalculado em %s s." % _fmt(dt, 1), "ok")
            else:
                self.form.mensagem.mostrar(erro, "erro")
            self._situacao()

        def pendencia(self):
            a = self.analise()
            if a is None:
                return "O documento não tem análise para o relatório."
            est = F.Estudo(analise=a)
            if est.tipo != "static":
                return "O relatório da bancada é para análise estática; a modal sai pelo assistente."
            chave, txt = estado(est)
            return None if chave == "atual" else txt

        def pronto_texto(self):
            return "OK escolhe onde gravar o PDF."

        def _salvar_campos(self, est):
            for chave, e in self.campos.items():
                if est.get(chave, "") != e.text():
                    est.put(chave, e.text())
            if est.get("UsinixRelObs", "") != self.obs.toPlainText():
                est.put("UsinixRelObs", self.obs.toPlainText())
            est.put("UsinixRelELU", self.elu.isChecked(), "App::PropertyBool")

        def caminho_padrao(self, a):
            doc = a.Document
            base = os.path.splitext(doc.FileName)[0] if doc.FileName else os.path.join(UsinixUtil.pasta_padrao(doc),
                                                                                         doc.Label)
            nome = re.sub(r"[\\\\/:*?\"<>|]", "-", a.Label)
            return "%s - relatorio %s.pdf" % (base, nome)

        def executar(self, caminho=None):
            a = self.analise()
            est = F.Estudo(analise=a)
            self._salvar_campos(est)
            if caminho is None:
                caminho, _f = QtWidgets.QFileDialog.getSaveFileName(None, "Salvar relatório", self.caminho_padrao(a),
                                                                    "PDF (*.pdf)")
                if not caminho:
                    raise ValueError("Escolha onde gravar o PDF.")
            QtWidgets.QApplication.setOverrideCursor(QtCore.Qt.WaitCursor)
            try:
                gerar_pdf(a, caminho, self.elu.isChecked(), self.gama.value(), self.fs.value())
            finally:
                QtWidgets.QApplication.restoreOverrideCursor()
            self.pdf = caminho
            try:
                QtCore.QTimer.singleShot(200, lambda: _abrir(caminho))
            except Exception:
                pass
            return []

    def _abrir(caminho):
        if os.environ.get("USINIX_TESTE"):
            return
        try:
            from PySide import QtGui
            QtGui.QDesktopServices.openUrl(QtCore.QUrl.fromLocalFile(caminho))
        except Exception:
            pass

    class CmdRelatorioMEF:
        def GetResources(self):
            import UsinixUtil
            return {"Pixmap": UsinixUtil.icone("relatorio_mef.svg"), "MenuText": "Relatório da análise",
                    "ToolTip": "Relatório completo em PDF de uma análise do documento, montada na bancada ou no "
                               "assistente: vistas, materiais, seções, apoios, cargas, resultados, reações, "
                               "equilíbrio e verificação."}

        def IsActive(self):
            return bool(analises())

        def Activated(self):
            PainelRelatorioMEF().mostrar()


    def _analise_escolhida():
        try:
            for o in FreeCADGui.Selection.getSelection():
                if o.isDerivedFrom("Fem::FemAnalysis"):
                    return o
                for p in o.InList:
                    if p.isDerivedFrom("Fem::FemAnalysis"):
                        return p
            import FemGui
            a = FemGui.getActiveAnalysis()
            if a is not None:
                return a
        except Exception:
            pass
        lst = analises()
        return lst[0] if len(lst) == 1 else None

    class CmdDuplicarAnalise:
        def GetResources(self):
            return {"Pixmap": UsinixUtil.icone("duplicar_analise.svg"), "MenuText": "Duplicar análise",
                    "ToolTip": "Cópia da análise escolhida (material, seções, apoios, cargas, malha e solver) sobre "
                               "a mesma geometria, para montar outro caso de carga ou de apoio. Os rótulos ficam "
                               "iguais no relatório; a cópia nasce sem resultado."}

        def IsActive(self):
            return _analise_escolhida() is not None

        def Activated(self):
            a = _analise_escolhida()
            if a is None:
                return
            doc = a.Document
            doc.openTransaction("Duplicar análise")
            try:
                n = duplicar_analise(a)
                doc.commitTransaction()
            except Exception as exc:
                doc.abortTransaction()
                QtWidgets.QMessageBox.warning(FreeCADGui.getMainWindow(), "Duplicar análise", str(exc))
                return
            try:
                import FemGui
                FemGui.setActiveAnalysis(n)
            except Exception:
                pass
            FreeCADGui.Selection.clearSelection()
            FreeCADGui.Selection.addSelection(n)


    class CmdCargaNaPonta:
        def GetResources(self):
            return {"Pixmap": UsinixUtil.icone("carga_ponta.svg"), "MenuText": "Carga na ponta",
                    "ToolTip": "Força vertical para baixo no ponto do modelo de barras mais distante dos apoios "
                               "(pessoa com carga na ponta de uma plataforma). Informe a massa conforme a norma "
                               "que se aplica ao projeto."}

        def IsActive(self):
            return _analise_escolhida() is not None

        def Activated(self):
            a = _analise_escolhida()
            if a is None:
                return
            kg, ok = QtWidgets.QInputDialog.getDouble(FreeCADGui.getMainWindow(), "Carga na ponta",
                                                      "Massa no ponto mais distante dos apoios (kg):", 100.0, 0.1,
                                                      100000.0, 1)
            if not ok:
                return
            doc = a.Document
            doc.openTransaction("Carga na ponta")
            try:
                c, _p, _d = carga_no_ponto_mais_distante(a, kg)
                doc.commitTransaction()
            except Exception as exc:
                doc.abortTransaction()
                QtWidgets.QMessageBox.warning(FreeCADGui.getMainWindow(), "Carga na ponta", str(exc))
                return
            FreeCADGui.Selection.clearSelection()
            FreeCADGui.Selection.addSelection(c)


def registrar_comandos():
    if FreeCADGui is not None and P is not None and "Usinix_CargaNaPonta" not in FreeCADGui.listCommands():
        FreeCADGui.addCommand("Usinix_CargaNaPonta", CmdCargaNaPonta())
    if FreeCADGui is not None and P is not None and "Usinix_RelatorioMEF" not in FreeCADGui.listCommands():
        FreeCADGui.addCommand("Usinix_RelatorioMEF", CmdRelatorioMEF())
    if FreeCADGui is not None and P is not None and "Usinix_DuplicarAnalise" not in FreeCADGui.listCommands():
        FreeCADGui.addCommand("Usinix_DuplicarAnalise", CmdDuplicarAnalise())
