# SPDX-License-Identifier: LGPL-2.1-or-later
"""Validação do cálculo: o Usinix resolve casos clássicos com solução conhecida e compara.

Cada caso monta o modelo do zero (num documento temporário, que é fechado no fim), calcula com o mesmo motor
das bancadas e confere o resultado com a fórmula fechada da resistência dos materiais. O relatório em PDF traz,
para cada caso, o modelo, a fórmula, o valor de referência, o valor do Usinix, a diferença e a tolerância.

Motores verificados:
- análise por barras (UsinixPortico: rigidez direta, 1ª e 2ª ordem, frequências);
- elementos finitos sólidos (Gmsh + CalculiX, estática e frequências).

Referências das fórmulas (soluções clássicas, de qualquer livro de resistência dos materiais e vibrações):
Timoshenko e Gere, "Mecânica dos Materiais"; Timoshenko e Gere, "Theory of Elastic Stability" (coluna em
balanço com carga axial e lateral); Blevins, "Formulas for Natural Frequency and Mode Shape".
"""

import math
import os
import tempfile
import time

import FreeCAD

try:
    import FreeCADGui
    from PySide import QtCore, QtWidgets
    import UsinixPainel as P
except Exception:          # sem interface (testes de linha de comando)
    FreeCADGui = None
    P = None

E_ACO = 200000.0            # MPa
NU_ACO = 0.3
RHO_ACO = 7.85e-9           # t/mm³ (7850 kg/m³)


class Resultado:
    def __init__(self, caso, usinix=None, referencia=None, erro=""):
        self.caso = caso
        self.usinix = usinix
        self.referencia = referencia
        self.erro = erro          # texto quando o caso não rodou (ex.: sem CalculiX)

    @property
    def diferenca(self):
        if self.usinix is None or not self.referencia:
            return None
        return 100.0 * (self.usinix - self.referencia) / abs(self.referencia)

    @property
    def ok(self):
        d = self.diferenca
        return d is not None and abs(d) <= self.caso["tol"]


# =========================================================================== análise por barras
def _secao(massa_kgm=0.0):
    import UsinixPortico as M
    # seção fictícia (inércias iguais nos dois eixos): só a rigidez importa para a comparação
    return M.Secao(A=2000.0, Iy=2.0e6, Iz=2.0e6, J=1.0e5, E=E_ACO, Gc=77000.0, massa_kgm=massa_kgm, nome="ref")


def _viga(n, L, vertical=False, massa_kgm=0.0):
    """Modelo com n barras iguais em linha (ao longo de X, ou de Z se vertical)."""
    import numpy as np
    import UsinixPortico as M
    m = M.Modelo()
    s = _secao(massa_kgm)
    nos = [m.no((0, 0, L * k / n) if vertical else (L * k / n, 0, 0)) for k in range(n + 1)]
    eixo_z = np.array([1.0, 0.0, 0.0]) if vertical else np.array([0.0, 0.0, 1.0])
    for a, b in zip(nos, nos[1:]):
        m.barras.append(M.Barra(a, b, s, eixo_z, "B%d" % a))
    return m, nos


def b1_balanco():
    import UsinixPortico as M
    L, P_kN = 2000.0, 10.0
    m, nos = _viga(1, L)
    m.apoios[nos[0]] = [True] * 6
    c = M.Caso("P")
    c.nos.append((nos[-1], [0, 0, -P_kN], [0, 0, 0]))
    r = m.resolver(c)
    usinix = abs(r.deslocamento(nos[-1])[2])
    ref = P_kN * 1000.0 * L ** 3 / (3 * E_ACO * 2.0e6)
    return usinix, ref


def b2_biapoiada():
    import UsinixPortico as M
    L, q = 4000.0, 5.0                        # kN/m = N/mm
    m, nos = _viga(1, L)
    m.apoios[nos[0]] = [True, True, True, True, False, False]
    m.apoios[nos[-1]] = [False, True, True, False, False, False]
    c = M.Caso("q")
    c.distribuidas.append((0, [0, 0, -q], True))
    r = m.resolver(c)
    usinix = r.flecha_local(0, 41)[1]
    ref = 5 * q * L ** 4 / (384 * E_ACO * 2.0e6)
    return usinix, ref


