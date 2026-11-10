# SPDX-License-Identifier: LGPL-2.1-or-later
# Usinix - escada industrial paramétrica (vigas, degraus e guarda-corpo num objeto só), conferida pela NR-12.
"""Escada industrial.

Um objeto "Escada" junta tudo o que forma a escada — as duas vigas (banzos), os degraus, o guarda-corpo e o
rodapé — e se edita por duplo clique: muda o desnível, o ângulo, a largura ou um perfil e a escada inteira se
refaz. Por dentro:
- banzos: uma estrutura soldada (Estruturas) com as pontas cortadas na horizontal no piso e no topo;
- guarda-corpo: outra estrutura soldada (montantes, travessão superior e intermediário) em cada lado escolhido;
- degraus e rodapés: peças desenhadas pela escada, contadas na lista de materiais pela quantidade.

A escada sobe no sentido +X local, com a largura em Y e o piso em z = 0; Posicao leva a escada para o lugar.

Verificação ao vivo pelo Anexo III da NR-12 (texto atualizado pela Portaria MTP n.º 4.219, de 20/12/2022,
conferido no gov.br em 10/11/2026): Figura 1 (escada com espelho de 20° a 45°; sem espelho de 45° a 75°, lidos na
figura), itens 7 (travessão superior de 1,10 m a 1,20 m, intermediário a 0,70 m, rodapé de 0,20 m), 11 (sem
espelho: largura útil 0,60 m, profundidade 0,15 m, altura até 0,25 m, 600 ≤ g + 2h ≤ 660 mm, patamar a cada
3,00 m, projeção r ≥ 0) e 12 (com espelho: profundidade 0,20 m, altura de 0,20 m a 0,25 m). Lance único com
menos de 1,50 m de altura: largura útil mínima de 0,50 m (11.1 e 12.1).
"""

import math
import os

import FreeCAD

AQUI = os.path.dirname(os.path.abspath(__file__))
TIPOS_DEGRAU = ("Grade de piso (sem espelho)", "Chapa xadrez dobrada (sem espelho)",
                "Chapa xadrez com espelho")
LADOS = ("Os dois lados", "Lado esquerdo", "Lado direito", "Sem guarda-corpo")
PERFIL_BANZO = 'I 8" x 27,3 kg/m'
PERFIL_GUARDA = "Tubo ○ 38,1 x 2"
NR12 = "NR-12, Anexo III (Portaria MTP n.º 4.219/2022)"
PARAMETROS = ("Posicao", "Desnivel", "Angulo", "LarguraUtil", "NumeroEspelhos", "TipoDegrau", "EspessuraDegrau",
              "Sobreposicao", "PerfilBanzo", "ElevacaoBanzo", "LadosGuarda", "PerfilGuarda", "AlturaGuarda",
              "AlturaIntermediario", "EspacamentoMontantes", "Rodape", "AlturaRodape", "Material")
DENS = 7850.0


def _n(v, casas=0):
    s = ("%." + str(casas) + "f") % v
    return s.replace(".", ",")


# ============================================================================ geometria (sem FreeCAD.Gui)
class Medidas:
    """Medidas calculadas da escada (mm e graus)."""

    def __init__(self, esc):
        self.H = float(esc.Desnivel.Value)
        self.ang = float(esc.Angulo.Value)
        self.W = float(esc.LarguraUtil.Value)
        th = math.radians(self.ang)
        self.tan = math.tan(th)
        self.sen, self.cos = math.sin(th), math.cos(th)
        self.L = self.H / self.tan                       # projeção horizontal do lance
        alvo = 630.0 / (2.0 + 1.0 / self.tan)            # 2h + g = 630 (meio da faixa 600-660)
        n = int(esc.NumeroEspelhos) if int(esc.NumeroEspelhos) > 0 else max(1, int(round(self.H / alvo)))
        self.n = n                                       # espelhos (subidas); degraus = n - 1 (o último é o piso)
        self.h = self.H / n
        self.g = self.h / self.tan                       # profundidade livre (passo horizontal)
        self.r = float(esc.Sobreposicao.Value)
        self.t = self.g + self.r                         # profundidade total do degrau
        self.e = float(esc.EspessuraDegrau.Value)
        self.espelho = esc.TipoDegrau == TIPOS_DEGRAU[2]
        import PrumoPerfis
        it = PrumoPerfis.perfil(esc.PerfilBanzo)
        larg, alt = PrumoPerfis.dimensoes(it) if it else (100.0, 200.0)
        self.bf, self.alt = larg, alt
        # faixa ocupada pelo degrau abaixo da linha de passo (perpendicular): fundo do degrau mais fundo
        D = self.t * self.sen + self.e * self.cos
        auto = max(0.0, alt / 2.0 - D / 2.0)
        self.sobra = float(esc.ElevacaoBanzo.Value) if esc.ElevacaoBanzo.Value > 0 else auto
        self.y_banzo = self.W / 2.0 + larg / 2.0         # eixo do banzo (abas na largura útil)

    def z_passo(self, x):
        """Altura da linha de passo (bordas dos degraus) em x."""
        return x * self.tan


