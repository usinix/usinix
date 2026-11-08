# SPDX-License-Identifier: LGPL-2.1-or-later
# Usinix - Desenho › Inserir peça ou montagem: escolhe o que desenhar numa lista (sem selecionar antes),
# a folha (nova ou a que está aberta), o formato, a orientação e as vistas; a escala que cabe sai sozinha.

import FreeCAD
import FreeCADGui

import PrumoFolhas as F
import PrumoPainel as P
import PrumoUtil

try:
    from PySide import QtCore, QtGui, QtWidgets
except ImportError:  # pragma: no cover
    from PySide2 import QtCore, QtGui, QtWidgets

# tipos que não entram na lista (não são peça)
_FORA = ("TechDraw::", "Sketcher::", "Spreadsheet::", "Fem::", "App::Origin", "App::VarSet", "App::Line",
         "App::Plane", "App::Point", "App::MaterialObject", "App::TextDocument")


def tipo_legivel(obj):
    t = obj.TypeId
    proxy = getattr(getattr(obj, "Proxy", None), "__class__", None)
    nome_proxy = proxy.__name__ if proxy else ""
    if t.startswith("Assembly::"):
        return "Montagem"
    if t == "PartDesign::Body":
        return "Peça"
    if t == "App::Part":
        return "Conjunto"
    if "Estrutura" in nome_proxy:
        return "Estrutura"
    if "Tubulacao" in nome_proxy:
        return "Tubulação"
    if "Vaso" in nome_proxy:
        return "Vaso"
    if "Piso" in nome_proxy:
        return "Piso"
    if t.startswith("App::DocumentObjectGroup"):
        return "Grupo"
    return "Sólido"


def _dentro_de_conjunto(o):
    """True se o objeto está dentro de um corpo, conjunto, montagem, estrutura ou outro grupo (pasta comum não
    conta: o que está numa pasta continua sendo do nível de cima). Quem só USA o objeto (vistas de uma folha,
    operações) não o esconde da lista."""
    for p in o.InList:
        if p.TypeId == "App::DocumentObjectGroup":
            continue
        if o in (getattr(p, "Group", None) or []):
            return True
    return False


def candidatos(doc):
    """Objetos do documento que podem ir para o desenho: os que têm sólido e não estão dentro de outro conjunto.
    Estrutura, montagem, conjunto e corpo entram inteiros; pastas comuns não aparecem, mas o que está nelas sim."""
    if doc is None:
        return []
    res = []
    for o in doc.Objects:
        if o.TypeId.startswith(_FORA) or o.TypeId == "App::DocumentObjectGroup":
            continue
        if _dentro_de_conjunto(o):
            continue
        try:
            if PrumoUtil.tem_peca([o]):
                res.append(o)
        except Exception:
            pass
    return res


def _visivel(o):
    try:
        return bool(o.ViewObject.Visibility)
    except Exception:
        return True


def pagina_ativa():
    """Folha aberta na janela do meio (ou None)."""
    try:
        v = FreeCADGui.activeView()
        if v is not None and hasattr(v, "getPage"):
            return v.getPage()
    except Exception:
        pass
    return None


# ------------------------------------------------------------------ ícones desenhados (sem arquivo)
def _pixmap(desenho, w=56, h=40):
    pm = QtGui.QPixmap(w * 2, h * 2)
    pm.fill(QtCore.Qt.transparent)
    p = QtGui.QPainter(pm)
    p.setRenderHint(QtGui.QPainter.Antialiasing)
    p.scale(2, 2)
    desenho(p, w, h)
    p.end()
    return QtGui.QIcon(pm)


_AZUL = QtGui.QColor("#1E5A96")
_NOITE = QtGui.QColor("#0F2A4A")
_CLARO = QtGui.QColor("#E8F0FA")
_AMBAR = QtGui.QColor("#F2A900")


def icone_orientacao(retrato):
    def d(p, w, h):
        fw, fh = (20, 28) if retrato else (30, 21)
        x, y = (w - fw) / 2.0, (h - fh) / 2.0
        p.setPen(QtGui.QPen(_NOITE, 1.6))
        p.setBrush(_CLARO)
        p.drawRect(QtCore.QRectF(x, y, fw, fh))
        p.setPen(QtCore.Qt.NoPen)
        p.setBrush(_AMBAR)
        p.drawRect(QtCore.QRectF(x + fw - 9, y + fh - 5, 7, 3))   # legenda
    return _pixmap(d)


