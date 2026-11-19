# SPDX-License-Identifier: LGPL-2.1-or-later
# Copyright (c) 2025-2026 OficineRobotica
# Modificado para o Usinix: importações do pacote, mensagens e configuração (ver __init__.py).
"""Image textures on objects, shown in the 3D view.

An object gets three properties: ``TextureImage`` (the picture, stored inside
the document), ``TextureScale`` (size of one repetition) and
``TextureRotation``.  The picture is laid on the object with a *box
projection*: every triangle is textured from the axis it faces most, in real
millimetres.  No unwrapping is needed and nothing stretches, which suits
materials -- wood, brushed metal, concrete; on round shapes a seam shows where
the projection changes side.

How it is drawn
---------------
FreeCAD's own face node sends no texture coordinates, so a textured copy of
the faces is drawn on top of them: a node added to the object's view provider,
built from the very same triangles (identical vertices give identical depth,
so the copy covers the original exactly, without flicker, and the edges stay
on top).  Explicit texture coordinates also work with the shadow shader.

The textured copy cannot be picked: selection goes through to the real faces.
A PartDesign Body is textured through its Tip, following it as it changes.
"""
import os

import FreeCAD
from pivy import coin

from . import view_utils

NODE_NAME = 'DisplayToolsTexture'
PROPERTIES = ('TextureImage', 'TextureScale', 'TextureRotation', 'TextureSource')
SHADED_MODES = ('Flat Lines', 'Shaded')
MAX_TRIANGLES = 400000
DELAY_MS = 80

_pending = set()
_textured_docs = set()
_timer = None
_bridge = None
_app_observer = None
_selection_observer = None


# ------------------------------------------------------------------ public API
def image_of(obj):
    """Path of the texture image of ``obj``, or '' if it has none."""
    try:
        path = getattr(obj, 'TextureImage', '') or ''
        # an empty TextureSource marks a texture taken away in the Appearance panel
        # (a file property cannot be emptied)
        if 'TextureSource' in obj.PropertiesList and not obj.TextureSource:
            return ''
    except Exception:
        return ''
    return path if path and os.path.isfile(path) else ''


def apply(obj, image_path, scale=None, rotation=None):
    """Give ``obj`` a texture (or replace the one it has)."""
    pl = obj.PropertiesList
    if 'TextureImage' not in pl:
        obj.addProperty("App::PropertyFileIncluded", "TextureImage", "Textura",
                        "Imagem aplicada na peça na vista 3D (guardada no documento)")
    if 'TextureScale' not in pl:
        obj.addProperty("App::PropertyLength", "TextureScale", "Textura",
                        "Tamanho de uma repetição da imagem")
        obj.TextureScale = scale if scale else default_scale(obj)
    elif scale:
        obj.TextureScale = scale
    if 'TextureRotation' not in pl:
        obj.addProperty("App::PropertyAngle", "TextureRotation", "Textura",
                        "Giro da imagem nas faces")
    if rotation is not None:
        obj.TextureRotation = rotation
    if 'TextureSource' not in obj.PropertiesList:
        obj.addProperty("App::PropertyString", "TextureSource", "Textura",
                        "Nome da imagem de onde a textura veio")
        obj.setEditorMode('TextureSource', 2)       # bookkeeping: not shown
    obj.TextureImage = image_path
    # the copy kept in the document may be renamed: remember where the image came from
    obj.TextureSource = os.path.basename(image_path)
    schedule(obj.Document)


def remove(obj):
    for name in PROPERTIES:
        if name in obj.PropertiesList:
            obj.removeProperty(name)
    schedule(obj.Document)


def default_scale(obj):
    """Half the size of the object, rounded to a tidy number."""
    try:
        size = obj.Shape.BoundBox.DiagonalLength / 2.0
    except Exception:
        size = 0.0
    if size <= 0 or size > 1e6:
        return 50.0
    return float('%.1g' % size)


