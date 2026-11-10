# SPDX-License-Identifier: LGPL-2.1-or-later
# Usinix - memorial de cálculo do vaso de pressão, com o enquadramento na NR-13, em PDF pronto para a ART.
"""Memorial NR-13 do vaso de pressão.

Junta num documento (PDF A4) o que o assistente de vaso já calcula — espessuras pelo ASME VIII-1 (UG-27 e UG-32),
PMTA e pressão de teste — com a identificação do equipamento, o enquadramento na NR-13 e os campos do responsável
técnico (nome, registro no CREA, número da ART), para assinar e anexar à ART.

Enquadramento, conferido no texto da NR-13 dado pela Portaria MTP n.º 1.846, de 01/07/2022 (DOU de 04/07/2022,
vigência a partir de 03/10/2022), retificada em 20/10/2022 — gov.br, consultado em 10/11/2026:
- abrangência (13.2.1, b): vasos com P·V maior que 8, com P (pressão máxima de operação) em kPa e V em m³;
- classe do fluido (13.5.1.1.1): A, B, C ou D;
- grupo de potencial de risco (13.5.1.1.3), P em MPa e V em m³: 1 se P·V > 100; 2 se 30 < P·V < 100;
  3 se 2,5 < P·V < 30; 4 se 1 < P·V < 2,5; 5 se P·V < 1. O texto retificado não diz em que grupo fica um valor
  exatamente igual a 100, 30, 2,5 ou 1: o Usinix adota o grupo de maior risco e avisa;
- categoria (Tabela 1) e prazos máximos das inspeções periódicas (13.5.4.5, Tabela 2).
Sem alterações da NR-13 posteriores a essa redação (confirmado em 10/11/2026).
"""

import datetime
import html
import os

import FreeCAD

import PrumoUtil
from PrumoUtil import fmt

NR13_FONTE = ("NR-13, redação da Portaria MTP n.º 1.846, de 01/07/2022 (vigência 03/10/2022), retificada em "
              "20/10/2022 — texto conferido no gov.br em 10/11/2026")
CLASSES = {
    "A": "fluidos inflamáveis; combustíveis a 200 °C ou mais; tóxicos com limite de tolerância de até 20 ppm; "
         "hidrogênio; acetileno",
    "B": "fluidos combustíveis abaixo de 200 °C; tóxicos com limite de tolerância acima de 20 ppm",
    "C": "vapor de água; gases asfixiantes simples; ar comprimido",
    "D": "outros fluidos não enquadrados nas classes anteriores",
}
CLASSES_LISTA = ["%s — %s" % (k, v) for k, v in CLASSES.items()]
CATEGORIAS = {  # Tabela 1 — classe: categorias dos grupos 1 a 5
    "A": ("I", "I", "II", "III", "III"),
    "B": ("I", "II", "III", "IV", "IV"),
    "C": ("I", "II", "III", "IV", "V"),
    "D": ("II", "III", "IV", "V", "V"),
}
PRAZOS = {  # Tabela 2 — categoria: (sem SPIE externo, interno, com SPIE externo, interno), em anos
    "I": (1, 3, 3, 6), "II": (2, 4, 4, 8), "III": (3, 6, 5, 10), "IV": (4, 8, 6, 12), "V": (5, 10, 7, None),
}
LIMITES = (100.0, 30.0, 2.5, 1.0)
TABELA = "<table width='100%' cellspacing='0' cellpadding='2'>"


def grupo(pv):
    """Grupo de potencial de risco (1 a 5) pelo produto P·V (MPa·m³). Devolve (grupo, aviso)."""
    pv = abs(float(pv))
    for g, lim in enumerate(LIMITES, start=1):
        if abs(pv - lim) < 1e-9:
            return g, ("P·V igual a %s MPa·m³: o texto da NR-13 (13.5.1.1.3, retificado) usa “maior que” e "
                       "“menor "
                       "que” e não enquadra o valor exato; adotado o grupo %d, de maior risco."
                       % (fmt(lim, 1 if lim < 10 else 0), g))
        if pv > lim:
            return g, ""
    return 5, ""


