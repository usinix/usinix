# SPDX-License-Identifier: LGPL-2.1-or-later
# Usinix - folhas de desenho ABNT (A0 a A4) e criação de folha com vistas e legenda preenchida.
"""Folhas de desenho no padrão brasileiro.

Modelos em Resources/folhas, gerados por prumo-build/ferramentas/gerar_folhas_abnt.py:
- NBR 16752:2020 (publicada em 23/01/2020, em vigor no catálogo ABNT/Confea em 10/11/2026; Tabela 4 conferida no
  texto da norma: margem esquerda 20 mm, demais 10 mm, quadro 1,0 mm no A0/A1 e 0,7 mm no A2 a A4; legenda de
  180 mm no canto inferior direito, com os campos de 5.3.1);
- NBR 10068:1987 (cancelada em 23/01/2020, substituída pela NBR 16752:2020; mantida só para continuar desenhos
  antigos: margem esquerda 25 mm, legenda 175/178 mm — medidas não conferidas, a norma não está mais à venda).
Todos os formatos em paisagem e em retrato. Legenda com empresa, cliente/obra, título,
material, massa, tolerâncias gerais, desenhista, verificado, aprovado, data, responsável técnico,
CREA/CFT, ART, escala, unidade, 1º diedro, formato, folha, número do desenho e revisão.
"""

import math
import os
import time

import FreeCAD
import FreeCADGui

import PrumoUtil

try:
    from PySide import QtCore, QtWidgets
except ImportError:  # pragma: no cover
    from PySide2 import QtCore, QtWidgets

DIR_FOLHAS = os.path.join(PrumoUtil.RES_DIR, "folhas")
FORMATOS = ["A0", "A1", "A2", "A3", "A4"]
FORMATOS_MM = {"A0": (1189.0, 841.0), "A1": (841.0, 594.0), "A2": (594.0, 420.0), "A3": (420.0, 297.0),
               "A4": (297.0, 210.0)}     # largura × altura deitada
NORMAS = {"NBR16752": "ABNT NBR 16752:2020 (em vigor)",
          "NBR10068": "ABNT NBR 10068:1987 (cancelada em 2020; só para desenhos antigos)"}
NORMA_PADRAO = "NBR16752"
FORMATO_PADRAO = "A3"

CAMPOS = ["empresa", "cliente", "titulo", "tipo_doc", "material", "massa", "tolerancias", "projetista", "desenhista",
          "verificado", "aprovado", "data", "resp_tecnico", "crea", "art", "escala", "unidade",
          "formato", "folha", "numero", "revisao"]


def arquivo(formato, norma=NORMA_PADRAO, retrato=None):
    if retrato is None:
        retrato = formato == "A4"
    nome = "Prumo_%s_%s_%s.svg" % (formato, "Retrato" if retrato else "Paisagem", norma)
    return os.path.join(DIR_FOLHAS, nome)


def lista_modelos():
    if not os.path.isdir(DIR_FOLHAS):
        return []
    return sorted(os.path.join(DIR_FOLHAS, n) for n in os.listdir(DIR_FOLHAS) if n.endswith(".svg"))


ESTILO_DESENHO_VERSAO = 1


def aplicar_estilo_desenho(forcar=False):
    """Linhas e texto do Desenho técnico no padrão do Usinix (uma vez por versão do estilo).

    - Grupo de linhas 0,35 mm (grossa 0,35, fina 0,18): o padrão do FreeCAD (0,70) deixava as vistas pesadas
      nas folhas A4/A3.
    - Texto das cotas e rótulos em Poppins, a fonte da interface (as folhas ABNT usam a mesma).
    - Pontos dos vértices só com o mouse sobre a vista (para pegar pontos de cota), não o tempo todo."""
    g = FreeCAD.ParamGet(PrumoUtil.PARAM_PATH)
    if not forcar and g.GetInt("EstiloDesenhoVersao", 0) >= ESTILO_DESENHO_VERSAO:
        return False
    base = "User parameter:BaseApp/Preferences/Mod/TechDraw/"
    FreeCAD.ParamGet(base + "Decorations").SetInt("LineGroup", 1)          # "FC 0.35mm" em LineGroup.csv
    FreeCAD.ParamGet(base + "Labels").SetString("LabelFont", "Poppins")
    FreeCAD.ParamGet(base + "General").SetBool("VerticesAlwaysVisible", False)
    g.SetInt("EstiloDesenhoVersao", ESTILO_DESENHO_VERSAO)
    return True


