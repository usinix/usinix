# SPDX-License-Identifier: LGPL-2.1-or-later
# Usinix - grade (tela quadriculada) na vista 3D, ligada e desligada por um botão na barra inferior.
"""Grade da área de trabalho.

Quadriculado no plano XY (o "chão", z = 0), com linhas finas a cada passo e linhas mais fortes a cada 5 passos,
e os eixos X (vermelho) e Y (verde). O passo segue a série 1-2-5 conforme o tamanho do modelo (uma peça de
200 mm ganha grade de 10 mm; um galpão de 30 m, de 2 m), e a grade se refaz quando o documento recalcula.
A grade não é selecionável, não aparece em capturas de seleção e não entra no arquivo: é só da tela.
O botão "Grade" fica na barra de vistas embaixo da vista 3D, ao lado de Aparência (1.14.0; antes ficava na
barra de status); a escolha fica gravada (Preferências › Usinix).
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
_estado = {"botao": None, "timer": None, "obs": None, "passos": {}}


def ligada():
    return FreeCAD.ParamGet(PARAM).GetBool("Grade", False)


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
    from pivy import coin
    raiz = viewer.getSceneGraph()
    for i in reversed(range(raiz.getNumChildren())):
        ch = raiz.getChild(i)
        if ch.getName().getString() == NOME_NO:
            raiz.removeChild(i)


def atualizar(doc=None):
    """Põe (ou tira) a grade em todas as vistas 3D, ou só nas do documento `doc`."""
    if FreeCADGui is None:
        return
    on = ligada()
    passos = {}
    for d, viewer in _vistas():
        if doc is not None and d is not doc:
            continue
        try:
            _tirar(viewer)
            if on:
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
    """Botão (marcado = ligada) e dica com o tamanho do quadrado."""
    on = ligada()
    p = passo_atual()
    if b.isChecked() != on:
        b.blockSignals(True)
        b.setChecked(on)
        b.blockSignals(False)
    b.setToolTip("Grade (tela quadriculada) no plano XY: %s.\nClique para %s." % (
        "ligada, quadrado de %s" % _fmt(p) if on and p else ("ligada" if on else "desligada"),
        "desligar" if on else "ligar"))


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
    def slotRecomputedDocument(self, doc):
        if ligada():
            QtCore.QTimer.singleShot(0, lambda d=doc: atualizar(d))

    def slotCreatedDocument(self, doc):
        if ligada():
            QtCore.QTimer.singleShot(300, lambda: atualizar())


def _icone():
    import os
    import PrumoUtil
    return QtGui.QIcon(PrumoUtil.icone("grade.svg")) if os.path.exists(PrumoUtil.icone("grade.svg")) else QtGui.QIcon()


class CmdGrade:
    def GetResources(self):
        import PrumoUtil
        return {"Pixmap": PrumoUtil.icone("grade.svg"), "MenuText": "Grade (tela quadriculada)",
                "ToolTip": "Liga e desliga a grade no plano XY (botão na barra de vistas, ao lado de Aparência)."}

    def IsActive(self):
        return True

    def Activated(self):
        alternar()


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
    for d, viewer in _vistas():
        raiz = viewer.getSceneGraph()
        if not any(raiz.getChild(i).getName().getString() == NOME_NO for i in range(raiz.getNumChildren())):
            faltam = True
    if faltam:
        atualizar()
    else:
        _atualizar_botao()
