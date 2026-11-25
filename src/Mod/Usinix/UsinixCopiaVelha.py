# SPDX-License-Identifier: LGPL-2.1-or-later
"""Apaga a cópia do complemento que ficou para trás na pasta do usuário.

Depois de um complemento (atualização só da parte em Python), a cópia fica em <dados do usuário>/Mod/Usinix. Quando
um pacote completo igual ou mais novo é instalado por cima, essa cópia passa a vez ao programa a cada abertura
(UsinixComplemento.motivo_para_voltar), mas continuava lá: o arquivo que decide qual complemento usar vinha sempre
da cópia velha, e o teste da versão mínima falhava com a versão mínima antiga (1.29.5 sobre a cópia da 1.29.4).

Este módulo roda pelo complemento do programa (não depende do UsinixComplemento já carregado, que pode ser o da
cópia velha) e só apaga quando a cópia é de versão igual ou anterior à do programa: uma cópia mais nova, mesmo
que tenha falhado ou que espere outro pacote, fica."""

import os
import re
import shutil

import FreeCAD


def _chave(rotulo):
    """'1.29.5' -> (1, 29, 5, 1); '1.30.0-beta' fica antes de '1.30.0'."""
    m = re.match(r"\s*v?(\d+)(?:\.(\d+))?(?:\.(\d+))?(.*)$", rotulo or "")
    if not m:
        return (0, 0, 0, 0)
    a, b, c, resto = m.groups()
    return (int(a), int(b or 0), int(c or 0), 0 if resto.strip(" -") else 1)


def _versao(pasta):
    for nome, padrao in (("UsinixVersaoCompilada.py", r'VERSAO_COMPILADA\s*=\s*"([^"]*)"'),
                         ("UsinixVersao.py", r'^VERSAO\s*=\s*"([^"]*)"')):
        try:
            with open(os.path.join(pasta, nome), encoding="utf-8") as f:
                m = re.search(padrao, f.read(), re.M)
            if m and m.group(1):
                return m.group(1)
        except OSError:
            continue
    return ""


def _norm(p):
    return os.path.normcase(os.path.realpath(p)) if p else ""


def pasta_usuario():
    return os.path.join(FreeCAD.getUserAppDataDir(), "Mod", "Usinix")


def pasta_programa():
    return os.path.join(FreeCAD.getHomePath(), "Mod", "Usinix")


def copia_velha(usuario=None, programa=None):
    """A pasta da cópia do usuário se ela é de versão igual ou anterior à do programa; senão None."""
    usuario = usuario or pasta_usuario()
    programa = programa or pasta_programa()
    if not os.path.isdir(usuario) or _norm(usuario) == _norm(programa):
        return None
    if not os.path.isfile(os.path.join(programa, "InitGui.py")):
        return None
    meu, dele = _versao(usuario), _versao(programa)
    if not dele:
        return None
    if meu and _chave(meu) > _chave(dele):
        return None
    return usuario


def apagar(usuario=None, programa=None):
    """Apaga a cópia velha (renomeia para fora de Mod e remove). Devolve a versão apagada ou ''."""
    d = copia_velha(usuario, programa)
    if not d:
        return ""
    versao = _versao(d) or "sem versão"
    destino = os.path.join(os.path.dirname(os.path.dirname(d)), "Usinix-complemento", "Usinix.antigo")
    try:
        os.makedirs(os.path.dirname(destino), exist_ok=True)
        if os.path.isdir(destino):
            shutil.rmtree(destino, ignore_errors=True)
        os.replace(d, destino)
        shutil.rmtree(destino, ignore_errors=True)
    except OSError as exc:
        FreeCAD.Console.PrintLog("Usinix: cópia antiga do complemento (%s) não apagada: %s\n" % (versao, exc))
        return ""
    FreeCAD.Console.PrintLog("Usinix: cópia antiga do complemento (%s) apagada da pasta do usuário\n" % versao)
    return versao


def apagar_depois():
    """Ao abrir, sem atrasar a janela."""
    try:
        from PySide import QtCore
        QtCore.QTimer.singleShot(3000, lambda: apagar())
    except Exception:
        apagar()