def categoria(classe, g):
    return CATEGORIAS[classe.strip()[:1].upper()][g - 1]


def classe_de(texto):
    t = (texto or "").strip()[:1].upper()
    return t if t in CLASSES else "C"


def enquadramento(p_mpa, v_m3, classe):
    """Enquadramento do vaso. p_mpa: pressão máxima de operação (MPa, manométrica); v_m3: volume interno."""
    classe = classe_de(classe)
    pv = abs(float(p_mpa)) * float(v_m3)
    pv_kpa = pv * 1000.0
    g, aviso = grupo(pv)
    cat = categoria(classe, g)
    pr = PRAZOS[cat]
    return {"classe": classe, "pv": pv, "pv_kpa": pv_kpa, "abrangido": pv_kpa > 8.0, "grupo": g,
            "categoria": cat, "prazos": pr, "aviso": aviso}


# ============================================================================ dados do memorial no vaso
CAMPOS = (  # (propriedade, rótulo, dica)
    ("MemTag", "Identificação (TAG / nº de série)", "Como o vaso é identificado na planta"),
    ("MemCliente", "Empresa / cliente", ""),
    ("MemLocal", "Local de instalação", ""),
    ("MemFluido", "Fluido", "Ex.: ar comprimido"),
    ("MemFabricante", "Fabricante", ""),
    ("MemAno", "Ano de fabricação", ""),
    ("MemCodigo", "Código de projeto e edição", "Ex.: ASME BPVC Seção VIII, Divisão 1, edição 2023"),
    ("MemResponsavel", "Responsável técnico", "Nome do profissional habilitado"),
    ("MemRegistro", "Registro (CREA)", ""),
    ("MemART", "Número da ART", ""),
    ("MemCidade", "Cidade", "Cidade da assinatura"),
)


def garantir_campos(v):
    """Propriedades do memorial no próprio vaso (ficam salvas no arquivo)."""
    for nome, rot, dica in CAMPOS:
        if nome not in v.PropertiesList:
            v.addProperty("App::PropertyString", nome, "Memorial NR-13",
                          "%s%s" % (rot, (" — " + dica) if dica else ""))
    if "MemClasseFluido" not in v.PropertiesList:
        v.addProperty("App::PropertyEnumeration", "MemClasseFluido", "Memorial NR-13",
                      "Classe do fluido (NR-13, 13.5.1.1.1)")
        v.MemClasseFluido = CLASSES_LISTA
        v.MemClasseFluido = CLASSES_LISTA[2]
    if "MemPressaoOperacao" not in v.PropertiesList:
        v.addProperty("App::PropertyFloat", "MemPressaoOperacao", "Memorial NR-13",
                      "Pressão máxima de operação (MPa, manométrica) para o enquadramento; 0 = a de projeto")
    if "MemSPIE" not in v.PropertiesList:
        v.addProperty("App::PropertyBool", "MemSPIE", "Memorial NR-13",
                      "Estabelecimento com Serviço Próprio de Inspeção de Equipamentos (SPIE) certificado")
    if "MemCodigo" in v.PropertiesList and not v.MemCodigo:
        v.MemCodigo = "ASME BPVC Seção VIII, Divisão 1 (informe a edição)"
    return v


def _e(t):
    return html.escape(str(t if t not in (None, "") else "—"))


def _p(v, mpa):
    import PrumoVaso
    return PrumoVaso.fmt_p(mpa, PrumoVaso._unid(v))


