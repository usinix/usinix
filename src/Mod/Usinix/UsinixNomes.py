# SPDX-License-Identifier: LGPL-2.1-or-later
"""Nomes em português na árvore do modelo.

O FreeCAD dá a cada objeto novo um rótulo igual ao nome interno, em inglês ("Pad", "Pocket001",
"Sketch"). Este observador troca o rótulo pelo nome em português logo depois da criação
("Extrusão", "Cavidade001", "Esboço"). O nome interno (Name) continua o mesmo, então macros,
expressões e arquivos antigos seguem funcionando.

Só age em objetos criados agora: arquivos abertos, objetos colados/importados e desfazer/refazer
ficam como estão.
"""

import re

import FreeCAD

try:
    from PySide import QtCore
except ImportError:  # pragma: no cover
    from PySide2 import QtCore

PARAM_PATH = "User parameter:BaseApp/Preferences/Mod/Usinix"

# rótulo base em inglês → português
NOMES = {
    # Peça (PartDesign)
    "Body": "Corpo", "Sketch": "Esboço", "Pad": "Extrusão", "Pocket": "Cavidade", "Revolution": "Revolução",
    "Groove": "Ranhura", "Hole": "Furo", "Fillet": "Arredondamento", "Chamfer": "Chanfro",
    "Draft": "Ângulo de saída", "Thickness": "Casca", "Mirrored": "Espelhamento",
    "LinearPattern": "Padrão linear", "PolarPattern": "Padrão circular", "MultiTransform": "Transformação múltipla",
    "Scaled": "Escala", "AdditiveLoft": "Loft aditivo", "SubtractiveLoft": "Loft subtrativo",
    "AdditivePipe": "Varredura aditiva", "SubtractivePipe": "Varredura subtrativa",
    "AdditiveHelix": "Hélice aditiva", "SubtractiveHelix": "Hélice subtrativa",
    "AdditiveBox": "Caixa aditiva", "SubtractiveBox": "Caixa subtrativa",
    "AdditiveCylinder": "Cilindro aditivo", "SubtractiveCylinder": "Cilindro subtrativo",
    "AdditiveSphere": "Esfera aditiva", "SubtractiveSphere": "Esfera subtrativa",
    "AdditiveCone": "Cone aditivo", "SubtractiveCone": "Cone subtrativo",
    "DatumPlane": "Plano de referência", "DatumLine": "Linha de referência", "DatumPoint": "Ponto de referência",
    "LocalCoordinateSystem": "Sistema de coordenadas local", "ShapeBinder": "Vínculo de forma",
    "SubShapeBinder": "Vínculo de subforma", "Binder": "Vínculo",
    "InvoluteGear": "Engrenagem evolvente", "Sprocket": "Roda dentada",
    # origem (eixos e planos)
    "Origin": "Origem", "X_Axis": "Eixo X", "Y_Axis": "Eixo Y", "Z_Axis": "Eixo Z",
    "XY_Plane": "Plano XY", "XZ_Plane": "Plano XZ", "YZ_Plane": "Plano YZ",
    # estrutura do documento
    "Part": "Parte", "Group": "Grupo", "Link": "Vínculo", "VarSet": "Variáveis",
    # Sólidos (Part)
    "Box": "Caixa", "Cylinder": "Cilindro", "Sphere": "Esfera", "Cone": "Cone", "Torus": "Toro",
    "Prism": "Prisma", "Wedge": "Cunha", "Tube": "Tubo", "Cut": "Subtração", "Fusion": "União",
    "Common": "Interseção", "Extrude": "Extrusão", "Revolve": "Revolução", "Mirror": "Espelho",
    "Offset": "Deslocamento", "Offset2D": "Deslocamento 2D", "Loft": "Loft", "Sweep": "Varredura",
    "Section": "Seção", "Compound": "Composto", "Refine": "Refinado",
    # Desenho técnico, planilha, montagem
    "Page": "Folha", "Template": "Modelo de folha", "View": "Vista", "ProjGroup": "Grupo de vistas",
    "Dimension": "Cota", "Balloon": "Balão", "Spreadsheet": "Planilha", "Assembly": "Montagem",
    "Joints": "Juntas", "GroundedJoint": "Fixação", "Measure": "Medida",
}

# vistas do grupo de projeção: o TechDraw dá a cada uma o tipo como rótulo ("Front", "FrontTopRight")
PROJECOES = {
    "Front": "Frontal", "Rear": "Posterior", "Top": "Superior", "Bottom": "Inferior",
    "Left": "Lateral esquerda", "Right": "Lateral direita",
    "FrontTopLeft": "Isométrica superior esquerda", "FrontTopRight": "Isométrica superior direita",
    "FrontBottomLeft": "Isométrica inferior esquerda", "FrontBottomRight": "Isométrica inferior direita",
}

# rótulos que o pt-BR do FreeCAD dá (diferentes dos nomes da faixa e da Paleta de vistas)
PROJECOES_QM = {"Frente", "Topo", "Esquerda", "Direito", "Direita", "Traseira", "De baixo", "Fundo"}

_RE = re.compile(r"^(.*?)(\d{3})?$")


def traduzir(rotulo):
    """'Pad' → 'Extrusão', 'Pocket001' → 'Cavidade001'. None se não houver tradução."""
    m = _RE.match(rotulo or "")
    if not m:
        return None
    base, num = m.group(1), m.group(2) or ""
    pt = NOMES.get(base)
    return pt + num if pt else None


