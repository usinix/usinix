# SPDX-License-Identifier: LGPL-2.1-or-later
"""Padrão de estrutura: repete uma estrutura soldada inteira em linha ou em volta de um eixo.

As cópias são vínculos (App::Link) da estrutura: o arquivo fica leve e mudar a original muda todas. A
quantidade conta a original; o espaçamento é a distância entre uma e a próxima ou do primeira à última (como o
padrão linear e os enrijecedores em série). A lista de materiais e a lista de corte contam as cópias.

Funciona fora de montagem (na montagem, o Padrão de componentes faz o mesmo com qualquer peça).
"""

import FreeCAD

import PrumoEstrutura as E

MODOS_ESPACO = ["Distância entre eles", "Distância total"]
TIPOS = ["Linear", "Circular"]


def passo(quantidade, modo, valor):
    """Passo de uma cópia à próxima (entre eles = o valor; total = valor ÷ (n − 1))."""
    n = max(1, int(quantidade))
    if modo == MODOS_ESPACO[1]:
        return float(valor) / (n - 1) if n > 1 else 0.0
    return float(valor)


def padroes_de(est):
    """Os padrões (válidos) que repetem esta estrutura."""
    if est is None:
        return []
    return [o for o in est.InList if isinstance(getattr(o, "Proxy", None), PadraoEstrutura)
            and getattr(o, "Original", None) is est]


def copias_de(est):
    """Quantas cópias da estrutura os padrões fazem (sem contar a original)."""
    return sum(len([c for c in (p.Group or []) if c is not None]) for p in padroes_de(est))


class PadraoEstrutura:
    """Grupo com os vínculos da estrutura, nas posições do padrão."""

    def __init__(self, obj):
        obj.Proxy = self
        self._props(obj)

    def _props(self, obj):
        def add(tipo, nome, dica, valor=None):
            if nome not in obj.PropertiesList:
                obj.addProperty(tipo, nome, "Padrão", dica)
                if valor is not None:
                    setattr(obj, nome, valor)
        add("App::PropertyLink", "Original", "Estrutura repetida")
        add("App::PropertyEnumeration", "Tipo", "Linear ou circular")
        if not obj.Tipo:
            obj.Tipo = TIPOS
        add("App::PropertyInteger", "Quantidade", "Total de estruturas, contando a original", 3)
        add("App::PropertyEnumeration", "ModoEspaco", "Linear: distância de uma à próxima ou da primeira à última")
        if not obj.ModoEspaco:
            obj.ModoEspaco = MODOS_ESPACO
        add("App::PropertyLength", "Espacamento", "Linear: o valor da distância", 1000.0)
        add("App::PropertyVector", "Direcao", "Linear: direção", FreeCAD.Vector(1, 0, 0))
        add("App::PropertyVector", "EixoPonto", "Circular: ponto do eixo", FreeCAD.Vector())
        add("App::PropertyVector", "EixoDirecao", "Circular: direção do eixo", FreeCAD.Vector(0, 0, 1))
        add("App::PropertyAngle", "AnguloTotal", "Circular: ângulo coberto; 360 = volta inteira", 360.0)
        add("App::PropertyStringList", "Avisos", "Problemas encontrados no último recálculo")
        obj.setEditorMode("Avisos", 1)

    def onDocumentRestored(self, obj):
        self._props(obj)

    def dumps(self):
        return None

    def loads(self, state):
        return None

    def execute(self, obj):
        try:
            atualizar(obj)
            obj.Avisos = []
        except ValueError as ex:
            obj.Avisos = [str(ex)]
            FreeCAD.Console.PrintWarning("Usinix: %s: %s\n" % (obj.Label, ex))


def transformacoes(obj):
    import PrumoMontagem as M
    n = max(1, int(obj.Quantidade))
    if obj.Tipo == "Linear":
        p = passo(n, obj.ModoEspaco, obj.Espacamento.Value)
        if n > 1 and p <= 1e-9:
            raise ValueError("o espaçamento tem de ser maior que zero")
        return M.transformacoes("linear", n, p, obj.Direcao)
    return M.transformacoes("circular", n, 0.0, None, obj.EixoPonto, obj.EixoDirecao, float(obj.AnguloTotal))


def atualizar(obj):
    """Acerta o número de vínculos e as posições."""
    est = obj.Original
    if est is None or not E.eh_estrutura(est):
        raise ValueError("escolha uma estrutura soldada")
    trs = transformacoes(obj)
    doc = obj.Document
    copias = [c for c in (obj.Group or []) if c is not None and c.isValid() and c.TypeId == "App::Link"]
    while len(copias) < len(trs):
        c = doc.addObject("App::Link", "CopiaEstrutura")
        c.LinkedObject = est
        copias.append(c)
    sobra = copias[len(trs):]
    copias = copias[:len(trs)]
    for k, (c, pl) in enumerate(zip(copias, trs), start=2):
        # só muda o que mudou (mexer nos vínculos dentro do recálculo do grupo deixa-os "tocados")
        if c.LinkedObject is not est:
            c.LinkedObject = est
        if not c.Placement.isSame(pl, 1e-9):
            c.Placement = pl
        nome = "%s (%d)" % (est.Label, k)
        if c.Label != nome:
            c.Label = nome
        try:
            c.purgeTouched()
        except Exception:
            pass
    if list(obj.Group) != copias:
        obj.Group = copias
    for c in sobra:
        try:
            doc.removeObject(c.Name)
        except Exception:
            pass


