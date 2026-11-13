# SPDX-License-Identifier: LGPL-2.1-or-later
"""Solda e rugosidade no desenho, em português e em cartões.

- Solda (símbolos da ISO 2553 / AWS A2.4 no desenho): escolha a aresta da vista onde vai a seta, o tipo
  (filete, V, meio-V, topo reto, U, J, cordão, tampão), o lado (da seta, oposto ou ambos), a garganta "a" e o
  comprimento, solda em todo o contorno e solda de campo. O Usinix cria a linha de chamada e o símbolo.
- Rugosidade (ISO 1302, a ABNT NBR 8404 é a correspondente antiga): processo (qualquer, com remoção de
  material, sem remoção), Ra, método de fabricação, direção das estrias e "todas as superfícies".

Os textos de norma ficam como referência no painel; conferir a edição vigente para documento com ART.
"""

import os

import FreeCAD

import PrumoUtil

DIR_SOLDA = os.path.join(PrumoUtil.RES_DIR, "solda")

# tipo: (rótulo, arquivo base, dica)
SOLDAS = [
    ("filete", "Filete", "Solda de canto (a mais comum em estrutura)"),
    ("v", "V", "Topo com chanfro em V"),
    ("meio_v", "Meio-V (bisel)", "Topo com chanfro numa peça só"),
    ("topo_reto", "Topo reto (I)", "Topo sem chanfro, chapa fina"),
    ("u", "U", "Topo com chanfro em U (chapa grossa)"),
    ("j", "J", "Topo com chanfro em J"),
    ("cordao", "Cordão (de raiz / reforço)", "Cordão do lado oposto ou de selagem"),
    ("tampao", "Tampão (bujão)", "Solda em furo ou rasgo"),
]
LADOS = [("seta", "Lado da seta"), ("oposto", "Lado oposto"), ("ambos", "Dos dois lados")]

# Ra preferenciais (µm, ISO 1302) e a classe N correspondente (NBR 8404)
RA = [("0,025", "N1"), ("0,05", "N2"), ("0,1", "N3"), ("0,2", "N4"), ("0,4", "N5"), ("0,8", "N6"), ("1,6", "N7"),
      ("3,2", "N8"), ("6,3", "N9"), ("12,5", "N10"), ("25", "N11"), ("50", "N12")]
PROCESSOS = [("qualquer", "Qualquer processo"), ("remover", "Com remoção de material (usinado)"),
             ("sem", "Sem remoção de material (bruto, laminado)")]
ESCALA_RUGOSIDADE = 3.0
PONTA_RUGOSIDADE = (-17.3, -8.9)      # (x, y) da ponta em relação ao centro, na escala acima (medido na tela)
ESTRIAS = [("", "Sem indicação"), ("=", "= paralelas à vista"), ("⊥", "⊥ perpendiculares"), ("X", "X cruzadas"),
           ("M", "M em várias direções"), ("C", "C circulares"), ("R", "R radiais")]


def arquivo_solda(tipo, acima=True):
    return os.path.join(DIR_SOLDA, "%s_%s.svg" % (tipo, "acima" if acima else "abaixo"))


def pagina_de(vista):
    try:
        return vista.findParentPage()
    except Exception:
        for o in vista.InList:
            if o.isDerivedFrom("TechDraw::DrawPage"):
                return o
            for p in o.InList:
                if p.isDerivedFrom("TechDraw::DrawPage"):
                    return p
    return None


def ponto_da_aresta(vista, aresta):
    """Ponto médio da aresta da vista, em mm de papel a partir do centro da vista (Y para cima)."""
    e = vista.getEdgeBySelection(aresta)
    p = e.valueAt((e.FirstParameter + e.LastParameter) / 2.0)
    esc = float(vista.getScale())
    return FreeCAD.Vector(p.x * esc, p.y * esc, 0)