def _ligado():
    return FreeCAD.ParamGet(PARAM_PATH).GetBool("NomesEmPortugues", True)


def _documento_ocupado(doc):
    for flag in ("Restoring", "Importing", "Transacting"):
        try:
            if getattr(doc, flag):
                return True
        except Exception:
            pass
    return False


def _dono_da_origem(obj):
    """Corpo, parte ou montagem cuja origem é `obj` (ou None)."""
    try:
        if obj.TypeId != "App::Origin":
            return None
        for o in obj.InList:
            if getattr(o, "Origin", None) is obj:
                return o
    except Exception:
        pass
    return None


def rotulo_da_origem(obj):
    """A origem leva o número do seu dono: Corpo001 → Origem001 (antes: Origem003, Origem005…, porque a
    numeração conta as origens do documento inteiro). None se não houver dono."""
    dono = _dono_da_origem(obj)
    if dono is None:
        return None
    m = _RE.match(dono.Name)
    return NOMES["Origin"] + ((m.group(2) or "") if m else "")


def renomear_origem(obj, original):
    """Dá à origem o número do seu dono, se o rótulo ainda é o que o FreeCAD pôs (o rótulo traduzido chega
    depois da criação, então vale qualquer "Origem…"/"Origin…" sem mudança do usuário)."""
    try:
        if obj is None or not re.match(r"^(Origem|Origin)\d*$", obj.Label or ""):
            return False
        novo = rotulo_da_origem(obj)
        if not novo or novo == obj.Label:
            return False
        # o ponto da origem também se chamava "Origem" e disputava o nome: a numeração pulava de 2 em 2
        num = novo[len(NOMES["Origin"]):]
        for f in getattr(obj, "OriginFeatures", []) or []:
            if f.TypeId == "App::Point" and f.Label.startswith(NOMES["Origin"]):
                f.Label = "Ponto de origem" + num
        obj.Label = novo
        return True
    except Exception:
        return False


def renomear(obj, original):
    """Troca o rótulo se ele ainda for o original em inglês."""
    try:
        if obj is None or obj.Label != original:
            return False
        novo = rotulo_da_origem(obj) or traduzir(original)
        if not novo:
            return False
        obj.Label = novo
        return True
    except Exception:
        return False


def renomear_projecao(obj):
    """Vista de grupo de projeção com o rótulo igual ao tipo em inglês ganha o nome em português."""
    try:
        if obj is None or obj.TypeId != "TechDraw::DrawProjGroupItem":
            return False
        novo = PROJECOES.get(obj.Type)
        if novo and obj.Label != novo and (obj.Label == obj.Type or obj.Label in PROJECOES_QM):
            obj.Label = novo
            return True
    except Exception:
        pass
    return False


def limpar_barra_do_documento(nome):
    """Tira da barra de status a mensagem que cita um documento que fechou ("Pré-seleção: Doc.Obj.Edge2"): o
    FreeCAD escreve num rótulo próprio da barra e a mensagem ficava lá depois de o documento sumir."""
    if not FreeCAD.GuiUp:
        return 0
    try:
        import FreeCADGui
        from PySide import QtWidgets
        sb = FreeCADGui.getMainWindow().statusBar()
    except Exception:
        return 0
    marca = "%s." % nome
    n = 0
    for lb in sb.findChildren(QtWidgets.QLabel):
        t = lb.text() or ""
        if marca in t.split(" ", 1)[-1] and (": " + marca in t or t.startswith(marca) or " " + marca in t):
            lb.setText("")
            n += 1
    if marca in (sb.currentMessage() or ""):
        sb.clearMessage()
        n += 1
    return n


class Observador:
    def slotDeletedDocument(self, doc):
        try:
            nome = doc.Name
        except Exception:
            return
        try:
            from PySide import QtCore
            QtCore.QTimer.singleShot(0, lambda n=nome: limpar_barra_do_documento(n))
        except Exception:
            pass

    def slotChangedObject(self, obj, prop):
        # o grupo de projeção cria a vista e só depois põe o tipo como rótulo
        if prop != "Label" or not _ligado():
            return
        try:
            if obj.TypeId != "TechDraw::DrawProjGroupItem" \
                    or (obj.Label not in PROJECOES and obj.Label not in PROJECOES_QM) \
                    or _documento_ocupado(obj.Document):
                return
        except Exception:
            return
        QtCore.QTimer.singleShot(0, lambda o=obj: renomear_projecao(o))

    def slotCreatedObject(self, obj):
        if not _ligado():
            return
        try:
            doc = obj.Document
            if _documento_ocupado(doc):
                return
            original = obj.Label
            origem = obj.TypeId == "App::Origin"
        except Exception:
            return
        if origem:
            # a origem já nasce em português, mas numerada pelo documento inteiro (Origem003 no Corpo001)
            QtCore.QTimer.singleShot(0, lambda o=obj, r=original: renomear_origem(o, r))
            return
        if traduzir(original) is None:
            return
        # adiado: alguns comandos ajustam o objeto logo depois de criá-lo
        QtCore.QTimer.singleShot(0, lambda o=obj, r=original: renomear(o, r))


_estado = {"obs": None}


def install():
    if _estado["obs"] is None:
        _estado["obs"] = Observador()
        FreeCAD.addDocumentObserver(_estado["obs"])
    return _estado["obs"]


def uninstall():
    if _estado["obs"] is not None:
        FreeCAD.removeDocumentObserver(_estado["obs"])
        _estado["obs"] = None
