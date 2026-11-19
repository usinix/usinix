# SPDX-License-Identifier: LGPL-2.1-or-later
"""Efeitos da vista e texturas da Aparência: sombra no chão, realce de cantos, textura de material e brilho.

A parte gráfica é o pacote UsinixCenaFX (motor do ShowRoom, de OficineRobotica, LGPL-2.1-or-later). Aqui fica o
que o Usinix usa dele, em português: liga e desliga por documento (desligado por padrão: os efeitos pesam na
vista) e textura por peça, guardada dentro do documento.
"""
import os

import FreeCAD

AQUI = os.path.dirname(os.path.abspath(__file__))
PASTA_TEXTURAS = os.path.join(AQUI, "UsinixCenaFX", "Texturas")
TEXTURAS = (("Aço escovado", "BrushedMetal.jpg"), ("Concreto", "Concrete.jpg"), ("Madeira", "Wood.jpg"),
            ("Fibra de carbono", "CarbonFibre.jpg"), ("Plástico texturizado", "PlasticGrain.jpg"))
ESCALA_MATERIAL = 250.0       # mm de uma repetição das texturas de material da lista
SEM_TEXTURA = "Sem textura"
OUTRA_IMAGEM = "Outra imagem…"


def _fx():
    from UsinixCenaFX import ambient_occlusion, config, textures, view_rig
    return ambient_occlusion, config, textures, view_rig


def disponivel():
    """Os efeitos precisam da interface e de um Coin com sombreadores."""
    if not FreeCAD.GuiUp:
        return False
    try:
        return bool(_fx()[0].available())
    except Exception:
        return False


def instalar():
    """Liga o acompanhamento dos documentos (ao abrir o programa): texturas e efeitos gravados num arquivo
    aparecem ao abrir. Documento sem efeito nem textura não paga nada."""
    if not FreeCAD.GuiUp:
        return False
    try:
        _ao, _config, textures, view_rig = _fx()
        textures.install()
        view_rig._ensure_hooks()
        view_rig.schedule_sync()
        return True
    except Exception as exc:
        FreeCAD.Console.PrintLog("Usinix: efeitos da vista indisponíveis: %s\n" % exc)
        return False


# ---------------------------------------------------------------------------- efeitos do documento
def estado(doc=None):
    """{"sombra": bool, "realce": bool} do documento."""
    doc = doc or FreeCAD.ActiveDocument
    try:
        cfg = _fx()[1].getSceneFolder(doc) if doc is not None else None
    except Exception:
        cfg = None
    return {"sombra": bool(getattr(cfg, "ShadowCatcher", False)), "realce": bool(getattr(cfg, "AmbientOcclusion", False))}


def definir(doc=None, sombra=None, realce=None):
    """Liga ou desliga a sombra no chão e o realce de cantos do documento (None = não mexe)."""
    doc = doc or FreeCAD.ActiveDocument
    if doc is None:
        return estado(doc)
    _ao, config, _tx, view_rig = _fx()
    quer_ligar = bool(sombra) or bool(realce)
    cfg = config.getSceneFolder(doc, create=quer_ligar)
    if cfg is None:
        return estado(doc)
    if (sombra or realce) and not disponivel():
        raise RuntimeError("Esta placa de vídeo (ou este programa) não tem os sombreadores que os efeitos pedem.")
    if sombra is not None and "ShadowCatcher" in cfg.PropertiesList and bool(cfg.ShadowCatcher) != bool(sombra):
        cfg.ShadowCatcher = bool(sombra)
    if realce is not None and "AmbientOcclusion" in cfg.PropertiesList and bool(cfg.AmbientOcclusion) != bool(realce):
        cfg.AmbientOcclusion = bool(realce)
    view_rig.schedule_sync(doc)
    return estado(doc)


# ---------------------------------------------------------------------------- textura da peça
def dono_da_textura(obj):
    return _fx()[2].texture_owner(obj)


def textura_de(obj):
    """Nome da textura da peça ("" = nenhuma): o nome da lista, ou o do arquivo da imagem."""
    try:
        textures = _fx()[2]
        dono = textures.texture_owner(obj)
        if not textures.image_of(dono):
            return ""
        origem = str(getattr(dono, "TextureSource", "") or "")
    except Exception:
        return ""
    for nome, arq in TEXTURAS:
        if arq == origem:
            return nome
    return origem or "Imagem"


def escala_de(obj):
    try:
        dono = dono_da_textura(obj)
        return float(dono.TextureScale) if "TextureScale" in dono.PropertiesList else 0.0
    except Exception:
        return 0.0


def aplicar_textura(obj, textura, escala=None):
    """Textura da lista (pelo nome) ou imagem do usuário (caminho) na peça; a imagem fica dentro do documento."""
    caminho = dict(TEXTURAS).get(textura)
    caminho = os.path.join(PASTA_TEXTURAS, caminho) if caminho else textura
    if not caminho or not os.path.isfile(caminho):
        raise ValueError("Imagem não encontrada: %s" % textura)
    textures = _fx()[2]
    textures.install()
    dono = textures.texture_owner(obj)
    if escala is None and textura in dict(TEXTURAS) and "TextureScale" not in dono.PropertiesList:
        escala = ESCALA_MATERIAL                 # textura de material: tamanho real, não o da peça
    textures.apply(dono, caminho, scale=escala)
    return dono


def tirar_textura(obj):
    textures = _fx()[2]
    dono = textures.texture_owner(obj)
    if "TextureImage" in dono.PropertiesList:
        textures.remove(dono)
    return dono


def definir_escala(obj, escala):
    dono = dono_da_textura(obj)
    if "TextureScale" in dono.PropertiesList and escala > 0:
        dono.TextureScale = float(escala)


# ---------------------------------------------------------------------------- brilho
def brilho_de(vo):
    """Brilho do material da peça, de 0 a 100 (None se a peça não tem material de aparência)."""
    try:
        return int(round(float(vo.ShapeAppearance[0].Shininess) * 100.0))
    except Exception:
        return None


def definir_brilho(vo, pct):
    pct = min(max(float(pct), 0.0), 100.0)
    mats = list(vo.ShapeAppearance)
    e = 0.10 + 0.75 * pct / 100.0
    for m in mats:
        m.Shininess = pct / 100.0
        m.SpecularColor = (e, e, e, 1.0)
    vo.ShapeAppearance = mats