def texture_owner(obj):
    """The object the texture properties belong on: the Body for a PartDesign feature."""
    try:
        for parent in obj.InList:
            if parent.isDerivedFrom('PartDesign::Body') and obj in parent.Group:
                return parent
    except Exception:
        pass
    return obj


# -------------------------------------------------------------------- geometry
def _source(obj):
    """The object whose faces show ``obj``: a Body is drawn by its Tip."""
    for _ in range(8):
        tip = getattr(obj, 'Tip', None)
        if tip is None or not hasattr(tip, 'ViewObject'):
            break
        obj = tip
    return obj


def _find_type(root, type_name):
    node_type = coin.SoType.fromName(type_name)
    if node_type.isBad():
        return None
    search = coin.SoSearchAction()
    search.setType(node_type)
    search.setInterest(coin.SoSearchAction.FIRST)
    search.setSearchingAll(True)
    search.apply(root)
    path = search.getPath()
    return path.getTail() if path is not None else None


def _face_nodes(root):
    """(coordinates, normals, face set) the view provider draws its faces from."""
    faces = _find_type(root, 'SoBrepFaceSet')
    coords = view_utils.find_child_of_type(root, 'Coordinate3')
    if faces is None or coords is None:
        return None
    return coords, _find_type(root, 'SoNormal'), faces


def _triangles(coords, normals, faces):
    """Unshared triangle vertices with box-projected texture coordinates (in mm)."""
    points = [p.getValue() for p in coords.point.getValues(0)]
    index = faces.coordIndex.getValues(0)
    vectors = None
    if normals is not None and normals.vector.getNum() == len(points):
        vectors = [n.getValue() for n in normals.vector.getValues(0)]

    out_points, out_normals, out_uv = [], [], []
    count = 0
    i, n = 0, len(index)
    while i + 2 < n:
        a, b, c = index[i], index[i + 1], index[i + 2]
        if a < 0 or b < 0 or c < 0:
            i += 1
            continue
        i += 3
        while i < n and index[i] >= 0:      # polygon with more corners: skip the rest
            i += 1
        i += 1                              # the -1 that ends the face
        pa, pb, pc = points[a], points[b], points[c]
        ux, uy, uz = pb[0] - pa[0], pb[1] - pa[1], pb[2] - pa[2]
        vx, vy, vz = pc[0] - pa[0], pc[1] - pa[1], pc[2] - pa[2]
        nx, ny, nz = uy * vz - uz * vy, uz * vx - ux * vz, ux * vy - uy * vx
        ax, ay, az = abs(nx), abs(ny), abs(nz)
        if vectors is not None:
            # side taken from the surface normal: steadier than the triangle's on curved faces
            sx, sy, sz = vectors[a]
            if (sx * nx + sy * ny + sz * nz) < 0:
                nx, ny, nz = -nx, -ny, -nz
        for corner in (a, b, c):
            x, y, z = points[corner]
            if ax >= ay and ax >= az:
                uv = (y if nx >= 0 else -y, z)
            elif ay >= az:
                uv = (-x if ny >= 0 else x, z)
            else:
                uv = (x if nz >= 0 else -x, y)
            out_points.append((x, y, z))
            out_uv.append(uv)
            if vectors is not None:
                out_normals.append(vectors[corner])
        if vectors is None:
            length = (nx * nx + ny * ny + nz * nz) ** 0.5 or 1.0
            out_normals += [(nx / length, ny / length, nz / length)] * 3
        count += 1
        if count >= MAX_TRIANGLES:
            FreeCAD.Console.PrintWarning(
                "Usinix: peça detalhada demais, a textura cobre só %d triângulos.\n"
                % MAX_TRIANGLES)
            break
    return out_points, out_normals, out_uv, count


# ----------------------------------------------------------------------- nodes
def _named(node, suffix):
    node.setName(NODE_NAME + suffix)
    return node


