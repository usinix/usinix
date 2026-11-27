# SPDX-License-Identifier: LGPL-2.1-or-later
"""Usinix: interface da Mangueira — painel (pontas, catálogo, terminais, pontos arrastáveis), vista e comando."""

import FreeCAD
import FreeCADGui
from PySide import QtCore, QtWidgets

import UsinixMangueira as M
import UsinixPainel as P

V = FreeCAD.Vector

COR_MANGUEIRA = {"hidraulica": (0.10, 0.10, 0.11), "pneumatica": (0.12, 0.36, 0.78)}
COR_TERMINAL = (0.74, 0.76, 0.79)


def filtro_ponta(obj, subs):
    """Pontas da mangueira: qualquer aresta redonda / face / vértice, menos da própria mangueira."""
    if M.e_mangueira(obj):
        return []
    return M.filtro_ponta(obj, subs)


def trechos_apertados(pts):
    """Divide os pontos apertados (amostras seguidas da curva) em trechos contínuos, cada um com pelo menos dois
    pontos (um ponto sozinho vira um traço curto em volta dele)."""
    if not pts:
        return []
    passos = [(pts[k + 1] - pts[k]).Length for k in range(len(pts) - 1)]
    lim = 3.0 * (sorted(passos)[len(passos) // 2] if passos else 1.0)
    trechos, atual = [], [pts[0]]
    for k in range(1, len(pts)):
        if (pts[k] - pts[k - 1]).Length > lim:
            trechos.append(atual)
            atual = []
        atual.append(pts[k])
    trechos.append(atual)
    res = []
    for t in trechos:
        if len(t) == 1:
            t = [t[0] - V(1, 0, 0), t[0] + V(1, 0, 0)]
        res.append(t)
    return res


def avisar_raio(obj):
    """Depois do OK: o aviso de raio fica também na barra de status e no relatório, fora do painel."""
    if obj is None or not getattr(obj, "Aviso", ""):
        return ""
    txt = "%s: %s" % (obj.Label, obj.Aviso)
    FreeCAD.Console.PrintWarning(txt + "\n")
    try:
        FreeCADGui.getMainWindow().statusBar().showMessage(txt, 15000)
    except Exception:
        pass
    return txt


# ============================================================================ vista
class VPMangueira:
    def __init__(self, vobj):
        vobj.Proxy = self

    def attach(self, vobj):
        self.Object = vobj.Object
        self._no = None
        try:
            # trecho abaixo do raio mínimo: faixa vermelha grossa ao longo do eixo, desenhada por cima da
            # mangueira (os pontos ficam no centro dela, escondidos se fossem desenhados normalmente)
            from pivy import coin
            self._no = coin.SoAnnotation()
            mat = coin.SoMaterial()
            mat.diffuseColor = (0.95, 0.12, 0.10)
            mat.emissiveColor = (0.95, 0.12, 0.10)
            est = coin.SoDrawStyle()
            est.lineWidth = 6
            est.pointSize = 9
            luz = coin.SoLightModel()
            luz.model = coin.SoLightModel.BASE_COLOR
            self._coords = coin.SoCoordinate3()
            self._linhas = coin.SoLineSet()
            self._linhas.numVertices.setNum(0)
            for n in (luz, mat, est, self._coords, self._linhas):
                self._no.addChild(n)
            vobj.RootNode.addChild(self._no)
            self._marcar_apertados(vobj.Object)
        except Exception:
            self._no = None

    def getIcon(self):
        import UsinixUtil
        return UsinixUtil.icone("mangueira.svg")

    def updateData(self, obj, prop):
        if prop == "Shape":
            QtCore.QTimer.singleShot(0, lambda: self.pintar(obj))
        elif prop == "Apertados":
            self._marcar_apertados(obj)

    def onChanged(self, vobj, prop):
        pass

    def pintar(self, obj=None):
        obj = obj or getattr(self, "Object", None)
        try:
            n = len(obj.Shape.Faces)
            nm = int(obj.FacesMangueira)
            if not n or nm > n:
                return
            cor = COR_MANGUEIRA.get(M.tipo(obj.Tipo)["familia"], COR_MANGUEIRA["hidraulica"])
            mats = []
            for i in range(n):
                m = FreeCAD.Material()
                c = cor if i < nm else COR_TERMINAL
                m.DiffuseColor = c
                m.AmbientColor = tuple(x * 0.35 for x in c)
                m.Shininess = 0.15 if i < nm else 0.55
                m.SpecularColor = (0.2, 0.2, 0.2) if i < nm else (0.6, 0.6, 0.6)
                mats.append(m)
            obj.ViewObject.ShapeAppearance = mats
        except Exception:
            pass

    def _marcar_apertados(self, obj):
        if self._no is None:
            return
        try:
            trechos = trechos_apertados(list(obj.Apertados))
            pts = [(p.x, p.y, p.z) for t in trechos for p in t]
            self._coords.point.setNum(0)
            self._linhas.numVertices.setNum(0)
            if pts:
                self._coords.point.setValues(0, len(pts), pts)
                self._linhas.numVertices.setValues(0, len(trechos), [len(t) for t in trechos])
        except Exception:
            pass

    def doubleClicked(self, vobj):
        PainelMangueira().editar_objeto(vobj.Object).mostrar()
        return True

    def setupContextMenu(self, vobj, menu):
        act = menu.addAction("Editar mangueira")
        act.triggered.connect(lambda: self.doubleClicked(vobj))

    def dumps(self):
        return None

    def loads(self, state):
        return None


# ============================================================================ painel
def _combo(itens, atual=None):
    w = QtWidgets.QComboBox()
    for t in itens:
        w.addItem(t, t)
    if atual is not None and w.findData(atual) >= 0:
        w.setCurrentIndex(w.findData(atual))
    return w


def _numero(v, minimo, maximo, sufixo, casas=1):
    w = QtWidgets.QDoubleSpinBox()
    w.setRange(minimo, maximo)
    w.setDecimals(casas)
    w.setSuffix(sufixo)
    w.setValue(v)
    try:
        w.setLocale(P.LOCALE)
    except Exception:
        pass
    return w


class _Lado:
    """Campos do terminal de um lado (A ou B)."""

    def __init__(self, painel, secao, lado):
        self.lado = lado
        self.rosca = QtWidgets.QComboBox()
        secao.linha("parafuso", self.rosca, "Sistema e rosca do terminal; a lista segue o tamanho da mangueira.", "Rosca")
        self.ligacao = _combo(M.LIGACOES_HIDRAULICA)
        self.lb_ligacao = secao.linha("ponta", self.ligacao, "Fêmea giratória (porca solta) ou macho.", "Ligação")
        self.forma = _combo(M.FORMAS)
        secao.linha("angulo", self.forma, "Terminal reto, curvo a 45° ou a 90°.", "Forma")
        self.auto = secao.linha("angulo", P.marcar("Virar para a outra ponta (giro automático)", True),
                                "O terminal curvo aponta sozinho para a outra ponta ou para o ponto de passagem mais perto.")
        self.giro = _numero(0.0, -360.0, 360.0, "°", 0)
        self.giro.setSingleStep(15.0)
        secao.linha("angulo", self.giro, "Gira o terminal curvo em torno do eixo da ponta.", "Giro")
        self.inverter = secao.linha("posicao", P.marcar("Inverter a saída desta ponta", False),
                                    "A mangueira sai para o outro lado da face escolhida.")
        self._secao = secao
        self.forma.currentIndexChanged.connect(self._forma)
        self.auto.toggled.connect(self._forma)
        self._forma()

    def _forma(self, *_a):
        curvo = self.forma.currentData() != "Reto"
        self.auto.setEnabled(curvo)
        self.giro.setEnabled(curvo and not self.auto.isChecked())

    def preencher_roscas(self, nome_tipo, tamanho):
        atual = self.rosca.currentData()
        self.rosca.blockSignals(True)
        self.rosca.clear()
        for sistema, rosca in M.roscas_para(nome_tipo, tamanho):
            txt = "%s | %s" % (sistema, rosca)
            self.rosca.addItem(txt, txt)
        i = self.rosca.findData(atual) if atual else -1
        if i < 0 and atual:
            sist = atual.split("|")[0].strip()
            i = next((k for k in range(self.rosca.count()) if self.rosca.itemData(k).startswith(sist + " |")), -1)
        self.rosca.setCurrentIndex(max(i, 0))
        self.rosca.blockSignals(False)
        pneu = M.tipo(nome_tipo)["familia"] == "pneumatica"
        self._secao.mostrar_linha(self.ligacao, not pneu)

    def termo(self):
        txt = self.rosca.currentData() or ""
        sistema, rosca = [x.strip() for x in txt.split("|", 1)] if "|" in txt else ("JIC 37°", "3/4-16 UNF")
        giro = None if self.auto.isChecked() else self.giro.value()
        return (sistema, rosca, self.ligacao.currentData(), self.forma.currentData(), giro)

    def carregar(self, obj):
        L = self.lado
        i = self.rosca.findData(getattr(obj, "Rosca" + L))
        if i >= 0:
            self.rosca.setCurrentIndex(i)
        for w, prop in ((self.ligacao, "Ligacao"), (self.forma, "Forma")):
            j = w.findData(getattr(obj, prop + L))
            if j >= 0:
                w.setCurrentIndex(j)
        self.giro.setValue(float(getattr(obj, "Giro" + L)))
        self.auto.setChecked(bool(getattr(obj, "GiroAuto" + L, False)))
        self.inverter.setChecked(bool(getattr(obj, "Inverter" + L)))

    def props(self):
        L = self.lado
        s, r, lig, forma, giro = self.termo()
        return {"Rosca" + L: "%s | %s" % (s, r), "Ligacao" + L: lig, "Forma" + L: forma,
                "GiroAuto" + L: giro is None, "Giro" + L: self.giro.value(),
                "Inverter" + L: self.inverter.isChecked()}


class PainelMangueira(P.PainelTarefa):
    titulo = "Mangueira"
    ajuda = ("Clique na ponta A e na ponta B: boca de tubo, furo ou face da máquina. A mangueira sai no eixo de cada "
             "ponta, com o terminal escolhido. Acrescente pontos e arraste-os na vista 3D para levar a mangueira por "
             "onde ela deve passar.")
    previa = True

    def montar(self):
        self.pontos = []
        self._arrastadores = []
        self._raiz = None
        self._pegando = None
        self._cb_evento = None
        f = self.form
        s0 = f.secao("Pontas", "selecao")
        self.ponta_a = f.caixa(s0, "Ponta A", filtro_ponta, minimo=1, maximo=1,
                               dica="Aresta redonda (boca do tubo, furo) ou face plana da máquina.")
        self.ponta_b = f.caixa(s0, "Ponta B", filtro_ponta, minimo=1, maximo=1,
                               dica="Aresta redonda (boca do tubo, furo) ou face plana da máquina.")
        self.ponta_a.mudou.connect(self._avancar)

        s1 = f.secao("Mangueira", "tipo")
        self.tipo = _combo(list(M.TIPOS), M.TIPO_PADRAO)
        s1.linha("tipo", self.tipo, "Tipo de mangueira (catálogo).", "Tipo")
        self.tamanho = QtWidgets.QComboBox()
        s1.linha("espessura", self.tamanho, "Tamanho: dash e bitola nominal, ou diâmetro externo do tubo.", "Tamanho")
        self.folga = _numero(0.0, 0.0, 10000.0, " mm", 0)
        s1.linha("folga", self.folga, "Somado ao comprimento de corte (sobra para montagem).", "Folga")

        self.lados = {}
        for L in ("A", "B"):
            sec = f.secao("Terminal " + L, "ponta", aberta=(L == "A"))
            self.lados[L] = _Lado(self, sec, L)

        s3 = f.secao("Pontos de passagem", "posicao")
        self.lb_pontos = QtWidgets.QLabel()
        self.lb_pontos.setWordWrap(True)
        s3.widget(self.lb_pontos)
        barra = QtWidgets.QWidget()
        hl = QtWidgets.QHBoxLayout(barra)
        hl.setContentsMargins(0, 0, 0, 0)
        self.bt_mais = QtWidgets.QPushButton("Adicionar ponto")
        self.bt_menos = QtWidgets.QPushButton("Remover último")
        self.bt_limpar = QtWidgets.QPushButton("Limpar")
        for b in (self.bt_mais, self.bt_menos, self.bt_limpar):
            hl.addWidget(b)
        s3.widget(barra)
        self.bt_mais.clicked.connect(self.adicionar_ponto)
        self.bt_menos.clicked.connect(self.remover_ponto)
        self.bt_limpar.clicked.connect(self.limpar_pontos)

        s4 = f.secao("Resultado", "info")
        self.lb_resultado = QtWidgets.QLabel("—")
        self.lb_resultado.setWordWrap(True)
        self.lb_resultado.setTextInteractionFlags(QtCore.Qt.TextSelectableByMouse)
        s4.widget(self.lb_resultado)

        self.tipo.currentIndexChanged.connect(self._tipo)
        self.tamanho.currentIndexChanged.connect(self._tamanho)
        self._tipo()
        self.lados["A"].forma.setCurrentIndex(0)
        self._texto_pontos()

    # ---- campos
    def _avancar(self):
        if self.ponta_a.valores() and not self.ponta_b.valores():
            self.form.ativar_caixa(self.ponta_b)

    def _tipo(self, *_a):
        nome = self.tipo.currentData()
        atual = self.tamanho.currentData()
        self.tamanho.blockSignals(True)
        self.tamanho.clear()
        for tam in M.tipo(nome)["tamanhos"]:
            self.tamanho.addItem(tam, tam)
        i = self.tamanho.findData(atual)
        if i < 0:
            i = self.tamanho.findData(M.TAMANHO_PADRAO)
        self.tamanho.setCurrentIndex(max(i, 0))
        self.tamanho.blockSignals(False)
        self._tamanho()

    def _tamanho(self, *_a):
        for lado in self.lados.values():
            lado.preencher_roscas(self.tipo.currentData(), self.tamanho.currentData())
        self._campo_mudou()

    def _texto_pontos(self):
        n = len(self.pontos)
        self.lb_pontos.setText(("%d ponto(s) de passagem. Arraste as alças na vista 3D para mudar o caminho." % n)
                               if n else "Sem pontos: a mangueira vai direto de A a B. \"Adicionar ponto\" põe "
                                         "um ponto no meio do maior trecho, para arrastar na vista 3D.")
        self.bt_menos.setEnabled(n > 0)
        self.bt_limpar.setEnabled(n > 0)

    # ---- pontos de passagem
    def _objeto(self):
        if self.editando is not None:
            return self.editando
        doc = self._doc_previa or FreeCAD.ActiveDocument
        for nome in self._previa_nomes:
            o = doc.getObject(nome) if doc else None
            if M.e_mangueira(o):
                return o
        return None

    def _curva(self):
        o = self._objeto()
        c = getattr(getattr(o, "Proxy", None), "curva", None) if o is not None else None
        if c is not None:
            return c
        # sem prévia (ainda): calcula aqui mesmo
        pa, na = self._ponta(self.ponta_a, "A")
        pb, nb = self._ponta(self.ponta_b, "B")
        r = M.montar(pa, na, pb, nb, self.tipo.currentData(), self.tamanho.currentData(),
                     self.lados["A"].termo(), self.lados["B"].termo(), self.pontos, self.folga.value())
        return r["curva"]

    def _ponta(self, caixa, L):
        obj, sub = caixa.valores()[0]
        p, n, _d = M.ponta_de(obj, sub)
        if self.lados[L].inverter.isChecked():
            n = n * -1
        return p, n

    def adicionar_ponto(self):
        if self.pendencia() is not None:
            return
        try:
            self.pontos = M.ponto_novo(self._curva(), self.pontos)
        except Exception as ex:
            self.form.mensagem.mostrar(str(ex), "erro")
            return
        self._pontos_mudaram()

    def remover_ponto(self):
        if self.pontos:
            self.pontos = self.pontos[:-1]
            self._pontos_mudaram()

    def limpar_pontos(self):
        self.pontos = []
        self._pontos_mudaram()

    def _pontos_mudaram(self):
        self._texto_pontos()
        self._montar_arrastadores()
        self._campo_mudou()

    def arrastou(self, i, ponto):
        """Ponto de passagem i levado até ponto (o arraste na vista chama isto; os testes também)."""
        if 0 <= i < len(self.pontos):
            self.pontos[i] = V(ponto)
            self._mover_alca(i)
            self._mudou()

    # ---- alças dos pontos de passagem
    # Sem arrastador do Coin (SoDragPointDragger): ele não respondia ao mouse dentro da vista do FreeCAD e, junto
    # com a prévia recriando a mangueira, chegou a dar "Access violation". As alças são esferas desenhadas por
    # cima de tudo (a mangueira não as esconde) e o arraste é feito aqui, num retorno de eventos da vista:
    # apertar o botão perto de uma alça pega a alça (o clique não chega à seleção), mover leva o ponto no plano
    # da tela que passa por ele, soltar termina.
    RAIO_TELA = 18          # pixels: distância do cursor até o centro da alça para pegar

    def _raio_alca(self):
        try:
            return max(M.dados(self.tipo.currentData(), self.tamanho.currentData())["de"] * 1.2, 8.0)
        except Exception:
            return 10.0

    def _vista(self):
        try:
            return FreeCADGui.ActiveDocument.ActiveView
        except Exception:
            return None

    def _montar_arrastadores(self):
        self._remover_arrastadores()
        if not FreeCAD.GuiUp or not self.pontos:
            return
        v = self._vista()
        try:
            from pivy import coin
            raiz = v.getSceneGraph()
        except Exception:
            return
        r = self._raio_alca()
        grupo = coin.SoAnnotation()          # por cima da mangueira e das peças
        for p in self.pontos:
            sep = coin.SoSeparator()
            tr = coin.SoTranslation()
            tr.translation = (p.x, p.y, p.z)
            mat = coin.SoMaterial()
            mat.diffuseColor = (0.97, 0.75, 0.0)
            mat.emissiveColor = (0.45, 0.33, 0.0)
            esf = coin.SoSphere()
            esf.radius = r
            sep.addChild(tr)
            sep.addChild(mat)
            sep.addChild(esf)
            grupo.addChild(sep)
            self._arrastadores.append((tr, mat))
        raiz.addChild(grupo)
        self._raiz = (raiz, grupo)
        try:
            self._cb_evento = v.addEventCallbackPivy(coin.SoEvent.getClassTypeId(), self._evento)
            self._cb_vista = v
        except Exception:
            self._cb_evento = None

    def _remover_arrastadores(self):
        cb = getattr(self, "_cb_evento", None)
        if cb is not None:
            try:
                from pivy import coin
                self._cb_vista.removeEventCallbackPivy(coin.SoEvent.getClassTypeId(), cb)
            except Exception:
                pass
        self._cb_evento = None
        if self._raiz is not None:
            try:
                raiz, grupo = self._raiz
                raiz.removeChild(grupo)
            except Exception:
                pass
        self._raiz = None
        self._arrastadores = []
        self._pegando = None

    def _mover_alca(self, i):
        if 0 <= i < len(self._arrastadores):
            p = self.pontos[i]
            self._arrastadores[i][0].translation = (p.x, p.y, p.z)

    def _destacar(self, i):
        for k, (_tr, mat) in enumerate(self._arrastadores):
            mat.diffuseColor = (1.0, 0.45, 0.0) if k == i else (0.97, 0.75, 0.0)

    def alca_em(self, pos):
        """Índice da alça sob a posição de tela pos (coordenadas da vista), ou -1."""
        v = self._vista()
        if v is None:
            return -1
        melhor, dist = -1, self.RAIO_TELA
        for i, p in enumerate(self.pontos):
            try:
                q = v.getPointOnViewport(V(p))
            except Exception:
                continue
            d = ((q[0] - pos[0]) ** 2 + (q[1] - pos[1]) ** 2) ** 0.5
            if d <= dist:
                melhor, dist = i, d
        return melhor

    def ponto_na_tela(self, i, pos):
        """Onde o ponto i vai parar com o cursor em pos: no plano da tela que passa pelo ponto."""
        v = self._vista()
        q = v.getPoint(int(pos[0]), int(pos[1]))
        d = V(v.getViewDirection()).normalize()
        return q + d * (V(self.pontos[i]) - q).dot(d)

    def pegar(self, pos):
        i = self.alca_em(pos)
        if i < 0:
            return False
        self._pegando = i
        self._destacar(i)
        return True

    def mover(self, pos):
        if self._pegando is None:
            self._destacar(self.alca_em(pos))
            return False
        self.arrastou(self._pegando, self.ponto_na_tela(self._pegando, pos))
        return True

    def soltar(self, pos):
        if self._pegando is None:
            return False
        i, self._pegando = self._pegando, None
        self.arrastou(i, self.ponto_na_tela(i, pos))
        self._destacar(-1)
        return True

    def _evento(self, no):
        try:
            from pivy import coin
            ev = no.getEvent()
            pos = ev.getPosition().getValue()
            usado = False
            if ev.isOfType(coin.SoMouseButtonEvent.getClassTypeId()) and \
                    ev.getButton() == coin.SoMouseButtonEvent.BUTTON1:
                if ev.getState() == coin.SoButtonEvent.DOWN:
                    usado = self.pegar(pos)
                elif ev.getState() == coin.SoButtonEvent.UP:
                    usado = self.soltar(pos)
            elif ev.isOfType(coin.SoLocation2Event.getClassTypeId()):
                usado = self.mover(pos)
            if usado:
                no.setHandled()
        except Exception as ex:
            self._pegando = None
            FreeCAD.Console.PrintWarning("Mangueira: arraste do ponto interrompido (%s)\n" % ex)

    # ---- resultado
    def _atualizar_previa(self):
        super()._atualizar_previa()
        self._mostrar_resultado()

    def _mostrar_resultado(self):
        o = self._objeto()
        if o is None or self.pendencia() is not None or o.Shape.isNull():
            self.lb_resultado.setText("—")
            return
        import UsinixUtil as U
        dd = M.dados(o.Tipo, o.Tamanho)
        linhas = ["Corte: <b>%s</b> (livre entre capas %s)" % (U.fmt(float(o.Corte), 0, " mm"),
                                                                U.fmt(float(o.Livre), 0, " mm")),
                  "Raio: %s medido · mínimo %s" % (U.fmt(float(o.RaioMedido), 0, " mm"),
                                                  U.fmt(float(o.RaioMinimo), 0, " mm")),
                  "Pressão de trabalho: %s" % U.fmt(dd["pt"], 0, " bar")]
        if o.Aviso:
            linhas.append("<span style='color:#B3261E'><b>%s</b></span>" % o.Aviso)
        self.lb_resultado.setText("<br>".join(linhas))
        if not self._previa_erro and o.Aviso:
            self.form.mensagem.mostrar(o.Aviso, "erro")

    def marcas(self):
        res = []
        for caixa, nome in ((self.ponta_a, "A"), (self.ponta_b, "B")):
            if caixa.valores():
                try:
                    res.append((self._ponta(caixa, nome)[0], nome, False))
                except Exception:
                    pass
        for i, p in enumerate(self.pontos):
            res.append((V(p), str(i + 1), False))
        o = self._objeto()
        if o is not None and list(o.Apertados):
            ap = list(o.Apertados)
            res.append((ap[len(ap) // 2], "raio pequeno", True))
        return res

    # ---- fluxo do painel
    def pendencia(self):
        if not self.ponta_a.valores():
            return "Clique na ponta A: boca do tubo, furo ou face da máquina."
        if not self.ponta_b.valores():
            return "Agora a ponta B."
        if self.ponta_a.valores() == self.ponta_b.valores():
            return "As pontas A e B são a mesma: escolha outra para B."
        return None

    def pronto_texto(self):
        return "OK cria a mangueira com os terminais. Arraste os pontos na vista para mudar o caminho."

    def carregar(self, obj):
        if obj.PontaA and obj.PontaA[1]:
            self.ponta_a.aceitar(obj.PontaA[0], [obj.PontaA[1][0]])
        if obj.PontaB and obj.PontaB[1]:
            self.ponta_b.aceitar(obj.PontaB[0], [obj.PontaB[1][0]])
        i = self.tipo.findData(obj.Tipo)
        if i >= 0:
            self.tipo.setCurrentIndex(i)
        j = self.tamanho.findData(obj.Tamanho)
        if j >= 0:
            self.tamanho.setCurrentIndex(j)
        self.folga.setValue(float(obj.Folga))
        for lado in self.lados.values():
            lado.carregar(obj)
        self.pontos = [V(p) for p in obj.Pontos]
        self._texto_pontos()
        self._montar_arrastadores()

    def props_edicao(self):
        (oa, sa), (ob, sb) = self.ponta_a.valores()[0], self.ponta_b.valores()[0]
        d = {"PontaA": (oa, [sa]), "PontaB": (ob, [sb]), "Tipo": self.tipo.currentData(),
             "Tamanho": self.tamanho.currentData(), "Folga": self.folga.value(), "Pontos": list(self.pontos)}
        for lado in self.lados.values():
            d.update(lado.props())
        return d

    def executar(self):
        obj = M.criar(self.ponta_a.valores()[0], self.ponta_b.valores()[0], self.tipo.currentData(),
                      self.tamanho.currentData(), self.lados["A"].termo(), self.lados["B"].termo(), self.pontos,
                      self.folga.value())
        obj.InverterA = self.lados["A"].inverter.isChecked()
        obj.InverterB = self.lados["B"].inverter.isChecked()
        if obj.InverterA or obj.InverterB:
            obj.recompute()
        return [obj]

    def accept(self):
        self._remover_arrastadores()
        ok = super().accept()
        if ok:
            avisar_raio(self._objeto_final())
        else:
            self._montar_arrastadores()
        return ok

    def _objeto_final(self):
        if self.editando is not None:
            return self.editando
        doc = FreeCAD.ActiveDocument
        objs = [o for o in (doc.Objects if doc else []) if M.e_mangueira(o)]
        return objs[-1] if objs else None

    def reject(self):
        self._remover_arrastadores()
        return super().reject()

    def close(self):
        self._remover_arrastadores()
        super().close()


class CmdMangueira:
    def GetResources(self):
        import UsinixUtil
        return {"Pixmap": UsinixUtil.icone("mangueira.svg"), "MenuText": "Mangueira",
                "ToolTip": "Mangueira flexível entre duas pontas (tubo–tubo, tubo–máquina ou máquina–máquina), com "
                           "terminais retos, 45° ou 90°, pontos de passagem arrastáveis, aviso de raio mínimo e "
                           "comprimento de corte."}

    def IsActive(self):
        return FreeCAD.ActiveDocument is not None

    def Activated(self):
        PainelMangueira().mostrar()


def registrar_comandos():
    FreeCADGui.addCommand("Usinix_Mangueira", CmdMangueira())