def linhas_banzos(m):
    """Linhas de centro dos dois banzos (locais): paralelas à linha de passo, com o topo da viga a `sobra`."""
    off = (m.sobra - m.alt / 2.0) / m.cos                # deslocamento vertical do eixo em relação à linha de passo
    # o eixo corta o piso (z = 0) e o topo (z = H)
    x0 = -off / m.tan
    x1 = (m.H - off) / m.tan
    res = []
    for y in (-m.y_banzo, m.y_banzo):
        res.append((FreeCAD.Vector(x0, y, 0.0), FreeCAD.Vector(x1, y, m.H)))
    return res


def degraus(m):
    """[(x da borda, z do piso do degrau)] dos degraus (sem o piso de chegada)."""
    return [(i * m.g, i * m.h) for i in range(1, m.n)]


def lados(esc):
    return {"Os dois lados": (-1, 1), "Lado esquerdo": (1,), "Lado direito": (-1,)}.get(esc.LadosGuarda, ())


def linhas_guarda(esc, m):
    """Linhas do guarda-corpo (locais): montantes, travessão superior e intermediário em cada lado."""
    res = []
    hc = float(esc.AlturaGuarda.Value)
    hi = float(esc.AlturaIntermediario.Value)
    xa = min(m.g * 0.5, 150.0) if m.n > 1 else 0.0
    xb = max(m.L - 100.0, xa + 1.0)
    vao = max(float(esc.EspacamentoMontantes.Value), 300.0)
    nm = max(2, int(math.ceil((xb - xa) / vao)) + 1)
    xs = [xa + (xb - xa) * k / (nm - 1) for k in range(nm)]
    # base do montante: topo do banzo (perpendicular `sobra` acima da linha de passo, medido na vertical)
    dz_base = m.sobra / m.cos
    for s in lados(esc):
        y = s * m.y_banzo
        topo = [FreeCAD.Vector(x, y, m.z_passo(x) + hc) for x in xs]
        meio = [FreeCAD.Vector(x, y, m.z_passo(x) + hi) for x in xs]
        for x, pt in zip(xs, topo):
            res.append((FreeCAD.Vector(x, y, m.z_passo(x) + dz_base), pt))
        # travessões em trechos de montante a montante (os montantes passam inteiros)
        for k in range(len(xs) - 1):
            res.append((topo[k], topo[k + 1]))
            res.append((meio[k], meio[k + 1]))
    return res, xs


def _solido_degrau(m, tipo, comp):
    """Degrau no sistema local: borda em x = 0, piso em z = 0, centrado em y (largura comp)."""
    import Part
    t, e = m.t, m.e
    if tipo == TIPOS_DEGRAU[0]:                          # grade: placa de altura e com chapas de ponta
        alt = max(e, 25.0)
        caixa = Part.makeBox(t, comp, alt, FreeCAD.Vector(0, -comp / 2.0, -alt))
        return caixa
    # chapa xadrez dobrada: piso + aba na frente (e no fundo); com espelho: aba de trás desce até o degrau de baixo
    aba = 40.0
    pts = [(0, 0), (t, 0), (t, -aba if not m.espelho else -m.h), (t - e, -aba if not m.espelho else -m.h),
           (t - e, -e), (e, -e), (e, -aba), (0, -aba)]
    if m.espelho:
        # espelho na frente: a chapa desce na borda até o piso do degrau de baixo
        pts = [(0, 0), (t, 0), (t, -aba), (t - e, -aba), (t - e, -e), (e, -e), (e, -m.h), (0, -m.h)]
    w = Part.makePolygon([FreeCAD.Vector(x, -comp / 2.0, z) for x, z in pts] +
                         [FreeCAD.Vector(pts[0][0], -comp / 2.0, pts[0][1])])
    return Part.Face(w).extrude(FreeCAD.Vector(0, comp, 0))