def aplicar_preferencias(forcar=False):
    """Faz do modelo ABNT A3 (NBR 16752) o padrão do Desenho técnico.

    Só muda na primeira vez (ou se a preferência aponta para um arquivo que não existe), para
    respeitar a escolha do usuário depois."""
    try:
        aplicar_estilo_desenho()
    except Exception as exc:
        FreeCAD.Console.PrintLog("Usinix: estilo do desenho: %s\n" % exc)
    g = FreeCAD.ParamGet(PrumoUtil.PARAM_PATH)
    f = FreeCAD.ParamGet("User parameter:BaseApp/Preferences/Mod/TechDraw/Files")
    atual = f.GetString("TemplateFile", "")
    padrao = arquivo(FORMATO_PADRAO)
    if not os.path.isfile(padrao):
        return False
    if forcar or not g.GetBool("FolhasABNTAplicadas", False) or (atual and not os.path.isfile(atual)):
        f.SetString("TemplateFile", padrao)
        f.SetString("TemplateDir", DIR_FOLHAS)
        g.SetBool("FolhasABNTAplicadas", True)
        # 1º diedro, como na prática brasileira
        FreeCAD.ParamGet("User parameter:BaseApp/Preferences/Mod/TechDraw/General").SetInt("ProjectionAngle", 0)
        return True
    return False


def campos_padrao(doc, objs=None):
    """Valores iniciais da legenda a partir do documento e das peças selecionadas."""
    v = {"data": time.strftime("%d/%m/%Y"), "unidade": "mm", "revisao": "0",
         "titulo": doc.Label if doc else "", "empresa": getattr(doc, "Company", "") or "",
         "desenhista": getattr(doc, "CreatedBy", "") or "", "folha": "1 / 1"}
    g = FreeCAD.ParamGet(PrumoUtil.PARAM_PATH)
    for chave in ("empresa", "resp_tecnico", "crea", "tolerancias"):
        salvo = g.GetString("Folha_" + chave, "")
        if salvo and not v.get(chave):
            v[chave] = salvo
    if objs and len(objs) == 1:
        # uma peça: a legenda vem das propriedades dela (código, denominação, revisão, material, massa)
        try:
            import PrumoPropriedades
            v.update({k: val for k, val in PrumoPropriedades.legenda_de(objs[0]).items() if val})
            return v
        except Exception:
            pass
    if objs:
        try:
            import PrumoMassa
            r = PrumoMassa.calcular(objs)
            if r.massa > 0:
                v["massa"] = PrumoUtil.fmt(r.massa, 3)
            mats = {it[1] for it in r.itens if it[5]}
            if len(mats) == 1:
                v["material"] = mats.pop()
        except Exception:
            pass
    return v


def lembrar_campos(campos):
    """Guarda empresa, responsável técnico, CREA e tolerâncias para as próximas folhas."""
    g = FreeCAD.ParamGet(PrumoUtil.PARAM_PATH)
    for chave in ("empresa", "resp_tecnico", "crea", "tolerancias"):
        if campos.get(chave):
            g.SetString("Folha_" + chave, campos[chave])


def nova_folha(doc, formato=FORMATO_PADRAO, norma=NORMA_PADRAO, retrato=None, campos=None,
               objs=None, escala=None, arranjo="3vistas_iso"):
    """Cria a folha com o modelo ABNT e a legenda preenchida. Com `objs`, coloca as vistas
    (frontal, superior e lateral no 1º diedro) e a isométrica. Retorna a folha."""
    caminho = arquivo(formato, norma, retrato)
    if not os.path.isfile(caminho):
        raise FileNotFoundError(caminho)
    doc.openTransaction("Nova folha ABNT")
    page = doc.addObject("TechDraw::DrawPage", "Folha")
    page.Label = "Folha %s" % formato
    tpl = doc.addObject("TechDraw::DrawSVGTemplate", "Modelo")
    tpl.Label = "Modelo %s %s" % (formato, NORMAS[norma].split(" (")[0])
    tpl.Template = caminho
    page.Template = tpl
    doc.recompute()
    valores = campos_padrao(doc, objs)
    valores["formato"] = formato
    if campos:
        valores.update({k: v for k, v in campos.items() if v is not None})
    if escala:
        page.Scale = escala
        valores["escala"] = _texto_escala(escala)
    et = dict(tpl.EditableTexts)
    for k, val in valores.items():
        if k in et:
            et[k] = str(val)
    tpl.EditableTexts = et
    if objs and len(objs) == 1:
        try:
            import PrumoPropriedades
            PrumoPropriedades.vincular_folha(page, objs[0])
        except Exception as exc:
            FreeCAD.Console.PrintLog("Usinix: folha ligada à peça: %s\n" % exc)
    if objs:
        _vistas(doc, page, objs, escala, arranjo)
        valores["escala"] = _texto_escala(page.Scale)
        et = dict(tpl.EditableTexts)
        et["escala"] = valores["escala"]
        tpl.EditableTexts = et
    doc.recompute()
    doc.commitTransaction()
    return page


