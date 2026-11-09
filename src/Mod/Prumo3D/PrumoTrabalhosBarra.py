# SPDX-License-Identifier: LGPL-2.1-or-later
# Usinix - trabalhos na barra da estrutura: corte das pontas soltas e furos, sem a barra virar corpo.
"""Trabalhos na barra (1.5.0).

A barra continua sendo barra da estrutura (lista de corte, cantos, análise): os trabalhos ficam
guardados na própria estrutura e entram no cálculo da barra (PrumoEstrutura.calcular_barra).

- Corte da ponta solta: reto (normal), horizontal, vertical ou pela face escolhida (aparar ou prolongar
  até ela). Ex.: banzo de escada a 45° com apoio no piso e chegada no topo cortados na horizontal.
- Furos: na alma ou nas mesas, a uma distância da ponta, em fila (quantidade e espaçamento), uma ou
  duas filas, para as barras escolhidas. A lista de corte mostra a furação de cada barra.
"""

import uuid

import FreeCAD
import FreeCADGui

import PrumoEstrutura as E
import PrumoPainel as P
import PrumoUtil
from PrumoUtil import fmt

try:
    from PySide import QtCore, QtWidgets
except ImportError:  # pragma: no cover
    from PySide2 import QtCore, QtWidgets

PARAM = "User parameter:BaseApp/Preferences/Mod/Prumo3D"
PARAFUSOS = ["Sem parafuso", "M8", "M10", "M12", "M16", "M20", "M22", "M24", "M27", "M30"]
OPCOES_PONTA = [
    (E.PONTA_RETO, "Reto", "ponta_reta", "Corte reto, a 90° da barra (como sempre foi)."),
    (E.PONTA_HORIZONTAL, "Horizontal", "ponta_horizontal", "Corte horizontal na ponta da linha: apoio no "
     "piso, chegada numa laje."),
    (E.PONTA_VERTICAL, "Vertical", "ponta_vertical", "Corte vertical na ponta da linha: encosto numa parede "
     "ou coluna."),
    ("face", "Pela face", "ponta_face", "Apara ou prolonga a barra até a face escolhida (selecione uma face "
     "plana de outra peça)."),
]
REFS = ["Início", "Fim", "As duas pontas"]


def folga_furo():
    """Folga entre o furo e o parafuso (mm), nas preferências; o padrão é 1,5 mm."""
    return FreeCAD.ParamGet(PARAM).GetFloat("FolgaFuroParafuso", 1.5)


def diametro_para(parafuso):
    """Diâmetro do furo para o parafuso (ex.: "M12" → 13,5 com folga 1,5) ou None."""
    if not parafuso or not parafuso.startswith("M"):
        return None
    try:
        return float(parafuso[1:]) + folga_furo()
    except ValueError:
        return None


def pontas_livres(barra):
    """Pontas (0 início, 1 fim) que não encostam em outra barra."""
    est = barra.Estrutura
    eds = E.arestas_ativas(est, E.arestas(est.Esqueleto))
    return [k for k, lig in enumerate(E.ligacoes(eds, barra.Indice)) if lig.tipo == "livre"]


def plano_da_face(obj, sub):
    """(ponto, normal) globais de uma face plana, ou None."""
    if not sub or not sub.startswith("Face"):
        return None
    try:
        f = PrumoUtil.forma_global(obj).Faces[int(sub[4:]) - 1]
    except Exception:
        return None
    if f.Surface.__class__.__name__ != "Plane":
        return None
    u0, u1, v0, v1 = f.ParameterRange
    n = f.normalAt((u0 + u1) / 2.0, (v0 + v1) / 2.0)
    return f.CenterOfMass, FreeCAD.Vector(n)


def _filtro_barras(obj, subs):
    return [(b.Label, b) for b in E.barras_do_item(obj, subs)]


