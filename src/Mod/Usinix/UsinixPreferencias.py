# SPDX-License-Identifier: LGPL-2.1-or-later
"""Preferências do Usinix: as opções que importam no dia a dia, em cartões, sem precisar abrir a janela
completa de preferências do FreeCAD (que continua a um clique).

Cada interruptor grava na hora. O que só vale ao reabrir o programa diz isso ao lado.
"""

import FreeCAD
import FreeCADGui
from PySide import QtCore, QtWidgets

import UsinixUI as UI

PARAM_PATH = "User parameter:BaseApp/Preferences/Mod/Usinix"
UNIDADES_PATH = "User parameter:BaseApp/Preferences/Units"
SKETCHER_PATH = "User parameter:BaseApp/Preferences/Mod/Sketcher/General"

# (parâmetro, rótulo, padrão, vale só ao reabrir?)
APARENCIA = [("TelaInicial", "Mostrar a tela inicial ao abrir", True, False),
             ("RibbonContextual", "Faixa só com as ferramentas do momento (as raras no “Mais”)", True, False),
             ("CaixaS", "Tecla S na vista 3D abre a caixa de ferramentas no cursor", True, False)]
PAINEL = [("PainelLateralUnico", "Painel lateral único (árvore, propriedades e comando em abas)", True, True),
          ("PropriedadesEmCartoes", "Propriedades em cartões", True, False),
          ("PainelDeComando", "Comandos em cartões (no lugar dos formulários do FreeCAD)", True, False),
          ("AbasCompactas", "Abas só com ícone quando falta espaço", True, False),
          ("OcultarLateralNoInicio", "Esconder o painel lateral na tela inicial", True, False)]
ESBOCO = [("RetirarAutomaticasEmConflito", "Retirar relações automáticas que não cabem no desenho", True, False),
          ("RecusarSuperRestricao", "Cota a mais vira cota de referência (o esboço não fica vermelho)", True, False),
          ("ReferenciasAutomaticas", "Referências automáticas ao editar (arestas e faces da peça)", True, False),
          ("EnquadrarAoSairDoEsboco", "Enquadrar a peça ao sair do esboço", True, False)]
ATUALIZACAO = [("VerificarAtualizacoes", "Procurar versão nova ao abrir (no máximo uma vez por dia)", True, False),
               ("AtualizarBetas", "Incluir versões de teste (beta)", True, False)]


ESQUEMAS_PT = {"Internal": "Padrão (mm, kg, s, graus)", "MKS": "MKS (m, kg, s, graus)",
               "Imperial": "Imperial (pol, lb)", "ImperialDecimal": "Imperial decimal (pol)",
               "Centimeter": "Centímetros (cm, m², m³)", "ImperialBuilding": "Imperial para construção (pés e pol)",
               "MmMin": "Peças pequenas e CNC (mm, mm/min)", "ImperialCivil": "Imperial civil (pés, mph)",
               "FEM": "Simulação (mm, N, s)", "MeterDecimal": "Metros decimais (m, m², m³)"}


def _p():
    return FreeCAD.ParamGet(PARAM_PATH)


def redesenhar_esboco_aberto():
    """Esboço em edição: liga e desliga o espaço virtual, o que refaz os ícones das restrições na hora."""
    try:
        gd = FreeCADGui.ActiveDocument
        vp = gd.getInEdit() if gd else None
        if vp is not None and vp.Object.TypeId == "Sketcher::SketchObject":
            FreeCADGui.runCommand("Sketcher_SwitchVirtualSpace")
            FreeCADGui.runCommand("Sketcher_SwitchVirtualSpace")
    except Exception:
        pass


def _u():
    return FreeCAD.ParamGet(UNIDADES_PATH)


