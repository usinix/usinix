# SPDX-License-Identifier: LGPL-2.1-or-later
# Usinix - proteção fixa de máquina (grade ou enclausuramento) com verificação das distâncias de segurança.
"""Proteção de máquina (NR-12) — grade ou enclausuramento parametrizado.

O objeto desenha o quadro (tubo quadrado) e a tela, e confere ao vivo, pela ABNT NBR ISO 13857:2021:
- a abertura da tela contra a distância da tela ao perigo (Tabela 4, ou Tabela 5 para crianças de 3 anos ou mais);
- o alcance por cima da proteção (Tabela 2, ou Tabela 1 quando a lesão é leve e pouco provável);
- a folga entre o piso e a proteção, para pés e pernas (Tabela 7).
Com um ponto de perigo escolhido no modelo (vértice, aresta, face ou peça), a distância e a altura do perigo
são medidas no próprio modelo; sem ele, valem as medidas digitadas.

A tela fica verde quando tudo confere e vermelha quando algum item não confere; a lista de verificação vai para
a propriedade Verificacao e para o relatório. A tela é desenhada como placa fina (sem os fios); a massa da tela é
estimada pela área aberta da malha. A verificação não substitui a apreciação de riscos da máquina.
"""

import math
import os

import FreeCAD

import PrumoDistancias as D

AQUI = os.path.dirname(os.path.abspath(__file__))
FORMAS = ("Painel (grade)", "Enclausuramento")
TIPOS_TELA = ("Malha quadrada", "Fenda (malha retangular)", "Chapa perfurada (furo redondo)")
TIPO_TABELA = {TIPOS_TELA[0]: "quadrada", TIPOS_TELA[1]: "fenda", TIPOS_TELA[2]: "circular"}
RISCOS = ("Alto (Tabela 2)", "Lesão leve e pouco provável (Tabela 1)")
PUBLICOS = ("14 anos ou mais (Tabela 4)", "Crianças de 3 anos ou mais (Tabela 5)")
DENS_ACO = 7850.0
COR_OK = (0.18, 0.62, 0.36)
COR_NOK = (0.85, 0.22, 0.18)
COR_QUADRO = (0.97, 0.75, 0.0)


def fracao_aberta(tipo, e, fio):
    """Fração da área da tela que é abertura (0 a 1) — estimativa geométrica da malha."""
    e, fio = max(float(e), 0.0), max(float(fio), 0.0)
    p = e + fio
    if p <= 0:
        return 0.0
    if tipo == "fenda":
        return e / p
    if tipo == "circular":            # furos a 60°, passo = furo + ponte
        return min(0.9069 * (e / p) ** 2, 0.9)
    return (e / p) ** 2


def _quadro(w, h, lado, parede):
    """Quadro retangular de tubo quadrado no plano XZ (y de 0 a lado), canto inferior esquerdo na origem."""
    import Part
    fora = Part.makeBox(w, lado, h)
    if w <= 2 * lado or h <= 2 * lado:
        return fora
    dentro = Part.makeBox(w - 2 * lado, lado, h - 2 * lado, FreeCAD.Vector(lado, 0, lado))
    q = fora.cut(dentro)
    if 0 < parede < lado / 2:
        # oco: tira o miolo dos tubos (seção quadrada de parede `parede`)
        ext = Part.makeBox(w - 2 * parede, lado - 2 * parede, h - 2 * parede,
                           FreeCAD.Vector(parede, parede, parede))
        inn = Part.makeBox(w - 2 * (lado - parede), lado, h - 2 * (lado - parede),
                           FreeCAD.Vector(lado - parede, 0, lado - parede))
        q = q.cut(ext.cut(inn))
    return q


def _tela(w, h, lado, esp):
    import Part
    if w <= 2 * lado or h <= 2 * lado:
        return None
    t = max(min(esp, lado), 0.5)
    return Part.makeBox(w - 2 * lado, t, h - 2 * lado, FreeCAD.Vector(lado, (lado - t) / 2.0, lado))