def _filtro_face(obj, subs):
    res = []
    for o, els in E.resolver_item(obj, subs):
        if E.eh_barra(o) or E.eh_estrutura(o):
            continue
        for el in els:
            pl = plano_da_face(o, el)
            if pl is not None:
                res.append(("%s · %s" % (o.Label, el), pl))
    return res


def aplicar(barras, pontas=None, furos=None, id_grupo=None, plano_face=None):
    """Grava os trabalhos nas barras (todas da mesma estrutura).

    pontas: {0: valor, 1: valor} (valor: reto, horizontal, vertical ou "face"; só pontas soltas mudam).
    furos: dicionário do grupo de furos (sem "barras"), lista desses ou None para tirar os furos do grupo.
    id_grupo: grupos de furos com esse id são trocados (o painel refaz sem duplicar)."""
    if not barras:
        return None
    est = barras[0].Estrutura
    if any(b.Estrutura is not est for b in barras):
        raise ValueError("as barras precisam ser da mesma estrutura")
    for b in barras:
        livres = pontas_livres(b)
        for k, valor in (pontas or {}).items():
            if k not in livres:
                continue
            if valor == "face":
                if plano_face is None:
                    continue
                valor = E.valor_plano(*plano_face)
            E.definir_ponta(est, b.Indice, k, valor)
    if id_grupo is not None:
        lista = [f for f in E.furos_de(est) if f.get("id") != id_grupo]
        novos = furos if isinstance(furos, list) else ([furos] if furos else [])
        for f in novos:
            d = dict(f)
            d["barras"] = sorted(b.Indice for b in barras)
            d["id"] = id_grupo
            lista.append(d)
        E.gravar_furos(est, lista)
    return est


