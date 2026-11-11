# SPDX-License-Identifier: LGPL-2.1-or-later
"""Usinix: ao criar um esboço, mostrar os planos com os eixos X, Y e Z.

- Janela "Escolher orientação" (Novo esboço da aba Esboço): o cubo pequeno dá lugar a um desenho dos três
  planos (XY, XZ, YZ) com os eixos e a origem; o plano escolhido fica em destaque.
- Painel de escolha do plano (Esboço da aba Peça): além dos planos, a vista 3D mostra os eixos X, Y e Z da
  origem do corpo, e os planos vão para o meio da tela (1.14.0: em qualquer modelo, não só no vazio). Com o
  corpo vazio, ou numa vista de topo/frente/lado, a vista vai para a isométrica, onde os três planos aparecem.
- Escolhido o plano, o esboço novo abre com a origem no meio da tela: o giro até o plano e o deslize até a
  origem são um movimento só, sem parada no meio.
  Ao fechar o painel o FreeCAD devolve a visibilidade de antes (planos e eixos voltam a ficar ocultos).
"""
import FreeCAD
import FreeCADGui
from PySide import QtCore, QtGui, QtWidgets

AZUL = "#003A70"
# quem vem do SolidWorks/Fusion (Y para cima) chama de "frente" o plano XY; aqui Z é para cima e a frente é XZ
NOMES_PLANOS = {"XY": "superior (planta)", "XZ": "frontal", "YZ": "lateral (direita)"}
AMARELO = "#F7BE00"
TAM = (200, 165)
_ESTADO = {"filtro": None}


# ------------------------------------------------------------------ desenho dos planos
def _iso(x, y, z, esc, ox, oy):
    """Projeção isométrica (X para a direita e para baixo, Y para a direita e para cima, Z para cima)."""
    import math
    c, s = math.cos(math.radians(30)), math.sin(math.radians(30))
    return QtCore.QPointF(ox + (x + y) * c * esc, oy + (x - y) * s * esc - z * esc)


def desenho_planos(plano="XY", invertido=False, largura=TAM[0], altura=TAM[1], escuro=False):
    """QPixmap com os três planos e os eixos; `plano` ("XY", "XZ", "YZ" ou None) fica em destaque."""
    dpr = 2.0
    pm = QtGui.QPixmap(int(largura * dpr), int(altura * dpr))
    pm.setDevicePixelRatio(dpr)
    pm.fill(QtCore.Qt.transparent)
    p = QtGui.QPainter(pm)
    p.setRenderHint(QtGui.QPainter.Antialiasing)
    # extensão do desenho: 1,73·esc na largura; 1,5·esc acima e 0,5·esc abaixo da origem
    esc = min(largura / 1.95, altura / 2.2)
    ox, oy = (largura - 1.73 * esc) / 2.0, (altura - 2.0 * esc) / 2.0 + 1.5 * esc
    base = QtGui.QColor("#8CBCEB" if escuro else AZUL)
    texto = QtGui.QColor("#DCE6F0" if escuro else AZUL)
    a, b = 0.12, 1.0          # os planos começam um pouco afastados da origem, como na vista 3D

    planos = {
        "YZ": [(0, a, a), (0, b, a), (0, b, b), (0, a, b)],
        "XZ": [(a, 0, a), (b, 0, a), (b, 0, b), (a, 0, b)],
        "XY": [(a, a, 0), (b, a, 0), (b, b, 0), (a, b, 0)],
    }
    rotulo_pos = {"YZ": (0, 0.62, 0.80), "XZ": (0.64, 0, 0.78), "XY": (0.70, 0.62, 0)}
    for nome in ("YZ", "XZ", "XY"):
        pts = [_iso(x, y, z, esc, ox, oy) for x, y, z in planos[nome]]
        destaque = (nome == plano)
        cor = QtGui.QColor(AMARELO if destaque else base)
        cor.setAlphaF(0.85 if destaque else 0.32)
        borda = QtGui.QColor("#B88A00" if destaque else base)
        p.setPen(QtGui.QPen(borda, 1.4 if destaque else 1.0))
        p.setBrush(cor)
        p.drawPolygon(QtGui.QPolygonF(pts))
        f = p.font()
        f.setBold(True)
        f.setPointSizeF(9.5 if destaque else 8.5)
        p.setFont(f)
        p.setPen(QtGui.QColor("#3D2E00") if destaque else texto)
        c = _iso(*rotulo_pos[nome], esc=esc, ox=ox, oy=oy)
        p.drawText(QtCore.QRectF(c.x() - 16, c.y() - 9, 32, 18), QtCore.Qt.AlignCenter, nome)

    # eixos e origem
    o = _iso(0, 0, 0, esc, ox, oy)
    f = p.font()
    f.setBold(False)
    f.setPointSizeF(8)
    p.setFont(f)
    for nome, (x, y, z) in (("X", (0.55, 0, 0)), ("Y", (0, 0.45, 0)), ("Z", (0, 0, 0.55))):
        fim = _iso(x, y, z, esc, ox, oy)
        p.setPen(QtGui.QPen(QtGui.QColor("#0B1F33") if not escuro else texto, 1.8))
        p.drawLine(o, fim)
        d = fim - o
        n = max((d.x() ** 2 + d.y() ** 2) ** 0.5, 1)
        q = fim + QtCore.QPointF(d.x() / n * 9, d.y() / n * 9)
        p.drawText(QtCore.QRectF(q.x() - 7, q.y() - 7, 14, 14), QtCore.Qt.AlignCenter, nome)
    p.setPen(QtCore.Qt.NoPen)
    p.setBrush(QtGui.QColor("#3D8BFD"))
    p.drawEllipse(o, 3, 3)

    if plano and invertido:
        p.setPen(texto)
        f.setPointSizeF(7.5)
        p.setFont(f)
        p.drawText(QtCore.QRectF(0, altura - 14, largura, 14), QtCore.Qt.AlignCenter, "direção invertida")
    p.end()
    return pm