def paineis(obj):
    """[(Placement local do painel, largura)] — o painel fica no plano XZ local, de x = 0 a largura."""
    L, P = obj.Largura.Value, obj.Profundidade.Value
    lado = obj.LadoQuadro.Value
    if obj.Forma == FORMAS[0]:
        return [(FreeCAD.Placement(), L)]
    rot = FreeCAD.Rotation(FreeCAD.Vector(0, 0, 1), 90)
    res = [(FreeCAD.Placement(FreeCAD.Vector(0, 0, 0), FreeCAD.Rotation()), L),                    # frente
           (FreeCAD.Placement(FreeCAD.Vector(0, P - lado, 0), FreeCAD.Rotation()), L)]             # fundo
    if P > 2 * lado:
        res.append((FreeCAD.Placement(FreeCAD.Vector(lado, lado, 0), rot), P - 2 * lado))         # esquerda
        res.append((FreeCAD.Placement(FreeCAD.Vector(L, lado, 0), rot), P - 2 * lado))            # direita
    return res


def geometria(obj):
    """(forma completa, tela) no sistema local do objeto."""
    import Part
    lado, parede = obj.LadoQuadro.Value, obj.ParedeQuadro.Value
    folga, H = obj.FolgaInferior.Value, obj.Altura.Value
    h = max(H - folga, 1.0)
    quadros, telas = [], []
    for pl, w in paineis(obj):
        base = FreeCAD.Placement(FreeCAD.Vector(0, 0, folga), FreeCAD.Rotation())
        q = _quadro(w, h, lado, parede)
        q.Placement = pl.multiply(base)
        quadros.append(q)
        t = _tela(w, h, lado, obj.FioTela.Value)
        if t is not None:
            t.Placement = pl.multiply(base)
            telas.append(t)
    if obj.Forma == FORMAS[1] and obj.Teto:
        L, P = obj.Largura.Value, obj.Profundidade.Value
        rot = FreeCAD.Rotation(FreeCAD.Vector(1, 0, 0), -90)      # altura local (Z) vira a profundidade (+Y)
        pl = FreeCAD.Placement(FreeCAD.Vector(0, 0, H), rot)
        q = _quadro(L, P, lado, parede)
        q.Placement = pl
        quadros.append(q)
        t = _tela(L, P, lado, obj.FioTela.Value)
        if t is not None:
            t.Placement = pl
            telas.append(t)
    return Part.makeCompound(quadros + telas), quadros, telas


def medir_perigo(obj):
    """(distância da tela ao perigo, altura do perigo acima do piso) medidas no modelo, ou None sem perigo."""
    link = getattr(obj, "PontoPerigo", None)
    if not link or link[0] is None:
        return None
    alvo, subs = link
    try:
        sh = alvo.Shape.getElement(subs[0]) if subs else alvo.Shape
    except Exception:
        return None
    if sh is None or sh.isNull():
        return None
    _f, _q, telas = geometria(obj)
    if not telas:
        return None
    import Part
    tela = Part.makeCompound([t.copy() for t in telas])
    tela.Placement = obj.Placement.multiply(tela.Placement)
    try:
        d, pares, _info = tela.distToShape(sh)
    except Exception:
        return None
    piso = obj.Placement.Base.z
    if pares:
        z = pares[0][1].z
    else:
        z = sh.BoundBox.ZMax
    # altura do perigo: o ponto mais alto do elemento perigoso (o mais desfavorável para o alcance por cima)
    z = max(z, sh.BoundBox.ZMax) if sh.ShapeType in ("Vertex", "Edge", "Face") else sh.BoundBox.ZMax
    return float(d), float(z - piso)


def verificar(obj):
    medido = medir_perigo(obj)
    if medido is not None:
        dist, alt = medido
    else:
        dist, alt = obj.DistanciaPerigo.Value, obj.AlturaPerigo.Value
    tipo = TIPO_TABELA.get(obj.TipoTela, "quadrada")
    fechado = obj.Forma == FORMAS[1] and obj.Teto
    ok, itens = D.verificar(
        obj.Abertura.Value, tipo, dist_abertura=dist,
        altura_protecao=obj.Altura.Value if not fechado else 1e6, altura_perigo=alt, dist_perigo=dist,
        folga_inferior=obj.FolgaInferior.Value,
        risco="baixo" if obj.Risco == RISCOS[1] else "alto",
        publico="3" if obj.Publico == PUBLICOS[1] else "14",
        comprimento_fenda=obj.ComprimentoFenda.Value if tipo == "fenda" and obj.ComprimentoFenda.Value else None,
        dist_folga=obj.DistanciaFolga.Value or None)
    if fechado:
        for i in itens:
            if i["nome"].startswith("Alcance sobre"):
                i.update({"nome": "Alcance por cima", "exigido": None, "ok": True,
                          "texto": "enclausuramento com teto: não há alcance por cima"})
    return all(i["ok"] for i in itens), itens, dist, alt