def _texto_escala(e):
    if e >= 1:
        n = round(e, 2)
        return ("%g:1" % n).replace(".", ",")
    return ("1:%g" % round(1.0 / e, 2)).replace(".", ",")


# série 1-2-5 (ISO 5455 / NBR 8196): ampliação, natural e redução
ESCALAS_NORMAIS = [50, 20, 10, 5, 2, 1, 1 / 2.0, 1 / 5.0, 1 / 10.0, 1 / 20.0, 1 / 50.0,
                   1 / 100.0, 1 / 200.0, 1 / 500.0, 1 / 1000.0]


# arranjos prontos de vistas (1º diedro): projeções do grupo + isométrica
ARRANJOS = {
    "3vistas_iso": ("Frontal, superior, lateral e isométrica", ("Front", "Top", "Left"), True),
    "frontal_lateral_iso": ("Frontal, lateral e isométrica", ("Front", "Left"), True),
    "frontal_superior": ("Frontal e superior", ("Front", "Top"), False),
    "frontal_iso": ("Frontal e isométrica", ("Front",), True),
    "so_iso": ("Só a isométrica", (), True),
}
ARRANJO_PADRAO = "3vistas_iso"

ESPACO_VISTAS = 15.0     # mm entre as vistas na folha (como o espaçamento automático do TechDraw)
FATOR_ISO = 0.6          # a isométrica sai menor que as vistas ortogonais


def _caixa(objs):
    bb = None
    for _o, sh in PrumoUtil.pecas(objs):
        bb = sh.BoundBox if bb is None else bb.united(sh.BoundBox)
    return bb


def _medidas_iso(bb):
    """(largura, altura) aproximadas da isométrica (direção 1,-1,1) em escala 1."""
    w = (bb.XLength + bb.YLength) * math.cos(math.radians(30))
    h = bb.ZLength + (bb.XLength + bb.YLength) * 0.5
    return w, h


def _medidas_arranjo(bb, projecoes=("Front", "Top", "Left"), iso=True):
    """(largura, altura) do conjunto em escala 1, sem os espaços entre as vistas: (larg, alt, n_col, n_lin)."""
    p = set(projecoes)
    larg = alt = 0.0
    col = lin = 0
    if "Front" in p:
        larg += bb.XLength
        alt += bb.ZLength
        col += 1
        lin += 1
    if p & {"Left", "Right"}:
        larg += bb.YLength * len(p & {"Left", "Right"})
        col += len(p & {"Left", "Right"})
    if p & {"Top", "Bottom"}:
        alt += bb.YLength * len(p & {"Top", "Bottom"})
        lin += len(p & {"Top", "Bottom"})
    if "Rear" in p:
        larg += bb.XLength
        col += 1
    iw = ih = 0.0
    if iso:
        iw, ih = _medidas_iso(bb)
        iw, ih = iw * FATOR_ISO, ih * FATOR_ISO
        col += 1
    return larg, alt, iw, ih, col, lin


def escala_que_cabe(objs, larg_util, alt_util, projecoes=("Front", "Top", "Left"), iso=True):
    """Maior escala normalizada em que as vistas do arranjo cabem lado a lado."""
    bb = _caixa(objs)
    if bb is None:
        return 1.0
    larg, alt, iw, ih, col, lin = _medidas_arranjo(bb, projecoes, iso)
    for e in ESCALAS_NORMAIS:
        # 1º diedro: frontal (X×Z) + laterais (Y×Z) lado a lado; superior/inferior (X×Y) embaixo/em cima
        L = (larg + iw) * e + max(col - 1, 0) * ESPACO_VISTAS + (ESPACO_VISTAS if iso and larg else 0)
        A = max(alt * e + max(lin - 1, 0) * ESPACO_VISTAS, ih * e)
        if L <= larg_util and A <= alt_util:
            return e
    return ESCALAS_NORMAIS[-1]


