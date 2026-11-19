# SPDX-License-Identifier: LGPL-2.1-or-later
"""Configuração dos efeitos de um documento.

Fica num objeto simples do documento (App::FeaturePython sem classe Python: o arquivo abre em qualquer FreeCAD),
com os mesmos nomes de propriedade da configuração de cena do ShowRoom; um documento feito com o ShowRoom é
reconhecido pelos mesmos nomes.
"""
import FreeCAD

NOME = "EfeitosDaVista"
MARCAS = ("AmbientOcclusion", "ShadowCatcher")
_usados = set()          # documentos que já tiveram efeito nesta sessão (para desligar limpa a vista)


_achado = {}             # documento -> nome do objeto de configuração (None = não tem); ver esquecer()


def esquecer(doc=None):
    """Depois de abrir, desfazer ou refazer: procura a configuração de novo na próxima consulta."""
    try:
        if doc is None:
            _achado.clear()
        else:
            _achado.pop(doc.Name, None)
    except ReferenceError:
        pass


def _e_config(obj):
    try:
        pl = obj.PropertiesList
        return all(m in pl for m in MARCAS)
    except Exception:
        return False


def getSceneFolder(doc=None, create=False):
    doc = doc or FreeCAD.ActiveDocument
    if doc is None:
        return None
    try:
        nome = doc.Name
        # consultas baratas primeiro: isto roda a cada peça criada ou mudada
        obj = doc.getObject(NOME)
        if obj is not None and _e_config(obj):
            _usados.add(nome)
            return obj
        if _achado.get(nome):
            obj = doc.getObject(_achado[nome])
            if obj is not None and _e_config(obj):
                return obj
            _achado.pop(nome, None)
        if nome not in _achado:
            # configuração com outro nome (documento feito com o ShowRoom): procura uma vez
            achado = None
            for obj in doc.Objects:
                if _e_config(obj):
                    achado = obj
                    break
            if achado is not None or not getattr(doc, "Restoring", False):
                _achado[nome] = achado.Name if achado is not None else None
            if achado is not None:
                _usados.add(nome)
                return achado
    except ReferenceError:
        return None
    return criar(doc) if create else None


def criar(doc):
    obj = doc.addObject("App::FeaturePython", NOME)
    obj.Label = "Efeitos da vista"
    obj.addProperty("App::PropertyBool", "ShadowCatcher", "Efeitos", "Sombra do modelo num chão invisível")
    obj.addProperty("App::PropertyBool", "AmbientOcclusion", "Efeitos",
                    "Realce de cantos: escurece cantos, furos e encostos")
    obj.addProperty("App::PropertyFloat", "ShadowDarkness", "Efeitos", "Sombra no chão: escuro (0 a 1)")
    obj.ShadowDarkness = 0.45
    obj.addProperty("App::PropertyFloat", "ShadowSoftness", "Efeitos", "Sombra no chão: suavidade (0 a 1)")
    obj.ShadowSoftness = 0.4
    obj.addProperty("App::PropertyFloat", "AOIntensity", "Efeitos", "Realce de cantos: intensidade")
    obj.AOIntensity = 1.0
    if FreeCAD.GuiUp:
        try:
            obj.ViewObject.ShowInTree = False
        except Exception:
            pass
    _usados.add(doc.Name)
    _achado[doc.Name] = obj.Name
    return obj


def em_uso(doc):
    """O documento tem (ou teve nesta sessão) efeitos: só esses são acompanhados."""
    try:
        return doc.Name in _usados or getSceneFolder(doc) is not None
    except ReferenceError:
        return False