class Protecao:
    def __init__(self, obj):
        obj.Proxy = self
        self._props(obj)

    def _props(self, obj):
        def add(tipo, nome, grupo, doc, valor=None):
            if nome not in obj.PropertiesList:
                obj.addProperty(tipo, nome, grupo, doc)
                if valor is not None:
                    setattr(obj, nome, valor)

        def enum(nome, grupo, doc, valores, padrao):
            if nome not in obj.PropertiesList:
                obj.addProperty("App::PropertyEnumeration", nome, grupo, doc)
                setattr(obj, nome, list(valores))
                setattr(obj, nome, padrao)
        add("App::PropertyBool", "ProtecaoNR12", "Proteção", "Marca do objeto (proteção de máquina)", True)
        obj.setEditorMode("ProtecaoNR12", 2)
        enum("Forma", "Proteção", "Painel (grade) ou enclausuramento em volta da máquina", FORMAS, FORMAS[0])
        add("App::PropertyLength", "Largura", "Proteção", "Largura do painel ou do enclausuramento (X)", 1000.0)
        add("App::PropertyLength", "Profundidade", "Proteção", "Profundidade do enclausuramento (Y)", 800.0)
        add("App::PropertyLength", "Altura", "Proteção", "Do piso ao topo da proteção", 2000.0)
        add("App::PropertyLength", "FolgaInferior", "Proteção", "Vão entre o piso e a proteção", 100.0)
        add("App::PropertyBool", "Teto", "Proteção", "Enclausuramento fechado em cima", False)
        add("App::PropertyLength", "LadoQuadro", "Quadro", "Lado do tubo quadrado do quadro", 30.0)
        add("App::PropertyLength", "ParedeQuadro", "Quadro", "Parede do tubo do quadro", 1.5)
        enum("TipoTela", "Tela", "Malha quadrada, fenda ou chapa perfurada", TIPOS_TELA, TIPOS_TELA[0])
        add("App::PropertyLength", "Abertura", "Tela", "Abertura da malha: lado, largura da fenda ou diâmetro do "
            "furo", 25.0)
        add("App::PropertyLength", "FioTela", "Tela", "Diâmetro do fio, largura da barra ou ponte entre furos", 3.0)
        add("App::PropertyLength", "ComprimentoFenda", "Tela", "Comprimento da fenda (fendas curtas têm nota "
            "própria na norma); 0 = longa", 0.0)
        add("App::PropertyLinkSub", "PontoPerigo", "Perigo", "Ponto de perigo no modelo (vértice, aresta, face "
            "ou peça): mede a distância e a altura")
        add("App::PropertyLength", "DistanciaPerigo", "Perigo", "Da tela ao ponto de perigo mais próximo (sem "
            "ponto escolhido)", 150.0)
        add("App::PropertyLength", "AlturaPerigo", "Perigo", "Altura do ponto de perigo acima do piso (sem ponto "
            "escolhido)", 1200.0)
        add("App::PropertyLength", "DistanciaFolga", "Perigo", "Da folga inferior ao perigo que os pés alcançam; "
            "0 = a mesma do perigo", 0.0)
        enum("Risco", "Perigo", "Gravidade da lesão (escolhe a tabela de alcance por cima)", RISCOS, RISCOS[0])
        enum("Publico", "Perigo", "Quem pode chegar à proteção", PUBLICOS, PUBLICOS[0])
        add("App::PropertyString", "Material", "Lista", "Material", "Aço carbono")
        add("App::PropertyString", "Denominacao", "Lista", "Descrição para a lista de materiais")
        add("App::PropertyString", "Observacao", "Lista", "Observação na lista de materiais")
        for nome, tipo, doc in (("Conforme", "App::PropertyBool", "Todas as distâncias conferem"),
                                ("Verificacao", "App::PropertyStringList", "Itens verificados"),
                                ("DistanciaMedida", "App::PropertyFloat", "Distância usada na verificação (mm)"),
                                ("AlturaMedida", "App::PropertyFloat", "Altura do perigo usada (mm)"),
                                ("MaiorAbertura", "App::PropertyFloat",
                                 "Maior abertura da tabela que atende à distância (mm)"),
                                ("AreaM2", "App::PropertyFloat", "Área de tela (m²)"),
                                ("Peso", "App::PropertyFloat", "Massa estimada: quadro + tela (kg)")):
            add(tipo, nome, "Resultado", doc)
            obj.setEditorMode(nome, 1)

    def onDocumentRestored(self, obj):
        self._props(obj)

    def execute(self, obj):
        forma, quadros, telas = geometria(obj)
        obj.Shape = forma
        ok, itens, dist, alt = verificar(obj)
        obj.Conforme = ok
        obj.Verificacao = [D.linha(i) for i in itens]
        obj.DistanciaMedida = dist
        obj.AlturaMedida = alt
        tipo = TIPO_TABELA.get(obj.TipoTela, "quadrada")
        obj.MaiorAbertura = D.maior_abertura(dist, tipo, "3" if obj.Publico == PUBLICOS[1] else "14")
        area = 0.0
        massa_tela = 0.0
        for t in telas:
            dims = sorted((t.BoundBox.XLength, t.BoundBox.YLength, t.BoundBox.ZLength))
            a = dims[1] * dims[2] * 1e-6
            area += a
            esp = obj.FioTela.Value
            massa_tela += a * esp * 1e-3 * DENS_ACO * (1.0 - fracao_aberta(tipo, obj.Abertura.Value, esp))
        massa_quadro = sum(q.Volume for q in quadros) * 1e-9 * DENS_ACO
        obj.AreaM2 = area
        obj.Peso = massa_quadro + massa_tela
        obj.Denominacao = "Proteção %s %s × %s mm, tela %s %s mm" % (
            "grade" if obj.Forma == FORMAS[0] else "enclausuramento", D._n(obj.Largura.Value),
            D._n(obj.Altura.Value), {"quadrada": "malha", "fenda": "fenda", "circular": "perfurada"}[tipo],
            D._n(obj.Abertura.Value))
        obj.Observacao = "%s; massa estimada" % ("distâncias conferem (NBR ISO 13857)" if ok
                                                 else "DISTÂNCIAS NÃO CONFEREM")
        if FreeCAD.GuiUp:
            colorir(obj, len(quadros), len(telas))