def b2m_biapoiada_momento():
    import UsinixPortico as M
    L, q = 4000.0, 5.0
    m, nos = _viga(1, L)
    m.apoios[nos[0]] = [True, True, True, True, False, False]
    m.apoios[nos[-1]] = [False, True, True, False, False, False]
    c = M.Caso("q")
    c.distribuidas.append((0, [0, 0, -q], True))
    r = m.resolver(c)
    usinix = abs(r.maximos(0, 41)["My"]) / 1e6
    ref = q * L ** 2 / 8.0 / 1e6
    return usinix, ref


def b3_biengastada():
    import UsinixPortico as M
    L, q = 4000.0, 5.0
    m, nos = _viga(1, L)
    m.apoios[nos[0]] = [True] * 6
    m.apoios[nos[-1]] = [True] * 6
    c = M.Caso("q")
    c.distribuidas.append((0, [0, 0, -q], True))
    r = m.resolver(c)
    usinix = abs(r.esforcos(0, 0.0)["My"]) / 1e6
    ref = q * L ** 2 / 12.0 / 1e6
    return usinix, ref


def b4_coluna_segunda_ordem():
    import UsinixPortico as M
    L, P_kN, H_kN = 3000.0, 50.0, 1.0
    m, nos = _viga(8, L, vertical=True)
    m.apoios[nos[0]] = [True] * 6
    c = M.Caso("PH")
    c.nos.append((nos[-1], [H_kN, 0, -P_kN], [0, 0, 0]))
    r = m.resolver(c, segunda_ordem=True)
    usinix = abs(r.deslocamento(nos[-1])[0])
    EI = E_ACO * 2.0e6
    P_N, H_N = P_kN * 1000.0, H_kN * 1000.0
    k = math.sqrt(P_N / EI)
    ref = H_N / P_N * (math.tan(k * L) / k - L)
    return usinix, ref


def b5_frequencia_biapoiada():
    L, mkgm = 4000.0, 50.0
    m, nos = _viga(10, L, massa_kgm=mkgm)
    m.apoios[nos[0]] = [True, True, True, True, False, False]
    m.apoios[nos[-1]] = [False, True, True, False, False, False]
    modos = m.modos(4)
    EI = E_ACO * 2.0e6
    massa = mkgm * 1e-6                        # t/mm
    ref = math.pi / (2 * L ** 2) * math.sqrt(EI / massa)
    usinix = min(f for f, _v in modos if f > 1e-6)
    return usinix, ref


# =========================================================================== elementos finitos sólidos
def _sem_calculix():
    try:
        import UsinixFEM as F
        return F._ccx_absoluto() is None
    except Exception:
        return True


def _estudo_bloco(doc, L, b, h, tamanho, tipo="static"):
    """Bloco L × b × h (X, Y, Z) engastado na face x = 0, com aço, malha Gmsh de 2ª ordem e CalculiX."""
    import ObjectsFem
    import UsinixFEM as F
    bloco = doc.addObject("Part::Box", "Bloco")
    bloco.Length, bloco.Width, bloco.Height = L, b, h
    doc.recompute()
    est = F.Estudo(doc)
    est.analise = None
    est.garantir(bloco)
    est.solver.AnalysisType = tipo
    mat = ObjectsFem.makeMaterialSolid(doc, "Aco")
    mat.Material = {"Name": "Aço de referência", "YoungsModulus": "%g MPa" % E_ACO, "PoissonRatio": str(NU_ACO),
                    "Density": "7850 kg/m^3"}
    est.analise.addObject(mat)
    faces = bloco.Shape.Faces
    x0 = [i + 1 for i, f in enumerate(faces) if abs(f.BoundBox.XMax) < 1e-6]
    x1 = [i + 1 for i, f in enumerate(faces) if abs(f.BoundBox.XMin - L) < 1e-6]
    fx = ObjectsFem.makeConstraintFixed(doc, "Engaste")
    fx.References = [(bloco, ("Face%d" % x0[0],))]
    est.analise.addObject(fx)
    doc.recompute()
    ok, msg = F.gerar_malha(est, tamanho, "2nd")
    if not ok:
        raise RuntimeError(msg)
    return est, bloco, "Face%d" % x1[0]


