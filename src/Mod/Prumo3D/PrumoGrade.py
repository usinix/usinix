# SPDX-License-Identifier: LGPL-2.1-or-later
# Usinix - grade (tela quadriculada) na vista 3D, ligada e desligada por um botão na barra inferior.
"""Grade da área de trabalho.

Quadriculado no plano XY (o "chão", z = 0), com linhas finas a cada passo e linhas mais fortes a cada 5 passos,
e os eixos X (vermelho) e Y (verde). O passo segue a série 1-2-5 conforme o tamanho do modelo (uma peça de
200 mm ganha grade de 10 mm; um galpão de 30 m, de 2 m), e a grade se refaz quando o documento recalcula.
A grade não é selecionável, não aparece em capturas de seleção e não entra no arquivo: é só da tela.
O botão "Grade" fica na barra de vistas embaixo da vista 3D, ao lado de Aparência (1.14.0; antes ficava na
barra de status); a escolha fica gravada (Preferências › Usinix).

Desde a 1.19.0 o botão tem três estados, um a cada clique:
1. grade no chão (plano XY, em perspectiva, como antes);
2. grade frontal infinita: virada para a tela, ocupa a área de trabalho inteira e acompanha a câmera (zoom, giro e
   deslocamento), atrás do modelo; o quadrado se ajusta ao zoom (série 1-2-5);
3. desligada.
"""

import math

import FreeCAD

try:
    import FreeCADGui
    from PySide import QtCore, QtGui, QtWidgets
except ImportError:     # sem interface
    FreeCADGui = None

PARAM = "User parameter:BaseApp/Preferences/Mod/Prumo3D"
NOME_NO = "PrumoGrade"
SERIE = (1.0, 2.0, 5.0)
NOME_TELA = "PrumoGradeTela"
DESLIGADA, CHAO, TELA = 0, 1, 2
NOMES_MODO = {DESLIGADA: "desligada", CHAO: "no chão (plano XY)", TELA: "frontal, na tela toda"}
_estado = {"botao": None, "timer": None, "obs": None, "passos": {}, "telas": {}}


def ligada():
    return FreeCAD.ParamGet(PARAM).GetBool("Grade", False)


def modo():
    """0 desligada, 1 no chão (perspectiva), 2 frontal infinita."""
    if not ligada():
        return DESLIGADA
    m = FreeCAD.ParamGet(PARAM).GetInt("GradeModo", CHAO)
    return m if m in (CHAO, TELA) else CHAO


def definir_modo(m):
    m = int(m) % 3
    FreeCAD.ParamGet(PARAM).SetBool("Grade", m != DESLIGADA)
    if m != DESLIGADA:
        FreeCAD.ParamGet(PARAM).SetInt("GradeModo", m)
    atualizar()
    return m


def proximo():
    """Um clique no botão: chão → frontal → desligada → chão..."""
    return definir_modo({DESLIGADA: CHAO, CHAO: TELA, TELA: DESLIGADA}[modo()])


def passo_para(tamanho, celulas=20):
    """Passo da série 1-2-5 (mm) que dá cerca de `celulas` quadrados no tamanho do modelo."""
    alvo = max(float(tamanho), 1.0) / float(celulas)
    exp = math.floor(math.log10(alvo))
    for m in SERIE + (10.0,):
        p = m * 10 ** exp
        if p >= alvo - 1e-9:
            return p
    return 10 ** (exp + 1)


def tamanho_do_modelo(doc):
    """Maior medida (mm) das peças visíveis do documento no plano XY; 200 mm se vazio."""
    bb = None
    for o in getattr(doc, "Objects", []):
        sh = getattr(o, "Shape", None)
        try:
            if sh is None or sh.isNull() or not o.ViewObject or not o.ViewObject.Visibility:
                continue
            b = sh.BoundBox
            if not b.isValid() or b.DiagonalLength > 1e7:
                continue
        except Exception:
            continue
        if bb is None:
            bb = FreeCAD.BoundBox(b)
        else:
            bb.add(b)
    if bb is None:
        return 200.0, FreeCAD.Vector()
    centro = FreeCAD.Vector(bb.Center.x, bb.Center.y, 0)
    return max(bb.XLength, bb.YLength, 1.0), centro