def colorir(obj, n_quadros=None, n_telas=None):
    """Quadro amarelo; tela verde (confere) ou vermelha (não confere), semitransparente."""
    try:
        vo = obj.ViewObject
        if vo is None:
            return
        faces = obj.Shape.Faces
        if n_quadros is None:
            _f, q, t = geometria(obj)
            n_quadros, n_telas = len(q), len(t)
        sol = obj.Shape.Solids
        cor_tela = COR_OK if obj.Conforme else COR_NOK
        mats = []
        for i, s in enumerate(sol):
            m = FreeCAD.Material()
            m.DiffuseColor = COR_QUADRO if i < n_quadros else cor_tela
            m.Transparency = 0.0 if i < n_quadros else 0.55
            mats.extend([m] * len(s.Faces))
        if len(mats) == len(faces):
            vo.ShapeAppearance = mats
    except Exception:
        pass


class VistaProtecao:
    def __init__(self, vobj):
        vobj.Proxy = self

    def attach(self, vobj):
        self.vobj = vobj

    def getIcon(self):
        return os.path.join(AQUI, "Resources", "icons", "protecao_nr12.svg")

    def updateData(self, obj, prop):
        pass

    def onChanged(self, vobj, prop):
        pass

    def dumps(self):
        return None

    def loads(self, state):
        return None


def criar(doc=None, ponto=None, **kw):
    doc = doc or FreeCAD.ActiveDocument
    obj = doc.addObject("Part::FeaturePython", "Protecao")
    Protecao(obj)
    for k, v in kw.items():
        setattr(obj, k, v)
    if ponto is not None:
        obj.PontoPerigo = ponto
    obj.Label = "Proteção NR-12"
    if FreeCAD.GuiUp:
        VistaProtecao(obj.ViewObject)
    doc.recompute()
    return obj