def _forca(doc, est, bloco, face, valor_N, direcao):
    """Força na face, na direção global pedida (vetor unitário)."""
    import ObjectsFem
    f = ObjectsFem.makeConstraintForce(doc, "Forca")
    f.References = [(bloco, (face,))]
    f.Force = "%g N" % valor_N
    eixo = max(range(3), key=lambda k: abs(direcao[k]))
    arestas = [i + 1 for i, e in enumerate(bloco.Shape.Edges)
               if abs(abs((e.Vertexes[1].Point - e.Vertexes[0].Point).normalize()[eixo]) - 1) < 1e-9]
    f.Direction = (bloco, ("Edge%d" % arestas[0],))
    f.Reversed = False
    doc.recompute()
    if f.DirectionVector[eixo] * direcao[eixo] < 0:
        f.Reversed = True
        doc.recompute()
    est.analise.addObject(f)
    doc.recompute()
    return f


def _rodar(est):
    import UsinixFEM as F
    ok, erro, _dt = F.calcular(est)
    if not ok:
        raise RuntimeError(erro)
    return F.estatisticas(est)


def s1_tracao(doc):
    L, a, F_N = 1000.0, 20.0, 10000.0
    est, bloco, face = _estudo_bloco(doc, L, a, a, 8.0)
    _forca(doc, est, bloco, face, F_N, (1, 0, 0))
    st = _rodar(est)
    return st["u_max"], F_N * L / (E_ACO * a * a)


def s2_balanco_solido(doc):
    L, b, h, P_N = 1000.0, 40.0, 80.0, 2000.0
    est, bloco, face = _estudo_bloco(doc, L, b, h, 14.0)
    _forca(doc, est, bloco, face, P_N, (0, 0, -1))
    st = _rodar(est)
    I = b * h ** 3 / 12.0
    G = E_ACO / (2 * (1 + NU_ACO))
    ref = P_N * L ** 3 / (3 * E_ACO * I) + P_N * L / (5.0 / 6.0 * G * b * h)   # flexão + cortante (Timoshenko)
    return st["u_max"], ref


def s3_frequencia_balanco(doc):
    import UsinixFEM as F
    L, b, h = 1000.0, 40.0, 80.0
    est, _bloco, _face = _estudo_bloco(doc, L, b, h, 14.0, tipo="frequency")
    ok, erro, _dt = F.calcular(est, modos=3)
    if not ok:
        raise RuntimeError(erro)
    st = F.estatisticas(est)
    f1 = min(f for _m, f in st["modos"] if f > 1e-6)
    I = h * b ** 3 / 12.0                       # o primeiro modo flete no lado mais fino
    ref = 1.875104 ** 2 / (2 * math.pi * L ** 2) * math.sqrt(E_ACO * I / (RHO_ACO * b * h))
    return f1, ref