def criar_solda(vista, ponto, tipo="filete", lado="seta", garganta="", comprimento="", contorno=False,
                campo=False, cauda=""):
    """Linha de chamada com o símbolo de solda. `ponto`: onde a seta toca (mm de papel, do centro da vista).
    Devolve (símbolo, linha de chamada)."""
    doc = vista.Document
    page = pagina_de(vista)
    lider = doc.addObject("TechDraw::DrawLeaderLine", "LinhaSolda")
    lider.Label = "Linha de chamada da solda"
    lider.LeaderParent = vista
    # o TechDraw guarda a ponta sem a escala da vista (e multiplica por ela ao desenhar); `ponto` vem em mm de
    # papel: dividir, senão numa vista 2:1 a seta cai no dobro da distância, fora da peça
    try:
        esc = float(vista.getScale()) or 1.0
    except Exception:
        esc = 1.0
    lider.X, lider.Y = ponto.x / esc, ponto.y / esc
    # seta subindo em 45° e a linha de referência para a direita
    # seta saindo para fora da peça (para o lado em que a aresta está) e subindo; linha de referência
    # horizontal. Os pontos vão com Y para baixo, como o TechDraw guarda.
    sx = lado_com_espaco(vista, ponto, page)
    lider.WayPoints = [FreeCAD.Vector(0, 0, 0), FreeCAD.Vector(sx * 15, -15, 0), FreeCAD.Vector(sx * 50, -15, 0)]
    lider.StartSymbol = 0            # seta cheia na ponta
    lider.EndSymbol = 7              # sem símbolo no fim
    destravar(lider)
    if page is not None:
        page.addView(lider)
    s = doc.addObject("TechDraw::DrawWeldSymbol", "Solda")
    s.Label = "Solda (%s)" % dict((k, r) for k, r, _d in SOLDAS).get(tipo, tipo)
    s.Leader = lider
    s.AllAround = bool(contorno)
    s.FieldWeld = bool(campo)
    s.TailText = cauda or ""
    if page is not None:
        page.addView(s)
    doc.recompute()
    # o símbolo nasce com as duas "telhas" (lado da seta, linha 0; lado oposto, linha -1) em branco
    linhas = {"seta": [0], "oposto": [-1], "ambos": [0, -1]}[lado]
    telhas = {t.TileRow: t for t in doc.Objects
              if t.TypeId == "TechDraw::DrawTileWeld" and t.TileParent is s}
    for row in (0, -1):
        t = telhas.get(row)
        if t is None:
            t = doc.addObject("TechDraw::DrawTileWeld", "TileSolda")
            t.TileParent = s
            t.TileRow = row
            t.TileColumn = 0
        if row in linhas:
            t.SymbolFile = arquivo_solda(tipo, acima=(row == 0))
            t.LeftText = garganta or ""
            t.RightText = comprimento or ""
    doc.recompute()
    return s, lider


def destravar(lider):
    """Linha de chamada sem cadeado: o TechDraw cria a linha travada (e mostra o cadeado ao passar o mouse);
    no Usinix ela se arrasta pelo símbolo ou pela linha, com a ponta da seta parada na aresta."""
    try:
        if lider.LockPosition:
            lider.LockPosition = False
    except Exception:
        pass


def lado_com_espaco(vista, ponto, page=None, folga=55.0, margem=25.0):
    """+1 (direita) ou −1 (esquerda): para fora da peça, mas para dentro se do lado de fora sair da folha."""
    sx = -1.0 if ponto.x < 0 else 1.0
    try:
        page = page or pagina_de(vista)
        largura = float(page.Template.Width) if page is not None and page.Template is not None else 0.0
        x = _x_na_folha(vista) + ponto.x
        if largura > 0:
            if sx < 0 and x - folga < margem:
                sx = 1.0
            elif sx > 0 and x + folga > largura - margem:
                sx = -1.0
    except Exception:
        pass
    return sx


