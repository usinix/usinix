# SPDX-License-Identifier: LGPL-2.1-or-later
"""Documento novo sem nome: o FreeCAD chama de "Unnamed" e esse nome interno aparece na barra de status
("Pré-seleção: Unnamed.Caixa.Face6"), nas expressões e na janela de seleção. O rótulo já sai traduzido
("Sem nome"); aqui o nome interno passa a ser "Sem_nome" (nome interno não aceita espaço).

O comando Novo (Std_New) roda App.newDocument() pelo interpretador, então trocar a função do módulo
FreeCAD vale para ele e para qualquer chamada sem nome. Com nome dado, nada muda."""

import FreeCAD

NOME = "Sem_nome"
ROTULO = "Sem nome"


def instalar():
    original = FreeCAD.newDocument
    if getattr(original, "_usinix", False):
        return

    def newDocument(name=None, label=None, hidden=False, temp=False):
        if not name:
            name = NOME
            if not label:
                label = ROTULO
        if label:
            return original(name, label, hidden, temp)
        return original(name, hidden=hidden, temp=temp)

    newDocument.__doc__ = original.__doc__
    newDocument._usinix = True
    newDocument._original = original
    FreeCAD.newDocument = newDocument