# =========================================================================== lista de casos
CASOS = [
    {"id": "B1", "motor": "barras", "funcao": b1_balanco, "tol": 0.5, "unidade": "mm", "grandeza": "flecha na ponta",
     "titulo": "Viga em balanço com carga na ponta",
     "modelo": "L = 2 000 mm, P = 10 kN, E = 200 000 MPa, I = 2,0 × 10⁶ mm⁴; 1 barra",
     "formula": "δ = P·L³ / (3·E·I)"},
    {"id": "B2", "motor": "barras", "funcao": b2_biapoiada, "tol": 0.5, "unidade": "mm", "grandeza": "flecha no meio",
     "titulo": "Viga biapoiada com carga distribuída",
     "modelo": "L = 4 000 mm, q = 5 kN/m, E = 200 000 MPa, I = 2,0 × 10⁶ mm⁴; 1 barra",
     "formula": "δ = 5·q·L⁴ / (384·E·I)"},
    {"id": "B3", "motor": "barras", "funcao": b2m_biapoiada_momento, "tol": 0.5, "unidade": "kN·m",
     "grandeza": "momento máximo", "titulo": "Viga biapoiada com carga distribuída (momento)",
     "modelo": "L = 4 000 mm, q = 5 kN/m; 1 barra", "formula": "M = q·L² / 8"},
    {"id": "B4", "motor": "barras", "funcao": b3_biengastada, "tol": 0.5, "unidade": "kN·m",
     "grandeza": "momento no engaste", "titulo": "Viga biengastada com carga distribuída",
     "modelo": "L = 4 000 mm, q = 5 kN/m; 1 barra", "formula": "M = q·L² / 12"},
    {"id": "B5", "motor": "barras", "funcao": b4_coluna_segunda_ordem, "tol": 2.0, "unidade": "mm",
     "grandeza": "deslocamento do topo (2ª ordem)", "titulo": "Coluna em balanço com carga axial e lateral (P-Δ)",
     "modelo": "L = 3 000 mm, P = 50 kN (compressão), H = 1 kN, E·I = 4,0 × 10¹¹ N·mm²; 8 barras",
     "formula": "δ = (H/P)·(tg(k·L)/k − L), k = √(P/E·I)"},
    {"id": "B6", "motor": "barras", "funcao": b5_frequencia_biapoiada, "tol": 1.0, "unidade": "Hz",
     "grandeza": "1ª frequência natural", "titulo": "Viga biapoiada vibrando (1º modo)",
     "modelo": "L = 4 000 mm, m = 50 kg/m, E·I = 4,0 × 10¹¹ N·mm²; 10 barras",
     "formula": "f₁ = (π / 2L²)·√(E·I / m)"},
    {"id": "S1", "motor": "sólidos", "funcao": s1_tracao, "tol": 1.0, "unidade": "mm",
     "grandeza": "alongamento", "titulo": "Barra tracionada (sólido)",
     "modelo": "barra 1 000 × 20 × 20 mm, F = 10 kN, engaste numa ponta; tetraedros de 2ª ordem, 8 mm",
     "formula": "δ = F·L / (E·A)"},
    {"id": "S2", "motor": "sólidos", "funcao": s2_balanco_solido, "tol": 3.0, "unidade": "mm",
     "grandeza": "flecha na ponta", "titulo": "Viga em balanço (sólido) com carga na ponta",
     "modelo": "bloco 1 000 × 40 × 80 mm, P = 2 kN na face da ponta; tetraedros de 2ª ordem, 14 mm",
     "formula": "δ = P·L³ / (3·E·I) + P·L / (κ·G·A), κ = 5/6"},
    {"id": "S3", "motor": "sólidos", "funcao": s3_frequencia_balanco, "tol": 3.0, "unidade": "Hz",
     "grandeza": "1ª frequência natural", "titulo": "Viga em balanço (sólido) vibrando (1º modo)",
     "modelo": "bloco 1 000 × 40 × 80 mm, aço (ρ = 7 850 kg/m³); tetraedros de 2ª ordem, 14 mm",
     "formula": "f₁ = (1,8751² / 2π·L²)·√(E·I / ρ·A)"},
]


def rodar(ids=None, progresso=None):
    """Roda os casos (todos, ou os de `ids`) e devolve [Resultado]. Os sólidos usam um documento temporário."""
    res = []
    casos = [c for c in CASOS if ids is None or c["id"] in ids]
    doc_ativo = FreeCAD.ActiveDocument
    for k, c in enumerate(casos):
        if progresso is not None:
            progresso(k, len(casos), c)
        if c["motor"] == "barras":
            try:
                u, ref = c["funcao"]()
                res.append(Resultado(c, u, ref))
            except Exception as exc:
                res.append(Resultado(c, erro=str(exc)))
            continue
        if _sem_calculix():
            res.append(Resultado(c, erro="CalculiX não encontrado"))
            continue
        doc = FreeCAD.newDocument("UsinixValidacao")
        try:
            u, ref = c["funcao"](doc)
            res.append(Resultado(c, u, ref))
        except Exception as exc:
            res.append(Resultado(c, erro=str(exc).strip().splitlines()[0] if str(exc).strip() else repr(exc)))
        finally:
            try:
                FreeCAD.closeDocument(doc.Name)
            except Exception:
                pass
    if doc_ativo is not None and doc_ativo.Name in FreeCAD.listDocuments():
        try:
            FreeCAD.setActiveDocument(doc_ativo.Name)
        except Exception:
            pass
    return res


# =========================================================================== relatório
def _num(v, casas=None):
    import UsinixUtil
    if v is None:
        return "—"
    if casas is None:
        casas = 3 if abs(v) < 10 else 2
    return UsinixUtil.fmt(v, casas)


def versoes():
    import UsinixVersao
    try:
        fc = ".".join(FreeCAD.Version()[:3])
    except Exception:
        fc = "?"
    ccx = "?"
    try:
        import UsinixFEM as F
        caminho = F._ccx_absoluto()
        if caminho:
            import subprocess
            out = subprocess.run([caminho, "-v"], capture_output=True, text=True, timeout=20).stdout
            import re
            m = re.search(r"[Vv]ersion\s+([\d.]+)", out)
            ccx = m.group(1) if m else "?"
    except Exception:
        pass
    return {"usinix": UsinixVersao.VERSAO, "freecad": fc, "calculix": ccx}


