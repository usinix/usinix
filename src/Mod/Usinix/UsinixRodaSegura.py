# SPDX-License-Identifier: LGPL-2.1-or-later
# Usinix - a roda do mouse só muda um campo numérico ou uma lista se o campo estiver em edição.
"""Rolando um painel com o mouse por cima dos campos, a roda mudava o valor (Patamar da escada de 1.000 para 990 mm,
sem aviso) e o painel só rolava pela margem. Agora, campo numérico ou lista sem o foco não muda com a roda: o
movimento vai para a rolagem do painel. Clicando no campo (foco), a roda volta a ajustar o valor."""

from PySide import QtCore, QtWidgets

_ESTADO = {"filtro": None}


def _campo(obj):
    """O campo (spin box ou lista) que recebeu a roda, ou None. A roda pode chegar na caixa de texto de dentro."""
    if isinstance(obj, (QtWidgets.QAbstractSpinBox, QtWidgets.QComboBox)):
        return obj
    pai = obj.parent() if isinstance(obj, QtWidgets.QLineEdit) else None
    if isinstance(pai, (QtWidgets.QAbstractSpinBox, QtWidgets.QComboBox)):
        return pai
    return None


def _area_de_rolagem(w):
    p = w.parentWidget()
    while p is not None:
        if isinstance(p, QtWidgets.QAbstractScrollArea) and not isinstance(p, QtWidgets.QAbstractItemView):
            return p
        p = p.parentWidget()
    return None


def rolar_em_vez_de_mudar(campo, delta_y):
    """Rola a área que contém o campo (passo de 3 linhas por clique da roda). Devolve True se havia o que rolar."""
    area = _area_de_rolagem(campo)
    if area is None:
        return False
    sb = area.verticalScrollBar()
    if sb is None or sb.maximum() <= sb.minimum():
        return False
    passos = delta_y / 120.0
    sb.setValue(int(round(sb.value() - passos * 3 * max(sb.singleStep(), 1))))
    return True


def em_edicao(campo):
    """O campo (ou a caixa de texto dele) está com o foco."""
    fw = QtWidgets.QApplication.focusWidget()
    return fw is not None and (fw is campo or campo.isAncestorOf(fw))


def sem_foco_pela_roda(campo):
    """Tira do campo o foco pela roda (Qt.WheelFocus, padrão do spin box): com ele, o Qt dá o foco ao campo na
    própria roda, antes deste filtro, e o campo parecia em edição (Lance até 3000 virou 2997 no teste pelo mouse).
    Clique e Tab continuam dando o foco."""
    pol = campo.focusPolicy()
    roda = QtCore.Qt.WheelFocus
    if pol == roda:
        campo.setFocusPolicy(QtCore.Qt.StrongFocus)


class _Filtro(QtCore.QObject):
    def eventFilter(self, obj, ev):
        tipo = ev.type()
        if tipo == QtCore.QEvent.Polish:
            try:
                if isinstance(obj, (QtWidgets.QAbstractSpinBox, QtWidgets.QComboBox)):
                    sem_foco_pela_roda(obj)
            except Exception:
                pass
            return False
        if tipo != QtCore.QEvent.Wheel:
            return False
        try:
            campo = _campo(obj)
            if campo is None:
                return False
            sem_foco_pela_roda(campo)              # campo criado antes do filtro: vale da próxima vez
            if em_edicao(campo):
                return False
            rolar_em_vez_de_mudar(campo, ev.angleDelta().y())
            return True                          # o valor não muda
        except Exception:
            return False


def instalar():
    if _ESTADO["filtro"] is not None:
        return
    app = QtWidgets.QApplication.instance()
    if app is None:
        return
    f = _Filtro(app)
    app.installEventFilter(f)
    _ESTADO["filtro"] = f