def _build():
    root = _named(coin.SoSeparator(), '')
    root.addChild(_named(coin.SoInfo(), 'Info'))
    switch = _named(coin.SoSwitch(), 'Switch')
    root.addChild(switch)
    body = coin.SoSeparator()
    switch.addChild(body)

    pick = coin.SoPickStyle()
    pick.style = coin.SoPickStyle.UNPICKABLE        # selection goes to the real faces
    body.addChild(pick)
    body.addChild(_named(coin.SoPolygonOffset(), 'Offset'))
    hints = coin.SoShapeHints()
    hints.vertexOrdering = coin.SoShapeHints.COUNTERCLOCKWISE
    hints.shapeType = coin.SoShapeHints.UNKNOWN_SHAPE_TYPE      # lit on both sides
    body.addChild(hints)
    style = coin.SoDrawStyle()
    style.style = coin.SoDrawStyle.FILLED
    body.addChild(style)
    material = coin.SoMaterial()
    material.diffuseColor = (1, 1, 1)               # the image gives the color
    material.ambientColor = (0.25, 0.25, 0.25)
    material.specularColor = (0.08, 0.08, 0.08)
    body.addChild(material)
    binding = coin.SoMaterialBinding()
    binding.value = coin.SoMaterialBinding.OVERALL
    body.addChild(binding)
    body.addChild(_named(coin.SoCoordinate3(), 'Points'))
    body.addChild(_named(coin.SoNormal(), 'Normals'))
    normal_binding = coin.SoNormalBinding()
    normal_binding.value = coin.SoNormalBinding.PER_VERTEX
    body.addChild(normal_binding)

    textured = coin.SoSeparator()
    body.addChild(textured)
    textured.addChild(_named(coin.SoTexture2Transform(), 'Transform'))
    texture = _named(coin.SoTexture2(), 'Image')
    texture.model = coin.SoTexture2.MODULATE
    textured.addChild(texture)
    textured.addChild(_named(coin.SoTextureCoordinate2(), 'UV'))
    uv_binding = coin.SoTextureCoordinateBinding()
    uv_binding.value = coin.SoTextureCoordinateBinding.PER_VERTEX
    textured.addChild(uv_binding)
    textured.addChild(_named(coin.SoFaceSet(), 'Faces'))

    # Selected and preselected faces, drawn over the image in FreeCAD's
    # highlight colors.  They reuse the points above (same depth again), each
    # face being a run of triangles picked with SoFaceSet.startIndex.
    for suffix in ('Selected', 'Preselected'):      # the hovered face is drawn last
        highlight = coin.SoSeparator()
        highlight.addChild(_named(coin.SoMaterial(), suffix + 'Color'))
        highlight.addChild(_named(coin.SoGroup(), suffix))
        body.addChild(highlight)
    return root


def _part(root, suffix):
    search = coin.SoSearchAction()
    search.setName(coin.SbName(NODE_NAME + suffix))
    search.setInterest(coin.SoSearchAction.FIRST)
    search.setSearchingAll(True)
    search.apply(root)
    path = search.getPath()
    return path.getTail() if path is not None else None


def _set_geometry(root, nodes):
    points, normals, uv, count = _triangles(*nodes)
    faces = _part(root, 'Faces')
    faces.numVertices.setNum(0)
    for suffix, field, values in (('Points', 'point', points), ('Normals', 'vector', normals),
                                  ('UV', 'point', uv)):
        target = getattr(_part(root, suffix), field)
        target.setNum(0)
        if values:
            target.setValues(0, len(values), values)
    if count:
        faces.numVertices.setValues(0, count, [3] * count)


def _signature(nodes):
    coords, normals, faces = nodes
    return '%d|%d|%d' % (coords.getNodeId(), faces.getNodeId(),
                         normals.getNodeId() if normals is not None else 0)