def e_protecao(obj):
    return obj is not None and isinstance(getattr(obj, "Proxy", None), Protecao)


def relatorio(obj):
    """Texto da verificação de uma proteção (para a janela, o memorial e a IA)."""
    L = ["%s — %s" % (obj.Label, "CONFORME" if obj.Conforme else "NÃO CONFORME"),
         "%s; tela %s, abertura %s mm, fio %s mm; altura %s mm, folga inferior %s mm" % (
             obj.Forma, obj.TipoTela.lower(), D._n(obj.Abertura.Value), D._n(obj.FioTela.Value),
             D._n(obj.Altura.Value), D._n(obj.FolgaInferior.Value)),
         "Perigo: %s mm da tela, %s mm acima do piso%s; %s; %s" % (
             D._n(obj.DistanciaMedida), D._n(obj.AlturaMedida),
             " (medido no modelo)" if obj.PontoPerigo and obj.PontoPerigo[0] is not None else "",
             "risco: " + obj.Risco, "quem chega: " + obj.Publico)]
    L.extend(obj.Verificacao)
    if obj.MaiorAbertura:
        L.append("Maior abertura que atende a esta distância: %s mm." % D._n(obj.MaiorAbertura))
    L.append("Referência: %s (conferida no %s). A verificação não substitui a apreciação de riscos da "
             "máquina (NR-12)." % (D.NORMA, D.CONFERIDA))
    return "\n".join(L)


# ============================================================================ interface
try:
    import FreeCADGui
    from PySide import QtCore, QtWidgets
    import PrumoPainel as P
except ImportError:
    FreeCADGui = None
    P = None


def _filtro_perigo(obj, subs):
    try:
        if e_protecao(obj) or not hasattr(obj, "Shape") or obj.Shape.isNull():
            return []
        r = [("%s · %s" % (obj.Label, s), (obj, s)) for s in (subs or ())
             if s.startswith(("Vertex", "Edge", "Face"))]
        return r or [(obj.Label, (obj, None))]
    except Exception:
        return []