def _tamanho_folha(page):
    try:
        return float(page.Template.Width), float(page.Template.Height)
    except Exception:
        return 420.0, 297.0


def posicionar(page, fontes, grupo=None, iso=None, escala=None):
    """Escala normalizada que cabe e posição do grupo de projeção e da isométrica na folha.

    O conjunto fica centrado na largura útil, no alto da folha (longe da legenda); a isométrica à direita."""
    larg, alt = _tamanho_folha(page)
    projecoes = tuple(v.Type for v in grupo.Views) if grupo is not None else ()
    com_iso = iso is not None
    e = escala or escala_que_cabe(fontes, larg - 30, alt - 20 - 60, projecoes, com_iso)
    page.Scale = e
    bb = _caixa(fontes)
    topo = 28.0                               # do alto da folha até o alto das vistas
    direita_grupo = 20.0
    if grupo is not None:
        if bb is not None:
            lg, _ag, iw, _ih, col, _lin = _medidas_arranjo(bb, projecoes, com_iso)
            fx, fy, fz = bb.XLength * e, bb.YLength * e, bb.ZLength * e
            total = (lg + iw) * e + max(col - 1, 0) * ESPACO_VISTAS + (ESPACO_VISTAS if com_iso else 0)
            x0 = 20.0 + max(10.0, ((larg - 30.0) - total) / 2.0)
            # 1º diedro: a lateral direita fica à esquerda da frontal; a posterior, na ponta
            esq = 0.0
            if "Right" in projecoes:
                esq += fy + ESPACO_VISTAS
            grupo.X = x0 + esq + fx / 2.0
            acima = fy + ESPACO_VISTAS if "Bottom" in projecoes else 0.0
            abaixo = fy + ESPACO_VISTAS if "Top" in projecoes else 0.0
            # no meio da faixa entre a legenda e o alto do quadro, com folga para as cotas gerais
            # (antes ficava colado no alto, com a metade de baixo da folha vazia)
            y_min, y_max = _faixa_vertical(page, alt)
            altura = acima + fz + abaixo
            topo_grupo = (y_min + y_max) / 2.0 + altura / 2.0
            if topo_grupo > y_max or topo_grupo - altura < y_min:
                topo_grupo = alt - topo
            grupo.Y = topo_grupo - acima - fz / 2.0
            direita_grupo = x0 + (lg * e) + max(col - (2 if com_iso else 1), 0) * ESPACO_VISTAS
        else:
            grupo.X, grupo.Y, direita_grupo = larg * 0.42, (alt + 60) * 0.55, larg * 0.6
    if iso is not None:
        iso.ScaleType = "Custom"
        iso.Scale = e * FATOR_ISO
        if bb is not None:
            iw, ih = _medidas_iso(bb)
            iw, ih = iw * iso.Scale, ih * iso.Scale
            if grupo is None:          # só a isométrica: no meio da área útil, acima da legenda
                iso.X = 20.0 + (larg - 30.0) / 2.0
                iso.Y = 70.0 + (alt - 80.0) / 2.0
            else:                      # à direita das vistas, no alto (longe da legenda)
                iso.X = min(larg - 20.0 - iw / 2.0, direita_grupo + 2 * ESPACO_VISTAS + iw / 2.0)
                iso.Y = alt - topo - ih / 2.0
        else:
            iso.X, iso.Y = larg * 0.80, alt * 0.70
    escrever_escala(page)
    return e


FOLGA_COTAS = 14.0       # mm livres em volta das vistas para as cotas gerais (ficam a 8 mm do contorno)


def _faixa_vertical(page, alt):
    """(y de baixo, y de cima) em mm da faixa útil para as vistas: da legenda até o alto do quadro,
    descontada a folga das cotas."""
    try:
        import PrumoBOM
        _e, _d, sup, inf = PrumoBOM.margens_da_folha(page)
        leg = PrumoBOM.altura_legenda(page)
    except Exception:
        sup, inf, leg = 10.0, 10.0, None
    leg = leg if leg else 60.0
    return inf + leg + FOLGA_COTAS, alt - sup - FOLGA_COTAS