def montar(v, data=None):
    """HTML do memorial (devolve (html, avisos))."""
    import PrumoVaso
    garantir_campos(v)
    data = data or datetime.date.today()
    avisos = []
    try:
        c = v.Proxy.calculo(v)
    except (ValueError, ZeroDivisionError) as ex:
        raise ValueError("O cálculo do vaso não fecha: %s" % ex)
    p_op = v.MemPressaoOperacao or v.PressaoProjeto
    if not v.MemPressaoOperacao:
        avisos.append("Enquadramento com a pressão de projeto (a pressão máxima de operação não foi informada).")
    enq = enquadramento(p_op, v.VolumeInterno, v.MemClasseFluido)
    if enq["aviso"]:
        avisos.append(enq["aviso"])
    tc = v.EspessuraCostado.Value or PrumoVaso.chapa_acima(v.MinimoCostado)
    tt = v.EspessuraTampo.Value or PrumoVaso.chapa_acima(v.MinimoTampo)
    form = {0: "t = P·D / (2·S·E − 0,2·P)", 1: "t = 0,885·P·L / (S·E − 0,1·P)",
            2: "t = P·L / (2·S·E − 0,2·P)"}[c.tipo]
    pr = enq["prazos"]
    if v.MemSPIE:
        ext, inte = pr[2], pr[3]
        quem = "estabelecimento com SPIE"
    else:
        ext, inte = pr[0], pr[1]
        quem = "estabelecimento sem SPIE"
    inte_txt = ("%d anos" % inte) if inte else "a critério"

    def linha(rot, val):
        return "<tr><th width='40%%'>%s</th><td width='60%%'>%s</td></tr>" % (_e(rot), val)

    css = """
    body { font-family: 'Poppins', 'Segoe UI', Arial, sans-serif; font-size: 9pt; color: #1E2A38; }
    h1 { font-size: 17pt; color: #0F2A4A; margin: 0 0 2pt 0; }
    h2 { font-size: 11pt; color: #FFFFFF; background: #0F2A4A; padding: 2pt 6pt; margin: 9pt 0 3pt 0; }
    .sub { color: #5A6B7D; font-size: 9pt; }
    .faixa { background: #F7BE00; height: 4pt; }
    table { border-collapse: collapse; width: 100%; }
    th { text-align: left; font-weight: 600; color: #0F2A4A; width: 38%; padding: 2.5pt 6pt;
         border-bottom: 0.5pt solid #D5DDE6; vertical-align: top; }
    td { padding: 2.5pt 6pt; border-bottom: 0.5pt solid #D5DDE6; vertical-align: top; }
    .grade th, .grade td { border: 0.5pt solid #C5CFDA; text-align: center; width: auto; }
    .grade th { background: #E8EEF5; }
    .destaque { background: #FFF4CC; font-weight: 700; }
    .formula { font-family: 'Consolas', 'DejaVu Sans Mono', monospace; }
    .aviso { color: #8A4B00; }
    .assin { margin-top: 26pt; }
    .peq { font-size: 8pt; color: #5A6B7D; }
    """
    H = ["<html><head><meta charset='utf-8'><style>%s</style></head><body>" % css]
    H.append("<h1>Memorial de cálculo — vaso de pressão</h1>")
    H.append("<div class='sub'>%s · %s · emitido em %s</div>" % (
        _e(v.MemTag or v.Label), _e(v.MemCliente), data.strftime("%d/%m/%Y")))
    H.append("<table width='100%' cellspacing='0' cellpadding='0'><tr>"
             "<td bgcolor='#F7BE00' height='3' style='font-size:2pt'>&nbsp;"
             "</td></tr></table>")

    H.append("<h2>1. Identificação</h2>" + TABELA)
    for rot, val in (("Identificação (TAG / nº de série)", v.MemTag or v.Label),
                     ("Empresa / cliente", v.MemCliente),
                     ("Local de instalação", v.MemLocal), ("Fluido", v.MemFluido), ("Fabricante", v.MemFabricante),
                     ("Ano de fabricação", v.MemAno), ("Código de projeto", v.MemCodigo)):
        H.append(linha(rot, _e(val)))
    H.append("</table>")

    H.append("<h2>2. Dados de projeto</h2>" + TABELA)
    H.append(linha("Diâmetro interno", _e(fmt(v.DiametroInterno.Value, 1, "mm"))))
    H.append(linha("Comprimento entre tangentes", _e(fmt(v.ComprimentoCostado.Value, 1, "mm"))))
    H.append(linha("Posição / tampos", _e("%s; %s" % (v.Orientacao, v.TipoTampo))))
    H.append(linha("Pressão de projeto (P)", _e(_p(v, v.PressaoProjeto))))
    H.append(linha("Temperatura de projeto", _e(v.TemperaturaProjeto)))
    H.append(linha("Material das chapas", _e(v.MaterialChapa)))
    H.append(linha("Tensão admissível (S)", _e(fmt(v.TensaoAdmissivel, 1, "MPa"))))
    H.append(linha("Eficiência de junta (E)", _e(fmt(v.EficienciaJunta, 2))))
    H.append(linha("Sobre-espessura de corrosão (CA)", _e(fmt(v.Corrosao.Value, 2, "mm"))))
    H.append(linha("Volume interno (V)", _e(fmt(v.VolumeInterno, 3, "m³"))))
    H.append("</table>")

    H.append("<h2>3. Espessuras mínimas (pressão interna)</h2>" + TABELA)
    H.append(linha("Costado — tensão circunferencial (UG-27(c)(1))",
                   "<span class='formula'>t = P·R / (S·E − 0,6·P)</span> = <b>%s</b>"
                   % _e(fmt(c.t_circ, 3, "mm"))))
    H.append(linha("Costado — tensão longitudinal (UG-27(c)(2))",
                   "<span class='formula'>t = P·R / (2·S·E + 0,4·P)</span> = <b>%s</b>"
                   % _e(fmt(c.t_long, 3, "mm"))))
    tampo_ref = {0: "UG-32(d)", 1: "UG-32(e)", 2: "UG-32(f)"}[c.tipo]
    extra = ""
    if c.tipo == 1:
        extra = "<br><span class='peq'>L = raio interno da coroa = %s; r = 6 %% de L</span>" % _e(
            fmt(c.L_tampo, 1, "mm"))
    H.append(linha("Tampo %s (%s)" % (v.TipoTampo, tampo_ref),
                   "<span class='formula'>%s</span> = <b>%s</b>%s" % (form, _e(fmt(c.t_tampo, 3, "mm")), extra)))
    H.append(linha("R, D e L", "medidas internas acrescidas da corrosão (raio + CA)"))
    H.append(linha("Mínimas com corrosão", _e("costado %s; tampo %s" % (fmt(v.MinimoCostado, 2, "mm"),
                                                                        fmt(v.MinimoTampo, 2, "mm")))))
    H.append(linha("Espessuras adotadas", "<b>%s</b>" % _e("costado %s; tampo %s" % (fmt(tc, 2, "mm"),
                                                                                       fmt(tt, 2, "mm")))))
    H.append("</table>")

    H.append("<h2>4. Pressão máxima de trabalho admissível e teste</h2>" + TABELA)
    H.append(linha("PMTA do costado (espessura adotada − corrosão)", _e(_p(v, v.PMTACostado))))
    H.append(linha("PMTA do tampo (espessura adotada − corrosão)", _e(_p(v, v.PMTATampo))))
    H.append(linha("PMTA do vaso", "<b>%s</b>" % _e(_p(v, min(v.PMTACostado, v.PMTATampo)))))
    if v.PressaoTeste:
        k = "1,3" if v.TipoTeste.startswith("Hidro") else "1,1"
        H.append(linha("Teste de pressão (%s)" % v.TipoTeste,
                       "<span class='formula'>Pt = %s × PMTA × (S teste / S projeto)</span> = <b>%s</b> no topo; "
                       "%s no ponto mais baixo" % (k, _e(_p(v, v.PressaoTeste)), _e(_p(v, v.PressaoTesteFundo)))))
        if v.TensaoTeste:
            H.append(linha("Tensão de membrana no teste (vaso novo)", _e(fmt(v.TensaoTeste, 1, "MPa"))))
    H.append("</table>")

    H.append("<h2>5. Enquadramento na NR-13</h2>" + TABELA)
    H.append(linha("Pressão máxima de operação (P)", _e(_p(v, p_op))))
    H.append(linha("Produto P·V", _e("%s MPa·m³ (%s kPa·m³)" % (fmt(enq["pv"], 3), fmt(enq["pv_kpa"], 1)))))
    H.append(linha("Abrangência (13.2.1, b: P·V > 8, P em kPa)",
                   "<b>%s</b>" % ("abrangido pela NR-13" if enq["abrangido"] else
                                  "P·V até 8 kPa·m³: fora da alínea b de 13.2.1 (conferir os demais critérios "
                                  "da norma)")))
    H.append(linha("Classe do fluido (13.5.1.1.1)", _e("%s — %s" % (enq["classe"], CLASSES[enq["classe"]]))))
    H.append(linha("Grupo de potencial de risco (13.5.1.1.3)", "<b>%d</b>" % enq["grupo"]))
    H.append(linha("Categoria (Tabela 1)", "<b>%s</b>" % enq["categoria"]))
    H.append("</table>")
    H.append("<p class='peq'>Tabela 1 da NR-13 — categoria por classe de fluido e grupo de potencial de risco:</p>")
    H.append("<table class='grade' border='1' cellspacing='0' cellpadding='2' width='70%%'><tr><th>Classe</th>%s</tr>"
             % "".join("<th>Grupo %d</th>" % g for g in range(1, 6)))
    for cl, cats in CATEGORIAS.items():
        cel = []
        for g, ct in enumerate(cats, start=1):
            marca = " class='destaque'" if cl == enq["classe"] and g == enq["grupo"] else ""
            cel.append("<td%s>%s</td>" % (marca, ct))
        H.append("<tr><th>%s</th>%s</tr>" % (cl, "".join(cel)))
    H.append("</table>")
    H.append("<p>Prazos máximos das inspeções de segurança periódicas (13.5.4.5, Tabela 2), %s, categoria %s: "
             "<b>exame externo a cada %d %s; exame interno: %s</b>.</p>" % (
                 quem, enq["categoria"], ext, "ano" if ext == 1 else "anos", inte_txt))

    todos = avisos + list(v.Avisos or [])
    if todos:
        H.append("<h2>6. Avisos</h2><ul>")
        H.extend("<li class='aviso'>%s</li>" % _e(a) for a in todos)
        H.append("</ul>")
    n = 7 if todos else 6
    H.append("<h2>%d. Limites deste memorial</h2>" % n)
    H.append("<p>Pré-dimensionamento por pressão interna. Não calculados: reforço de aberturas (UG-37), pressão "
             "externa e vácuo (UG-28), cargas de vento, sismo, apoios e cargas localizadas. A tensão admissível e a "
             "edição do código são as informadas pelo responsável técnico, a quem cabe a verificação final.</p>")
    H.append("<p class='peq'>Referências: ASME BPVC Seção VIII, Divisão 1 (edição informada acima) — UG-27, UG-32, "
             "UG-99/UG-100. %s.</p>" % _e(NR13_FONTE))

    H.append("<br><table class='assin' style='page-break-inside: avoid' width='100%%' cellspacing='0' "
             "cellpadding='2'><tr>"
             "<td width='45%%' style='border:none' valign='bottom'>%s, %s</td>"
             "<td width='55%%' style='border:none' align='center'>______________________________<br>"
             "<b>%s</b><br>%s<br>ART nº %s</td></tr></table>" % (
                 _e(v.MemCidade or "________________"), data.strftime("%d/%m/%Y"), _e(v.MemResponsavel),
                 _e(("CREA " + v.MemRegistro) if v.MemRegistro else "CREA ________"), _e(v.MemART or "________")))
    H.append("<p class='peq'>Gerado pelo Usinix %s a partir do modelo %s.</p>" % (_versao(), _e(v.Label)))
    H.append("</body></html>")
    return "".join(H), todos