def forma_degraus(esc, m):
    """(compound dos degraus e rodapés no sistema local, [(denominação, qtd, massa unitária kg, dims)])."""
    import Part
    folga = 5.0
    comp = m.W - 2 * folga
    base = _solido_degrau(m, esc.TipoDegrau, comp)
    sol = []
    for x, z in degraus(m):
        s = base.copy()
        s.translate(FreeCAD.Vector(x, 0, z))
        sol.append(s)
    itens = []
    if sol:
        massa = base.Volume * 1e-9 * DENS
        if esc.TipoDegrau == TIPOS_DEGRAU[0]:
            # grade: massa estimada de grade 30 × 3 mm, malha 30 × 100 (≈ 22 % de aço)
            massa *= 0.22
            den = "Degrau de grade de piso %s × %s mm" % (_n(m.t), _n(comp))
        else:
            den = "Degrau de chapa xadrez %s mm, %s × %s mm" % (_n(m.e, 2), _n(m.t), _n(comp))
        itens.append((den, len(sol), massa, "%s × %s" % (_n(m.t), _n(comp))))
    # rodapé (chapa 1/8" × 200 mm) ao longo da escada, por dentro, em cada lado com guarda-corpo
    if esc.Rodape and lados(esc):
        alt_r = float(esc.AlturaRodape.Value)
        esp = 3.0
        x0, x1 = 0.0, m.L
        for s in lados(esc):
            y = s * (m.W / 2.0 + esp / 2.0)
            off = 0.0
            pts = [FreeCAD.Vector(x0, y - esp / 2.0, m.z_passo(x0) + off),
                   FreeCAD.Vector(x1, y - esp / 2.0, m.z_passo(x1) + off),
                   FreeCAD.Vector(x1, y - esp / 2.0, m.z_passo(x1) + off + alt_r),
                   FreeCAD.Vector(x0, y - esp / 2.0, m.z_passo(x0) + off + alt_r)]
            f = Part.Face(Part.makePolygon(pts + [pts[0]]))
            sol.append(f.extrude(FreeCAD.Vector(0, esp, 0)))
        compr = math.hypot(m.L, m.H)
        itens.append(("Rodapé chapa %s × %s mm" % (_n(esp), _n(alt_r)), len(lados(esc)),
                      compr * alt_r * esp * 1e-9 * DENS, "%s mm" % _n(compr)))
    return (Part.makeCompound(sol) if sol else Part.Shape()), itens


# ============================================================================ verificação NR-12
def verificar(esc, m=None):
    """[(ok, texto)] pelo Anexo III da NR-12."""
    m = m or Medidas(esc)
    v = []

    def item(ok, txt):
        v.append((bool(ok), txt))
    if m.espelho:
        item(20.0 - 1e-6 <= m.ang <= 45.0 + 1e-6, "Ângulo %s° — escada com espelho: de 20° a 45° (Figura 1)"
             % _n(m.ang, 1))
    else:
        item(20.0 - 1e-6 <= m.ang <= 75.0 + 1e-6, "Ângulo %s° — escada de degraus: de 20° a 75° (Figura 1; com "
             "espelho até 45°)" % _n(m.ang, 1))
    lim_w = 500.0 if m.H < 1500.0 else 600.0
    item(m.W >= lim_w - 1e-6, "Largura útil %s mm — mínimo %s mm (%s)" % (
        _n(m.W), _n(lim_w), "11.1/12.1, lance com menos de 1,50 m" if lim_w < 600 else "11 a / 12 a"))
    if m.espelho:
        item(m.g >= 200.0 - 1e-6, "Profundidade do degrau %s mm — mínimo 200 mm (12 b)" % _n(m.g))
        item(200.0 - 1e-6 <= m.h <= 250.0 + 1e-6, "Altura entre degraus %s mm — de 200 a 250 mm (12 d)" % _n(m.h))
    else:
        item(m.g >= 150.0 - 1e-6, "Profundidade livre do degrau g = %s mm — mínimo 150 mm (11 b)" % _n(m.g))
        item(m.h <= 250.0 + 1e-6, "Altura entre degraus h = %s mm — máximo 250 mm (11 d)" % _n(m.h))
        f = m.g + 2 * m.h
        item(600.0 - 1e-6 <= f <= 660.0 + 1e-6, "g + 2h = %s mm — de 600 a 660 mm (11 g)" % _n(f))
        item(m.r >= -1e-6, "Projeção de um degrau sobre o outro r = %s mm — maior ou igual a 0 (11 f)" % _n(m.r))
    item(m.H <= 3000.0 + 1e-6, "Desnível %s mm — patamar de descanso a cada 3 000 mm no máximo (11 e / 12 e)%s"
         % (_n(m.H), "" if m.H <= 3000.0 else ": divida em lances com patamar"))
    if lados(esc):
        hc = float(esc.AlturaGuarda.Value)
        item(1100.0 - 1e-6 <= hc <= 1200.0 + 1e-6, "Travessão superior a %s mm — de 1 100 a 1 200 mm (7 c)" % _n(hc))
        hi = float(esc.AlturaIntermediario.Value)
        item(abs(hi - 700.0) < 1e-6, "Travessão intermediário a %s mm — 700 mm (7 e)" % _n(hi))
        item(bool(esc.Rodape) and esc.AlturaRodape.Value >= 200.0 - 1e-6,
             "Rodapé %s — mínimo 200 mm (7 e)" % ("de %s mm" % _n(esc.AlturaRodape.Value) if esc.Rodape
                                                 else "não previsto"))
        if len(lados(esc)) < 2:
            item(False, "Guarda-corpo em um lado só — o item 7 c pede travessão superior em ambos os lados")
    else:
        item(False, "Sem guarda-corpo — o item 7 pede proteção contra quedas em ambos os lados")
    return v


