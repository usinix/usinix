# SPDX-License-Identifier: LGPL-2.1-or-later
# Usinix - edição das anotações de texto da folha com duplo clique (como os campos da legenda).
"""Anotações da folha.

O duplo clique numa anotação de texto (TechDraw "Anotação") procurava o editor de propriedades padrão do
FreeCAD para abrir o campo Texto; no Usinix o painel de propriedades é outro, e nada acontecia. Aqui o duplo
clique abre uma janela com o texto (uma linha por linha da anotação), o tamanho da letra e a cor.
A anotação com formatação (texto rico) já tem editor próprio do TechDraw e continua com ele.
"""

import FreeCAD

try:
    import FreeCADGui
    from PySide import QtCore, QtGui, QtWidgets
except ImportError:      # sem interface
    FreeCADGui = None

import PrumoUtil

TIPOS = ("TechDraw::DrawViewAnnotation",)


def eh_anotacao(o):
    return o is not None and getattr(o, "TypeId", "") in TIPOS


def aplicar(anot, linhas, tamanho=None, cor=None):
    """Grava o texto (lista de linhas), o tamanho da letra (mm) e a cor (r, g, b de 0 a 1) da anotação."""
    doc = anot.Document
    doc.openTransaction("Editar anotação")
    try:
        anot.Text = [l for l in linhas] or [""]
        if tamanho:
            anot.TextSize = float(tamanho)
        if cor is not None:
            anot.TextColor = tuple(cor)
        anot.recompute()
        doc.recompute()
    finally:
        doc.commitTransaction()
    return anot


if FreeCADGui is not None:
    class JanelaAnotacao(QtWidgets.QDialog):
        def __init__(self, anot, parent=None):
            super().__init__(parent or FreeCADGui.getMainWindow())
            self.anot = anot
            self.setWindowTitle("Editar anotação")
            self.setMinimumWidth(420)
            lay = QtWidgets.QVBoxLayout(self)
            lay.addWidget(QtWidgets.QLabel("Texto (cada linha da janela é uma linha na folha):"))
            self.texto = QtWidgets.QPlainTextEdit("\n".join(list(anot.Text)))
            self.texto.setMinimumHeight(140)
            lay.addWidget(self.texto)
            form = QtWidgets.QFormLayout()
            self.tamanho = QtWidgets.QDoubleSpinBox()
            self.tamanho.setRange(1.0, 50.0)
            self.tamanho.setDecimals(1)
            self.tamanho.setSuffix(" mm")
            self.tamanho.setValue(float(getattr(anot, "TextSize", 5.0)))
            form.addRow("Altura da letra", self.tamanho)
            self.cor = QtWidgets.QPushButton()
            self._cor = tuple(getattr(anot, "TextColor", (0.0, 0.0, 0.0))[:3])
            self._pintar()
            self.cor.clicked.connect(self._escolher_cor)
            form.addRow("Cor", self.cor)
            lay.addLayout(form)
            bb = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel)
            bb.button(QtWidgets.QDialogButtonBox.Ok).setText("OK")
            bb.button(QtWidgets.QDialogButtonBox.Cancel).setText("Cancelar")
            bb.accepted.connect(self.accept)
            bb.rejected.connect(self.reject)
            lay.addWidget(bb)
            self.texto.setFocus()

        def _pintar(self):
            r, g, b = (int(round(c * 255)) for c in self._cor)
            self.cor.setText("#%02X%02X%02X" % (r, g, b))
            self.cor.setStyleSheet("QPushButton { background: rgb(%d,%d,%d); color: %s; }"
                                   % (r, g, b, "#FFFFFF" if r + g + b < 380 else "#000000"))

        def _escolher_cor(self):
            c = QtWidgets.QColorDialog.getColor(QtGui.QColor.fromRgbF(*self._cor), self, "Cor do texto")
            if c.isValid():
                self._cor = (c.redF(), c.greenF(), c.blueF())
                self._pintar()

        def valores(self):
            return self.texto.toPlainText().split("\n"), self.tamanho.value(), self._cor

        def accept(self):
            linhas, tam, cor = self.valores()
            aplicar(self.anot, linhas, tam, cor)
            super().accept()

    def editar(anot):
        j = JanelaAnotacao(anot)
        j.setAttribute(QtCore.Qt.WA_DeleteOnClose)
        j.open()
        return j

    class CmdEditarAnotacao:
        def GetResources(self):
            return {"Pixmap": PrumoUtil.icone("legenda.svg"), "MenuText": "Editar anotação",
                    "ToolTip": "Abre o texto da anotação selecionada na folha para editar (também com duplo "
                               "clique na anotação)."}

        def IsActive(self):
            return any(eh_anotacao(s.Object) for s in FreeCADGui.Selection.getSelectionEx())

        def Activated(self):
            for s in FreeCADGui.Selection.getSelectionEx():
                if eh_anotacao(s.Object):
                    return editar(s.Object)
            return None

    class _DuploClique(QtCore.QObject):
        """Duplo clique na folha: se a anotação de texto ficou selecionada, abre a edição."""

        def eventFilter(self, obj, ev):
            try:
                if ev.type() == QtCore.QEvent.MouseButtonDblClick:
                    QtCore.QTimer.singleShot(60, _abrir_da_selecao)
            except Exception:
                pass
            return False

    def _abrir_da_selecao():
        sel = [s.Object for s in FreeCADGui.Selection.getSelectionEx()]
        if len(sel) == 1 and eh_anotacao(sel[0]):
            if not any(isinstance(w, JanelaAnotacao) and w.isVisible() for w in QtWidgets.QApplication.topLevelWidgets()):
                editar(sel[0])

    _estado = {"filtro": None}

    def _instalar_nas_folhas():
        f = _estado["filtro"]
        mw = FreeCADGui.getMainWindow()
        mdi = mw.findChild(QtWidgets.QMdiArea)
        if mdi is None:
            return
        for sw in mdi.subWindowList():
            for gv in sw.findChildren(QtWidgets.QGraphicsView):
                vp = gv.viewport()
                if vp.property("prumo_anotacao"):
                    continue
                vp.installEventFilter(f)
                vp.setProperty("prumo_anotacao", True)

    def install():
        if _estado["filtro"] is not None:
            return
        _estado["filtro"] = _DuploClique(FreeCADGui.getMainWindow())
        mdi = FreeCADGui.getMainWindow().findChild(QtWidgets.QMdiArea)
        if mdi is not None:
            mdi.subWindowActivated.connect(lambda *_a: QtCore.QTimer.singleShot(0, _instalar_nas_folhas))
        t = QtCore.QTimer(FreeCADGui.getMainWindow())
        t.setInterval(2000)
        t.timeout.connect(_instalar_nas_folhas)
        t.start()
        _estado["timer"] = t
        QtCore.QTimer.singleShot(0, _instalar_nas_folhas)


def registrar_comandos():
    if FreeCADGui is not None:
        FreeCADGui.addCommand("Prumo_EditarAnotacao", CmdEditarAnotacao())