class PainelTrabalhos(P.PainelTarefa):
    titulo = "Trabalhos na barra"
    ajuda = ("Corte das pontas soltas e furos nas barras da estrutura. A barra continua barra: a lista de "
             "corte sai com o comprimento, o ângulo das pontas e a furação.")
    previa = True

    def montar(self):
        f = self.form
        s1 = f.secao("Barras", "selecao")
        self.barras = f.caixa(s1, "Barras", _filtro_barras, minimo=1,
                              dica="Clique nas barras na tela ou na árvore (várias de uma vez valem para todas).")
        s2 = f.secao("Pontas soltas", "ponta")
        self.p0 = P.Opcoes(OPCOES_PONTA, E.PONTA_RETO, colunas=4)
        self.p1 = P.Opcoes(OPCOES_PONTA, E.PONTA_RETO, colunas=4)
        s2.linha("ponta", self.p0, "Corte da ponta inicial da barra (onde a linha começa).", "Ponta inicial")
        s2.linha("ponta", self.p1, "Corte da ponta final da barra (onde a linha termina).", "Ponta final")
        self.face = f.caixa(s2, "Face para o corte (Pela face)", _filtro_face, minimo=0, maximo=1,
                            dica="Face plana de outra peça (piso, laje, chapa) onde a barra é aparada ou "
                                 "prolongada.")
        self.nota_pontas = s2.texto("")
        self.p0.mudou.connect(self._mostrar_face)
        self.p1.mudou.connect(self._mostrar_face)
        self._mostrar_face()
        s3 = f.secao("Furos", "furo")
        self.furar = P.marcar("Furar as barras", False)
        s3.widget(self.furar)
        self.face_furo = s3.linha("tipo", P.lista(E.FACES_FURO), "Alma: furo atravessa na largura. Mesas: "
                                  "furo em cima, embaixo ou nas duas.", "Onde")
        self.parafuso = s3.linha("parafuso", P.lista(PARAFUSOS, "M12"), "O diâmetro do furo sai do parafuso "
                                 "mais a folga (preferência do Usinix).", "Parafuso")
        self.diam = s3.linha("furo", P.numero(13.5, 1.0, 200.0), "Diâmetro do furo.", "Diâmetro do furo")
        self.ref = s3.linha("ponta", P.lista(REFS), "De qual ponta da linha medir a distância.", "Medir de")
        self.dist = s3.linha("comprimento", P.numero(50.0, 0.0, 50000.0), "Da ponta da linha até o primeiro "
                             "furo.", "Distância da ponta")
        self.qtd = QtWidgets.QSpinBox()
        self.qtd.setRange(1, 200)
        self.qtd.setValue(2)
        s3.linha("quantidade", self.qtd, "Furos ao longo da barra.", "Quantidade")
        self.passo = s3.linha("comprimento", P.numero(80.0, 0.0, 50000.0), "Distância entre os furos ao longo "
                              "da barra.", "Espaçamento")
        self.filas = s3.linha("quantidade", P.lista(["1 fila", "2 filas"]), "Duas filas: lado a lado na face "
                              "(nas mesas, uma de cada lado da alma).", "Filas")
        self.gab = s3.linha("largura", P.numero(60.0, 0.0, 2000.0), "Distância entre as duas filas "
                            "(gabarito).", "Entre filas")
        self.desloc = s3.linha("posicao", P.numero(0.0, -2000.0, 2000.0), "Desloca as filas em relação ao "
                               "centro da face.", "Deslocamento")
        self.parafuso.currentIndexChanged.connect(self._parafuso_mudou)
        self.face_furo.currentIndexChanged.connect(self._face_mudou)
        self.furar.toggled.connect(self._habilitar)
        self.id_grupo = "tb-" + uuid.uuid4().hex[:8]
        self._carregado = False
        self._habilitar()

    # ---- campos
    def _mostrar_face(self, *_a):
        """A caixa da face só aparece quando uma das pontas é "Pela face"."""
        self.face.setVisible("face" in (self.p0.valor(), self.p1.valor()))

    def _parafuso_mudou(self, *_a):
        d = diametro_para(self.parafuso.currentText())
        if d is not None:
            self.diam.setValue(d)

    def _face_mudou(self, *_a):
        mesas = self.face_furo.currentText() != "Alma"
        if mesas and self.filas.currentIndex() == 0:
            self.filas.setCurrentIndex(1)     # nas mesas, normalmente um furo de cada lado da alma
        bs = self.barras.valores()
        if mesas and bs:
            try:
                it = E.PrumoPerfis.perfil(bs[0].Perfil)
                self.gab.setValue(round(it.get("bf", 0) / 2.0) or self.gab.value())
            except Exception:
                pass

    def _habilitar(self, *_a):
        on = self.furar.isChecked()
        for w in (self.face_furo, self.parafuso, self.diam, self.ref, self.dist, self.qtd, self.passo,
                  self.filas, self.gab, self.desloc):
            w.setEnabled(on)

    # ---- o que já está gravado nas barras
    def _carregar_da_barra(self, b):
        est = b.Estrutura
        for k, w in ((0, self.p0), (1, self.p1)):
            v = E.ponta(est, b.Indice, k)
            w.definir("face" if v.startswith(E.PONTA_PLANO) else v)
        fs = E.furos_da_barra(est, b.Indice)
        if fs:
            g = fs[0]
            self.id_grupo = g.get("id") or self.id_grupo
            mesmos = [f for f in fs if f.get("id") == g.get("id")]
            self.furar.setChecked(True)
            self.face_furo.setCurrentText(g.get("face", "Alma"))
            self.parafuso.setCurrentText(g.get("parafuso") or "Sem parafuso")
            self.diam.setValue(float(g.get("diam", 13.5)))
            refs = {f.get("ref", "inicio") for f in mesmos}
            self.ref.setCurrentText("As duas pontas" if len(refs) > 1 else
                                    ("Fim" if g.get("ref") == "fim" else "Início"))
            self.dist.setValue(float(g.get("dist", 50)))
            self.qtd.setValue(int(g.get("qtd", 1)))
            self.passo.setValue(float(g.get("passo", 0)))
            self.filas.setCurrentIndex(1 if int(g.get("filas", 1)) >= 2 else 0)
            self.gab.setValue(float(g.get("gab", 0)))
            self.desloc.setValue(float(g.get("desloc", 0)))

    def atualizar(self):
        bs = self.barras.valores()
        if bs and not self._carregado:
            self._carregado = True
            try:
                self._carregar_da_barra(bs[0])
            except Exception:
                pass
        self._nota()
        super().atualizar()

    def _nota(self):
        presas = []
        for b in self.barras.valores():
            try:
                livres = pontas_livres(b)
            except Exception:
                continue
            for k, nome in ((0, "início"), (1, "fim")):
                if k not in livres:
                    presas.append("%s (%s)" % (b.Label, nome))
        txt = ("Pontas presas em outra barra seguem o tratamento do canto: %s." % ", ".join(presas)) if presas \
            else "O corte vale só para as pontas soltas (que não encostam em outra barra)."
        try:
            self.nota_pontas.setText(txt)
        except Exception:
            pass

    # ---- o trabalho
    def grupo_furos(self):
        if not self.furar.isChecked():
            return None
        par = self.parafuso.currentText()
        base = {"face": self.face_furo.currentText(), "diam": round(self.diam.value(), 3),
                "dist": self.dist.value(), "qtd": self.qtd.value(), "passo": self.passo.value(),
                "filas": 2 if self.filas.currentIndex() == 1 else 1, "gab": self.gab.value(),
                "desloc": self.desloc.value(), "parafuso": "" if par == "Sem parafuso" else par}
        ref = self.ref.currentText()
        if ref == "As duas pontas":
            return [dict(base, ref="inicio"), dict(base, ref="fim")]
        return [dict(base, ref="fim" if ref == "Fim" else "inicio")]

    def pendencia(self):
        falta = super().pendencia()
        if falta:
            return falta
        bs = self.barras.valores()
        if len({b.Estrutura.Name for b in bs if b.Estrutura is not None}) > 1:
            return "Escolha barras de uma estrutura só."
        if "face" in (self.p0.valor(), self.p1.valor()) and not self.face.valores():
            return "Pela face: selecione a face plana (piso, laje, chapa) onde a barra é cortada."
        g = self.grupo_furos()
        if g and g[0]["qtd"] > 1 and g[0]["passo"] <= 0:
            return "Furos: informe o espaçamento entre os furos."
        return None

    def executar(self):
        bs = self.barras.valores()
        pl = self.face.valores()[0] if self.face.valores() else None
        est = aplicar(bs, {0: self.p0.valor(), 1: self.p1.valor()}, self.grupo_furos(), self.id_grupo, pl)
        if est is not None:
            for b in E.barras_de(est):
                b.touch()
        return bs

    def pronto_texto(self):
        bs = self.barras.valores()
        partes = []
        for b in bs[:4]:
            fu = getattr(b, "Furacao", "") or "sem furos"
            partes.append("%s: %s mm, pontas %s° / %s°, %s" % (b.Label, fmt(b.ComprimentoCorte.Value, 1),
                                                               fmt(b.CorteInicio.Value, 0),
                                                               fmt(b.CorteFim.Value, 0), fu))
        return ("; ".join(partes) + ". OK grava.") if partes else super().pronto_texto()


class CmdTrabalhosBarra:
    def GetResources(self):
        return {"Pixmap": PrumoUtil.icone("trabalhos_barra.svg"), "MenuText": "Trabalhos na barra",
                "ToolTip": "Corte das pontas soltas (horizontal, vertical ou pela face) e furos na alma ou nas "
                           "mesas das barras da estrutura. A barra continua na lista de corte, com a furação."}

    def IsActive(self):
        return FreeCAD.ActiveDocument is not None

    def Activated(self):
        PainelTrabalhos().mostrar()


def registrar_comandos():
    FreeCADGui.addCommand("Prumo_TrabalhosBarra", CmdTrabalhosBarra())