def criar_padrao_estrutura(est, tipo="linear", quantidade=3, modo=MODOS_ESPACO[0], espacamento=1000.0,
                           direcao=None, eixo_ponto=None, eixo_dir=None, angulo_total=360.0):
    est = E.estrutura_de(est)
    if est is None:
        raise ValueError("Escolha uma estrutura soldada (ou uma barra dela).")
    if int(quantidade) < 2:
        raise ValueError("A quantidade tem de ser pelo menos 2 (a original e uma cópia).")
    if tipo == "linear" and passo(quantidade, modo, espacamento) <= 0:
        raise ValueError("O espaçamento tem de ser maior que zero.")
    doc = est.Document
    obj = doc.addObject("App::DocumentObjectGroupPython", "PadraoEstrutura")
    PadraoEstrutura(obj)
    obj.Label = "Padrão de %s" % est.Label
    obj.Original = est
    obj.Tipo = "Linear" if tipo == "linear" else "Circular"
    obj.Quantidade = int(quantidade)
    obj.ModoEspaco = modo
    obj.Espacamento = float(espacamento)
    if direcao is not None:
        obj.Direcao = FreeCAD.Vector(direcao)
    if eixo_ponto is not None:
        obj.EixoPonto = FreeCAD.Vector(eixo_ponto)
    if eixo_dir is not None:
        obj.EixoDirecao = FreeCAD.Vector(eixo_dir)
    obj.AnguloTotal = float(angulo_total)
    if FreeCAD.GuiUp:
        VPPadraoEstrutura(obj.ViewObject)
    doc.recompute()
    return obj


