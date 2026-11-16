# SPDX-License-Identifier: LGPL-2.1-or-later
"""Compatibilidade com o nome antigo (Prumo, até a 1.20.0).

Depois da 1.20.0 tudo passou a se chamar Usinix: a pasta do módulo (Mod/Prumo3D → Mod/Usinix), os arquivos
(PrumoX.py → UsinixX.py), os comandos (Prumo_X → Usinix_X), as preferências (Mod/Prumo3D → Mod/Usinix), as
propriedades dos objetos (PrumoX → UsinixX) e as pastas de dados. Este módulo faz a ponte:

- arquivos salvos antes guardam o módulo de cada objeto pelo nome antigo ("PrumoEstrutura"): o importador
  abaixo entrega o módulo novo ("UsinixEstrutura") no lugar;
- as propriedades PrumoX e o grupo "Prumo" do editor de propriedades viram UsinixX e "Usinix" ao abrir;
- as preferências, os atalhos de teclado e a bancada lembrada passam para os nomes novos uma vez;
- a cópia antiga do complemento na pasta do usuário (Mod/Prumo3D) sai do caminho, senão carregaria junto.
"""

import importlib
import importlib.abc
import importlib.util
import os
import shutil
import sys

import FreeCAD

ANTIGO = "Prumo"
NOVO = "Usinix"
PREF = "User parameter:BaseApp/Preferences/Mod/"
PREF_ANTIGA = PREF + "Prumo3D"
PREF_NOVA = PREF + "Usinix"


# ------------------------------------------------------------------ importador: PrumoX → UsinixX
def nome_novo(nome):
    """'PrumoEstrutura' → 'UsinixEstrutura'; outros nomes voltam iguais."""
    if nome.startswith(ANTIGO) and len(nome) > len(ANTIGO):
        return NOVO + nome[len(ANTIGO):]
    return nome


class _Apelido(importlib.abc.Loader):
    def __init__(self, novo):
        self.novo = novo

    def create_module(self, spec):
        return importlib.import_module(self.novo)

    def exec_module(self, module):
        pass


class Importador(importlib.abc.MetaPathFinder):
    """import PrumoX (arquivos antigos, macros, pacotes de terceiros) entrega o módulo UsinixX."""

    def find_spec(self, fullname, path=None, target=None):
        if "." in fullname or not fullname.startswith(ANTIGO) or fullname == ANTIGO:
            return None
        novo = nome_novo(fullname)
        try:
            if importlib.util.find_spec(novo) is None:
                return None
        except (ImportError, ValueError):
            return None
        return importlib.util.spec_from_loader(fullname, _Apelido(novo))


def instalar_importador():
    if not any(isinstance(f, Importador) for f in sys.meta_path):
        sys.meta_path.append(Importador())     # no fim: um módulo de verdade com o nome antigo vence


# ------------------------------------------------------------------ complemento antigo na pasta do usuário
def desativar_complemento_antigo():
    """<dados do usuário>/Mod/Prumo3D (atualização só do complemento, até a 1.20.0) carregaria junto com este
    módulo e repetiria todos os comandos. Sai de Mod (vai para Usinix-complemento/Prumo3D.antigo); se não der
    para mover, recebe o arquivo ADDON_DISABLED, que faz o FreeCAD pular a pasta."""
    velha = os.path.join(FreeCAD.getUserAppDataDir(), "Mod", ANTIGO + "3D")
    aqui = os.path.dirname(os.path.abspath(__file__))
    if not os.path.isdir(velha) or os.path.normcase(os.path.realpath(velha)) == os.path.normcase(
            os.path.realpath(aqui)):
        return False
    destino = os.path.join(FreeCAD.getUserAppDataDir(), "Usinix-complemento", ANTIGO + "3D.antigo")
    try:
        if os.path.exists(destino):
            shutil.rmtree(destino, ignore_errors=True)
        os.makedirs(os.path.dirname(destino), exist_ok=True)
        shutil.move(velha, destino)
        FreeCAD.Console.PrintLog("Usinix: complemento antigo (Mod/Prumo3D) movido para %s\n" % destino)
        return True
    except Exception:
        try:
            with open(os.path.join(velha, "ADDON_DISABLED"), "w", encoding="utf-8") as f:
                f.write("Desativado pelo Usinix: o módulo agora se chama Usinix (Mod/Usinix).\n")
            return True
        except OSError as exc:
            FreeCAD.Console.PrintWarning("Usinix: não foi possível desativar Mod/Prumo3D: %s\n" % exc)
            return False