def _x_na_folha(vista):
    """X do centro da vista na folha (a vista de um grupo de projeção guarda X relativo ao grupo)."""
    def num(v):
        return float(v.Value if hasattr(v, "Value") else v)
    x = num(vista.X)
    for o in vista.InList:
        if o.isDerivedFrom("TechDraw::DrawProjGroup"):
            x += num(o.X)
            break
    return x


def pontos_arrastados(pontos, dx, dy):
    """Pontos da linha de chamada depois de arrastar o símbolo (dx, dy em mm, Y para baixo como o TechDraw
    guarda): a ponta (1º ponto) fica onde está, o resto anda junto. Com 3 pontos (seta, cotovelo, fim), se o
    cotovelo passar para o outro lado da ponta, a linha de referência vira para continuar saindo para fora."""
    pts = [FreeCAD.Vector(p) for p in pontos]
    if len(pts) < 2:
        return pts
    d = FreeCAD.Vector(dx, dy, 0)
    novos = [pts[0]] + [p + d for p in pts[1:]]
    if len(novos) == 3:
        cot, fim = novos[1], novos[2]
        ref = fim.x - cot.x
        if abs(cot.x) > 1e-6 and ref * cot.x < 0:
            novos[2] = FreeCAD.Vector(cot.x - ref, fim.y, fim.z)
    return novos