class JanelaPreferencias(QtWidgets.QDialog):
    def __init__(self, parent=None):
        super().__init__(parent or FreeCADGui.getMainWindow())
        self.setObjectName("UsinixUI")
        self.setWindowTitle("Preferências do Usinix")
        self.setStyleSheet(UI.qss())
        self.setMinimumWidth(520)
        self.resize(560, 720)
        self.campos = {}
        lay = QtWidgets.QVBoxLayout(self)
        lay.setContentsMargins(14, 14, 14, 12)
        lay.setSpacing(10)
        t = QtWidgets.QLabel("Preferências")
        t.setStyleSheet(UI.tema("color: #003A70; font-size: 13pt; font-weight: 700;"))
        lay.addWidget(t)
        interno = QtWidgets.QWidget()
        col = QtWidgets.QVBoxLayout(interno)
        col.setContentsMargins(0, 0, 4, 0)
        area = UI.rolagem(interno)
        self.col = col
        col.setSpacing(10)
        self._tema()
        self._mouse()
        self._cadastro()
        self._grupo("Aparência", "aparencia", APARENCIA)
        self._grupo("Painel lateral", "arvore", PAINEL)
        self._modo_limpo(self._grupo("Esboço", "esboco", ESBOCO))
        self._unidades()
        self._desenho()
        self._atualizacao()
        self._programacao()
        col.addStretch(1)
        lay.addWidget(area, 1)
        rod = QtWidgets.QHBoxLayout()
        todas = QtWidgets.QPushButton("Todas as preferências do FreeCAD…")
        todas.setAutoDefault(False)
        todas.clicked.connect(self._todas)
        rod.addWidget(todas)
        rod.addStretch(1)
        fechar = QtWidgets.QPushButton("Fechar")
        fechar.setObjectName("UsinixPrimario")
        fechar.setAutoDefault(False)
        fechar.clicked.connect(self.accept)
        rod.addWidget(fechar)
        lay.addLayout(rod)

    # ---------------------------------------------------------------- cartões
    def _grupo(self, titulo, icone, itens):
        c = UI.Cartao(titulo, icone)
        for chave, rotulo, padrao, reabrir in itens:
            sw = UI.Interruptor(_p().GetBool(chave, padrao))
            sw.toggled.connect(lambda on, k=chave: (_p().SetBool(k, bool(on)), self._aplicar(k)))
            c.linha(rotulo + (" (vale ao reabrir)" if reabrir else ""), sw)
            self.campos[chave] = sw
        self.col.addWidget(c)
        return c

    def _cadastro(self):
        """Dados das pranchas: vão preenchidos em toda prancha nova (e continuam editáveis em cada uma)."""
        import UsinixFolhas
        c = UI.Cartao("Dados das pranchas", "folha")
        nota = QtWidgets.QLabel("Vão preenchidos na legenda de toda prancha nova; em cada prancha ainda dá para "
                                "mudar. Ficam só neste computador.")
        nota.setWordWrap(True)
        nota.setObjectName("UsinixDica")
        c.widget(nota)
        atual = UsinixFolhas.cadastro()
        self.cadastro = {}
        for chave, rotulo in UsinixFolhas.CADASTRO:
            ed = QtWidgets.QLineEdit(atual.get(chave, ""))
            ed.setObjectName("UsinixCampo")
            ed.setClearButtonEnabled(True)
            ed.setMinimumWidth(280)
            ed.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Fixed)
            ed.textChanged.connect(lambda txt, k=chave: UsinixFolhas.gravar_cadastro({k: txt}))
            c.linha(rotulo, ed)
            self.cadastro[chave] = ed
            self.campos["folha_" + chave] = ed
        limpar = QtWidgets.QPushButton("Limpar os dados")
        limpar.setAutoDefault(False)
        limpar.clicked.connect(lambda: [ed.clear() for ed in self.cadastro.values()])
        c.widget(limpar)
        self.campos["folha_limpar"] = limpar
        self.col.addWidget(c)
        return c

    def _modo_limpo(self, cartao):
        """Modo limpo do esboço: ícones de restrição só da geometria selecionada (as cotas ficam sempre).
        É lido pelo próprio esboço (parâmetro do Sketcher), por isso fica fora da lista ESBOCO."""
        g = FreeCAD.ParamGet(SKETCHER_PATH)
        sw = UI.Interruptor(g.GetBool("ShowOnlySelectedConstraintIcons", True))

        def mudar(on):
            g.SetBool("ShowOnlySelectedConstraintIcons", bool(on))
            redesenhar_esboco_aberto()
        sw.toggled.connect(mudar)
        cartao.linha("Ícones das restrições só da linha ou ponto selecionado (modo limpo)", sw)
        self.campos["modo_limpo"] = sw

    def _aplicar(self, chave):
        """Opções que valem na hora."""
        if chave == "RibbonContextual":
            try:
                import UsinixRibbon
                rb = UsinixRibbon._state.get("ribbon")
                if rb is not None and rb.tabbar.currentIndex() >= 0:
                    rb.build(rb._tabs[rb.tabbar.currentIndex()])
            except Exception:
                pass

    def _mouse(self):
        """Mouse da vista 3D pelo nome do programa de origem (SolidWorks, Inventor/Fusion...)."""
        import UsinixOrigemCAD
        c, combo = UsinixOrigemCAD.cartao_preferencias(UI)
        self.campos["mouse"] = combo
        self.col.addWidget(c)
        return c

    def _programacao(self):
        """Relatório e console Python: fechados para quem só desenha; quem programa liga aqui."""
        c = UI.Cartao("Para quem programa", "comando")
        g = FreeCAD.ParamGet("User parameter:BaseApp/Preferences/Mod/Usinix")
        sw = UI.Interruptor(not g.GetBool("ModoDistribuicao", True))

        def mudar(on):
            g.SetBool("ModoDistribuicao", not bool(on))
            try:
                import UsinixGui
                UsinixGui.apply_modo_distribuicao(not bool(on))
            except Exception:
                pass
        sw.toggled.connect(mudar)
        c.linha("Mostrar Relatório e console Python", sw)
        self.campos["programacao"] = sw
        self.col.addWidget(c)
        return c

    def _tema(self):
        import UsinixEstilo
        c = UI.Cartao("Tema", "aparencia")
        atual = "escuro" if UsinixEstilo.escuro() else "claro"
        seg = UI.Segmentado([("claro", "Claro", "olho"), ("escuro", "Escuro", "olho")], atual, colunas=2)
        seg.mudou.connect(self._trocar_tema)
        c.widget(seg)
        nota = QtWidgets.QLabel("Trocar o tema fecha e abre o Usinix de novo (ele pergunta antes).")
        nota.setObjectName("UsinixSub")
        nota.setWordWrap(True)
        c.widget(nota)
        self.campos["tema"] = seg
        self.col.addWidget(c)

    def _trocar_tema(self, chave):
        import UsinixEstilo
        if (chave == "escuro") == UsinixEstilo.escuro():
            return
        try:
            FreeCADGui.runCommand("Usinix_TemaEscuro", 0)
        finally:
            # se o usuário desistiu, a escolha volta a mostrar o tema atual
            self.campos["tema"].definir("escuro" if UsinixEstilo.escuro() else "claro")

    def _unidades(self):
        c = UI.Cartao("Unidades", "medida")
        cb = QtWidgets.QComboBox()
        cb.setObjectName("UsinixLista")
        cb.setSizeAdjustPolicy(QtWidgets.QComboBox.AdjustToMinimumContentsLengthWithIcon)
        cb.setMinimumContentsLength(18)
        cb.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Fixed)
        try:
            nomes = list(FreeCAD.Units.listSchemas())
        except Exception:
            nomes = []
        for i, n in enumerate(nomes):
            cb.addItem(ESQUEMAS_PT.get(n, n), i)
        cb.setCurrentIndex(max(0, min(_u().GetInt("UserSchema", 0), cb.count() - 1)))
        cb.activated.connect(self._esquema)
        c.linha("Sistema de unidades", cb)
        self.campos["esquema"] = cb
        dec = QtWidgets.QSpinBox()
        dec.setObjectName("UsinixNum")
        dec.setButtonSymbols(QtWidgets.QAbstractSpinBox.NoButtons)
        dec.setRange(0, 8)
        dec.setAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)
        dec.setMaximumWidth(80)
        dec.setValue(_u().GetInt("Decimals", 2))
        dec.valueChanged.connect(self._decimais)
        c.linha("Casas decimais nos campos", dec)
        self.campos["decimais"] = dec
        self.col.addWidget(c)

    def _mm(self, valor, minimo=0.5, maximo=50.0):
        sb = QtWidgets.QDoubleSpinBox()
        sb.setObjectName("UsinixNum")
        sb.setButtonSymbols(QtWidgets.QAbstractSpinBox.NoButtons)
        sb.setRange(minimo, maximo)
        sb.setDecimals(1)
        sb.setSingleStep(0.5)
        sb.setSuffix(" mm")
        sb.setLocale(QtCore.QLocale(QtCore.QLocale.Portuguese, QtCore.QLocale.Brazil))     # 3,5 mm
        sb.setAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)
        sb.setMaximumWidth(90)
        sb.setValue(valor)
        return sb

    def _desenho(self):
        """Texto das cotas e dos rótulos das vistas. São dois tamanhos diferentes no FreeCAD (Dimensões ›
        Tamanho da fonte e Geral › Tamanho do rótulo), e mudar o rótulo não muda as cotas."""
        import UsinixFolhas
        c = UI.Cartao("Desenho técnico", "folha")
        cot = self._mm(UsinixFolhas.texto_cotas())
        cot.editingFinished.connect(lambda: UsinixFolhas.definir_texto_cotas(cot.value()))
        c.linha("Texto das cotas", cot)
        rot = self._mm(UsinixFolhas.texto_rotulos())
        rot.editingFinished.connect(lambda: FreeCAD.ParamGet(UsinixFolhas.ROTULOS_PATH).SetFloat(
            "LabelSize", rot.value()))
        c.linha("Texto do nome das vistas", rot)
        nota = QtWidgets.QLabel("As cotas que estão no tamanho padrão acompanham a mudança, também nos desenhos "
                                "abertos; uma cota mudada à mão fica como está.")
        nota.setWordWrap(True)
        nota.setObjectName("UsinixDica")
        c.widget(nota)
        self.campos["texto_cotas"] = cot
        self.campos["texto_rotulos"] = rot
        self.col.addWidget(c)

    def _esquema(self, i):
        _u().SetInt("UserSchema", int(i))
        try:
            FreeCAD.Units.setSchema(int(i))
        except Exception:
            pass

    def _decimais(self, n):
        _u().SetInt("Decimals", int(n))
        try:
            FreeCAD.Units.setDecimals(int(n))
        except Exception:
            pass

    def _atualizacao(self):
        c = self._grupo("Atualizações", "info", ATUALIZACAO)
        b = QtWidgets.QPushButton("Verificar agora")
        b.setAutoDefault(False)
        b.clicked.connect(self._verificar)
        c.widget(b)
        self.campos["verificar"] = b

    def _verificar(self):
        import UsinixAtualizar
        self._verificacao = UsinixAtualizar.verificar_agora(self)

    def _todas(self):
        self.accept()
        QtCore.QTimer.singleShot(0, lambda: FreeCADGui.runCommand("Std_DlgPreferences", 0))


_estado = {"janela": None}


def abrir():
    j = _estado["janela"]
    try:
        if j is not None and j.isVisible():
            j.raise_()
            j.activateWindow()
            return j
    except RuntimeError:
        pass
    j = JanelaPreferencias()
    _estado["janela"] = j
    j.show()
    return j


class CmdPreferencias:
    def GetResources(self):
        return {"Pixmap": "preferences-general", "MenuText": "Preferências",
                "ToolTip": "As opções do Usinix em cartões (tema, dados das pranchas, painel lateral, esboço, unidades, "
                           "atualizações)"}

    def IsActive(self):
        return True

    def Activated(self):
        abrir()


def registrar():
    FreeCADGui.addCommand("Usinix_Preferencias", CmdPreferencias())