def icone_arranjo(chave):
    _rot, proj, iso = F.ARRANJOS[chave]
    proj = set(proj)

    def d(p, w, h):
        p.setPen(QtGui.QPen(_AZUL, 1.4))
        p.setBrush(_CLARO)
        x0 = 6
        if "Front" in proj:
            p.drawRect(QtCore.QRectF(x0, 6, 14, 11))
            if "Left" in proj:
                p.drawRect(QtCore.QRectF(x0 + 17, 6, 9, 11))
            if "Top" in proj:
                p.drawRect(QtCore.QRectF(x0, 20, 14, 9))
        if iso:
            cx = 42 if proj else w / 2.0
            cy = 16 if proj else h / 2.0
            s = 7.0 if proj else 9.0
            top = [QtCore.QPointF(cx, cy - s), QtCore.QPointF(cx + s, cy - s / 2), QtCore.QPointF(cx, cy),
                   QtCore.QPointF(cx - s, cy - s / 2)]
            p.setBrush(QtGui.QColor("#BFD4EE"))
            p.drawPolygon(QtGui.QPolygonF(top))
            p.setBrush(_CLARO)
            p.drawPolygon(QtGui.QPolygonF([QtCore.QPointF(cx - s, cy - s / 2), QtCore.QPointF(cx, cy),
                                          QtCore.QPointF(cx, cy + s), QtCore.QPointF(cx - s, cy + s / 2)]))
            p.setBrush(QtGui.QColor("#8FB4DE"))
            p.drawPolygon(QtGui.QPolygonF([QtCore.QPointF(cx, cy), QtCore.QPointF(cx + s, cy - s / 2),
                                          QtCore.QPointF(cx + s, cy + s / 2), QtCore.QPointF(cx, cy + s)]))
    return _pixmap(d)


# ------------------------------------------------------------------ vistas numa folha que já existe
def vistas_na_folha(page, objs, arranjo=F.ARRANJO_PADRAO, escala=None):
    """Põe as vistas das peças numa folha existente. Se a folha já tem vistas, usa a mesma escala dela."""
    doc = page.Document
    ja_tem = any(v.isDerivedFrom("TechDraw::DrawViewPart") or v.isDerivedFrom("TechDraw::DrawProjGroup")
                 for v in page.Views)
    if escala is None and ja_tem:
        escala = page.Scale
    doc.openTransaction("Inserir vistas")
    try:
        vista = F._vistas(doc, page, objs, escala, arranjo)
        F.escrever_escala(page)
        doc.recompute()
    finally:
        doc.commitTransaction()
    return vista


def _bloco(secao, rotulo_, widget, dica=""):
    """Rótulo + campo num bloco só (para esconder a linha inteira)."""
    w = QtWidgets.QWidget()
    lay = QtWidgets.QVBoxLayout(w)
    lay.setContentsMargins(0, 0, 0, 0)
    lay.setSpacing(2)
    lb = QtWidgets.QLabel(rotulo_)
    lb.setObjectName("PrumoDica")
    lay.addWidget(lb)
    lay.addWidget(widget)
    if dica:
        widget.setToolTip(dica)
    secao.widget(w)
    return w