def escrever_escala(page):
    """Põe a escala da folha no campo ESCALA da legenda."""
    try:
        tpl = page.Template
        et = dict(tpl.EditableTexts)
        if "escala" in et and et["escala"] != _texto_escala(page.Scale):
            et["escala"] = _texto_escala(page.Scale)
            tpl.EditableTexts = et
    except Exception:
        pass


def novo_grupo(doc, page, fontes, projecoes=("Front",)):
    grupo = doc.addObject("TechDraw::DrawProjGroup", "Vistas")
    grupo.Label = "Vistas"
    page.addView(grupo)
    grupo.Source = fontes
    grupo.ProjectionType = "First angle"
    grupo.ScaleType = "Page"
    for pr in projecoes:     # no 1º diedro a vista lateral esquerda fica à direita da frontal
        grupo.addProjection(pr)
    grupo.AutoDistribute = True
    return grupo


def nova_iso(doc, page, fontes):
    iso = doc.addObject("TechDraw::DrawViewPart", "Isometrica")
    iso.Label = "Isométrica"
    page.addView(iso)
    iso.Source = fontes
    iso.Direction = FreeCAD.Vector(1, -1, 1)
    iso.XDirection = FreeCAD.Vector(1, 1, 0)
    iso.ScaleType = "Custom"
    return iso


def _vistas(doc, page, objs, escala=None, arranjo=ARRANJO_PADRAO):
    fontes = [o for o, _sh in PrumoUtil.pecas(objs)]
    fontes = list(dict.fromkeys(objs if objs else fontes))
    _rot, projecoes, com_iso = ARRANJOS.get(arranjo, ARRANJOS[ARRANJO_PADRAO])
    # escala ANTES de criar as vistas: as projeções feitas com a folha ainda em 1:1 guardavam a geometria em
    # tamanho natural (estrutura de 6 m estourava a folha, só a frontal se refazia na escala certa)
    if not escala:
        larg, alt = _tamanho_folha(page)
        escala = escala_que_cabe(fontes, larg - 30, alt - 20 - 60, projecoes, com_iso)
    page.Scale = escala
    doc.recompute()
    grupo = novo_grupo(doc, page, fontes, projecoes) if projecoes else None
    iso = nova_iso(doc, page, fontes) if com_iso else None
    posicionar(page, fontes, grupo, iso, escala)
    doc.recompute()
    # as projeções criadas antes da escala da folha ficar pronta guardam a escala velha (vistas pequenas
    # ao lado de uma frontal grande): tocar faz o TechDraw refazê-las na escala certa
    for v in (list(grupo.Views) if grupo is not None else []) + ([iso] if iso is not None else []):
        v.touch()
    doc.recompute()
    return grupo if grupo is not None else iso


# ============================================================================ diálogo
import PrumoPainel as P

CAMPOS_LEGENDA = (("titulo", "Título", "texto"), ("tipo_doc", "Tipo de documento", "folha"),
                  ("numero", "Nº do desenho", "quantidade"),
                  ("empresa", "Empresa", "folha"), ("cliente", "Cliente / obra", "folha"),
                  ("material", "Material", "material"), ("tolerancias", "Tolerâncias gerais", "folga"),
                  ("projetista", "Projetista", "texto"), ("desenhista", "Desenhista", "texto"),
                  ("resp_tecnico", "Responsável técnico", "texto"),
                  ("crea", "CREA / CFT", "texto"), ("art", "ART nº", "quantidade"), ("revisao", "Revisão", "texto"))


def _filtro_pecas(obj, subs):
    return [(obj.Label, obj)] if PrumoUtil.pecas([obj]) else []