def _pct(d):
    if d is None:
        return "—"
    if abs(d) < 0.005:
        d = 0.0
    return ("%+.2f%%" % d).replace(".", ",") if d else "0,00%"


class _EstudoDoRelatorio:
    """O que o gerador de PDF do relatório MEF precisa saber (capa, cabeçalho), sem estudo de verdade."""

    def __init__(self, campos):
        self._c = campos
        self.peca = None
        self.tipo = "static"
        # o gerador guarda e restaura a visibilidade dos objetos do documento; aqui não há nenhum
        self.doc = type("SemDocumento", (), {"Objects": []})()

    def get(self, nome, padrao=""):
        return self._c.get(nome, padrao)


def corpo_html(resultados, info=None):
    import UsinixFEMRelatorio as R
    info = info or versoes()
    aprovados = sum(1 for r in resultados if r.ok)
    rodados = sum(1 for r in resultados if r.erro == "")
    h = ["<h1>1. Objetivo</h1>",
         "<p>Conferir os motores de cálculo do Usinix com casos clássicos de solução conhecida. Cada caso é montado "
         "do zero, calculado com o mesmo motor que as bancadas usam e comparado com a fórmula fechada da resistência "
         "dos materiais. A diferença tem de ficar dentro da tolerância do caso.</p>",
         "<h1>2. Resumo</h1>",
         R._tab([R._par("Casos aprovados", "%d de %d" % (aprovados, len(resultados))),
                 R._par("Casos que não rodaram", str(len(resultados) - rodados)),
                 R._par("Usinix", info["usinix"]), R._par("Base FreeCAD", info["freecad"]),
                 R._par("CalculiX", info["calculix"]), R._par("Data", time.strftime("%d/%m/%Y %H:%M"))]),
         "<h1>3. Resultados</h1>"]
    linhas = []
    for r in resultados:
        c = r.caso
        if r.erro:
            sit = "<span style='color:#9A6B00'>não rodou: %s</span>" % r.erro
        else:
            sit = ("<b style='color:#1E7B4D'>✓ ok</b>" if r.ok else "<b style='color:#B5523F'>✗ fora</b>")
        d = r.diferenca
        linhas.append([c["id"], c["titulo"], "%s (%s)" % (c["grandeza"], c["unidade"]), _num(r.referencia),
                       _num(r.usinix), _pct(d), ("±%s%%" % _num(c["tol"], 1)), sit])
    h.append(R._tab(linhas, ["Caso", "Descrição", "Grandeza", "Ref.", "Usinix", "Dif.", "Tol.", ""],
                    ["7%", "31%", "20%", "10%", "10%", "8%", "7%", "7%"]))
    h.append("<h1>4. Casos</h1>")
    for r in resultados:
        c = r.caso
        h.append("<h2>%s · %s</h2>" % (c["id"], c["titulo"]))
        h.append(R._tab([R._par("Motor", "análise por barras (rigidez direta)" if c["motor"] == "barras"
                                else "elementos finitos sólidos (Gmsh + CalculiX)"),
                         R._par("Modelo", c["modelo"]), R._par("Fórmula de referência", c["formula"]),
                         R._par("Referência", "%s %s" % (_num(r.referencia), c["unidade"])),
                         R._par("Usinix", "%s %s" % (_num(r.usinix), c["unidade"]) if not r.erro else r.erro)]))
    h.append("<h1>5. Premissas</h1>")
    h.append("<p>Material elástico linear (aço, E = 200 000 MPa, ν = 0,3, ρ = 7 850 kg/m³). As fórmulas são as "
             "soluções clássicas de viga (Euler-Bernoulli; na viga sólida em balanço, com a parcela de cortante de "
             "Timoshenko) e da coluna em balanço com carga axial e lateral. Nos sólidos, o engaste trava toda a face, "
             "o que enrijece um pouco a ponta presa em relação à teoria de viga: por isso a tolerância dos sólidos é "
             "maior. A validação mostra que os motores reproduzem a teoria; não substitui a conferência de cada "
             "projeto pelo responsável técnico.</p>")
    h.append("<p class='nota'>Fontes das fórmulas: Timoshenko e Gere, Mecânica dos Materiais; Timoshenko e Gere, "
             "Theory of Elastic Stability; Blevins, Formulas for Natural Frequency and Mode Shape.</p>")
    return "".join(h)