def _escuro():
    try:
        import PrumoEstilo
        return PrumoEstilo.escuro()
    except Exception:
        return False


# ------------------------------------------------------------------ janela "Escolher orientação"
class _Desenho(QtCore.QObject):
    """Filho da janela que redesenha a prévia. Não guarda objetos Python dos widgets: o PySide invalida esses
    invólucros quando outro código pega o mesmo widget; tudo é buscado de novo a partir de parent()."""

    def atualizar(self, *_a):
        dlg = self.parent()
        if dlg is None:
            return
        rotulo = dlg.findChild(QtWidgets.QLabel, "previewLabel")
        if rotulo is None:
            return
        plano = None
        for n in ("XY", "XZ", "YZ"):
            r = dlg.findChild(QtWidgets.QRadioButton, n + "_radioButton")
            if r is not None and r.isChecked():
                plano = n
        inv = dlg.findChild(QtWidgets.QCheckBox, "Reverse_checkBox")
        rotulo.setPixmap(desenho_planos(plano, bool(inv is not None and inv.isChecked()), escuro=_escuro()))


def ajustar_dialogo(dlg):
    """Troca o cubo da janela de orientação pelo desenho dos planos e o mantém em dia com a escolha."""
    import shiboken6
    if not shiboken6.isValid(dlg) or dlg.findChild(_Desenho) is not None:
        return False
    rotulo = dlg.findChild(QtWidgets.QLabel, "previewLabel")
    radios = [dlg.findChild(QtWidgets.QRadioButton, n + "_radioButton") for n in ("XY", "XZ", "YZ")]
    inv = dlg.findChild(QtWidgets.QCheckBox, "Reverse_checkBox")
    if rotulo is None or None in radios:
        return False
    rotulo.setMinimumSize(*TAM)
    rotulo.setMaximumSize(*TAM)
    rotulo.setToolTip("Planos XY, XZ e YZ com os eixos X, Y e Z; o plano escolhido fica em amarelo.\n"
                      "Aqui Z aponta para cima: a frente é o plano XZ (no SolidWorks e no Fusion, a "
                      "\"frente\" é o XY).")
    for n, r in zip(("XY", "XZ", "YZ"), radios):
        r.setText("Plano %s: %s" % (n, NOMES_PLANOS[n]))
    des = _Desenho(dlg)
    # o FreeCAD redesenha o cubo no "clicked"; nossas ligações vêm depois da dele, então o desenho fica por último
    for w in radios + ([inv] if inv is not None else []):
        w.toggled.connect(des.atualizar)
        w.clicked.connect(des.atualizar)
    des.atualizar()
    dlg.adjustSize()
    return True


