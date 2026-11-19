# SPDX-License-Identifier: LGPL-2.1-or-later
# Copyright (c) 2025-2026 OficineRobotica
"""Helpers to reach the 3D views and the Coin scene graph of a document.

Nothing in here relies on ``FreeCADGui.ActiveDocument`` / ``ActiveView``:
view providers are attached while documents are being loaded, when the active
document may be another one (or none at all) and the active view may not be a
3D view (TechDraw page, spreadsheet, ...).
"""
import FreeCAD
from pivy import coin

VIEW_TYPE = 'Gui::View3DInventor'
SELECTION_ROOT_TYPE = 'SoFCUnifiedSelection'


def gui_up():
    return bool(FreeCAD.GuiUp)


def gui_document(doc):
    """Gui document of an App document (or None)."""
    if not gui_up() or doc is None:
        return None
    import FreeCADGui
    try:
        return FreeCADGui.getDocument(doc.Name)
    except Exception:
        return None


def views_of(doc):
    """All the 3D views showing ``doc``."""
    gdoc = gui_document(doc)
    if gdoc is None:
        return []
    try:
        return list(gdoc.mdiViewsOfType(VIEW_TYPE))
    except Exception:
        return []


def first_view(doc):
    views = views_of(doc)
    return views[0] if views else None


def new_node(type_name, keep=False):
    """Create a Coin node from its type name, or None if the type is unknown.

    Used for the nodes pivy has no Python class for (the shadow nodes) and for
    FreeCAD's own node types.

    Mind the ownership: unlike ``coin.SoSomething()``, the Python object
    returned here does *not* hold a reference to the node.  The node lives as
    long as it is the child of some group.  Pass ``keep=True`` for a node that
    has to survive being taken out of the scene graph (it is then never freed).
    """
    node_type = coin.SoType.fromName(type_name)
    if node_type.isBad() or not node_type.canCreateInstance():
        return None
    node = node_type.createInstance()
    if node is not None and keep:
        node.ref()
    return node


def set_field(node, name, value):
    """Set a field by name using Coin's text syntax; works for unwrapped node types."""
    field = node.getField(name)
    if field is None:
        return False
    return bool(field.set(str(value)))


def type_name(node):
    return node.getTypeId().getName().getString()


def find_child(group, name):
    """Direct child of ``group`` with the given node name."""
    for i in range(group.getNumChildren()):
        child = group.getChild(i)
        if child.getName().getString() == name:
            return child
    return None


def find_child_of_type(group, wanted):
    for i in range(group.getNumChildren()):
        child = group.getChild(i)
        if type_name(child) == wanted:
            return child
    return None


def skip_bounding_group():
    """Group whose content is ignored by "fit all" and by bounding box queries."""
    node = new_node('SoSkipBoundingGroup')
    if node is None:
        return coin.SoGroup()
    set_field(node, 'mode', 'EXCLUDE_BBOX')
    return node


class SceneParts:
    """The parts of a view's scene graph the workbench hooks into.

    FreeCAD 26.3:    getSceneGraph() -> Separator [ Group(view lights), SoFCUnifiedSelection ]
    FreeCAD 1.0/1.1: getSceneGraph() -> SoFCUnifiedSelection

    Never rely on child positions: look the nodes up.
    """

    def __init__(self, view):
        self.view = view
        self.scene = view.getSceneGraph()
        self.selection = None      # SoFCUnifiedSelection: holds every view provider
        self.parent = None         # direct parent of the selection root (possibly our shadow group)

        if type_name(self.scene) == SELECTION_ROOT_TYPE:
            self.selection = self.scene
            self.parent = self._parent_of(self.selection)
            return

        search = coin.SoSearchAction()
        search.setType(coin.SoType.fromName(SELECTION_ROOT_TYPE))
        search.setInterest(coin.SoSearchAction.FIRST)
        search.apply(self.scene)
        path = search.getPath()
        if path is None:
            return
        self.selection = path.getTail()
        self.parent = path.getNodeFromTail(1)

    @property
    def light_host(self):
        """Group our lights are added to, as its first child.

        It is the selection root itself, in front of every view provider: a
        light only affects what comes after it, and this is also the node
        FreeCAD renders for saved images and thumbnails.
        """
        return self.selection

    def _parent_of(self, node):
        try:
            root = self.view.getViewer().getSoRenderManager().getSceneGraph()
        except Exception:
            return None
        search = coin.SoSearchAction()
        search.setNode(node)
        search.setInterest(coin.SoSearchAction.FIRST)
        search.apply(root)
        path = search.getPath()
        if path is None or path.getLength() < 2:
            return None
        return path.getNodeFromTail(1)

    def valid(self):
        return self.selection is not None