def gerar_pdf(resultados, caminho, campos=None):
    import UsinixFEMRelatorio as R
    c = {"UsinixRelTitulo": "Validação do motor de cálculo", "UsinixRelPeca": "Casos de referência",
         "UsinixRelSubtitulo": "Relatório de validação do cálculo", "UsinixRelCabecalho": "Validação do cálculo",
         "UsinixRelTipo": "Barras e sólidos, estática e modal"}
    c.update(campos or {})
    est = _EstudoDoRelatorio(c)
    info = versoes()
    return R.gerar(est, caminho, corpo=lambda _e, _doc, _imgs, _w: corpo_html(resultados, info),
                   capturas=lambda _e, _p: {})


# =========================================================================== painel e comando
if P is not None:
    class PainelValidacao(P.PainelTarefa):
        titulo = "Validação do cálculo"
        icone_cmd = "validacao.svg"
        ajuda = ("Roda casos clássicos de solução conhecida (vigas, coluna em 2ª ordem, barra tracionada, "
                 "frequências) nos motores de cálculo do Usinix e compara com a fórmula. Gera um PDF para "
                 "anexar à documentação técnica.")

        def montar(self):
            f = self.form
            s1 = f.secao("Casos", "info")
            self.marcas = {}
            for c in CASOS:
                m = P.marcar("%s · %s" % (c["id"], c["titulo"]), True)
                self.marcas[c["id"]] = m
                s1.widget(m)
            s2 = f.secao("Resultado", "comando")
            self.saida = QtWidgets.QLabel("Escolha os casos e clique em OK: os sólidos levam alguns segundos cada.")
            self.saida.setWordWrap(True)
            self.saida.setTextFormat(QtCore.Qt.RichText)
            s2.widget(self.saida)

        def pendencia(self):
            if not any(m.isChecked() for m in self.marcas.values()):
                return "Marque pelo menos um caso."
            return None

        def pronto_texto(self):
            return "OK roda os casos e grava o PDF."

        def executar(self, caminho=None):
            ids = [k for k, m in self.marcas.items() if m.isChecked()]
            if caminho is None:
                padrao = os.path.join(os.path.expanduser("~"), "Validacao do calculo Usinix %s.pdf"
                                      % time.strftime("%Y-%m-%d"))
                caminho, _f = QtWidgets.QFileDialog.getSaveFileName(None, "Salvar relatório", padrao, "PDF (*.pdf)")
                if not caminho:
                    raise ValueError("Escolha onde gravar o PDF.")

            def prog(k, n, c):
                self.saida.setText("Rodando %d de %d: %s…" % (k + 1, n, c["titulo"]))
                QtWidgets.QApplication.processEvents()
            QtWidgets.QApplication.setOverrideCursor(QtCore.Qt.WaitCursor)
            try:
                self.resultados = rodar(ids, prog)
                gerar_pdf(self.resultados, caminho)
            finally:
                QtWidgets.QApplication.restoreOverrideCursor()
            ok = sum(1 for r in self.resultados if r.ok)
            self.saida.setText("%d de %d casos dentro da tolerância. PDF gravado." % (ok, len(self.resultados)))
            self.pdf = caminho
            if not os.environ.get("USINIX_TESTE"):
                try:
                    from PySide import QtGui
                    QtCore.QTimer.singleShot(200, lambda: QtGui.QDesktopServices.openUrl(
                        QtCore.QUrl.fromLocalFile(caminho)))
                except Exception:
                    pass
            return []

    class CmdValidacao:
        def GetResources(self):
            import UsinixUtil
            return {"Pixmap": UsinixUtil.icone("validacao.svg"), "MenuText": "Validação do cálculo",
                    "ToolTip": "Roda casos clássicos de solução conhecida nos motores de cálculo do Usinix (barras "
                               "e elementos finitos) e gera o relatório da comparação."}

        def IsActive(self):
            return True

        def Activated(self):
            PainelValidacao().mostrar()


def registrar_comandos():
    if FreeCADGui is not None and P is not None and "Usinix_Validacao" not in FreeCADGui.listCommands():
        FreeCADGui.addCommand("Usinix_Validacao", CmdValidacao())