# ------------------------------------------------------------------ painel de escolha do plano (Peça)
def _origens_em_escolha(doc):
    """Origens com planos mostrados temporariamente (painel de escolha aberto)."""
    res = []
    for o in (doc.Objects if doc else []):
        if o.TypeId not in ("App::Origin", "App::LocalCoordinateSystem"):
            continue
        try:
            filhos = list(o.OriginFeatures)
        except Exception:
            continue
        planos = [f for f in filhos if getattr(f, "Role", "").endswith("_Plane")]
        if planos and any(getattr(f.ViewObject, "Visibility", False) for f in planos):
            res.append((o, filhos))
    return res


def nomear_planos_na_lista(painel):
    """Lista do painel de escolha: "Plano-XY (Plano de base)" ganha o nome familiar (superior, frontal...)."""
    import re
    n = 0
    for lw in painel.findChildren(QtWidgets.QListWidget):
        for i in range(lw.count()):
            it = lw.item(i)
            t = it.text()
            m = re.search(r"\b(XY|XZ|YZ)[-_ ]?(?:Plane|plane)?\b", t)
            if m and "(" in t and NOMES_PLANOS[m.group(1)] not in t:
                it.setText("%s: %s" % (t, NOMES_PLANOS[m.group(1)]))
                n += 1
    return n


def mostrar_eixos():
    """Com o painel de escolha do plano aberto: mostra também os eixos (o FreeCAD só mostra os planos)."""
    try:
        if not FreeCADGui.Control.activeDialog():
            return 0
    except Exception:
        return 0
    doc = FreeCAD.ActiveDocument
    ligados = []
    for _o, filhos in _origens_em_escolha(doc):
        for f in filhos:
            if getattr(f, "Role", "").endswith("_Axis") and not f.ViewObject.Visibility:
                f.ViewObject.Visibility = True
                ligados.append((doc.Name, f.Name))
    if ligados:
        _ESTADO.setdefault("eixos", []).extend(ligados)
        _vigiar_fechamento()
    return len(ligados)


def _vigiar_fechamento():
    """Quando o painel fecha, esconde de novo os eixos que a Usinix mostrou (se ainda estiverem à vista)."""
    if _ESTADO.get("vigia") is not None:
        return
    t = QtCore.QTimer(QtWidgets.QApplication.instance())
    t.setInterval(250)

    def conferir():
        try:
            aberto = FreeCADGui.Control.activeDialog()
        except Exception:
            aberto = False
        if aberto:
            return
        restaurar_eixos()
        t.stop()
        t.deleteLater()
        _ESTADO["vigia"] = None

    t.timeout.connect(conferir)
    t.start()
    _ESTADO["vigia"] = t


def restaurar_eixos():
    for doc_nome, nome in _ESTADO.pop("eixos", []):
        try:
            o = FreeCAD.getDocument(doc_nome).getObject(nome)
            if o is not None and o.ViewObject.Visibility:
                o.ViewObject.Visibility = False
        except Exception:
            pass


ISOMETRICA = (0.424708, 0.17592, 0.339851, 0.820473)     # mesma rotação da vista isométrica do FreeCAD


def _modelo_vazio(doc):
    for o in doc.Objects:
        vo = getattr(o, "ViewObject", None)
        try:
            if (vo is not None and vo.Visibility and hasattr(o, "Shape") and o.TypeId != "PartDesign::Body"
                    and not o.Shape.isNull() and o.Shape.Volume > 1e-9):
                return False
        except Exception:
            continue
    return True


def _tamanho(view):
    try:
        w, h = view.getSize()
        return max(1, int(w)), max(1, int(h))
    except Exception:
        return 800, 600