# ============================================================================ objetos
class Escada:
    def __init__(self, obj):
        obj.Proxy = self
        self._props(obj)

    def _props(self, obj):
        def add(tipo, nome, grupo, doc, valor=None, so_ler=False):
            if nome not in obj.PropertiesList:
                obj.addProperty(tipo, nome, grupo, doc)
                if valor is not None:
                    setattr(obj, nome, valor)
            if so_ler:
                obj.setEditorMode(nome, 1)

        def enum(nome, grupo, doc, valores, padrao):
            if nome not in obj.PropertiesList:
                obj.addProperty("App::PropertyEnumeration", nome, grupo, doc)
                setattr(obj, nome, list(valores))
                setattr(obj, nome, padrao)
        add("App::PropertyBool", "EscadaUsinix", "Escada", "Marca do objeto", True)
        obj.setEditorMode("EscadaUsinix", 2)
        add("App::PropertyPlacement", "Posicao", "Escada", "Onde fica o pé da escada (sobe em +X local)")
        add("App::PropertyLength", "Desnivel", "Escada", "Altura do piso de baixo ao piso de cima", 2400.0)
        add("App::PropertyAngle", "Angulo", "Escada", "Inclinação da escada", 45.0)
        add("App::PropertyLength", "LarguraUtil", "Escada", "Largura livre entre os banzos", 800.0)
        add("App::PropertyInteger", "NumeroEspelhos", "Degraus", "Número de subidas; 0 = automático "
            "(g + 2h perto de 630 mm)", 0)
        enum("TipoDegrau", "Degraus", "Tipo de degrau", TIPOS_DEGRAU, TIPOS_DEGRAU[0])
        add("App::PropertyLength", "EspessuraDegrau", "Degraus", "Altura da grade ou espessura da chapa", 30.0)
        add("App::PropertyLength", "Sobreposicao", "Degraus", "Projeção r de um degrau sobre o outro", 25.0)
        add("App::PropertyString", "PerfilBanzo", "Banzos", "Perfil das duas vigas", PERFIL_BANZO)
        add("App::PropertyLength", "ElevacaoBanzo", "Banzos", "Topo da viga acima da linha de passo; 0 = "
            "automático (degrau no meio da viga)", 0.0)
        enum("LadosGuarda", "Guarda-corpo", "Onde vai guarda-corpo", LADOS, LADOS[0])
        add("App::PropertyString", "PerfilGuarda", "Guarda-corpo", "Perfil de montantes e travessões", PERFIL_GUARDA)
        add("App::PropertyLength", "AlturaGuarda", "Guarda-corpo", "Travessão superior acima da linha de passo",
            1100.0)
        add("App::PropertyLength", "AlturaIntermediario", "Guarda-corpo", "Travessão intermediário", 700.0)
        add("App::PropertyLength", "EspacamentoMontantes", "Guarda-corpo", "Distância máxima entre montantes "
            "(na horizontal)", 1200.0)
        add("App::PropertyBool", "Rodape", "Guarda-corpo", "Chapa de rodapé", True)
        add("App::PropertyLength", "AlturaRodape", "Guarda-corpo", "Altura do rodapé", 200.0)
        add("App::PropertyString", "Material", "Lista", "Material", "Aço carbono")
        for nome, tipo, doc in (("AlturaEspelho", "App::PropertyFloat", "Altura entre degraus h (mm)"),
                                ("ProfundidadeLivre", "App::PropertyFloat", "Profundidade livre g (mm)"),
                                ("Degraus", "App::PropertyInteger", "Número de degraus"),
                                ("Vao", "App::PropertyFloat", "Projeção horizontal do lance (mm)"),
                                ("Conforme", "App::PropertyBool", "Tudo confere com a NR-12"),
                                ("Verificacao", "App::PropertyStringList", "Itens verificados (NR-12, Anexo III)")):
            add(tipo, nome, "Resultado", doc, so_ler=True)
        add("App::PropertyLinkHidden", "EsqBanzos", "Partes", "Esqueleto dos banzos")
        add("App::PropertyLinkHidden", "EsqGuarda", "Partes", "Esqueleto do guarda-corpo")
        add("App::PropertyLinkHidden", "Banzos", "Partes", "Estrutura dos banzos")
        add("App::PropertyLinkHidden", "GuardaCorpo", "Partes", "Estrutura do guarda-corpo")
        add("App::PropertyLinkHidden", "PecasDegraus", "Partes", "Degraus e rodapés")

    def onDocumentRestored(self, obj):
        obj.Proxy = self
        self._props(obj)

    def onChanged(self, obj, prop):
        """Mudou um parâmetro no painel Propriedades: refaz as partes (fora do recálculo)."""
        if prop not in PARAMETROS or not FreeCAD.GuiUp or "Banzos" not in obj.PropertiesList:
            return
        if _chave(obj) in _OCUPADAS:
            return           # a própria escada está se refazendo (ou sendo criada)
        try:
            import FreeCADGui as G
            if obj.Document.Restoring or G.Control.activeDialog():
                return       # abrindo o arquivo, ou o painel da escada já refaz
            from PySide import QtCore
        except Exception:
            return
        if getattr(self, "_agendado", False):
            return
        self._agendado = True

        def refazer(o=obj, eu=self):
            eu._agendado = False
            try:
                if o.Document.getObject(o.Name) is not None and _chave(o) not in _OCUPADAS:
                    reconstruir(o)
            except Exception as exc:
                FreeCAD.Console.PrintWarning("Usinix: escada: %s\n" % exc)
        QtCore.QTimer.singleShot(0, refazer)

    def execute(self, obj):
        m = Medidas(obj)
        obj.AlturaEspelho = m.h
        obj.ProfundidadeLivre = m.g
        obj.Degraus = max(0, m.n - 1)
        obj.Vao = m.L
        v = verificar(obj, m)
        obj.Conforme = all(ok for ok, _t in v)
        obj.Verificacao = [("✓ " if ok else "✗ ") + t for ok, t in v]