def _update(source, owner):
    """Make the textured copy on ``source``'s view provider show ``owner``'s texture."""
    vobj = source.ViewObject
    vp_root = vobj.RootNode
    nodes = _face_nodes(vp_root)
    root = view_utils.find_child(vp_root, NODE_NAME)
    if nodes is None:
        if root is not None:
            vp_root.removeChild(root)
        return
    if root is None:
        root = _build()
        vp_root.addChild(root)

    info = view_utils.find_child(root, NODE_NAME + 'Info')
    signature = _signature(nodes)
    if info.string.getValue().getString() != signature:
        _set_geometry(root, nodes)
        info.string = signature

    image = _part(root, 'Image')
    path = image_of(owner)
    # FreeCAD keeps a new image under the name of the old copy: compare the file too
    stamp = _stamp(path)
    key = (source.Document.Name, source.Name)
    if image.filename.getValue().getString() != path or _loaded.get(key) != stamp:
        image.filename = ''
        image.filename = path
        _loaded[key] = stamp

    scale = getattr(owner, 'TextureScale', 50.0)
    scale = max(float(getattr(scale, 'Value', scale)), 1e-6)
    angle = getattr(owner, 'TextureRotation', 0.0)
    angle = float(getattr(angle, 'Value', angle)) * 0.017453292519943295
    transform = _part(root, 'Transform')
    if abs(transform.scaleFactor.getValue()[0] - 1.0 / scale) > 1e-12:
        transform.scaleFactor = (1.0 / scale, 1.0 / scale)
    if abs(transform.rotation.getValue() - angle) > 1e-9:
        transform.rotation = angle

    _watch_mode(source, vobj)
    mode = str(getattr(vobj, 'DisplayMode', 'Flat Lines'))
    # "Flat Lines" pushes its faces back to let the edges through: do the same,
    # so that the copy has exactly the depth of the faces it covers
    offset = _part(root, 'Offset')
    if bool(offset.on.getValue()) != (mode == 'Flat Lines'):
        offset.on = (mode == 'Flat Lines')
    show = bool(vobj.Visibility) and mode in SHADED_MODES and bool(path)
    switch = view_utils.find_child(root, NODE_NAME + 'Switch')
    wanted = coin.SO_SWITCH_ALL if show else coin.SO_SWITCH_NONE
    if switch.whichChild.getValue() != wanted:
        switch.whichChild = wanted


_loaded = {}            # (document, object) -> stamp of the image file shown


def _stamp(path):
    try:
        st = os.stat(path)
        return (path, st.st_size, st.st_mtime_ns)
    except OSError:
        return (path, 0, 0)


def clear(obj):
    """Leave the texture properties but show no image (undone with the transaction)."""
    if 'TextureSource' in obj.PropertiesList:
        obj.TextureSource = ''
        schedule(obj.Document)
    elif 'TextureImage' in obj.PropertiesList:
        remove(obj)


# ------------------------------------------------------------------ highlight
_face_ranges = {}       # (document, object) -> (signature, first triangle of each face + total)
_preselected = None     # (document, object) showing the preselection highlight


def _color(parameter, default):
    packed = FreeCAD.ParamGet("User parameter:BaseApp/Preferences/View").GetUnsigned(parameter,
                                                                                    default)
    return ((packed >> 24) & 255) / 255.0, ((packed >> 16) & 255) / 255.0, \
        ((packed >> 8) & 255) / 255.0


def _ranges(obj, root):
    """Where the triangles of each face start in the textured copy."""
    key = (obj.Document.Name, obj.Name)
    signature = view_utils.find_child(root, NODE_NAME + 'Info').string.getValue().getString()
    cached = _face_ranges.get(key)
    if cached is not None and cached[0] == signature:
        return cached[1]
    starts = [0]
    faces = _find_type(obj.ViewObject.RootNode, 'SoBrepFaceSet')
    field = faces.getField('partIndex') if faces is not None else None
    if field is not None:
        for count in coin.cast(field, 'SoMFInt32').getValues(0):
            starts.append(starts[-1] + count)
    _face_ranges[key] = (signature, starts)
    return starts