def svg_rugosidade(ra="3,2", processo="remover", metodo="", estrias="", todas=False, n_classe=False):
    """SVG do símbolo de rugosidade (como o do TechDraw, com os textos em português)."""
    el = ["<?xml version='1.0'?>", "<svg xmlns='http://www.w3.org/2000/svg' width='150' height='64'>"]

    def linha(x1, y1, x2, y2):
        el.append("<path stroke='#000' stroke-width='1' fill='none' d='M%g,%g L%g,%g'/>" % (x1, y1, x2, y2))

    def circ(cx, cy, r):
        el.append("<circle cx='%g' cy='%g' r='%g' fill='none' stroke='#000' stroke-width='1'/>" % (cx, cy, r))

    def texto(x, y, t):
        t = (t or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        el.append("<text x='%g' y='%g' style='font-size:18px;font-family:sans-serif'>%s</text>" % (x, y, t))

    linha(0, 44, 12, 64)
    linha(12, 64, 42, 14)
    if processo == "sem":
        circ(12, 46, 9)
    elif processo == "remover":
        linha(0, 44, 24, 44)
    mover = 0
    if todas:
        circ(42, 14, 6)
        mover = 5
    valor = ra
    if n_classe:
        valor = dict(RA).get(ra, ra)
    else:
        valor = "Ra " + ra
    texto(42 + mover, 11, metodo)
    texto(42 + mover, 30, valor)
    largura = max(len(metodo or ""), len(valor)) * 9.25 + mover
    linha(42, 14, 42 + largura, 14)
    if estrias:
        texto(20, 60, estrias)
    el.append("</svg>")
    return "\n".join(el)


def criar_rugosidade(vista, ponto, ra="3,2", processo="remover", metodo="", estrias="", todas=False,
                     angulo=0.0, n_classe=False):
    doc = vista.Document
    page = pagina_de(vista)
    s = doc.addObject("TechDraw::DrawViewSymbol", "Rugosidade")
    s.Label = "Rugosidade Ra %s" % ra
    s.Symbol = svg_rugosidade(ra, processo, metodo, estrias, todas, n_classe)
    s.Rotation = float(angulo)
    import math as _m
    try:
        s.Owner = vista
    except Exception:
        pass
    s.ScaleType = "Custom"
    s.Scale = ESCALA_RUGOSIDADE      # ~12 mm de altura na folha
    # com dono (a vista), X e Y contam a partir do centro dela. A ponta do "V" encosta na aresta pelo lado de
    # fora da peça: em cima, em pé; embaixo, de cabeça para baixo; nos lados, deitado.
    # (a norma pede leitura de baixo ou da direita: embaixo e à direita, o símbolo vai em pé numa linha de
    # chamada, sem ficar de cabeça para baixo)
    alvo = ponto
    if not angulo:
        if abs(ponto.y) >= abs(ponto.x) and ponto.y >= 0:
            angulo = 0.0                                  # em cima: em pé, encostado
        elif abs(ponto.x) > abs(ponto.y) and ponto.x < 0:
            angulo = 90.0                                 # à esquerda: deitado, lê-se da direita
        else:
            angulo = 0.0                                  # embaixo ou à direita: linha de chamada
            baixo = abs(ponto.y) >= abs(ponto.x)
            lider = doc.addObject("TechDraw::DrawLeaderLine", "LinhaRugosidade")
            lider.Label = "Linha de chamada da rugosidade"
            lider.LeaderParent = vista
            lider.X, lider.Y = ponto.x, ponto.y
            dy = 20.0 if baixo else -10.0                 # pontos com Y para baixo
            lider.WayPoints = [FreeCAD.Vector(0, 0, 0), FreeCAD.Vector(10, dy, 0), FreeCAD.Vector(28, dy, 0)]
            lider.StartSymbol = 0
            lider.EndSymbol = 7
            if page is not None:
                page.addView(lider)
            alvo = FreeCAD.Vector(ponto.x + 20.0, ponto.y - dy, 0)
        s.Rotation = angulo
    ponto = alvo
    a = _m.radians(angulo)
    dx, dy = PONTA_RUGOSIDADE         # do centro do símbolo até a ponta, em mm, com o símbolo em pé
    s.X = ponto.x - (dx * _m.cos(a) - dy * _m.sin(a))
    s.Y = ponto.y - (dx * _m.sin(a) + dy * _m.cos(a))
    if page is not None:
        page.addView(s)
    try:
        s.ViewObject.StackOrder = 2
    except Exception:
        pass
    doc.recompute()
    return s


# ======================================================================== interface
try:
    import FreeCADGui
    from PySide import QtWidgets
    import PrumoPainel as P
except ImportError:  # pragma: no cover
    FreeCADGui = P = None


def _vista_de(obj):
    return obj.isDerivedFrom("TechDraw::DrawViewPart")


def _filtro_aresta(obj, subs):
    if not _vista_de(obj):
        return []
    res = [("%s (%s)" % (s.replace("Edge", "aresta "), obj.Label), (obj, s)) for s in subs if s.startswith("Edge")]
    return res or [("%s (centro)" % obj.Label, (obj, ""))]


def _onde(valor):
    vista, aresta = valor
    if aresta:
        try:
            return vista, ponto_da_aresta(vista, aresta)
        except Exception:
            pass
    return vista, FreeCAD.Vector(0, 0, 0)


if P is not None:
    class PainelSolda(P.PainelTarefa):
        titulo = "Solda"
        ajuda = ("Clique na aresta da vista onde vai a seta e escolha a solda. O Usinix cria a linha de chamada e "
                 "o símbolo (ISO 2553).")

        def montar(self):
            f = self.form
            s0 = f.secao("Onde", "selecao")
            self.onde = f.caixa(s0, "Aresta da vista (ponta da seta)", _filtro_aresta, minimo=1, maximo=1)
            s1 = f.secao("Solda", "solda")
            self.tipo = P.Opcoes([(k, r, arquivo_solda(k, True), d) for k, r, d in SOLDAS], "filete", colunas=2)
            s1.widget(self.tipo)
            self.lado = P.Opcoes([(k, r, "lado", r) for k, r in LADOS], "seta", colunas=3)
            s1.widget(self.lado)
            s2 = f.secao("Medidas", "espessura")
            self.garganta = s2.linha("espessura", QtWidgets.QLineEdit("a5"), "Garganta (ex.: a5) ou perna (z7) "
                                     "à esquerda do símbolo.", "Garganta / perna")
            self.comp = s2.linha("comprimento", QtWidgets.QLineEdit(""), "Comprimento ou intermitente (ex.: "
                                 "4×50 (100)) à direita do símbolo. Vazio = em todo o comprimento.", "Comprimento")
            self.contorno = s2.linha("posicao", P.marcar("Em todo o contorno (círculo na quebra)"), "")
            self.campo = s2.linha("posicao", P.marcar("Solda de campo (bandeira)"), "")
            self.cauda = s2.linha("processo", QtWidgets.QLineEdit(""), "Processo, eletrodo ou norma na cauda "
                                  "(ex.: 135, E7018).", "Cauda")

        def pendencia(self):
            if not self.onde.valores():
                return "Clique na aresta da vista onde vai a seta."
            return None

        def pronto_texto(self):
            return "OK cria a linha de chamada e o símbolo de solda."

        def executar(self):
            vista, p = _onde(self.onde.valores()[0])
            s, _l = criar_solda(vista, p, self.tipo.valor(), self.lado.valor(), self.garganta.text().strip(),
                                self.comp.text().strip(), self.contorno.isChecked(), self.campo.isChecked(),
                                self.cauda.text().strip())
            return [s]

    class PainelRugosidade(P.PainelTarefa):
        titulo = "Rugosidade"
        ajuda = "Clique na aresta (ou na vista) onde vai o símbolo e escolha o acabamento (ISO 1302)."

        def montar(self):
            f = self.form
            s0 = f.secao("Onde", "selecao")
            self.onde = f.caixa(s0, "Aresta ou vista", _filtro_aresta, minimo=1, maximo=1)
            s1 = f.secao("Acabamento", "material")
            self.processo = P.Opcoes([(k, r, os.path.join(DIR_SOLDA, "rug_%s.svg" % k), r) for k, r in PROCESSOS],
                                     "remover", colunas=1)
            s1.widget(self.processo)
            self.ra = QtWidgets.QComboBox()
            for v, n in RA:
                self.ra.addItem("Ra %s µm (%s)" % (v, n), v)
            self.ra.setCurrentIndex([v for v, _n in RA].index("3,2"))
            s1.linha("quantidade", self.ra, "Rugosidade média Ra em µm; entre parênteses, a classe N da NBR 8404.",
                     "Ra")
            self.n_classe = s1.linha("tipo", P.marcar("Escrever a classe N (N8) no lugar do Ra"), "")
            self.metodo = s1.linha("texto", QtWidgets.QLineEdit(""), "Ex.: torneado, retificado, fresado.",
                                   "Método de fabricação")
            self.estrias = QtWidgets.QComboBox()
            for k, r in ESTRIAS:
                self.estrias.addItem(r, k)
            s1.linha("posicao", self.estrias, "Direção das marcas de usinagem.", "Estrias")
            self.todas = s1.linha("posicao", P.marcar("Todas as superfícies (círculo no símbolo)"), "")
            self.angulo = s1.linha("angulo", P.numero(0.0, -180.0, 180.0, "°", 0), "Gira o símbolo.", "Ângulo")

        def pendencia(self):
            if not self.onde.valores():
                return "Clique na aresta ou na vista onde vai o símbolo."
            return None

        def pronto_texto(self):
            return "OK põe o símbolo de rugosidade na folha."

        def executar(self):
            vista, p = _onde(self.onde.valores()[0])
            return [criar_rugosidade(vista, p, self.ra.currentData(), self.processo.valor(),
                                     self.metodo.text().strip(), self.estrias.currentData(), self.todas.isChecked(),
                                     self.angulo.value(), self.n_classe.isChecked())]

    class _Cmd:
        painel = None
        recursos = {}

        def GetResources(self):
            return dict(self.recursos)

        def IsActive(self):
            doc = FreeCAD.ActiveDocument
            return doc is not None and any(o.isDerivedFrom("TechDraw::DrawPage") for o in doc.Objects)

        def Activated(self):
            self.painel().mostrar()

    class CmdSolda(_Cmd):
        painel = PainelSolda
        recursos = {"Pixmap": os.path.join(DIR_SOLDA, "filete_acima.svg"), "MenuText": "Solda",
                    "ToolTip": "Símbolo de solda (ISO 2553) em português: tipo, lado, garganta, comprimento, "
                               "todo o contorno e solda de campo."}

    class CmdRugosidade(_Cmd):
        painel = PainelRugosidade
        recursos = {"Pixmap": os.path.join(DIR_SOLDA, "rug_remover.svg"), "MenuText": "Rugosidade",
                    "ToolTip": "Símbolo de rugosidade (ISO 1302) em português: processo, Ra, método e estrias."}


def registrar_comandos():
    if FreeCADGui is not None and P is not None:
        FreeCADGui.addCommand("Prumo_Solda2D", CmdSolda())
        FreeCADGui.addCommand("Prumo_Rugosidade", CmdRugosidade())
        instalar_arrasto()


# ======================================================================== arrastar a chamada na folha
def _lider_do_objeto(obj):
    """A linha de chamada que um clique no símbolo de solda (ou na própria linha) deve mover."""
    if obj is None:
        return None
    if obj.TypeId == "TechDraw::DrawWeldSymbol":
        return getattr(obj, "Leader", None)
    if obj.TypeId == "TechDraw::DrawTileWeld":
        return _lider_do_objeto(getattr(obj, "TileParent", None))
    if obj.TypeId == "TechDraw::DrawLeaderLine":
        return obj
    return None


def _rez():
    try:
        return FreeCAD.ParamGet("User parameter:BaseApp/Preferences/Mod/TechDraw/Rez").GetFloat("Resolution", 10.0) \
            or 10.0
    except Exception:
        return 10.0


def delta_em_pontos(lider, dx_cena, dy_cena):
    """Deslocamento na cena (unidades do TechDraw, Y para baixo) → nos pontos da linha (mm, Y para baixo)."""
    import math
    dx, dy = dx_cena / _rez(), dy_cena / _rez()
    try:
        pai = lider.LeaderParent
        if getattr(lider, "Scalable", False) and pai is not None:
            esc = float(pai.getScale())
            dx, dy = dx / esc, dy / esc
        rot = float(getattr(pai, "Rotation", 0.0) or 0.0) if pai is not None else 0.0
        if rot and getattr(lider, "RotatesWithParent", True):
            a = -math.radians(rot)
            ux, uy = dx, -dy                         # Y para cima, gira, volta
            rx, ry = ux * math.cos(a) - uy * math.sin(a), ux * math.sin(a) + uy * math.cos(a)
            dx, dy = rx, -ry
    except Exception:
        pass
    return dx, dy


if FreeCADGui is not None:
    from PySide import QtCore

    class ArrastoDeChamada(QtCore.QObject):
        """Filtro no papel do TechDraw: arrastar o símbolo de solda (ou a linha de chamada) move a linha de
        referência e o símbolo; a ponta da seta fica na aresta. Desfazer volta (uma transação por arrasto)."""

        LIMIAR = 4    # px antes de considerar arrasto (clique simples continua selecionando)

        def __init__(self, parent=None):
            super().__init__(parent)
            self._ini = None

        def _objeto(self, view, item):
            doc = getattr(FreeCADGui.ActiveDocument, "Document", None)
            while item is not None:
                if item.data(0) == "QGIV" and doc is not None:
                    return doc.getObject(str(item.data(1)))
                item = item.parentItem()
            return None

        @staticmethod
        def _pos(ev):
            try:
                return ev.position().toPoint()
            except AttributeError:
                return ev.pos()

        def eventFilter(self, vp, ev):
            try:
                return self._filtrar(vp, ev)
            except Exception as exc:
                FreeCAD.Console.PrintLog("Usinix: arrastar chamada: %s\n" % exc)
                self._ini = None
                return False

        def _filtrar(self, vp, ev):
            t = ev.type()
            if t == QtCore.QEvent.MouseButtonPress:
                self._ini = None
                if ev.button() != QtCore.Qt.LeftButton:
                    return False
                view = vp.parent()
                pos = self._pos(ev)
                lider = _lider_do_objeto(self._objeto(view, view.itemAt(pos)))
                if lider is None:
                    return False
                vo = getattr(lider, "ViewObject", None)
                if vo is not None and FreeCADGui.ActiveDocument.getInEdit() is not None:
                    return False                      # editando os pontos (duplo clique): deixa o TechDraw
                self._ini = {"view": view, "pos": pos, "cena": view.mapToScene(pos), "lider": lider,
                             "pontos": [FreeCAD.Vector(p) for p in lider.WayPoints], "moveu": False, "t": 0.0}
                return False                          # o clique segue: seleciona como sempre
            if self._ini is None:
                return False
            if t == QtCore.QEvent.MouseMove:
                if not (ev.buttons() & QtCore.Qt.LeftButton):
                    self._ini = None
                    return False
                pos = self._pos(ev)
                if not self._ini["moveu"]:
                    if (pos - self._ini["pos"]).manhattanLength() < self.LIMIAR:
                        return True
                    self._ini["moveu"] = True
                    doc = self._ini["lider"].Document
                    doc.openTransaction("Mover chamada")
                    destravar(self._ini["lider"])
                import time
                agora = time.time()
                if agora - self._ini["t"] > 0.04:
                    self._ini["t"] = agora
                    self._aplicar(pos, final=False)
                return True
            if t == QtCore.QEvent.MouseButtonRelease and ev.button() == QtCore.Qt.LeftButton:
                ini = self._ini
                if ini["moveu"]:
                    self._aplicar(self._pos(ev), final=True)
                    ini["lider"].Document.commitTransaction()
                self._ini = None
                return False                          # o Qt solta o item normalmente
            return False

        def _aplicar(self, pos, final):
            ini = self._ini
            d = ini["view"].mapToScene(pos) - ini["cena"]
            dx, dy = delta_em_pontos(ini["lider"], d.x(), d.y())
            lider = ini["lider"]
            lider.WayPoints = pontos_arrastados(ini["pontos"], dx, dy)
            lider.recompute()
            for o in lider.InList:
                if o.TypeId == "TechDraw::DrawWeldSymbol":
                    o.recompute()
            if final:
                lider.Document.recompute()

    _FILTRO = []

    def instalar_nas_folhas(*_a):
        """Põe o filtro de arrasto em todas as folhas abertas (uma vez por folha)."""
        try:
            mw = FreeCADGui.getMainWindow()
        except Exception:
            return
        if not _FILTRO:
            _FILTRO.append(ArrastoDeChamada(mw))
        from PySide import QtWidgets as _W
        for v in mw.findChildren(_W.QGraphicsView):
            if v.metaObject().className() != "TechDrawGui::QGVPage" or v.property("usinix_arrasto"):
                continue
            v.viewport().installEventFilter(_FILTRO[0])
            v.setProperty("usinix_arrasto", True)

    def instalar_arrasto():
        try:
            from PySide import QtWidgets as _W
            area = FreeCADGui.getMainWindow().findChild(_W.QMdiArea)
            if area is not None and not area.property("usinix_arrasto"):
                area.subWindowActivated.connect(lambda *_a: QtCore.QTimer.singleShot(0, instalar_nas_folhas))
                area.setProperty("usinix_arrasto", True)
        except Exception as exc:
            FreeCAD.Console.PrintLog("Usinix: arrasto de chamada: %s\n" % exc)
        instalar_nas_folhas()