if P is not None:
    class PainelProtecao(P.PainelTarefa):
        titulo = "Proteção NR-12"
        ajuda = ("Grade ou enclausuramento com quadro e tela. Escolha o ponto de perigo no modelo (opcional) e a "
                 "tela: o Usinix confere as distâncias da ABNT NBR ISO 13857 enquanto você muda os valores.")
        previa = True

        def montar(self):
            f = self.form
            s0 = f.secao("Ponto de perigo (opcional)", "selecao")
            self.perigo = f.caixa(s0, "Ponto de perigo", _filtro_perigo, minimo=0, maximo=1,
                                  dica="Vértice, aresta, face ou peça perigosa: a distância e a altura são medidas "
                                       "no modelo.")
            s1 = f.secao("Proteção", "tipo")
            self.forma = P.lista(list(FORMAS), FORMAS[0])
            s1.linha("tipo", self.forma, "Painel avulso ou enclausuramento de quatro lados.", "Forma")
            self.largura = P.numero(1000.0, 100.0, 20000.0)
            s1.linha("largura", self.largura, "Largura (X).", "Largura")
            self.altura = P.numero(2000.0, 300.0, 6000.0)
            s1.linha("altura", self.altura, "Do piso ao topo.", "Altura")
            self.folga = P.numero(100.0, 0.0, 1000.0)
            s1.linha("altura", self.folga, "Vão entre o piso e a proteção.", "Folga inferior")
            self.s_enc = f.secao("Enclausuramento", "comprimento")
            self.prof = P.numero(800.0, 100.0, 20000.0)
            self.s_enc.linha("comprimento", self.prof, "Profundidade do enclausuramento (Y).", "Profundidade")
            self.teto = self.s_enc.linha("posicao", P.marcar("Fechado em cima (teto de tela)"), "")
            s2 = f.secao("Tela", "furo")
            self.tipo = P.lista(list(TIPOS_TELA), TIPOS_TELA[0])
            s2.linha("tipo", self.tipo, "Malha quadrada, fenda ou chapa perfurada.", "Tela")
            self.abertura = P.numero(25.0, 1.0, 500.0)
            s2.linha("furo", self.abertura, "Lado da malha, largura da fenda ou diâmetro do furo.", "Abertura")
            self.fio = P.numero(3.0, 0.5, 50.0)
            s2.linha("espessura", self.fio, "Fio, barra ou ponte entre furos.", "Fio")
            self.s_fenda = f.secao("Fenda", "comprimento")
            self.comp_fenda = P.numero(0.0, 0.0, 5000.0)
            self.s_fenda.linha("comprimento", self.comp_fenda, "Comprimento da fenda; fendas curtas têm nota "
                               "própria na norma. 0 = longa.", "Comprimento da fenda")
            s3 = f.secao("Perigo", "info")
            self.dist = P.numero(150.0, 0.0, 10000.0)
            s3.linha("largura", self.dist, "Da tela ao perigo (sem ponto escolhido).", "Distância")
            self.alt = P.numero(1200.0, 0.0, 6000.0)
            s3.linha("altura", self.alt, "Altura do perigo (sem ponto escolhido).", "Altura do perigo")
            self.risco = P.lista(list(RISCOS), RISCOS[0])
            s3.linha("tipo", self.risco, "Tabela 1 só quando a lesão é leve e pouco provável.", "Gravidade")
            self.publico = P.lista(list(PUBLICOS), PUBLICOS[0])
            s3.linha("tipo", self.publico, "Lugar com acesso de crianças usa a Tabela 5.", "Quem chega")
            s4 = f.secao("Verificação", "info")
            self.resultado = QtWidgets.QLabel("—")
            self.resultado.setWordWrap(True)
            self.resultado.setTextFormat(QtCore.Qt.RichText)
            s4.widget(self.resultado)
            self.forma.currentIndexChanged.connect(self._forma)
            self.tipo.currentIndexChanged.connect(self._forma)
            self._forma()

        def _forma(self, *_a):
            self.s_enc.setVisible(self.forma.currentText() == FORMAS[1])
            self.s_fenda.setVisible(self.tipo.currentText() == TIPOS_TELA[1])

        def pendencia(self):
            if self.altura.value() <= self.folga.value() + 100:
                return "A altura tem de passar a folga inferior."
            return None

        def pronto_texto(self):
            return "OK grava a proteção." if self.editando is not None else "OK cria a proteção."

        def _kw(self):
            return {"Forma": self.forma.currentText(), "Largura": self.largura.value(),
                    "Profundidade": self.prof.value(), "Altura": self.altura.value(),
                    "FolgaInferior": self.folga.value(), "Teto": self.teto.isChecked(),
                    "TipoTela": self.tipo.currentText(), "Abertura": self.abertura.value(),
                    "FioTela": self.fio.value(), "ComprimentoFenda": self.comp_fenda.value(),
                    "DistanciaPerigo": self.dist.value(), "AlturaPerigo": self.alt.value(),
                    "Risco": self.risco.currentText(), "Publico": self.publico.currentText()}

        def _ponto(self):
            v = self.perigo.valores()
            if not v:
                return None
            o, s = v[0]
            return (o, [s] if s else [])

        def carregar(self, obj):
            if obj.PontoPerigo and obj.PontoPerigo[0] is not None:
                o, subs = obj.PontoPerigo
                self.perigo.aceitar(o, list(subs or ()))
            self.forma.setCurrentText(obj.Forma)
            self.largura.setValue(obj.Largura.Value)
            self.prof.setValue(obj.Profundidade.Value)
            self.altura.setValue(obj.Altura.Value)
            self.folga.setValue(obj.FolgaInferior.Value)
            self.teto.setChecked(bool(obj.Teto))
            self.tipo.setCurrentText(obj.TipoTela)
            self.abertura.setValue(obj.Abertura.Value)
            self.fio.setValue(obj.FioTela.Value)
            self.comp_fenda.setValue(obj.ComprimentoFenda.Value)
            self.dist.setValue(obj.DistanciaPerigo.Value)
            self.alt.setValue(obj.AlturaPerigo.Value)
            self.risco.setCurrentText(obj.Risco)
            self.publico.setCurrentText(obj.Publico)
            self._forma()

        def props_edicao(self):
            d = self._kw()
            d["PontoPerigo"] = self._ponto()
            return d

        def executar(self):
            obj = criar(ponto=self._ponto(), **self._kw())
            self._mostrar_resultado(obj)
            return [obj]

        def _atualizar_previa(self):
            super()._atualizar_previa()
            alvo = self.editando
            if alvo is None:
                doc = self._doc_previa
                nomes = [n for n in self._previa_nomes if doc and doc.getObject(n) is not None
                         and e_protecao(doc.getObject(n))]
                alvo = doc.getObject(nomes[0]) if nomes else None
            self._mostrar_resultado(alvo)

        def _mostrar_resultado(self, obj):
            if obj is None:
                self.resultado.setText("—")
                return
            cor = "#2E8B57" if obj.Conforme else "#C0392B"
            linhas = ["<b style='color:%s'>%s</b>" % (cor, "CONFORME" if obj.Conforme else "NÃO CONFORME")]
            for v in obj.Verificacao:
                c = "#2E8B57" if v.startswith("✓") else "#C0392B"
                linhas.append("<span style='color:%s'>%s</span>" % (c, v.replace("<", "&lt;")))
            if obj.MaiorAbertura:
                linhas.append("Maior abertura que atende a %s mm: <b>%s mm</b>" % (
                    D._n(obj.DistanciaMedida), D._n(obj.MaiorAbertura)))
            linhas.append("<span style='color:#666'>Massa estimada: %s kg · tela %s m²</span>" % (
                ("%.1f" % obj.Peso).replace(".", ","), ("%.2f" % obj.AreaM2).replace(".", ",")))
            self.resultado.setText("<br>".join(linhas))

    class CmdProtecao:
        def GetResources(self):
            import PrumoUtil
            return {"Pixmap": PrumoUtil.icone("protecao_nr12.svg"), "MenuText": "Proteção NR-12",
                    "ToolTip": "Grade ou enclausuramento de máquina com quadro e tela; confere a abertura da malha, "
                               "o alcance por cima e a folga inferior pela ABNT NBR ISO 13857."}

        def IsActive(self):
            return FreeCAD.ActiveDocument is not None

        def Activated(self):
            PainelProtecao().mostrar()

    class CmdRelatorioProtecao:
        def GetResources(self):
            import PrumoUtil
            return {"Pixmap": PrumoUtil.icone("protecao_nr12.svg"), "MenuText": "Relatório das proteções",
                    "ToolTip": "Lista as proteções NR-12 do projeto com a verificação de cada uma."}

        def IsActive(self):
            doc = FreeCAD.ActiveDocument
            return doc is not None and any(e_protecao(o) for o in doc.Objects)

        def Activated(self):
            doc = FreeCAD.ActiveDocument
            txt = "\n\n".join(relatorio(o) for o in doc.Objects if e_protecao(o))
            dlg = QtWidgets.QDialog(FreeCADGui.getMainWindow())
            dlg.setWindowTitle("Proteções NR-12")
            dlg.resize(760, 520)
            lay = QtWidgets.QVBoxLayout(dlg)
            t = QtWidgets.QPlainTextEdit(txt)
            t.setReadOnly(True)
            lay.addWidget(t)
            bb = QtWidgets.QHBoxLayout()
            copiar = QtWidgets.QPushButton("Copiar")
            copiar.clicked.connect(lambda: QtWidgets.QApplication.clipboard().setText(txt))
            fechar = QtWidgets.QPushButton("Fechar")
            fechar.clicked.connect(dlg.accept)
            bb.addWidget(copiar)
            bb.addStretch(1)
            bb.addWidget(fechar)
            lay.addLayout(bb)
            dlg.exec_() if hasattr(dlg, "exec_") else dlg.exec()

    def _duplo_clique(self, vobj):
        PainelProtecao().editar_objeto(vobj.Object).mostrar()
        return True

    VistaProtecao.doubleClicked = _duplo_clique


def registrar_comandos():
    if FreeCADGui is not None and P is not None and "Prumo_ProtecaoNR12" not in FreeCADGui.listCommands():
        FreeCADGui.addCommand("Prumo_ProtecaoNR12", CmdProtecao())
        FreeCADGui.addCommand("Prumo_RelatorioProtecao", CmdRelatorioProtecao())