def node_address(node):
    """C++ address of a Coin node, usable to tell whether two wrappers are the same node."""
    if node is None:
        return 0
    try:
        return int(node.this)
    except Exception:
        return id(node)


def same_node(a, b):
    return node_address(a) == node_address(b)


def set_children(group, nodes):
    """Make ``nodes`` the children of ``group``; leaves the graph untouched if already so."""
    current = [group.getChild(i) for i in range(group.getNumChildren())]
    if len(current) == len(nodes) and all(same_node(a, b) for a, b in zip(current, nodes)):
        return False
    for node in nodes:      # keep alive the ones only this group was holding
        node.ref()
    group.removeAllChildren()
    for node in nodes:
        group.addChild(node)
        node.unref()
    return True


def viewport_size(view):
    """Viewport size in device pixels."""
    try:
        size = view.getViewer().getSoRenderManager().getViewportRegion().getViewportSizePixels()
        return int(size[0]), int(size[1])
    except Exception:
        w, h = view.getSize()
        return int(w), int(h)


# Children of FreeCAD's selection root that are not model geometry.  Besides
# not being "the scene", the first one holds nodes that make Coin draw paths
# *after* the frame (selection drawn on top): such nodes must never be traversed
# by an off-screen pass, see SceneFX/ambient_occlusion.py.
NON_GEOMETRY_NAMES = ('GroupOnTop', 'EditingRoot', 'RootDimensions',
                      'DisplayToolsLights')
OBJECT_GROUP_NAME = 'ObjectGroup'
NON_GEOMETRY_TYPES = ('EventCallback', 'TransformSeparator', 'Environment',
                      'DirectionalLight', 'PointLight', 'SpotLight', 'ShadowDirectionalLight',
                      'ShadowSpotLight')


def helper_roots(doc):
    """Addresses of the root nodes of this workbench's helpers (lights, grids) in ``doc``."""
    roots = {}
    if doc is None:
        return roots
    try:
        objects = doc.Objects
    except ReferenceError:
        return roots
    for obj in objects:
        proxy = getattr(obj, 'Proxy', None)
        kind = None
        if getattr(proxy, 'isDisplayToolsLight', False):
            kind = 'light'
        elif getattr(proxy, 'type', None) == 'DynamicGrid':
            kind = 'grid'
        if kind is None:
            continue
        try:
            roots[node_address(obj.ViewObject.RootNode)] = kind
        except Exception:
            pass
    return roots


def geometry_nodes(view, doc=None, skip=('light', 'grid')):
    """The view provider roots under the selection root: what the model is made of.

    ``skip`` lists the kinds of helpers of this workbench to leave out.
    """
    parts = SceneParts(view)
    if parts.selection is None:
        return []
    helpers = helper_roots(doc)
    nodes = []

    def collect(group):
        for i in range(group.getNumChildren()):
            child = group.getChild(i)
            name = child.getName().getString()
            if name == OBJECT_GROUP_NAME:
                collect(child)          # FreeCAD 26.3+: view providers live in here
                continue
            if name in NON_GEOMETRY_NAMES or type_name(child) in NON_GEOMETRY_TYPES:
                continue
            if helpers.get(node_address(child)) in skip:
                continue
            nodes.append(child)

    collect(parts.selection)
    return nodes


def scene_bound_box(view, doc=None):
    """Bounding box (xmin, ymin, zmin, xmax, ymax, zmax) of the model shown by the view.

    Measured on the Coin scene graph, so it is exactly what is on screen:
    hidden objects do not count, objects inside Parts / Bodies / Links are
    taken where they really are, and meshes, points, etc. are included.
    The lights and grids of this workbench (in ``doc``) are left out.
    Returns None for an empty scene.
    """
    w, h = viewport_size(view)
    region = coin.SbViewportRegion(max(w, 1), max(h, 1))
    total = coin.SbBox3f()
    for node in geometry_nodes(view, doc):
        action = coin.SoGetBoundingBoxAction(region)
        action.apply(node)
        box = action.getBoundingBox()
        if not box.isEmpty():
            total.extendBy(box)
    if total.isEmpty():
        return None
    lo = total.getMin()
    hi = total.getMax()
    values = (lo[0], lo[1], lo[2], hi[0], hi[1], hi[2])
    if any(abs(v) > 1e30 for v in values):
        return None
    return values