class ListaDePecas:
    """Busca + lista do que tem sólido no documento, para escolher a peça no próprio painel (sem ir à
    árvore). Usada pela Nova folha ABNT e pela Paleta de vistas. Precisa de self.doc e self.pecas (caixa);
    `unica=True` deixa marcar só uma (a Paleta trabalha com uma peça por vez)."""

    def _montar_lista_pecas(self, s0, unica=False):
        self._lista_unica = unica
        self.busca = QtWidgets.QLineEdit()
        self.busca.setPlaceholderText("Buscar peça, corpo ou montagem…")
        self.busca.setClearButtonEnabled(True)
        s0.widget(self.busca)
        self.lista = QtWidgets.QListWidget()
        self.lista.setObjectName("PrumoListaPecas")
        self.lista.setMinimumHeight(130)
        self.lista.setIconSize(QtCore.QSize(20, 20))
        s0.widget(self.lista)
        self._encher_lista()
        self.busca.textChanged.connect(self._filtrar)
        self.lista.itemChanged.connect(self._item_marcado)
        self.lista.itemDoubleClicked.connect(
            lambda it: it.setCheckState(QtCore.Qt.Unchecked if it.checkState() == QtCore.Qt.Checked
                                        else QtCore.Qt.Checked))
        self.pecas.mudou.connect(self._marcar_da_caixa)

    def _encher_lista(self):
        import PrumoInserirDesenho as I
        self.lista.blockSignals(True)
        self.lista.clear()
        try:
            cands = I.candidatos(self.doc)
        except Exception:
            cands = []
        cands.sort(key=lambda o: (not I._visivel(o), o.Label.lower()))
        marcados = {o.Name for o in self.pecas.valores()}
        for o in cands:
            it = QtWidgets.QListWidgetItem("%s  ·  %s%s" % (o.Label, I.tipo_legivel(o),
                                                            "" if I._visivel(o) else " (oculto)"))
            try:
                it.setIcon(o.ViewObject.Icon)
            except Exception:
                pass
            it.setData(QtCore.Qt.UserRole, o.Name)
            it.setFlags(it.flags() | QtCore.Qt.ItemIsUserCheckable)
            it.setCheckState(QtCore.Qt.Checked if o.Name in marcados else QtCore.Qt.Unchecked)
            self.lista.addItem(it)
        self.lista.blockSignals(False)

    def _filtrar(self, texto):
        t = (texto or "").strip().lower()
        for i in range(self.lista.count()):
            it = self.lista.item(i)
            it.setHidden(bool(t) and t not in it.text().lower())

    def _item_marcado(self, it):
        o = self.doc.getObject(it.data(QtCore.Qt.UserRole)) if self.doc else None
        if o is None:
            return
        if it.checkState() == QtCore.Qt.Checked:
            if getattr(self, "_lista_unica", False):
                for v in list(self.pecas.valores()):
                    if v is not o:
                        self.pecas.remover_valor(v)
            self.pecas.aceitar(o)
        else:
            self.pecas.remover_valor(o)

    def _marcar_da_caixa(self):
        marcados = {o.Name for o in self.pecas.valores()}
        self.lista.blockSignals(True)
        for i in range(self.lista.count()):
            it = self.lista.item(i)
            it.setCheckState(QtCore.Qt.Checked if it.data(QtCore.Qt.UserRole) in marcados
                             else QtCore.Qt.Unchecked)
        self.lista.blockSignals(False)