def caixa_dos_planos(doc, view):
    """Caixa (SbBox3f, coordenadas globais) dos planos e eixos de origem à vista no painel de escolha."""
    from pivy import coin
    viewer = view.getViewer()
    raiz = viewer.getSceneGraph()
    w, h = _tamanho(view)
    vp = coin.SbViewportRegion(w, h)
    caixa = coin.SbBox3f()
    for _o, filhos in _origens_em_escolha(doc):
        for f in filhos:
            try:
                if not f.ViewObject.Visibility:
                    continue
                sa = coin.SoSearchAction()
                sa.setNode(f.ViewObject.RootNode)
                sa.apply(raiz)
                caminho = sa.getPath()
                if caminho is None:
                    continue
                bba = coin.SoGetBoundingBoxAction(vp)
                bba.apply(caminho)
                b = bba.getBoundingBox()
                if not b.isEmpty():
                    caixa.extendBy(b)
            except Exception:
                continue
    return caixa


def alvo_dos_planos(doc, view):
    """(giro, centro, altura) para os planos de origem ficarem no meio da tela. Gira para a isométrica com o
    modelo vazio ou quando a vista está de topo/frente/lado (os planos ficariam de perfil).

    Os planos de origem do FreeCAD têm tamanho fixo na tela (crescem e encolhem com o zoom), então o zoom fica
    como está (altura None) e só o centro muda: o meio da caixa dos planos vai para o meio da tela."""
    from pivy import coin
    caixa = caixa_dos_planos(doc, view)
    if caixa.isEmpty():
        return None
    cam = view.getCameraNode()
    ori = cam.orientation.getValue()
    d = ori.multVec(coin.SbVec3f(0, 0, -1))
    de_perfil = max(abs(d[0]), abs(d[1]), abs(d[2])) > 0.98
    vazio = _modelo_vazio(doc)
    if vazio or de_perfil:
        ori = coin.SbRotation(*ISOMETRICA)
    c = caixa.getCenter()
    centro = FreeCAD.Vector(c[0], c[1], c[2])
    altura = None
    if vazio and _ortografica(cam):
        # modelo vazio: zoom de uma peça pequena (200 mm na altura da tela), como no esboço novo; os planos
        # mantêm o tamanho na tela, então o centro deles anda junto com o zoom
        # o centro é refeito a cada quadro do movimento (enquadrar_planos)
        altura = 200.0
    return ori, centro, altura


def enquadrar_planos(tentativas=15, _anterior=None):
    """Painel de escolha do plano aberto: leva os planos para o meio da tela, num movimento suave.

    Espera os planos assentarem: o FreeCAD mostra os planos e logo depois ajusta o tamanho deles ao modelo
    (1.14.0: a vista ia para o tamanho antigo e os planos ficavam pequenos e fora do meio)."""
    try:
        if not FreeCADGui.Control.activeDialog():
            return False
        doc = FreeCAD.ActiveDocument
        view = FreeCADGui.ActiveDocument.ActiveView
        caixa = caixa_dos_planos(doc, view)
        chave = None if caixa.isEmpty() else tuple(round(x, 3) for x in caixa.getMin().getValue() +
                                                    caixa.getMax().getValue())
    except Exception:
        return False
    if (chave is None or chave != _anterior) and tentativas > 0:
        QtCore.QTimer.singleShot(50, lambda: enquadrar_planos(tentativas - 1, chave))
        return False
    alvo = alvo_dos_planos(doc, view)
    if alvo is None:
        return False
    ori, centro, altura = alvo
    _ESTADO["alvo_planos"] = (ori, centro, altura)

    def centro_agora():
        cx = caixa_dos_planos(doc, view)
        if cx.isEmpty():
            return None
        c = cx.getCenter()
        return FreeCAD.Vector(c[0], c[1], c[2])

    animar_camera(view, ori=ori, centro=centro, altura=altura, duracao_ms=380,
                  centro_fn=centro_agora)
    return True


def _vista_que_mostra_os_planos(doc):
    """Mantido para quem chama: agora enquadrar_planos faz isso para qualquer modelo."""
    return enquadrar_planos()


