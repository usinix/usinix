# SPDX-License-Identifier: LGPL-2.1-or-later
# Usinix - título da janela com a versão do Usinix (não a do FreeCAD de base).
"""O título da janela dizia "Usinix 1.1.4" (versão do FreeCAD de que o Usinix deriva) enquanto a versão do Usinix
era outra. Troca a versão de base pela do Usinix sempre que o título muda."""

import FreeCAD

_ESTADO = {"ligado": False}


def _versoes():
    import UsinixVersao
    v = FreeCAD.Version()
    base = "%s.%s.%s" % (v[0], v[1], v[2]) if len(v) >= 3 else ""
    return base, UsinixVersao.VERSAO


def corrigir(titulo):
    """Título com a versão do Usinix no lugar da do FreeCAD de base (texto igual se não houver o que trocar)."""
    base, nossa = _versoes()
    if not base or base == nossa or ("Usinix " + base) not in titulo:
        return titulo
    return titulo.replace("Usinix " + base, "Usinix " + nossa)


def instalar():
    if _ESTADO["ligado"] or not FreeCAD.GuiUp:
        return
    import FreeCADGui
    mw = FreeCADGui.getMainWindow()

    def ao_mudar(t):
        novo = corrigir(t)
        if novo != t:
            mw.setWindowTitle(novo)

    mw.windowTitleChanged.connect(ao_mudar)
    ao_mudar(mw.windowTitle())
    _ESTADO["ligado"] = True