class PainelFolha(ListaDePecas, P.PainelTarefa):
    titulo = "Nova folha ABNT"
    ajuda = "Marque na lista (ou selecione na tela) as peças para as vistas e confira a legenda."

    def __init__(self, doc=None, objs=None):
        self.doc = doc or FreeCAD.ActiveDocument
        self._objs_iniciais = list(objs or [])
        super().__init__()

    def montar(self):
        f = self.form
        s0 = f.secao("Peças", "selecao")
        self.pecas = f.caixa(s0, "Peças para as vistas", _filtro_pecas, minimo=0,
                             dica="Peças, corpos, partes ou montagens. Sem peças, a folha sai em branco.")
        for o in self._objs_iniciais:
            self.pecas.aceitar(o)
        self._montar_lista_pecas(s0)
        s1 = f.secao("Folha", "folha")
        self.formato = s1.linha("folha", P.lista(FORMATOS, FREECAD_PARAM().GetString("FolhaFormato",
                                                                                       FORMATO_PADRAO)),
                                "A0 a A4.", "Formato")
        self.orientacao = s1.linha("altura", P.Opcoes([
            ("horizontal", "Horizontal", _icone_orientacao(False), "Folha deitada (paisagem)"),
            ("vertical", "Vertical", _icone_orientacao(True), "Folha em pé (retrato)")],
            FREECAD_PARAM().GetString("FolhaOrientacao", "horizontal")), "Folha deitada ou em pé.", "Orientação")
        for b in self.orientacao.botoes.values():
            b.setIconSize(QtCore.QSize(42, 30))
        self.norma = QtWidgets.QComboBox()
        for k, v in NORMAS.items():
            self.norma.addItem(v, k)
        idx = self.norma.findData(FREECAD_PARAM().GetString("FolhaNorma", NORMA_PADRAO))
        self.norma.setCurrentIndex(max(idx, 0))
        s1.linha("tipo", self.norma, "Modelo da folha: NBR 16752:2020, a norma em vigor. A NBR 10068 foi cancelada "
                 "em 2020; use só para continuar desenhos antigos.", "Padrão da folha")
        s2 = f.secao("Legenda", "texto")
        valores = campos_padrao(self.doc, self.pecas.valores())
        self.campos = {}
        for chave, rotulo, ic in CAMPOS_LEGENDA:
            self.campos[chave] = s2.linha(ic, QtWidgets.QLineEdit(valores.get(chave, "")), rotulo, rotulo)
        self._auto = {k: valores.get(k, "") for k in self.campos if valores.get(k)}
        self.massa = valores.get("massa", "")
        s3 = f.secao("Vistas", "posicao")
        self.vistas = s3.linha("posicao", P.marcar("Colocar as vistas", bool(self.pecas.valores())),
                               "Vistas no 1º diedro, na escala normalizada que cabe.")
        self.arranjo = QtWidgets.QComboBox()
        for k, (rot, _p, _i) in ARRANJOS.items():
            self.arranjo.addItem(rot, k)
        i = self.arranjo.findData(FREECAD_PARAM().GetString("FolhaArranjo", ARRANJO_PADRAO))
        self.arranjo.setCurrentIndex(max(i, 0))
        s3.linha("posicao", self.arranjo, "Quais vistas entram (1º diedro). Depois dá para pôr outras com a "
                 "Paleta de vistas.", "Arranjo")
        self.vistas.toggled.connect(self.arranjo.setEnabled)
        self.arranjo.setEnabled(self.vistas.isChecked())
        self.pecas.mudou.connect(self._pecas_mudaram)

    def _pecas_mudaram(self):
        objs = self.pecas.valores()
        self.vistas.setChecked(bool(objs))
        v = campos_padrao(self.doc, objs)
        self.massa = v.get("massa", "")
        auto = getattr(self, "_auto", {})
        for chave in ("material", "numero", "revisao", "titulo"):
            atual = self.campos[chave].text().strip()
            # troca só o que estava vazio ou foi preenchido automaticamente (não o digitado)
            if v.get(chave) and (not atual or atual == auto.get(chave)):
                self.campos[chave].setText(v[chave])
                auto[chave] = v[chave]
        self._auto = auto

    def pendencia(self):
        if self.doc is None:
            return "Abra ou crie um documento."
        return None

    def pronto_texto(self):
        n = len(self.pecas.valores())
        return ("Pronto: folha com as vistas de %d peça(s)." % n) if n and self.vistas.isChecked() \
            else "Pronto: folha em branco (selecione peças para as vistas)."

    def valores(self):
        c = {k: w.text().strip() for k, w in self.campos.items()}
        if self.massa:
            c["massa"] = self.massa
        return c

    @property
    def objs(self):
        return self.pecas.valores()

    def criar(self):
        formato = self.formato.currentText()
        norma = self.norma.currentData()
        FREECAD_PARAM().SetString("FolhaFormato", formato)
        FREECAD_PARAM().SetString("FolhaNorma", norma)
        FREECAD_PARAM().SetString("FolhaArranjo", self.arranjo.currentData())
        FREECAD_PARAM().SetString("FolhaOrientacao", self.orientacao.valor())
        campos = self.valores()
        lembrar_campos(campos)
        return nova_folha(self.doc, formato, norma, self.orientacao.valor() == "vertical",
                          campos, self.objs if self.vistas.isChecked() and self.objs else None,
                          arranjo=self.arranjo.currentData())

    def executar(self):
        page = self.criar()
        QtCore.QTimer.singleShot(0, lambda: _abrir_folha(page))
        return page


def _icone_orientacao(retrato):
    import PrumoInserirDesenho
    return PrumoInserirDesenho.icone_orientacao(retrato)