def _cores():
    try:
        import PrumoEstilo
        esc = PrumoEstilo.escuro()
    except Exception:
        esc = False
    if esc:
        return (0.20, 0.24, 0.30), (0.29, 0.34, 0.41), (0.75, 0.33, 0.33), (0.36, 0.66, 0.40)
    return (0.84, 0.87, 0.91), (0.70, 0.75, 0.81), (0.85, 0.35, 0.35), (0.35, 0.68, 0.40)


def construir_no(tamanho, centro=None):
    """Nó Coin da grade: (separador, passo em mm)."""
    from pivy import coin
    centro = centro or FreeCAD.Vector()
    passo = passo_para(tamanho)
    forte = passo * 5
    meia = math.ceil(max(tamanho * 1.5, forte * 4) / forte) * forte     # sempre termina numa linha forte
    cx = round(centro.x / forte) * forte
    cy = round(centro.y / forte) * forte
    fina, grossa, cor_x, cor_y = _cores()

    sep = coin.SoSeparator()
    sep.setName(NOME_NO)
    ps = coin.SoPickStyle()
    ps.style = coin.SoPickStyle.UNPICKABLE
    sep.addChild(ps)
    lm = coin.SoLightModel()
    lm.model = coin.SoLightModel.BASE_COLOR
    sep.addChild(lm)

    def linhas(pontos, cor, largura):
        g = coin.SoSeparator()
        ds = coin.SoDrawStyle()
        ds.lineWidth = largura
        g.addChild(ds)
        c = coin.SoBaseColor()
        c.rgb = cor
        g.addChild(c)
        co = coin.SoCoordinate3()
        co.point.setValues(0, len(pontos), pontos)
        g.addChild(co)
        ls = coin.SoLineSet()
        ls.numVertices.setValues(0, len(pontos) // 2, [2] * (len(pontos) // 2))
        g.addChild(ls)
        sep.addChild(g)

    n = int(round(meia / passo))
    finas, fortes = [], []
    for i in range(-n, n + 1):
        d = i * passo
        alvo = fortes if i % 5 == 0 else finas
        alvo += [(cx + d, cy - meia, 0), (cx + d, cy + meia, 0), (cx - meia, cy + d, 0), (cx + meia, cy + d, 0)]
    linhas(finas, fina, 1)
    linhas(fortes, grossa, 1)
    # eixos X e Y por cima das linhas da grade, quando passam pela área
    if cy - meia <= 0 <= cy + meia:
        linhas([(cx - meia, 0, 0.001), (cx + meia, 0, 0.001)], cor_x, 2)
    if cx - meia <= 0 <= cx + meia:
        linhas([(0, cy - meia, 0.001), (0, cy + meia, 0.001)], cor_y, 2)
    return sep, passo


def _vistas():
    """[(documento, viewer)] das vistas 3D abertas."""
    res = []
    for d in (FreeCADGui.getDocument(n) for n in FreeCAD.listDocuments()):
        if d is None:
            continue
        try:
            for v in d.mdiViewsOfType("Gui::View3DInventor"):
                res.append((d.Document, v.getViewer()))
        except Exception:
            try:
                res.append((d.Document, d.ActiveView.getViewer()))
            except Exception:
                pass
    return res


def _tirar(viewer):
    raiz = viewer.getSceneGraph()
    for i in reversed(range(raiz.getNumChildren())):
        ch = raiz.getChild(i)
        if ch.getName().getString() in (NOME_NO, NOME_TELA):
            raiz.removeChild(i)
    t = _estado["telas"].pop(_chave(viewer), None)
    if t is not None:
        t.parar()


def _chave(viewer):
    try:
        return int(viewer.getSceneGraph().this)
    except Exception:
        return id(viewer)


# ------------------------------------------------------------------ grade frontal (na tela toda)
def linhas_da_tela(foco, direita, cima, meia_altura, aspecto, celulas=16):
    """Linhas (pares de pontos 3D) da grade frontal que cobre a vista: plano pela distância focal, virado para
    a câmera. As linhas caem em múltiplos do passo medidos no mundo, então a grade anda junto com o modelo ao
    deslocar a vista. Devolve (finas, fortes, passo)."""
    meia_altura = max(float(meia_altura), 1e-6)
    meia_larg = meia_altura * max(float(aspecto), 1e-3)
    passo = passo_para(2 * meia_altura, celulas)
    u0, v0 = foco.dot(direita), foco.dot(cima)
    finas, fortes = [], []

    def ponto(u, v):
        p = foco + direita * (u - u0) + cima * (v - v0)
        return (p.x, p.y, p.z)
    folga = passo
    ui, uf = u0 - meia_larg - folga, u0 + meia_larg + folga
    vi, vf = v0 - meia_altura - folga, v0 + meia_altura + folga
    for k in range(int(math.floor(ui / passo)), int(math.ceil(uf / passo)) + 1):
        alvo = fortes if k % 5 == 0 else finas
        alvo += [ponto(k * passo, vi), ponto(k * passo, vf)]
    for k in range(int(math.floor(vi / passo)), int(math.ceil(vf / passo)) + 1):
        alvo = fortes if k % 5 == 0 else finas
        alvo += [ponto(ui, k * passo), ponto(uf, k * passo)]
    return finas, fortes, passo


class _GradeTela:
    """Grade frontal de uma vista 3D: refeita quando a câmera muda (sensor) ou a janela muda de tamanho."""

    def __init__(self, viewer, doc):
        from pivy import coin
        self.viewer, self.doc = viewer, doc
        self.sep = coin.SoSeparator()
        self.sep.setName(NOME_TELA)
        ps = coin.SoPickStyle()
        ps.style = coin.SoPickStyle.UNPICKABLE
        self.sep.addChild(ps)
        lm = coin.SoLightModel()
        lm.model = coin.SoLightModel.BASE_COLOR
        self.sep.addChild(lm)
        # fica atrás de tudo: desenhada primeiro e sem gravar profundidade, o modelo pinta por cima
        if hasattr(coin, "SoDepthBuffer"):
            db = coin.SoDepthBuffer()
            db.test = False
            db.write = False
            self.sep.addChild(db)
        fina, grossa, _cx, _cy = _cores()
        self.grupos = []
        for cor in (fina, grossa):
            g = coin.SoSeparator()
            ds = coin.SoDrawStyle()
            ds.lineWidth = 1
            c = coin.SoBaseColor()
            c.rgb = cor
            co = coin.SoCoordinate3()
            ls = coin.SoLineSet()
            for n in (ds, c, co, ls):
                g.addChild(n)
            self.sep.addChild(g)
            self.grupos.append((co, ls))
        self.camera = None
        self.sensor = None
        self.ultimo = None
        self.passo = None
        viewer.getSceneGraph().insertChild(self.sep, 0)
        self.chave = _chave(viewer)
        self._ligar_camera()
        self.refazer()
        self.timer = QtCore.QTimer()
        self.timer.setInterval(400)
        self.timer.timeout.connect(self._conferir)
        self.timer.start()

    def _camera_atual(self):
        try:
            return self.viewer.getSoRenderManager().getCamera()
        except Exception:
            return None

    def _ligar_camera(self):
        from pivy import coin
        cam = self._camera_atual()
        if cam is None:
            return
        if self.sensor is not None:
            self.sensor.detach()
        self.camera = cam
        self.sensor = coin.SoNodeSensor(lambda *_a: self._na_camera(), None)
        self.sensor.setPriority(0)
        self.sensor.attach(cam)

    def _conferir(self):
        # vista fechada: para de vez (não mexe mais no visualizador que sumiu)
        try:
            vivas = set(_chave(v) for _d, v in _vistas())
        except Exception:
            vivas = set()
        if self.chave not in vivas:
            self.parar()
            _estado["telas"].pop(self.chave, None)
            return
        # câmera trocada (ortográfica/perspectiva) ou janela redimensionada
        try:
            cam = self._camera_atual()
            if cam is not None and (self.camera is None or int(cam.this) != int(self.camera.this)):
                self._ligar_camera()
            self.refazer()
        except Exception:
            pass

    def _na_camera(self):
        if self.sensor is None:
            return
        try:
            self.refazer()
        except Exception:
            pass

    def estado_camera(self):
        from pivy import coin
        cam = self._camera_atual()
        if cam is None:
            return None
        V = FreeCAD.Vector
        rot = cam.orientation.getValue()
        dire = rot.multVec(coin.SbVec3f(1, 0, 0))
        cima = rot.multVec(coin.SbVec3f(0, 1, 0))
        olhar = rot.multVec(coin.SbVec3f(0, 0, -1))
        pos = cam.position.getValue()
        dist = cam.focalDistance.getValue()
        foco = V(*pos.getValue()) + V(*olhar.getValue()) * dist
        tipo = cam.getTypeId().getName().getString()
        if "Orthographic" in tipo:
            meia = coin.cast(cam, "SoOrthographicCamera").height.getValue() / 2.0
        else:
            ang = coin.cast(cam, "SoPerspectiveCamera").heightAngle.getValue()
            meia = dist * math.tan(ang / 2.0)
        try:
            asp = self.viewer.getSoRenderManager().getViewportRegion().getViewportAspectRatio()
        except Exception:
            asp = 16.0 / 9.0
        return foco, V(*dire.getValue()), V(*cima.getValue()), meia, asp

    def refazer(self):
        e = self.estado_camera()
        if e is None:
            return
        chave = (tuple(round(x, 6) for x in e[0]), tuple(round(x, 6) for x in e[1]),
                 tuple(round(x, 6) for x in e[2]), round(e[3], 6), round(e[4], 4))
        if chave == self.ultimo:
            return
        self.ultimo = chave
        finas, fortes, passo = linhas_da_tela(*e)
        self.passo = passo
        for (co, ls), pts in zip(self.grupos, (finas, fortes)):
            co.point.setNum(0)
            if pts:
                co.point.setValues(0, len(pts), pts)
            ls.numVertices.setNum(0)
            if pts:
                ls.numVertices.setValues(0, len(pts) // 2, [2] * (len(pts) // 2))
        try:
            if passo != _estado["passos"].get(self.doc.Name):
                _estado["passos"][self.doc.Name] = passo
                _atualizar_botao()
        except Exception:
            pass

    def parar(self):
        try:
            self.timer.stop()
        except Exception:
            pass
        if self.sensor is not None:
            try:
                self.sensor.detach()
            except Exception:
                pass
        self.sensor = None


def atualizar(doc=None):
    """Põe (ou tira) a grade em todas as vistas 3D, ou só nas do documento `doc`."""
    if FreeCADGui is None:
        return
    m = modo()
    passos = {}
    for d, viewer in _vistas():
        if doc is not None and d is not doc:
            continue
        try:
            if m == TELA:
                # a frontal acompanha a câmera sozinha: recálculo do documento não precisa refazer
                if doc is not None and _chave(viewer) in _estado["telas"]:
                    continue
                _tirar(viewer)
                t = _GradeTela(viewer, d)
                _estado["telas"][_chave(viewer)] = t
                passos[d.Name] = t.passo
                continue
            _tirar(viewer)
            if m == CHAO:
                tam, centro = tamanho_do_modelo(d)
                no, passo = construir_no(tam, centro)
                viewer.getSceneGraph().insertChild(no, 0)
                passos[d.Name] = passo
        except Exception as exc:
            FreeCAD.Console.PrintLog("Usinix: grade: %s\n" % exc)
    _estado["passos"].update(passos)
    _atualizar_botao()


def passo_atual():
    try:
        return _estado["passos"].get(FreeCAD.ActiveDocument.Name)
    except Exception:
        return None


def alternar(ligar=None):
    """Liga (no modo escolhido por último) ou desliga. O botão usa proximo(), que passa pelos três estados."""
    on = (not ligada()) if ligar is None else bool(ligar)
    FreeCAD.ParamGet(PARAM).SetBool("Grade", on)
    atualizar()
    return on


def _fmt(p):
    if p is None:
        return ""
    if p >= 1000:
        v = p / 1000.0
        return ("%g m" % v).replace(".", ",")
    return ("%g mm" % p).replace(".", ",")


def ajustar_botao(b):
    """Botão (marcado = ligada; ícone diferente na frontal) e dica com o tamanho do quadrado."""
    m = modo()
    on = m != DESLIGADA
    p = passo_atual()
    if b.isChecked() != on:
        b.blockSignals(True)
        b.setChecked(on)
        b.blockSignals(False)
    if b.property("grade_modo") != m:
        b.setProperty("grade_modo", m)
        b.setIcon(_icone("grade_tela.svg" if m == TELA else "grade.svg"))
    proximo_txt = {DESLIGADA: "ligar a grade no chão (plano XY)",
                   CHAO: "trocar pela grade frontal, na tela toda",
                   TELA: "desligar"}[m]
    if m == DESLIGADA:
        estado = "desligada"
    else:
        estado = "%s, quadrado de %s" % (NOMES_MODO[m], _fmt(p)) if p else NOMES_MODO[m]
    b.setToolTip("Grade (tela quadriculada): %s.\nClique para %s." % (estado, proximo_txt))


def botoes():
    """Botões Grade das barras de vistas abertas."""
    if FreeCADGui is None:
        return []
    import shiboken6
    res = []
    for b in FreeCADGui.getMainWindow().findChildren(QtWidgets.QToolButton, "PrumoBotaoGrade"):
        if shiboken6.isValid(b):
            res.append(b)
    return res


def _atualizar_botao():
    for b in botoes():
        ajustar_botao(b)


class _Observador:
    def slotDeletedDocument(self, doc):
        for k, t in list(_estado["telas"].items()):
            try:
                mesmo = t.doc is doc or t.doc.Name == doc.Name
            except Exception:
                mesmo = True
            if mesmo:
                t.parar()
                _estado["telas"].pop(k, None)

    def slotRecomputedDocument(self, doc):
        if ligada():
            QtCore.QTimer.singleShot(0, lambda d=doc: atualizar(d))

    def slotCreatedDocument(self, doc):
        if ligada():
            QtCore.QTimer.singleShot(300, lambda: atualizar())


def _icone(arq="grade.svg"):
    import os
    import PrumoUtil
    return QtGui.QIcon(PrumoUtil.icone(arq)) if os.path.exists(PrumoUtil.icone(arq)) else QtGui.QIcon()


class CmdGrade:
    def GetResources(self):
        import PrumoUtil
        return {"Pixmap": PrumoUtil.icone("grade.svg"), "MenuText": "Grade (tela quadriculada)",
                "ToolTip": "A cada clique: grade no chão (plano XY), grade frontal na tela toda, desligada (botão na "
                           "barra de vistas, ao lado de Aparência)."}

    def IsActive(self):
        return True

    def Activated(self):
        proximo()


def install():
    """Comando Grade, observador e grade nas vistas (as abertas e as que abrirem). O botão fica na barra de
    vistas (PrumoBarraVista)."""
    if FreeCADGui is None or _estado["obs"] is not None:
        return None
    if "Prumo_Grade" not in FreeCADGui.listCommands():
        FreeCADGui.addCommand("Prumo_Grade", CmdGrade())
    mw = FreeCADGui.getMainWindow()
    obs = _Observador()
    FreeCAD.addDocumentObserver(obs)
    _estado["obs"] = obs
    mdi = mw.findChild(QtWidgets.QMdiArea)
    if mdi is not None:
        mdi.subWindowActivated.connect(lambda *_a: QtCore.QTimer.singleShot(0, _garantir))
    QtCore.QTimer.singleShot(500, _garantir)
    return obs


def _garantir():
    """Vistas novas (outra janela, vista dividida) ganham a grade; o texto do botão segue o documento ativo."""
    if not ligada():
        _atualizar_botao()
        return
    faltam = False
    nome = NOME_TELA if modo() == TELA else NOME_NO
    for d, viewer in _vistas():
        raiz = viewer.getSceneGraph()
        if not any(raiz.getChild(i).getName().getString() == nome for i in range(raiz.getNumChildren())):
            faltam = True
    if faltam:
        atualizar()
    else:
        _atualizar_botao()
