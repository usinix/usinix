# SPDX-License-Identifier: LGPL-2.1-or-later
# Usinix - nova peça (corpo) desenhada numa face de barra, chapa ou outro corpo, ligada a ela.
"""Peça na face.

Para o que se faz em volta da estrutura — batente, suporte de escada, chapa de ligação, orelha, calço — o
desenho começa numa face que já existe: a alma de uma viga, a aba de uma cantoneira, o tampo de uma base. Este
comando cria um corpo novo (Peça) com uma referência ligada a essa face (cópia associativa, SubShapeBinder) e
um esboço apoiado nela, já aberto para desenhar. Se a barra ou o corpo de origem mudam, a referência, o esboço
e a peça acompanham. A peça entra na lista de materiais como peça; a verificação de interferência e a folha de
montagem a tratam junto com a estrutura.
"""

import FreeCAD

try:
    import FreeCADGui
    from PySide import QtWidgets
except ImportError:
    FreeCADGui = None


def _plana(face):
    try:
        return face.Surface.isPlanar() if hasattr(face.Surface, "isPlanar") else face.Surface.TypeId == \
            "Part::GeomPlane"
    except Exception:
        return False


def _tres_vertices(sh):
    """Três vértices não alinhados da face (nomes VertexN), afastados entre si."""
    vs = sh.Vertexes
    if len(vs) < 3:
        return None
    p = [v.Point for v in vs]
    i0 = 0
    i1 = max(range(len(p)), key=lambda k: (p[k] - p[i0]).Length)
    def area(k):
        return (p[i1] - p[i0]).cross(p[k] - p[i0]).Length
    i2 = max(range(len(p)), key=area)
    if area(i2) < 1e-6 or (p[i1] - p[i0]).Length < 1e-6:
        return None
    return ["Vertex%d" % (i + 1) for i in (i0, i1, i2)]


def criar(origem, face_nome, nome=None, abrir=True):
    """Corpo novo com a face `face_nome` de `origem` como referência ligada e um esboço sobre ela."""
    doc = origem.Document
    face = origem.Shape.getElement(face_nome)
    if not _plana(face):
        raise ValueError("A face escolhida não é plana; escolha uma face plana para começar o esboço.")
    body = doc.addObject("PartDesign::Body", "Peca")
    body.Label = nome or "Peça em %s" % origem.Label
    ref = body.newObject("PartDesign::SubShapeBinder", "Referencia")
    ref.Support = [(origem, (face_nome,))]
    ref.Label = "Referência (%s · %s)" % (origem.Label, face_nome)
    try:
        ref.BindMode = "Synchronized"
    except Exception:
        pass
    doc.recompute()
    sk = body.newObject("Sketcher::SketchObject", "Esboco")
    # preso a três vértices da face (não só ao plano dela): se a barra cresce ou anda no próprio plano da face,
    # o esboço vai junto; sem três vértices bons, fica no plano da face
    tres = _tres_vertices(ref.Shape)
    if tres:
        sk.AttachmentSupport = [(ref, tres[0]), (ref, tres[1]), (ref, tres[2])]
        sk.MapMode = "ThreePointsPlane"
    else:
        sk.AttachmentSupport = [(ref, "Face1")]
        sk.MapMode = "FlatFace"
    sk.Label = "Esboço da peça"
    doc.recompute()
    # origem do esboço no meio da face (o plano da face pode ter a origem longe da peça)
    try:
        centro = ref.Shape.Faces[0].CenterOfMass
        local = sk.Placement.inverse().multVec(centro)
        sk.AttachmentOffset = FreeCAD.Placement(FreeCAD.Vector(local.x, local.y, 0), FreeCAD.Rotation())
        doc.recompute()
    except Exception as exc:
        FreeCAD.Console.PrintLog("Usinix: peça na face: origem: %s\n" % exc)
    if FreeCAD.GuiUp:
        try:
            ref.ViewObject.Visibility = False
        except Exception:
            pass
        if abrir:
            try:
                FreeCADGui.ActiveDocument.ActiveView.setActiveObject("pdbody", body)
                FreeCADGui.ActiveDocument.setEdit(sk.Name)
            except Exception as exc:
                FreeCAD.Console.PrintWarning("Usinix: não abriu o esboço: %s\n" % exc)
    return body, sk


def _selecao_face():
    if FreeCADGui is None:
        return None
    for s in FreeCADGui.Selection.getSelectionEx("", 0):
        for sub in s.SubElementNames:
            nome = sub.split(".")[-1]
            if nome.startswith("Face"):
                obj = s.Object
                # seleção dentro de contêiner (Body/Part): o objeto que tem a face
                if "." in sub:
                    try:
                        alvo = obj.getSubObject(sub, retType=1)
                        if alvo is not None:
                            obj = alvo
                    except Exception:
                        pass
                return obj, nome
    return None


if FreeCADGui is not None:
    class CmdPecaNaFace:
        def GetResources(self):
            import PrumoUtil
            return {"Pixmap": PrumoUtil.icone("peca_na_face.svg"), "MenuText": "Peça na face",
                    "ToolTip": "Nova peça desenhada numa face de barra, chapa ou corpo (batente, suporte, chapa de "
                               "ligação…): cria o corpo com a face ligada e abre o esboço sobre ela."}

        def IsActive(self):
            return FreeCAD.ActiveDocument is not None

        def Activated(self):
            sel = _selecao_face()
            if sel is None:
                QtWidgets.QMessageBox.information(
                    FreeCADGui.getMainWindow(), "Peça na face",
                    "Clique numa face plana de uma barra, chapa ou corpo (a alma da viga, a aba da cantoneira, o "
                    "tampo da base) e use Peça na face de novo.")
                return None
            obj, face = sel
            doc = obj.Document
            doc.openTransaction("Peça na face")
            try:
                body, _sk = criar(obj, face)
            except ValueError as ex:
                doc.abortTransaction()
                QtWidgets.QMessageBox.information(FreeCADGui.getMainWindow(), "Peça na face", str(ex))
                return None
            doc.commitTransaction()
            return body


def registrar_comandos():
    if FreeCADGui is not None and "Prumo_PecaNaFace" not in FreeCADGui.listCommands():
        FreeCADGui.addCommand("Prumo_PecaNaFace", CmdPecaNaFace())