# ------------------------------------------------------------------ preferências
def _texto_novo(v):
    """Valores gravados que apontam para nomes antigos (comandos, bancada, aba, modelos de folha)."""
    if v == "prumo":                       # id da aba Usinix na faixa
        return "usinix"
    for a, b in (("Prumo_", "Usinix_"), ("PrumoWorkbench", "UsinixWorkbench"), ("/Mod/Prumo3D/", "/Mod/Usinix/"),
                 ("\\Mod\\Prumo3D\\", "\\Mod\\Usinix\\"), ("MateriaisPrumo", "MateriaisUsinix")):
        v = v.replace(a, b)
    return v


def _chave_nova(k):
    return k.replace("Prumo", "Usinix").replace("prumo", "usinix")


def _copiar_grupo(origem, destino):
    """Copia um grupo de preferências (com subgrupos), com chaves e valores nos nomes novos. Não sobrescreve o
    que já existe no destino."""
    n = 0
    try:
        conteudo = origem.GetContents() or []
    except Exception:
        conteudo = []
    existentes = {(t, k) for t, k, _v in (destino.GetContents() or [])}
    for tipo, chave, valor in conteudo:
        nova = _chave_nova(chave)
        if (tipo, nova) in existentes:
            continue
        if tipo == "String":
            destino.SetString(nova, _texto_novo(valor))
        elif tipo == "Integer":
            destino.SetInt(nova, valor)
        elif tipo == "Unsigned":
            destino.SetUnsigned(nova, valor)
        elif tipo == "Float":
            destino.SetFloat(nova, valor)
        elif tipo == "Boolean":
            destino.SetBool(nova, valor)
        else:
            continue
        n += 1
    for g in origem.GetGroups():
        n += _copiar_grupo(origem.GetGroup(g), destino.GetGroup(_chave_nova(g)))
    return n


def migrar_preferencias():
    """Uma vez: Mod/Prumo3D → Mod/Usinix (o grupo antigo sai), atalhos Prumo_X → Usinix_X, bancada lembrada
    e caminhos de ícones antigos. Devolve o número de valores copiados."""
    raiz = FreeCAD.ParamGet(PREF.rstrip("/"))
    nova = FreeCAD.ParamGet(PREF_NOVA)
    if nova.GetBool("MigracaoNomeAntigo", False):
        return 0
    n = 0
    if raiz.HasGroup(ANTIGO + "3D"):
        n = _copiar_grupo(raiz.GetGroup(ANTIGO + "3D"), nova)
        raiz.RemGroup(ANTIGO + "3D")
    # atalhos de teclado personalizados
    for caminho in ("User parameter:BaseApp/Preferences/Shortcut",
                    "User parameter:BaseApp/Preferences/Shortcut/Settings"):
        g = FreeCAD.ParamGet(caminho)
        for tipo, chave, valor in list(g.GetContents() or []):
            if tipo == "String" and chave.startswith(ANTIGO + "_"):
                novo = NOVO + chave[len(ANTIGO):]
                if not g.GetString(novo, ""):
                    g.SetString(novo, valor)
                g.RemString(chave)
                n += 1
    # bancada de abertura e listas de bancadas
    for caminho, chaves in (("User parameter:BaseApp/Preferences/General", ("AutoloadModule", "LastModule")),
                            ("User parameter:BaseApp/Preferences/Workbenches", ("Enabled", "Disabled", "Ordered"))):
        g = FreeCAD.ParamGet(caminho)
        for k in chaves:
            v = g.GetString(k, "")
            if ANTIGO + "Workbench" in v:
                g.SetString(k, v.replace(ANTIGO + "Workbench", NOVO + "Workbench"))
                n += 1
    # caminho de ícones do tema antigo (pasta PrumoIcones/PrumoIconesEscuro, que deixa de ser atualizada)
    bm = FreeCAD.ParamGet("User parameter:BaseApp/Preferences/Bitmaps")
    if bm.GetString("CustomPath" + ANTIGO, ""):
        bm.RemString("CustomPath" + ANTIGO)
        n += 1
    nova.SetBool("MigracaoNomeAntigo", True)
    return n