def _nomear_se_vivo(painel):
    try:
        import shiboken6
        if shiboken6.isValid(painel):
            nomear_planos_na_lista(painel)
    except Exception:
        pass


# ------------------------------------------------------------------ ganchos
class _Filtro(QtCore.QObject):
    def eventFilter(self, obj, ev):
        try:
            if ev.type() == QtCore.QEvent.Show and isinstance(obj, QtWidgets.QWidget):
                nome = obj.metaObject().className()
                if nome == "SketcherGui::SketchOrientationDialog":
                    QtCore.QTimer.singleShot(0, lambda d=obj: ajustar_dialogo(d))
                elif nome == "PartDesignGui::TaskFeaturePick":
                    for atraso in (0, 300):
                        QtCore.QTimer.singleShot(atraso, mostrar_eixos)
                    # depois que os eixos aparecem (entram na caixa), os planos vão para o meio da tela
                    QtCore.QTimer.singleShot(30, enquadrar_planos)
                    QtCore.QTimer.singleShot(0, lambda p=obj: _nomear_se_vivo(p))
        except Exception:
            pass
        return False


def alvo_da_camera(sk, altura_vazio=200.0):
    """Posição da câmera com o centro da vista na origem do esboço (sem girar) e, com o modelo vazio numa
    câmera ortográfica, a altura do zoom (senão None)."""
    from pivy import coin
    v = FreeCADGui.ActiveDocument.ActiveView
    cam = v.getCameraNode()
    alvo = sk.getGlobalPlacement().Base
    dirv = cam.orientation.getValue().multVec(coin.SbVec3f(0, 0, -1))
    dist = cam.focalDistance.getValue()
    p = coin.SbVec3f(alvo.x, alvo.y, alvo.z) - dirv * dist
    vazio = not any(getattr(o, "Shape", None) is not None and not o.Shape.isNull() and o.Shape.Solids
                    for o in sk.Document.Objects)
    altura = None
    if vazio and sk.GeometryCount == 0 and cam.isOfType(coin.SoOrthographicCamera.getClassTypeId()):
        altura = float(altura_vazio)
    return p, altura


def centralizar_no_esboco(sk, altura_vazio=200.0):
    """Leva o centro da vista para a origem do esboço (sem girar), de uma vez. Com o modelo vazio, ajusta o zoom."""
    cam = FreeCADGui.ActiveDocument.ActiveView.getCameraNode()
    p, altura = alvo_da_camera(sk, altura_vazio)
    cam.position.setValue(p)
    if altura is not None:
        cam.height.setValue(altura)
    return True


def _suave(t):
    """Começa e termina devagar (sem tranco)."""
    return t * t * (3.0 - 2.0 * t)


# ------------------------------------------------------------------ câmera num movimento só
def _rot_coin(rot):
    from pivy import coin
    q = rot.Q
    return coin.SbRotation(q[0], q[1], q[2], q[3])


def _ortografica(cam):
    from pivy import coin
    return cam.isOfType(coin.SoOrthographicCamera.getClassTypeId())


def parar_animacao():
    tm = _ESTADO.get("deslize")
    if tm is not None:
        try:
            tm.stop()
            tm.deleteLater()
        except Exception:
            pass
    _ESTADO["deslize"] = None


