# SPDX-License-Identifier: LGPL-2.1-or-later
# Usinix - perfil de marca dos relatórios e das folhas (logo, nome, cores, rodapé).
"""Marca usada nos relatórios em PDF (memorial NR-13, análise estrutural, simulação) e nas folhas de desenho.

Sem pacote externo, é a do Usinix. Um pacote troca com definir(provedor), em que o provedor tem
perfil() → dict com as chaves de PADRAO (só as que mudam) e, se quiser, modelo_folha(caminho) → caminho de uma
cópia do modelo de folha com a logo da empresa.
"""

import os

HERE = os.path.dirname(os.path.abspath(__file__))
ICONES = os.path.join(HERE, "Resources", "icons")

PADRAO = {
    "nome": "USINIX",                                        # texto ao lado da logo na capa
    "descricao": "CAD 3D da metal-mecânica · software livre",
    "logo_capa": os.path.join(ICONES, "usinix.png"),          # sobre o fundo da capa (cor)
    "logo": os.path.join(ICONES, "usinix.png"),               # sobre fundo branco (cabeçalho, memorial)
    "logo_tem_nome": False,                                  # logo horizontal com o nome: não escreve o nome ao lado
    "cor": "#003A70",                                        # capa, títulos, tabelas
    "cor_destaque": "#F7BE00",                               # réguas
    "cabecalho": "USINIX",                                   # canto direito do cabeçalho das páginas
    "rodape": "Gerado no Usinix",                            # rodapé das páginas
    "rodape_linhas": [],                                     # linhas extras (empresa, CREA, CNPJ, contato)
    "empresa": "",                                           # padrão do campo Empresa da legenda
    "responsavel": "",                                       # padrão do responsável técnico
    "registro": "",                                          # CREA/CFT do responsável
    "cidade": "",
}

_ESTADO = {"provedor": None}


def definir(provedor):
    """provedor: objeto com perfil() e, opcional, modelo_folha(caminho); None volta à marca do Usinix."""
    _ESTADO["provedor"] = provedor


def atual():
    """Perfil em uso (cópia; as chaves que o provedor não informa vêm do Usinix)."""
    p = dict(PADRAO)
    prov = _ESTADO["provedor"]
    if prov is not None:
        try:
            extra = prov.perfil() or {}
            p.update({k: v for k, v in extra.items() if v is not None})
        except Exception as exc:
            import FreeCAD
            FreeCAD.Console.PrintWarning("Usinix: perfil de marca: %s\n" % exc)
    for chave in ("logo", "logo_capa"):
        if p.get(chave) and not os.path.isfile(p[chave]):
            p[chave] = PADRAO[chave]
    return p


def propria():
    """True quando a marca não é a do Usinix (um pacote definiu outra)."""
    return _ESTADO["provedor"] is not None


def modelo_folha(caminho):
    """Modelo de folha a usar: o do provedor (com a logo da empresa) ou o próprio."""
    prov = _ESTADO["provedor"]
    if prov is not None and hasattr(prov, "modelo_folha"):
        try:
            novo = prov.modelo_folha(caminho)
            if novo and os.path.isfile(novo):
                return novo
        except Exception as exc:
            import FreeCAD
            FreeCAD.Console.PrintWarning("Usinix: folha com a marca: %s\n" % exc)
    return caminho


def desenhar_logo(painter, rect, caminho, alinhar="esquerda"):
    """Desenha a logo dentro de rect (QRectF) mantendo a proporção. Devolve o QRectF ocupado (ou None)."""
    from PySide import QtCore, QtGui
    if not caminho or not os.path.isfile(caminho):
        return None
    if caminho.lower().endswith(".svg"):
        try:
            from PySide import QtSvg
            r = QtSvg.QSvgRenderer(caminho)
            tam = r.defaultSize()
            w0, h0 = float(tam.width() or 1), float(tam.height() or 1)
        except Exception:
            return None
    else:
        img = QtGui.QImage(caminho)
        if img.isNull():
            return None
        w0, h0 = float(img.width()), float(img.height())
    esc = min(rect.width() / w0, rect.height() / h0)
    w, h = w0 * esc, h0 * esc
    x = rect.x() if alinhar == "esquerda" else (rect.right() - w if alinhar == "direita" else rect.center().x() - w / 2)
    alvo = QtCore.QRectF(x, rect.center().y() - h / 2, w, h)
    if caminho.lower().endswith(".svg"):
        r.render(painter, alvo)
    else:
        painter.drawImage(alvo, img)
    return alvo