class Degraus:
    """Degraus e rodapés da escada (uma peça só no modelo; na lista, um item por tipo com a quantidade)."""

    def __init__(self, obj):
        obj.Proxy = self
        if "Escada" not in obj.PropertiesList:
            obj.addProperty("App::PropertyLink", "Escada", "Degraus", "Escada a que pertence")
        if "Itens" not in obj.PropertiesList:
            obj.addProperty("App::PropertyStringList", "Itens", "Degraus", "Itens para a lista de materiais")
            obj.setEditorMode("Itens", 1)

    def onDocumentRestored(self, obj):
        obj.Proxy = self

    def execute(self, obj):
        esc = obj.Escada
        if esc is None:
            return
        m = Medidas(esc)
        sh, itens = forma_degraus(esc, m)
        obj.Shape = sh
        obj.Placement = esc.Posicao
        import json
        obj.Itens = [json.dumps({"den": d, "qtd": q, "massa": round(ms, 3), "dim": dim}, ensure_ascii=False)
                     for d, q, ms, dim in itens]

    def linhas_bom(self, obj):
        """[(chave, denominação, material, dimensões, quantidade, massa unitária, obs)]."""
        import json
        mat = getattr(obj.Escada, "Material", "") if obj.Escada else ""
        res = []
        for t in obj.Itens:
            d = json.loads(t)
            res.append((("escada", d["den"], mat), d["den"], mat, d["dim"], d["qtd"], d["massa"], "escada"))
        return res


def _arame(linhas, pl):
    import Part
    eds = [Part.makeLine(pl.multVec(a), pl.multVec(b)) for a, b in linhas if (b - a).Length > 1e-6]
    return Part.makeCompound(eds)


_OCUPADAS = set()


def _chave(o):
    try:
        return (o.Document.Name, o.Name)
    except Exception:
        return None


def reconstruir(esc):
    """Refaz banzos, degraus e guarda-corpo com os parâmetros atuais da escada (cria as partes que faltam)."""
    k = _chave(esc)
    if k in _OCUPADAS:
        return esc
    _OCUPADAS.add(k)
    try:
        return _reconstruir(esc)
    finally:
        _OCUPADAS.discard(k)