def animar_camera(view, ori=None, centro=None, altura=None, duracao_ms=420, centro_fn=None):
    """Leva a câmera da posição atual até `ori` (giro), `centro` (ponto no meio da tela) e `altura` (zoom da
    câmera ortográfica) num movimento só, que começa e termina devagar. O giro e o deslize andam juntos: não há
    parada no meio (1.14.0: antes o FreeCAD girava, a vista parava e só depois deslizava até o centro).

    `centro_fn` (opcional) dá o centro a cada quadro, para alvos que mudam com o zoom (os planos de origem têm
    tamanho fixo na tela); no fim, segue alguns quadros até o alvo parar."""
    import time
    from pivy import coin
    parar_animacao()
    try:
        view.stopAnimating()           # giro do próprio FreeCAD: este movimento o substitui
    except Exception:
        pass
    cam = view.getCameraNode()
    o0 = cam.orientation.getValue()
    o1 = ori if ori is not None else o0
    dist = cam.focalDistance.getValue()
    d0 = o0.multVec(coin.SbVec3f(0, 0, -1))
    c0 = cam.position.getValue() + d0 * dist
    c1 = coin.SbVec3f(centro.x, centro.y, centro.z) if centro is not None else c0
    orto = _ortografica(cam)
    h0 = cam.height.getValue() if orto else None
    h1 = altura if (orto and altura is not None) else h0
    est = {"t0": None, "c1": c1, "extra": 0}   # o relógio começa no 1º quadro (o FreeCAD pode estar ocupado)
    tm = QtCore.QTimer(QtWidgets.QApplication.instance())
    tm.setInterval(15)
    _ESTADO["deslize"] = tm

    def pose(k):
        o = coin.SbRotation.slerp(o0, o1, k)
        c = c0 + (est["c1"] - c0) * k
        d = o.multVec(coin.SbVec3f(0, 0, -1))
        cam.orientation.setValue(o)
        cam.position.setValue(c - d * dist)
        if h0 is not None:
            cam.height.setValue(h0 + (h1 - h0) * k)

    def passo():
        try:
            if est["t0"] is None:
                est["t0"] = time.time()
            t = min(1.0, (time.time() - est["t0"]) * 1000.0 / max(1, duracao_ms))
            antes = est["c1"]
            if centro_fn is not None:
                novo = centro_fn()
                if novo is not None:
                    est["c1"] = coin.SbVec3f(novo.x, novo.y, novo.z)
            pose(_suave(t))
            if t >= 1.0:
                est["extra"] += 1
                if centro_fn is None or est["extra"] > 8 or (est["c1"] - antes).length() < 1e-4 * max(1.0, dist):
                    parar_animacao()
        except Exception:
            parar_animacao()

    tm.timeout.connect(passo)
    tm.start()
    return tm


def centralizar_suave(doc_nome, nome, duracao_ms=420):
    """Esboço novo: gira para o plano do esboço e desliza até a origem dele, tudo junto."""
    o = FreeCAD.getDocument(doc_nome).getObject(nome)
    gd = FreeCADGui.getDocument(doc_nome)
    _p, altura = alvo_da_camera(o)
    return animar_camera(gd.ActiveView, ori=_rot_coin(o.getGlobalPlacement().Rotation),
                         centro=o.getGlobalPlacement().Base, altura=altura, duracao_ms=duracao_ms)


def _centralizar_ligado():
    return FreeCAD.ParamGet("User parameter:BaseApp/Preferences/Mod/Prumo3D").GetBool("CentralizarEsbocoNovo", True)


class _ObsEdicao:
    """Avisado pelo FreeCAD no mesmo instante em que o esboço entra em edição (o giro do FreeCAD acabou de
    começar): troca esse giro pelo movimento único até a origem do esboço."""

    def slotInEdit(self, vp):
        try:
            obj = vp.Object
            _ESTADO["editando"] = (obj.Document.Name, obj.Name)
            if obj.TypeId == "Sketcher::SketchObject" and obj.GeometryCount == 0 and _centralizar_ligado():
                centralizar_suave(obj.Document.Name, obj.Name)
        except Exception as exc:
            FreeCAD.Console.PrintLog("Usinix: centralizar esboço: %s\n" % exc)

    def slotResetEdit(self, vp):
        _ESTADO["editando"] = None


def _vigiar_esbocos():
    """Mantido para quem chama; o centro do esboço novo agora vem do aviso de edição (_ObsEdicao)."""
    return None


def instalar():
    if _ESTADO["filtro"] is not None:
        return
    obs = _ObsEdicao()
    FreeCADGui.addDocumentObserver(obs)
    _ESTADO["vigia_esboco"] = obs
    f = _Filtro(QtWidgets.QApplication.instance())
    QtWidgets.QApplication.instance().installEventFilter(f)
    _ESTADO["filtro"] = f