def _versao():
    try:
        import PrumoVersao
        return PrumoVersao.VERSAO
    except Exception:
        return ""


def _fontes():
    try:
        from PySide import QtGui
        pasta = os.path.join(PrumoUtil.RES_DIR, "fonts")
        for f in ("Poppins-Regular.ttf", "Poppins-SemiBold.ttf", "Poppins-Bold.ttf"):
            p = os.path.join(pasta, f)
            if os.path.isfile(p):
                QtGui.QFontDatabase.addApplicationFont(p)
    except Exception:
        pass


def salvar_pdf(v, caminho, data=None):
    """Grava o memorial em PDF A4. Devolve (caminho, avisos)."""
    from PySide import QtCore, QtGui
    _fontes()
    texto, avisos = montar(v, data)
    doc = QtGui.QTextDocument()
    doc.setDefaultFont(QtGui.QFont("Poppins", 9))
    doc.setHtml(texto)
    escritor = QtGui.QPdfWriter(caminho)
    escritor.setPageSize(QtGui.QPageSize(QtGui.QPageSize.A4))
    escritor.setPageMargins(QtCore.QMarginsF(18, 16, 15, 16), QtGui.QPageLayout.Millimeter)
    escritor.setResolution(300)
    escritor.setTitle("Memorial de cálculo — %s" % (v.MemTag or v.Label))
    escritor.setCreator("Usinix")
    imprimir = getattr(doc, "print_", None) or getattr(doc, "print")
    imprimir(escritor)
    return caminho, avisos