def _reconstruir(esc):
    import PrumoEstrutura as E
    doc = esc.Document
    m = Medidas(esc)
    pl = esc.Posicao
    # banzos
    if esc.EsqBanzos is None:
        sk = doc.addObject("Part::Feature", "EsqueletoBanzos")
        sk.Label = "Esqueleto dos banzos"
        esc.EsqBanzos = sk
        esc.addObject(sk)
    esc.EsqBanzos.Shape = _arame(linhas_banzos(m), pl)
    # as duas linhas dos banzos ficam num plano inclinado: a altura da viga tem de ficar no plano vertical
    # da escada (giro de 90° quando o Usinix toma o plano inclinado como "pórtico"; em escada quase deitada
    # ele já põe a altura na vertical)
    giro = 0.0 if abs(m.cos) > 0.9 else 90.0
    if esc.Banzos is None:
        est = E.criar(doc, esc.EsqBanzos, esc.PerfilBanzo, rotacao=giro, transacao=False, material=esc.Material)
        est.Label = "Banzos"
        esc.Banzos = est
        esc.addObject(est)
    else:
        esc.Banzos.Perfil = esc.PerfilBanzo
        esc.Banzos.Rotacao = giro
        esc.Banzos.Material = esc.Material
        E.sincronizar_barras(esc.Banzos)
    for i in range(2):
        E.definir_ponta(esc.Banzos, i, 0, E.PONTA_HORIZONTAL)
        E.definir_ponta(esc.Banzos, i, 1, E.PONTA_HORIZONTAL)
    # degraus e rodapés
    if esc.PecasDegraus is None:
        dg = doc.addObject("Part::FeaturePython", "Degraus")
        Degraus(dg)
        dg.Escada = esc
        dg.Label = "Degraus e rodapés"
        if FreeCAD.GuiUp:
            VistaDegraus(dg.ViewObject)
        esc.PecasDegraus = dg
        esc.addObject(dg)
    esc.PecasDegraus.touch()
    # guarda-corpo
    linhas, _xs = linhas_guarda(esc, m)
    if linhas:
        if esc.EsqGuarda is None:
            sk = doc.addObject("Part::Feature", "EsqueletoGuarda")
            sk.Label = "Esqueleto do guarda-corpo"
            esc.EsqGuarda = sk
            esc.addObject(sk)
        velho = esc.EsqGuarda.Shape
        esc.EsqGuarda.Shape = _arame(linhas, pl)
        if esc.GuardaCorpo is not None and len(velho.Edges) != len(esc.EsqGuarda.Shape.Edges):
            _apagar_estrutura(esc.GuardaCorpo)
            esc.GuardaCorpo = None
        if esc.GuardaCorpo is None:
            est = E.criar(doc, esc.EsqGuarda, esc.PerfilGuarda, transacao=False, material=esc.Material)
            est.Label = "Guarda-corpo"
            esc.GuardaCorpo = est
            esc.addObject(est)
        else:
            esc.GuardaCorpo.Perfil = esc.PerfilGuarda
            E.sincronizar_barras(esc.GuardaCorpo)
    elif esc.GuardaCorpo is not None:
        _apagar_estrutura(esc.GuardaCorpo)
        esc.GuardaCorpo = None
    for o in (esc.EsqBanzos, esc.EsqGuarda):
        if o is not None and FreeCAD.GuiUp:
            try:
                o.ViewObject.Visibility = False
            except Exception:
                pass
    esc.touch()
    doc.recompute()
    return esc


def _apagar_estrutura(est):
    import PrumoEstrutura as E
    doc = est.Document
    for b in list(E.barras_de(est)):
        doc.removeObject(b.Name)
    doc.removeObject(est.Name)


def criar(doc=None, **kw):
    doc = doc or FreeCAD.ActiveDocument
    esc = doc.addObject("App::DocumentObjectGroupPython", "Escada")
    k = _chave(esc)
    _OCUPADAS.add(k)
    try:
        Escada(esc)
        for nome, v in kw.items():
            setattr(esc, nome, v)
        esc.Label = "Escada"
        if FreeCAD.GuiUp:
            VistaEscada(esc.ViewObject)
    finally:
        _OCUPADAS.discard(k)
    reconstruir(esc)
    return esc


def e_escada(o):
    return o is not None and isinstance(getattr(o, "Proxy", None), Escada)


def escada_de(o):
    if e_escada(o):
        return o
    for p in getattr(o, "InList", []) or []:
        if e_escada(p):
            return p
        for q in getattr(p, "InList", []) or []:
            if e_escada(q):
                return q
    return None


def relatorio(esc):
    L = ["%s — %s" % (esc.Label, "confere com a NR-12" if esc.Conforme else "NÃO CONFERE com a NR-12"),
         "Desnível %s mm, ângulo %s°, vão %s mm, largura útil %s mm" % (
             _n(esc.Desnivel.Value), _n(esc.Angulo.Value, 1), _n(esc.Vao), _n(esc.LarguraUtil.Value)),
         "%d degraus (%s), h = %s mm, g = %s mm" % (esc.Degraus, esc.TipoDegrau, _n(esc.AlturaEspelho, 1),
                                                    _n(esc.ProfundidadeLivre, 1))]
    L.extend(esc.Verificacao)
    L.append("Referência: %s, texto conferido no gov.br em 10/11/2026." % NR12)
    return "\n".join(L)


# ============================================================================ interface
try:
    import FreeCADGui
    from PySide import QtCore, QtWidgets
    import PrumoPainel as P
except ImportError:
    FreeCADGui = None
    P = None