if FreeCAD.GuiUp:
    import FreeCADGui
    from PySide import QtWidgets

    import PrumoPainel as P
    import PrumoUtil

    class VPPadraoEstrutura:
        def __init__(self, vobj):
            vobj.Proxy = self

        def attach(self, vobj):
            self.Object = vobj.Object

        def getIcon(self):
            return PrumoUtil.icone("padrao_componentes.svg")

        def doubleClicked(self, vobj):
            PainelPadraoEstrutura(editar=vobj.Object).mostrar()
            return True

        def setupContextMenu(self, vobj, menu):
            a = menu.addAction("Editar padrão")
            a.triggered.connect(lambda: PainelPadraoEstrutura(editar=vobj.Object).mostrar())

        def dumps(self):
            return None

        def loads(self, state):
            return None

    def _filtro_estrutura(obj, subs):
        est = E.estrutura_de(obj)
        if est is None:
            for o, _els in E.resolver_item(obj, subs):
                est = E.estrutura_de(o)
                if est is not None:
                    break
        return [(est.Label, est)] if est is not None else []

    def _filtro_referencia(raiz, caminhos):
        import PrumoMontagem as M
        res = []
        for c in caminhos:
            r = M.eixo_de_elemento(raiz, c)
            if r is not None:
                res.append(("%s (%s)" % (c.split(".")[-1].replace("Edge", "aresta ").replace("Face", "face "),
                                         raiz.Label), r))
        return res

    _filtro_referencia.caminho_completo = True

    class PainelPadraoEstrutura(P.PainelTarefa):
        titulo = "Padrão de estrutura"
        previa = True
        ajuda = ("Escolha a estrutura (clique numa barra dela) e, se quiser, uma aresta ou face que dá a direção "
                 "(linear) ou o eixo (circular). Sem referência: eixo X (linear) ou Z (circular). As cópias "
                 "acompanham a original e entram na lista de materiais e na de corte.")

        def __init__(self, editar=None):
            self._editar = editar
            super().__init__()
            if editar is not None:
                self.editar_objeto(editar)

        def montar(self):
            f = self.form
            s0 = f.secao("O que repetir", "selecao")
            self.est = f.caixa(s0, "Estrutura", _filtro_estrutura, minimo=1, maximo=1,
                               dica="Clique numa barra da estrutura.")
            self.ref = f.caixa(s0, "Direção / eixo (opcional)", _filtro_referencia, minimo=0, maximo=1,
                               dica="Aresta reta ou face plana: direção. Aresta circular ou face cilíndrica: eixo.")
            self.est.mudou.connect(lambda: self.est.pronta() and self.est.ativa and
                                   self.form.ativar_caixa(self.ref))
            s1 = f.secao("Padrão", "quantidade")
            self.tipo = P.Opcoes([("linear", "Linear", "comprimento", "Em linha"),
                                  ("circular", "Circular", "angulo", "Em volta de um eixo")])
            s1.widget(self.tipo)
            self.qtd = QtWidgets.QSpinBox()
            self.qtd.setRange(2, 500)
            self.qtd.setValue(3)
            self.qtd.setKeyboardTracking(False)
            s1.linha("quantidade", self.qtd, "Total, contando a original.", "Quantidade")
            self.modo = s1.linha("largura", P.lista(MODOS_ESPACO), "Distância entre elas: de uma à próxima. "
                                 "Distância total: da primeira à última.", "Espaçamento")
            self.passo = s1.linha("comprimento", P.numero(1000.0, 0.01, 1e7), "Valor da distância.", "Distância")
            self.angulo = s1.linha("angulo", P.numero(360.0, 1.0, 360.0, "°"), "360° = distribuídas na volta "
                                   "inteira; menos que isso = da primeira à última dentro do ângulo.",
                                   "Ângulo total")
            self.eixo = P.lista(["X", "Y", "Z"], "X")
            s1.linha("posicao", self.eixo, "Usado quando não há referência escolhida.", "Eixo")
            self.inverter = P.marcar("Inverter o sentido", False)
            s1.widget(self.inverter)
            self.tipo.mudou.connect(self._tipo)
            self._tipo(self.tipo.valor())

        def _tipo(self, t):
            lin = t == "linear"
            self.modo.setEnabled(lin)
            self.passo.setEnabled(lin)
            self.angulo.setEnabled(not lin)
            atual = self.eixo.currentText()
            if not self.ref.valores():
                self.eixo.setCurrentText("X" if lin and atual == "Z" else ("Z" if not lin and atual == "X" else atual))

        def pendencia(self):
            if super().pendencia():
                return "Escolha a estrutura que vai ser repetida (clique numa barra dela)."
            return None

        def pronto_texto(self):
            return "Pronto: %d estruturas (a original e %d cópias)." % (self.qtd.value(), self.qtd.value() - 1)

        def parametros(self):
            t = self.tipo.valor()
            refs = self.ref.valores()
            e = FreeCAD.Vector(*{"X": (1, 0, 0), "Y": (0, 1, 0), "Z": (0, 0, 1)}[self.eixo.currentText()])
            ponto, direcao = FreeCAD.Vector(), e
            if refs:
                ponto, direcao = refs[0]
            elif getattr(self, "_dir_salva", None) is not None:
                ponto, direcao = self._dir_salva
            direcao = FreeCAD.Vector(direcao)
            if self.inverter.isChecked():
                direcao = direcao * -1.0
            return dict(tipo=t, quantidade=self.qtd.value(), modo=self.modo.currentText(),
                        espacamento=self.passo.value(), direcao=direcao, eixo_ponto=ponto, eixo_dir=direcao,
                        angulo_total=self.angulo.value())

        def carregar(self, obj):
            if obj.Original is not None:
                self.est.aceitar(obj.Original)
            self.tipo.definir("linear" if obj.Tipo == "Linear" else "circular")
            self.qtd.setValue(obj.Quantidade)
            self.modo.setCurrentText(obj.ModoEspaco)
            self.passo.setValue(float(obj.Espacamento))
            self.angulo.setValue(float(obj.AnguloTotal))
            self._dir_salva = (FreeCAD.Vector(obj.EixoPonto), FreeCAD.Vector(obj.Direcao if obj.Tipo == "Linear"
                                                                              else obj.EixoDirecao))

        def props_edicao(self):
            p = self.parametros()
            return {"Tipo": "Linear" if p["tipo"] == "linear" else "Circular", "Quantidade": p["quantidade"],
                    "ModoEspaco": p["modo"], "Espacamento": p["espacamento"], "Direcao": p["direcao"],
                    "EixoPonto": p["eixo_ponto"], "EixoDirecao": p["eixo_dir"],
                    "AnguloTotal": p["angulo_total"]}

        def executar(self):
            return [criar_padrao_estrutura(self.est.valores()[0], **self.parametros())]

    class CmdPadraoEstrutura:
        def GetResources(self):
            return {"Pixmap": PrumoUtil.icone("padrao_componentes.svg"), "MenuText": "Padrão de estrutura",
                    "ToolTip": "Repete a estrutura soldada inteira em linha ou em volta de um eixo (vários "
                               "pórticos, mesas iguais...). As cópias acompanham a original e entram nas listas "
                               "de materiais e de corte."}

        def IsActive(self):
            return FreeCAD.ActiveDocument is not None

        def Activated(self):
            p = PainelPadraoEstrutura()
            p.mostrar()
            for o in FreeCADGui.Selection.getSelection():
                if E.estrutura_de(o) is not None:
                    p.est.aceitar(E.estrutura_de(o))
                    break

    def registrar_comandos():
        FreeCADGui.addCommand("Prumo_PadraoEstrutura", CmdPadraoEstrutura())