# ============================================================================ interface
try:
    import FreeCADGui
    from PySide import QtCore, QtWidgets
except ImportError:
    FreeCADGui = None


def _vaso_selecionado():
    if FreeCADGui is None:
        return None
    for o in FreeCADGui.Selection.getSelection():
        if "PressaoProjeto" in o.PropertiesList:
            return o
    doc = FreeCAD.ActiveDocument
    vs = [o for o in (doc.Objects if doc else []) if "PressaoProjeto" in o.PropertiesList]
    return vs[0] if len(vs) == 1 else None


if FreeCADGui is not None:
    class JanelaMemorial(QtWidgets.QDialog):
        def __init__(self, v, parent=None):
            super().__init__(parent or FreeCADGui.getMainWindow())
            import PrumoUI as UI
            self.setObjectName("PrumoUI")
            self.setStyleSheet(UI.qss())
            self.v = garantir_campos(v)
            self.setWindowTitle("Memorial NR-13 — %s" % v.Label)
            self.setMinimumWidth(620)
            lay = QtWidgets.QVBoxLayout(self)
            intro = QtWidgets.QLabel("Preencha a identificação e o responsável técnico. Os dados ficam salvos no "
                                     "vaso; o PDF sai com o cálculo, o enquadramento na NR-13 e o campo de assinatura.")
            intro.setWordWrap(True)
            lay.addWidget(intro)
            form = QtWidgets.QFormLayout()
            self.campos = {}
            for nome, rot, dica in CAMPOS:
                e = QtWidgets.QLineEdit(getattr(v, nome))
                if dica:
                    e.setPlaceholderText(dica)
                form.addRow(rot, e)
                self.campos[nome] = e
            self.classe = QtWidgets.QComboBox()
            self.classe.addItems(CLASSES_LISTA)
            self.classe.setCurrentText(v.MemClasseFluido)
            form.addRow("Classe do fluido", self.classe)
            self.pop = QtWidgets.QDoubleSpinBox()
            self.pop.setRange(0.0, 1000.0)
            self.pop.setDecimals(3)
            self.pop.setSuffix(" MPa")
            self.pop.setValue(float(v.MemPressaoOperacao or 0.0))
            self.pop.setSpecialValueText("a de projeto")
            form.addRow("Pressão máx. de operação", self.pop)
            self.spie = QtWidgets.QCheckBox("Estabelecimento com SPIE certificado")
            self.spie.setChecked(bool(v.MemSPIE))
            form.addRow("", self.spie)
            lay.addLayout(form)
            self.resumo = QtWidgets.QLabel()
            self.resumo.setWordWrap(True)
            self.resumo.setObjectName("PrumoSub")
            lay.addWidget(self.resumo)
            bts = QtWidgets.QHBoxLayout()
            bts.addStretch(1)
            fechar = QtWidgets.QPushButton("Fechar")
            fechar.clicked.connect(self.reject)
            self.pdf = QtWidgets.QPushButton("Salvar PDF")
            self.pdf.setObjectName("PrumoPrimario")
            self.pdf.setDefault(True)
            self.pdf.clicked.connect(self.salvar)
            bts.addWidget(fechar)
            bts.addWidget(self.pdf)
            lay.addLayout(bts)
            self.classe.currentIndexChanged.connect(self._resumo)
            self.pop.valueChanged.connect(self._resumo)
            self._resumo()

        def gravar(self):
            v = self.v
            for nome, e in self.campos.items():
                setattr(v, nome, e.text().strip())
            v.MemClasseFluido = self.classe.currentText()
            v.MemPressaoOperacao = float(self.pop.value())
            v.MemSPIE = self.spie.isChecked()

        def _resumo(self, *_a):
            p = self.pop.value() or self.v.PressaoProjeto
            e = enquadramento(p, self.v.VolumeInterno, self.classe.currentText())
            self.resumo.setText("P·V = %s MPa·m³ → grupo %d, categoria %s%s" % (
                fmt(e["pv"], 3), e["grupo"], e["categoria"],
                "" if e["abrangido"] else " (P·V até 8 kPa·m³: fora da alínea b de 13.2.1)"))

        def salvar(self):
            self.gravar()
            pasta = os.path.dirname(self.v.Document.FileName) if self.v.Document.FileName else os.path.expanduser("~")
            nome = "Memorial NR-13 - %s.pdf" % (self.v.MemTag or self.v.Label).replace("/", "-")
            caminho, _f = QtWidgets.QFileDialog.getSaveFileName(self, "Salvar memorial", os.path.join(pasta, nome),
                                                                "PDF (*.pdf)")
            if not caminho:
                return None
            if not caminho.lower().endswith(".pdf"):
                caminho += ".pdf"
            try:
                salvar_pdf(self.v, caminho)
            except Exception as ex:
                QtWidgets.QMessageBox.warning(self, "Memorial NR-13", "Não foi possível gerar o PDF: %s" % ex)
                return None
            try:
                from PySide import QtGui
                QtGui.QDesktopServices.openUrl(QtCore.QUrl.fromLocalFile(caminho))
            except Exception:
                pass
            self.accept()
            return caminho

    class CmdMemorialNR13:
        def GetResources(self):
            return {"Pixmap": PrumoUtil.icone("memorial_nr13.svg"), "MenuText": "Memorial NR-13",
                    "ToolTip": "Gera o memorial de cálculo do vaso em PDF: espessuras, PMTA, teste, enquadramento na "
                               "NR-13 (grupo e categoria) e campo do responsável técnico para a ART."}

        def IsActive(self):
            return _vaso_selecionado() is not None

        def Activated(self):
            v = _vaso_selecionado()
            j = JanelaMemorial(v)
            j.exec_() if hasattr(j, "exec_") else j.exec()


def registrar_comandos():
    if FreeCADGui is not None and "Prumo_MemorialNR13" not in FreeCADGui.listCommands():
        FreeCADGui.addCommand("Prumo_MemorialNR13", CmdMemorialNR13())