class VistaEscada:
    def __init__(self, vobj):
        vobj.Proxy = self

    def attach(self, vobj):
        self.vobj = vobj

    def getIcon(self):
        return os.path.join(AQUI, "Resources", "icons", "escada.svg")

    def claimChildren(self):
        o = self.vobj.Object
        return [c for c in (o.Banzos, o.PecasDegraus, o.GuardaCorpo, o.EsqBanzos, o.EsqGuarda) if c is not None]

    def doubleClicked(self, vobj):
        if P is not None:
            PainelEscada().editar_objeto(vobj.Object).mostrar()
            return True
        return False

    def onDelete(self, vobj, subelements):
        o = vobj.Object
        doc = o.Document
        for est in (o.Banzos, o.GuardaCorpo):
            if est is not None:
                try:
                    _apagar_estrutura(est)
                except Exception:
                    pass
        for c in (o.PecasDegraus, o.EsqBanzos, o.EsqGuarda):
            if c is not None:
                try:
                    doc.removeObject(c.Name)
                except Exception:
                    pass
        return True

    def dumps(self):
        return None

    def loads(self, state):
        return None


class VistaDegraus:
    def __init__(self, vobj):
        vobj.Proxy = self

    def attach(self, vobj):
        self.vobj = vobj
        try:
            vobj.ShapeAppearance = [FreeCAD.Material(DiffuseColor=(0.62, 0.66, 0.70))]
        except Exception:
            pass

    def getIcon(self):
        return os.path.join(AQUI, "Resources", "icons", "escada.svg")

    def doubleClicked(self, vobj):
        esc = vobj.Object.Escada
        if esc is not None and P is not None:
            PainelEscada().editar_objeto(esc).mostrar()
            return True
        return False

    def dumps(self):
        return None

    def loads(self, state):
        return None