def _abrir_folha(page):
    """Mostra a folha (sem o duplo clique, que agora também abre a edição da legenda)."""
    try:
        FreeCADGui.activateWorkbench("TechDrawWorkbench")
    except Exception:
        pass
    try:
        page.ViewObject.show()
    except Exception:
        try:
            page.ViewObject.doubleClicked()
        except Exception:
            pass


# ---------------------------------------------------------------------- editar a legenda de uma folha
TODOS_CAMPOS_LEGENDA = CAMPOS_LEGENDA + (
    ("verificado", "Verificado", "texto"), ("aprovado", "Aprovado", "texto"), ("data", "Data", "texto"),
    ("massa", "Massa (kg)", "material"), ("escala", "Escala", "escala"), ("unidade", "Unidade", "texto"),
    ("folha", "Folha", "folha"))


def pagina_de(obj):
    """A folha de um objeto selecionado (a própria folha, o modelo dela ou uma vista)."""
    if obj is None:
        return None
    if obj.isDerivedFrom("TechDraw::DrawPage"):
        return obj
    for o in getattr(obj, "InList", []):
        if o.isDerivedFrom("TechDraw::DrawPage"):
            return o
    return None


class PainelLegenda(P.PainelTarefa):
    titulo = "Legenda da folha"
    ajuda = "Os campos do carimbo desta folha. OK grava; Cancelar deixa como estava."

    def __init__(self, page):
        self.page = page
        super().__init__()      # sem caixas de seleção: a seleção atual não mexe em nada aqui

    def montar(self):
        f = self.form
        s = f.secao("Legenda — %s" % self.page.Label, "texto")
        tpl = self.page.Template
        et = dict(tpl.EditableTexts) if tpl is not None and hasattr(tpl, "EditableTexts") else {}
        self.campos = {}
        for chave, rotulo, ic in TODOS_CAMPOS_LEGENDA:
            if chave in et:
                self.campos[chave] = s.linha(ic, QtWidgets.QLineEdit(et.get(chave, "")), rotulo, rotulo)
        outros = [k for k in et if k not in self.campos]
        for k in sorted(outros):                     # campos de modelos que não são do Usinix
            self.campos[k] = s.linha("texto", QtWidgets.QLineEdit(et.get(k, "")), k, k)
        if not self.campos:
            s.texto("O modelo desta folha não tem campos editáveis.")

    def pendencia(self):
        return None

    def pronto_texto(self):
        return "Altere os campos e clique em OK."

    def executar(self):
        tpl = self.page.Template
        et = dict(tpl.EditableTexts)
        mudou = False
        for k, w in self.campos.items():
            v = w.text()
            if et.get(k) != v:
                et[k] = v
                mudou = True
        if mudou:
            tpl.EditableTexts = et
            lembrar_campos({k: et[k] for k in ("empresa", "desenhista", "resp_tecnico", "crea") if k in et})
            self.page.Document.recompute()
        return self.page


class CmdEditarLegenda:
    def GetResources(self):
        return {"Pixmap": PrumoUtil.icone("folha_abnt.svg"), "MenuText": "Editar legenda",
                "ToolTip": "Abre os campos do carimbo da folha selecionada (duplo clique na folha também abre)."}

    def IsActive(self):
        sel = FreeCADGui.Selection.getSelection()
        return bool(sel) and pagina_de(sel[0]) is not None

    def Activated(self):
        sel = FreeCADGui.Selection.getSelection()
        page = pagina_de(sel[0]) if sel else None
        if page is not None:
            PainelLegenda(page).mostrar()


DialogoFolha = PainelFolha   # nome antigo


def FREECAD_PARAM():
    return FreeCAD.ParamGet(PrumoUtil.PARAM_PATH)


class CmdNovaFolha:
    def GetResources(self):
        return {"Pixmap": PrumoUtil.icone("folha_abnt.svg"),
                "MenuText": "Nova folha ABNT",
                "ToolTip": "Folha de desenho A0 a A4 no padrão ABNT (NBR 16752 ou NBR 10068), com a "
                           "legenda preenchida e, se houver peças selecionadas, as vistas no 1º diedro."}

    def IsActive(self):
        return FreeCAD.ActiveDocument is not None

    def Activated(self):
        try:
            import TechDraw  # noqa: F401
            import TechDrawGui  # noqa: F401
        except ImportError:
            pass
        PainelFolha(FreeCAD.ActiveDocument).mostrar()