# ------------------------------------------------------------------ painel
class PainelInserir(P.PainelTarefa):
    titulo = "Inserir peça ou montagem"
    ajuda = "Marque o que vai para o desenho, escolha a folha e as vistas. A escala que cabe sai sozinha."

    def __init__(self, doc=None):
        self.doc = doc or FreeCAD.ActiveDocument
        self.pagina = pagina_ativa()
        if self.pagina is not None and self.pagina.Document is not self.doc:
            self.pagina = None
        super().__init__()

    def _preencher_com_selecao(self):
        """A seleção atual só marca itens da lista (não é obrigatória)."""
        try:
            sel = {o.Name for o in FreeCADGui.Selection.getSelection(self.doc.Name)} if self.doc else set()
        except Exception:
            sel = set()
        marcou = False
        for i in range(self.lista.count()):
            it = self.lista.item(i)
            if it.data(QtCore.Qt.UserRole) in sel:
                it.setCheckState(QtCore.Qt.Checked)
                marcou = True
        if not marcou and self.lista.count() == 1:
            self.lista.item(0).setCheckState(QtCore.Qt.Checked)

    def montar(self):
        f = self.form
        param = F.FREECAD_PARAM()
        # ---- o que desenhar
        s0 = f.secao("O que desenhar", "selecao")
        self.lista = QtWidgets.QListWidget()
        self.lista.setObjectName("PrumoListaPecas")
        self.lista.setMinimumHeight(150)
        self.lista.setIconSize(QtCore.QSize(20, 20))
        cands = candidatos(self.doc)
        cands.sort(key=lambda o: (not _visivel(o),))
        for o in cands:
            it = QtWidgets.QListWidgetItem("%s  ·  %s%s" % (o.Label, tipo_legivel(o), "" if _visivel(o) else " (oculto)"))
            try:
                it.setIcon(o.ViewObject.Icon)
            except Exception:
                pass
            it.setData(QtCore.Qt.UserRole, o.Name)
            it.setFlags(it.flags() | QtCore.Qt.ItemIsUserCheckable)
            it.setCheckState(QtCore.Qt.Unchecked)
            self.lista.addItem(it)
        self.lista.itemChanged.connect(lambda *_a: self.atualizar())
        self.lista.itemDoubleClicked.connect(self._alternar_item)
        s0.widget(self.lista)
        if not cands:
            s0.texto("Este documento ainda não tem peça, montagem ou estrutura com sólido.")
        # ---- onde
        s1 = f.secao("Folha", "folha")
        opcoes_onde = [("nova", "Folha nova", "folha", "Cria uma folha ABNT com as vistas")]
        if self.pagina is not None:
            opcoes_onde.append(("aberta", "Na folha aberta", "posicao", "Põe as vistas em %s" % self.pagina.Label))
        self.onde = P.Opcoes(opcoes_onde, "aberta" if self.pagina is not None else "nova")
        if len(opcoes_onde) > 1:
            _bloco(s1, "Onde", self.onde, "Onde as vistas entram.")
        self.formato = P.Opcoes([(k, k, "folha", "Formato %s" % k) for k in ("A4", "A3", "A2", "A1", "A0")],
                                param.GetString("FolhaFormato", F.FORMATO_PADRAO), colunas=5)
        for b in self.formato.botoes.values():
            b.setToolButtonStyle(QtCore.Qt.ToolButtonTextOnly)
            b.setMinimumWidth(40)
        self._lin_formato = _bloco(s1, "Formato", self.formato, "A4 a A0.")
        self.orientacao = P.Opcoes([("horizontal", "Horizontal", icone_orientacao(False), "Folha deitada (paisagem)"),
                                    ("vertical", "Vertical", icone_orientacao(True), "Folha em pé (retrato)")],
                                   param.GetString("FolhaOrientacao", "horizontal"))
        for b in self.orientacao.botoes.values():
            b.setIconSize(QtCore.QSize(42, 30))
        self._lin_orient = _bloco(s1, "Orientação", self.orientacao, "Deitada ou em pé.")
        self.norma = QtWidgets.QComboBox()
        for k, v in F.NORMAS.items():
            self.norma.addItem(v, k)
        self.norma.setCurrentIndex(max(self.norma.findData(param.GetString("FolhaNorma", F.NORMA_PADRAO)), 0))
        self._lin_norma = _bloco(s1, "Padrão da folha", self.norma, "Modelo de legenda.")
        # ---- vistas
        s2 = f.secao("Vistas", "posicao")
        self.arranjo = P.Opcoes([(k, rot.replace(", ", ",\n", 1) if len(rot) > 22 else rot, icone_arranjo(k), rot)
                                 for k, (rot, _p, _i) in F.ARRANJOS.items()],
                                param.GetString("FolhaArranjo", F.ARRANJO_PADRAO), colunas=2)
        for b in self.arranjo.botoes.values():
            b.setIconSize(QtCore.QSize(56, 40))
        s2.widget(self.arranjo)
        self.escala = QtWidgets.QComboBox()
        self.escala.addItem("Automática (a maior que cabe)", 0.0)
        for e in F.ESCALAS_NORMAIS:
            self.escala.addItem(F._texto_escala(e), e)
        _bloco(s2, "Escala", self.escala, "Série normalizada 1:2, 1:5, 1:10...")
        self.resumo = QtWidgets.QLabel()
        self.resumo.setWordWrap(True)
        self.resumo.setObjectName("PrumoDica")
        s2.widget(self.resumo)
        # ---- legenda (só folha nova)
        self.s3 = f.secao("Legenda", "texto", aberta=False)
        self.campos = {}
        for chave, rotulo_, ic in (("titulo", "Título", "texto"), ("numero", "Nº do desenho", "quantidade"),
                                   ("desenhista", "Desenhista", "texto"), ("revisao", "Revisão", "texto")):
            self.campos[chave] = self.s3.linha(ic, QtWidgets.QLineEdit(), rotulo_, rotulo_)
        for w in (self.onde, self.formato, self.orientacao, self.arranjo):
            w.mudou.connect(lambda *_a: self.atualizar())
        self.escala.currentIndexChanged.connect(lambda *_a: self.atualizar())
        self.norma.currentIndexChanged.connect(lambda *_a: self.atualizar())

    def _alternar_item(self, it):
        it.setCheckState(QtCore.Qt.Unchecked if it.checkState() == QtCore.Qt.Checked else QtCore.Qt.Checked)

    # ---- valores
    @property
    def objs(self):
        if self.doc is None:
            return []
        out = []
        for i in range(self.lista.count()):
            it = self.lista.item(i)
            if it.checkState() == QtCore.Qt.Checked:
                o = self.doc.getObject(it.data(QtCore.Qt.UserRole))
                if o is not None:
                    out.append(o)
        return out

    def folha_nova(self):
        return self.onde.valor() != "aberta" or self.pagina is None

    def _escala_prevista(self):
        e = self.escala.currentData() or 0.0
        if e:
            return e
        objs = self.objs
        if not objs:
            return None
        _rot, proj, iso = F.ARRANJOS[self.arranjo.valor()]
        if self.folha_nova():
            larg, alt = F.FORMATOS_MM[self.formato.valor()]
            if self.orientacao.valor() == "vertical":
                larg, alt = min(larg, alt), max(larg, alt)
        else:
            if any(v.isDerivedFrom("TechDraw::DrawViewPart") or v.isDerivedFrom("TechDraw::DrawProjGroup")
                   for v in self.pagina.Views):
                return self.pagina.Scale
            larg, alt = F._tamanho_folha(self.pagina)
        try:
            return F.escala_que_cabe(objs, larg - 30, alt - 20 - 60, proj, iso)
        except Exception:
            return None

    def atualizar(self):
        nova = self.folha_nova()
        for w in (self._lin_formato, self._lin_orient, self._lin_norma, self.s3):
            if w is not None:
                w.setVisible(nova)
        e = self._escala_prevista()
        if e:
            onde = ("%s %s" % (self.formato.valor(), self.orientacao.valor())) if nova else self.pagina.Label
            self.resumo.setText("Escala %s · %s" % (F._texto_escala(e), onde))
        else:
            self.resumo.setText("Marque o que vai para o desenho.")
        super().atualizar()

    def pendencia(self):
        if self.doc is None:
            return "Abra ou crie um documento com a peça."
        if not self.objs:
            return "Marque na lista o que vai para o desenho."
        return None

    def pronto_texto(self):
        n = len(self.objs)
        return "Pronto: %d item(ns) no desenho. OK cria e abre a folha." % n

    def executar(self):
        objs = self.objs
        arranjo = self.arranjo.valor()
        escala = self.escala.currentData() or None
        param = F.FREECAD_PARAM()
        param.SetString("FolhaArranjo", arranjo)
        try:
            import TechDraw  # noqa: F401
            import TechDrawGui  # noqa: F401
        except ImportError:
            pass
        if not self.folha_nova():
            vistas_na_folha(self.pagina, objs, arranjo, escala)
            page = self.pagina
        else:
            formato, norma = self.formato.valor(), self.norma.currentData()
            retrato = self.orientacao.valor() == "vertical"
            param.SetString("FolhaFormato", formato)
            param.SetString("FolhaNorma", norma)
            param.SetString("FolhaOrientacao", self.orientacao.valor())
            campos = {k: w.text().strip() for k, w in self.campos.items() if w.text().strip()}
            page = F.nova_folha(self.doc, formato, norma, retrato, campos, objs, escala, arranjo)
        QtCore.QTimer.singleShot(0, lambda: F._abrir_folha(page))
        return page


class CmdInserirDesenho:
    def GetResources(self):
        return {"Pixmap": PrumoUtil.icone("inserir_desenho.svg"),
                "MenuText": "Inserir peça ou montagem",
                "ToolTip": "Escolhe numa lista a peça, montagem ou estrutura e põe as vistas numa folha nova ou na "
                           "folha aberta, na escala que cabe. Não precisa selecionar antes."}

    def IsActive(self):
        return FreeCAD.ActiveDocument is not None

    def Activated(self):
        PainelInserir(FreeCAD.ActiveDocument).mostrar()


def registrar_comandos():
    FreeCADGui.addCommand("Prumo_InserirDesenho", CmdInserirDesenho())