if P is not None:
    class PainelEscada(P.PainelTarefa):
        titulo = "Escada"
        ajuda = ("Escada industrial com as duas vigas, os degraus e o guarda-corpo num objeto só. Informe o desnível "
                 "e o ângulo: o Usinix calcula os degraus e confere a NR-12 (Anexo III) enquanto você muda.")
        previa = True

        def montar(self):
            import PrumoPerfis
            f = self.form
            s1 = f.secao("Escada", "tipo")
            self.desnivel = P.numero(2400.0, 200.0, 20000.0)
            s1.linha("altura", self.desnivel, "Do piso de baixo ao piso de cima.", "Desnível")
            self.angulo = P.numero(45.0, 20.0, 75.0, sufixo="°")
            s1.linha("angulo", self.angulo, "Inclinação (20° a 45° com espelho; até 75° sem espelho).", "Ângulo")
            self.largura = P.numero(800.0, 400.0, 3000.0)
            s1.linha("largura", self.largura, "Largura livre entre as vigas (mínimo 600 mm).", "Largura útil")
            s2 = f.secao("Degraus", "furo")
            self.tipo = P.lista(list(TIPOS_DEGRAU), TIPOS_DEGRAU[0])
            s2.linha("tipo", self.tipo, "Grade ou chapa xadrez.", "Degrau")
            self.n = QtWidgets.QSpinBox()
            self.n.setRange(0, 60)
            self.n.setSpecialValueText("automático")
            s2.linha("comprimento", self.n, "Número de subidas; automático deixa g + 2h perto de 630 mm.",
                     "Subidas")
            self.esp = P.numero(30.0, 2.0, 80.0)
            s2.linha("espessura", self.esp, "Altura da grade ou espessura da chapa.", "Espessura")
            s3 = f.secao("Vigas (banzos)", "estrutura")
            nomes = [it["nome"] for fam in ("I", "U", "W") for it in (PrumoPerfis.familia(fam) or {}).get("itens", [])]
            self.perfil = P.lista(nomes or [PERFIL_BANZO], PERFIL_BANZO)
            self.perfil.setEditable(True)
            s3.linha("perfil", self.perfil, "Perfil das duas vigas.", "Perfil")
            s4 = f.secao("Guarda-corpo", "posicao")
            self.lados = P.lista(list(LADOS), LADOS[0])
            s4.linha("posicao", self.lados, "A NR-12 pede guarda-corpo dos dois lados.", "Lados")
            self.hg = P.numero(1100.0, 900.0, 1300.0)
            s4.linha("altura", self.hg, "Travessão superior acima da linha dos degraus (1 100 a 1 200 mm).",
                     "Altura")
            self.rodape = s4.linha("posicao", P.marcar("Rodapé de 200 mm"), "")
            self.rodape.setChecked(True)
            s6 = f.secao("Posição do pé da escada", "posicao")
            self.px = P.numero(0.0, -1e6, 1e6)
            s6.linha("posicao", self.px, "Pé da escada (início do primeiro degrau), em X.", "X")
            self.py = P.numero(0.0, -1e6, 1e6)
            s6.linha("posicao", self.py, "Em Y (meio da largura).", "Y")
            self.pz = P.numero(0.0, -1e6, 1e6)
            s6.linha("altura", self.pz, "Nível do piso de baixo.", "Z")
            self.giro = P.numero(0.0, -360.0, 360.0, sufixo="°")
            s6.linha("angulo", self.giro, "Giro em planta: 0° sobe para +X, 90° sobe para +Y.", "Giro")
            s5 = f.secao("Conferência NR-12", "info")
            self.resultado = QtWidgets.QLabel("—")
            self.resultado.setWordWrap(True)
            self.resultado.setTextFormat(QtCore.Qt.RichText)
            s5.widget(self.resultado)

        def pendencia(self):
            import PrumoPerfis
            if PrumoPerfis.perfil(self.perfil.currentText()) is None:
                return "Perfil desconhecido: %s" % self.perfil.currentText()
            return None

        def pronto_texto(self):
            return "OK grava a escada." if self.editando is not None else "OK cria a escada."

        def _kw(self):
            return {"Desnivel": self.desnivel.value(), "Angulo": self.angulo.value(),
                    "LarguraUtil": self.largura.value(), "TipoDegrau": self.tipo.currentText(),
                    "NumeroEspelhos": int(self.n.value()), "EspessuraDegrau": self.esp.value(),
                    "PerfilBanzo": self.perfil.currentText(), "LadosGuarda": self.lados.currentText(),
                    "AlturaGuarda": self.hg.value(), "Rodape": self.rodape.isChecked(),
                    "Posicao": FreeCAD.Placement(FreeCAD.Vector(self.px.value(), self.py.value(), self.pz.value()),
                                                 FreeCAD.Rotation(FreeCAD.Vector(0, 0, 1), self.giro.value()))}

        def carregar(self, obj):
            self.desnivel.setValue(obj.Desnivel.Value)
            self.angulo.setValue(obj.Angulo.Value)
            self.largura.setValue(obj.LarguraUtil.Value)
            self.tipo.setCurrentText(obj.TipoDegrau)
            self.n.setValue(int(obj.NumeroEspelhos))
            self.esp.setValue(obj.EspessuraDegrau.Value)
            self.perfil.setCurrentText(obj.PerfilBanzo)
            self.lados.setCurrentText(obj.LadosGuarda)
            self.hg.setValue(obj.AlturaGuarda.Value)
            self.rodape.setChecked(bool(obj.Rodape))
            b = obj.Posicao.Base
            self.px.setValue(b.x)
            self.py.setValue(b.y)
            self.pz.setValue(b.z)
            self.giro.setValue(math.degrees(obj.Posicao.Rotation.Angle) * (1 if obj.Posicao.Rotation.Axis.z >= 0
                                                                            else -1))
            self._mostrar_resultado(obj)

        def props_edicao(self):
            return self._kw()

        def aplicar_edicao(self, obj):
            super().aplicar_edicao(obj)
            reconstruir(obj)
            return obj

        def executar(self):
            esc = criar(**self._kw())
            self._mostrar_resultado(esc)
            if FreeCAD.GuiUp and not getattr(self, "_enquadrou", False):
                self._enquadrou = True
                try:
                    FreeCADGui.activeDocument().activeView().viewIsometric()
                    FreeCADGui.SendMsgToActiveView("ViewFit")
                except Exception:
                    pass
            return [esc]

        def _atualizar_previa(self):
            super()._atualizar_previa()
            alvo = self.editando
            if alvo is None:
                doc = self._doc_previa
                nomes = [n for n in self._previa_nomes if doc and doc.getObject(n) is not None
                         and e_escada(doc.getObject(n))]
                alvo = doc.getObject(nomes[0]) if nomes else None
            self._mostrar_resultado(alvo)

        def _mostrar_resultado(self, esc):
            if esc is None:
                self.resultado.setText("—")
                return
            cor = "#2E8B57" if esc.Conforme else "#C0392B"
            L = ["<b style='color:%s'>%s</b>" % (cor, "Confere com a NR-12" if esc.Conforme else "Não confere"),
                 "%d degraus · h = %s mm · g = %s mm · vão %s mm" % (
                     esc.Degraus, _n(esc.AlturaEspelho, 1), _n(esc.ProfundidadeLivre, 1), _n(esc.Vao))]
            for v in esc.Verificacao:
                c = "#2E8B57" if v.startswith("✓") else "#C0392B"
                L.append("<span style='color:%s'>%s</span>" % (c, v))
            self.resultado.setText("<br>".join(L))

    class CmdEscada:
        def GetResources(self):
            import PrumoUtil
            return {"Pixmap": PrumoUtil.icone("escada.svg"), "MenuText": "Escada",
                    "ToolTip": "Escada industrial com vigas, degraus e guarda-corpo num objeto só; calcula os "
                               "degraus e confere a NR-12 (Anexo III)."}

        def IsActive(self):
            return FreeCAD.ActiveDocument is not None

        def Activated(self):
            PainelEscada().mostrar()


def registrar_comandos():
    if FreeCADGui is not None and P is not None and "Prumo_Escada" not in FreeCADGui.listCommands():
        FreeCADGui.addCommand("Prumo_Escada", CmdEscada())