def _show_faces(obj, suffix, subnames, color):
    """Highlight the faces ``subnames`` ('Face3', ...; '' = all) of ``obj``; None clears."""
    try:
        root = view_utils.find_child(obj.ViewObject.RootNode, NODE_NAME)
    except Exception:
        return
    if root is None:
        return
    group = _part(root, suffix)
    if group is None:
        return
    runs = []
    if subnames:
        starts = _ranges(obj, root)
        total = _part(root, 'Faces').numVertices.getNum()
        for sub in subnames:
            if sub == '':
                runs = [(0, total)]
                break
            if not sub.startswith('Face'):
                continue
            try:
                face = int(sub[4:])
            except ValueError:
                continue
            if 1 <= face < len(starts):
                first = min(starts[face - 1], total)
                count = min(starts[face], total) - first
                if count > 0:
                    runs.append((first, count))
    current = [(group.getChild(i).startIndex.getValue() // 3, group.getChild(i).numVertices.getNum())
               for i in range(group.getNumChildren())]
    if current == runs:
        return
    group.removeAllChildren()
    if runs:
        material = _part(root, suffix + 'Color')
        material.diffuseColor = color
        material.emissiveColor = tuple(0.35 * c for c in color)
    for first, count in runs:
        faces = coin.SoFaceSet()
        faces.startIndex = 3 * first
        faces.numVertices.setValues(0, count, [3] * count)
        group.addChild(faces)


def _textured(doc_name, obj_name):
    doc = FreeCAD.listDocuments().get(doc_name)
    obj = doc.getObject(obj_name) if doc is not None else None
    if obj is None or not hasattr(obj, 'ViewObject'):
        return None
    return obj


def refresh_selection(doc):
    """Show the selected faces of the textured objects of ``doc``."""
    import FreeCADGui
    try:
        selected = {}
        for item in FreeCADGui.Selection.getSelectionEx(doc.Name):
            names = list(item.SubElementNames) or ['']
            selected.setdefault(item.ObjectName, []).extend(names)
        color = _color('SelectionColor', 0x00abffff)
        for obj in doc.Objects:
            _show_faces(obj, 'Selected', selected.get(obj.Name), color)
    except Exception as error:
        FreeCAD.Console.PrintLog("Usinix: textura: realce da seleção pulado: %s\n" % error)


class _SelectionObserver:
    """Mirrors FreeCAD's face highlighting on the textured copies."""

    def setPreselection(self, doc, obj, sub):
        global _preselected
        self.removePreselection(doc, obj, sub)
        if doc not in _textured_docs:
            return
        target = _textured(doc, obj)
        if target is not None:
            _show_faces(target, 'Preselected', [sub], _color('HighlightColor', 0x0ac8ffff))
            _preselected = (doc, obj)

    def removePreselection(self, doc, obj, sub):
        global _preselected
        if _preselected is not None:
            target = _textured(*_preselected)
            _preselected = None
            if target is not None:
                _show_faces(target, 'Preselected', None, None)

    def _changed(self, doc_name):
        if doc_name in _textured_docs:
            doc = FreeCAD.listDocuments().get(doc_name)
            if doc is not None:
                refresh_selection(doc)

    def addSelection(self, doc, obj, sub, pos):
        self._changed(doc)

    def removeSelection(self, doc, obj, sub):
        self._changed(doc)

    def setSelection(self, doc):
        self._changed(doc)

    def clearSelection(self, doc):
        for name in ([doc] if doc else list(_textured_docs)):
            self._changed(name)


def sync_document(doc):
    """Bring the textured copies of ``doc`` in line with the texture properties."""
    if not FreeCAD.GuiUp or doc is None:
        return
    try:
        objects = doc.Objects
    except ReferenceError:
        return
    wanted = {}
    for obj in objects:
        if 'TextureImage' in obj.PropertiesList and image_of(obj):
            source = _source(obj)
            wanted.setdefault(source.Name, (source, obj))
    if wanted:
        _textured_docs.add(doc.Name)
    else:
        _textured_docs.discard(doc.Name)
    for obj in objects:
        try:
            vp_root = obj.ViewObject.RootNode
        except Exception:
            continue
        if obj.Name in wanted:
            try:
                _update(*wanted[obj.Name])
            except Exception as error:
                FreeCAD.Console.PrintError("Usinix: a textura em %s falhou: %s\n"
                                           % (obj.Label, error))
        else:
            stale = view_utils.find_child(vp_root, NODE_NAME)
            if stale is not None:
                vp_root.removeChild(stale)
                _forget_mode(obj)
    if wanted:
        refresh_selection(doc)


# ----------------------------------------------------------------------- hooks
def _run_pending():
    names = list(_pending)
    _pending.clear()
    documents = FreeCAD.listDocuments()
    for name in names:
        doc = documents.get(name)
        if doc is not None:
            sync_document(doc)


def schedule(doc):
    global _timer, _bridge
    if not FreeCAD.GuiUp or doc is None:
        return
    try:
        _pending.add(doc.Name)
    except ReferenceError:
        return
    if _bridge is None:
        import FreeCADGui
        from PySide import QtCore

        class Bridge(QtCore.QObject):
            wake = QtCore.Signal()

        _bridge = Bridge(FreeCADGui.getMainWindow())
        _timer = QtCore.QTimer(_bridge)
        _timer.setSingleShot(True)
        _timer.setInterval(DELAY_MS)
        _timer.timeout.connect(_run_pending)
        _bridge.wake.connect(_timer.start)      # also when told from a recompute thread
    _bridge.wake.emit()


class _AppObserver:
    def slotChangedObject(self, obj, prop):
        if prop in PROPERTIES:
            schedule(obj.Document)
        elif prop in ('Shape', 'Tip', 'Visibility'):
            try:
                doc = obj.Document
                if doc.Name in _textured_docs:
                    schedule(doc)
            except Exception:
                pass

    def slotCreatedObject(self, obj):
        try:
            if obj.Document.Name in _textured_docs:
                schedule(obj.Document)
        except Exception:
            pass

    def slotUndoDocument(self, doc):
        schedule(doc)

    def slotRedoDocument(self, doc):
        schedule(doc)

    def slotFinishRestoreDocument(self, doc):
        schedule(doc)

    def slotDeletedDocument(self, doc):
        try:
            _textured_docs.discard(doc.Name)
            for key in [k for k in _mode_sensors if k[0] == doc.Name]:
                entry = _mode_sensors.pop(key)
                entry[1].detach()
        except Exception:
            pass


# No GUI document observer here: FreeCAD calls its slotChangedObject while a
# view provider is still being built, and handing that view provider to Python
# then gives it the generic wrapper for good (Part objects lose DiffuseColor,
# which breaks other add-ons such as SheetMetal). The display mode of a
# textured object is followed with a sensor on its mode switch instead, and
# visibility through the App observer.
_mode_sensors = {}          # (document, object) -> SoFieldSensor on the mode switch


def _watch_mode(source, vobj):
    key = (source.Document.Name, source.Name)
    try:
        switch = vobj.SwitchNode
    except Exception:
        return
    current = _mode_sensors.get(key)
    if current is not None and current[0] is switch:
        return
    doc_name = source.Document.Name

    def changed(*_):
        schedule(FreeCAD.listDocuments().get(doc_name))
    sensor = coin.SoFieldSensor(changed, None)
    sensor.attach(switch.whichChild)
    _mode_sensors[key] = (switch, sensor, changed)


def _forget_mode(source):
    try:
        key = (source.Document.Name, source.Name)
    except Exception:
        return
    entry = _mode_sensors.pop(key, None)
    if entry is not None:
        try:
            entry[1].detach()
        except Exception:
            pass


def install():
    """Start watching the documents. Called when FreeCAD starts, so that the
    textures of a document show up without opening this workbench first."""
    global _app_observer, _selection_observer
    if _app_observer is not None or not FreeCAD.GuiUp:
        return
    import FreeCADGui
    _app_observer = _AppObserver()
    FreeCAD.addDocumentObserver(_app_observer)
    try:
        _selection_observer = _SelectionObserver()
        FreeCADGui.Selection.addObserver(_selection_observer)
    except Exception:
        _selection_observer = None
    for doc in FreeCAD.listDocuments().values():
        schedule(doc)