def limpar_pastas_antigas():
    """Caches com o nome antigo (refeitos com o nome novo quando precisa)."""
    base = FreeCAD.getUserAppDataDir()
    for nome in ("PrumoIcones", "PrumoIconesEscuro", "PrumoPisos", "PrumoUI", "PrumoUIEscuro"):
        p = os.path.join(base, nome)
        if os.path.isdir(p):
            shutil.rmtree(p, ignore_errors=True)
    try:
        cache = FreeCAD.getUserCachePath()
        p = os.path.join(cache, "PrumoPisos")
        if os.path.isdir(p):
            shutil.rmtree(p, ignore_errors=True)
    except Exception:
        pass


# ------------------------------------------------------------------ documentos salvos antes da 1.21.0
def _copiar_estado(o, velha, nova):
    try:
        o.setEditorMode(nova, o.getEditorMode(velha))
    except Exception:
        pass


def _modelo_novo(caminho):
    """Modelo de folha de até a 1.20.0 (.../Mod/Prumo3D/Resources/folhas/Prumo_A3_...svg) que não existe mais: o
    equivalente nas folhas do Usinix, ou None."""
    if not caminho or "Prumo" not in caminho or os.path.isfile(caminho):
        return None
    nome = os.path.basename(caminho.replace("\\", "/"))
    if not nome.startswith(ANTIGO + "_"):
        return None
    novo = os.path.join(os.path.dirname(os.path.abspath(__file__)), "Resources", "folhas",
                        NOVO + nome[len(ANTIGO):])
    return novo if os.path.isfile(novo) else None


def _migrar_modelo(o):
    """Aponta o modelo da folha para o arquivo novo, sem perder os textos da legenda."""
    if o.TypeId != "TechDraw::DrawSVGTemplate":
        return 0
    novo = _modelo_novo(getattr(o, "Template", ""))
    if not novo:
        return 0
    textos = dict(o.EditableTexts)
    o.Template = novo
    et = dict(o.EditableTexts)
    et.update({k: v for k, v in textos.items() if k in et})
    o.EditableTexts = et
    return 1


def migrar_documento(doc):
    """Propriedades PrumoX → UsinixX e grupo "Prumo" → "Usinix" em todos os objetos. Devolve quantas
    propriedades mudaram (de nome ou de grupo)."""
    n = 0
    try:
        objs = list(doc.Objects)
    except Exception:
        return 0
    for o in objs:
        try:
            n += _migrar_modelo(o)
        except Exception as exc:
            FreeCAD.Console.PrintLog("Usinix: modelo da folha %s: %s\n" % (o.Name, exc))
        try:
            nomes = list(o.PropertiesList)
        except Exception:
            continue
        for p in nomes:
            try:
                grupo = o.getGroupOfProperty(p)
                if p.startswith(ANTIGO) and len(p) > len(ANTIGO) and p[len(ANTIGO)].isupper():
                    novo = NOVO + p[len(ANTIGO):]
                    if grupo == ANTIGO:
                        grupo = NOVO
                    if novo not in o.PropertiesList:
                        o.addProperty(o.getTypeIdOfProperty(p), novo, grupo, o.getDocumentationOfProperty(p))
                    _copiar_estado(o, p, novo)
                    setattr(o, novo, getattr(o, p))
                    o.removeProperty(p)
                    n += 1
                elif grupo == ANTIGO:
                    o.setGroupOfProperty(p, NOVO)
                    n += 1
            except Exception as exc:
                FreeCAD.Console.PrintLog("Usinix: %s.%s (nome antigo): %s\n" % (o.Name, p, exc))
    return n


def ao_iniciar():
    """Chamado pelo Init.py antes de tudo."""
    instalar_importador()
    for passo in (desativar_complemento_antigo, migrar_preferencias, limpar_pastas_antigas):
        try:
            passo()
        except Exception as exc:  # nunca impedir o programa de abrir
            FreeCAD.Console.PrintWarning("Usinix: nome antigo (%s): %s\n" % (passo.__name__, exc))
