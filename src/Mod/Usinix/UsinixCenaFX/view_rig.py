# SPDX-License-Identifier: LGPL-2.1-or-later
# Copyright (c) 2025-2026 OficineRobotica
# Modificado para o Usinix: importações do pacote, mensagens e configuração (ver __init__.py).
"""Keeps the 3D views of a document in line with its lights and effect settings.

``sync_document`` is idempotent: it looks at what the document contains now
(lights, scene configuration) and at what each of its 3D views contains now,
and fixes the difference.  It is simply run again, a moment later, whenever
something that matters may have changed -- object created or deleted, undo,
redo, document loaded, new view opened, effect setting edited -- so there is
no bookkeeping to get out of step.

What it maintains in every view (FreeCAD 26.3 layout):

    scene root
     +- view lights group
     +- [our lights without shadows] <- here while shadows are on ...
     +- [ShadowGroup]                <- only while shadows are on
     |    +- shadow casting lights
     |    +- SoFCUnifiedSelection    (FreeCAD's root of all view providers)
     |         +- [our lights without shadows]  <- ... here otherwise
     |         +- view providers ...
     +- [ambient occlusion pass]     <- only while ambient occlusion is on
"""
import FreeCAD
from pivy import coin

from . import view_utils
from . import shadows, ambient_occlusion, navigation, shadow_catcher

LIGHTS_NAME = 'DisplayToolsLights'
MAX_GL_LIGHTS = 8          # fixed-function OpenGL limit, FreeCAD's own lights included
SYNC_DELAY_MS = 30
WATCH_INTERVAL_MS = 400

# Per document: groups listing the view providers' roots (shared by all the
# views of a document), from which the off-screen passes draw the scene.
_mirrors = {}

_pending = set()
_timer = None
_watch_timer = None
_observer = None
_bridge = None
_warned = set()


class Settings:
    """Effect settings of a document, read from its scene configuration."""

    def __init__(self, doc):
        from . import config as create_scene_config
        cfg = create_scene_config.getSceneFolder(doc)
        self.shadows = bool(getattr(cfg, 'Shadows', False))
        self.shadow_darkness = float(getattr(cfg, 'ShadowDarkness', 0.5))
        self.shadow_softness = float(getattr(cfg, 'ShadowSoftness', 0.3))
        self.shadow_quality = str(getattr(cfg, 'ShadowQuality', 'High'))
        self.ao = bool(getattr(cfg, 'AmbientOcclusion', False))
        self.ao_intensity = float(getattr(cfg, 'AOIntensity', 1.0))
        radius = getattr(cfg, 'AORadius', 0.0)
        self.ao_radius = float(getattr(radius, 'Value', radius))
        self.ao_quality = str(getattr(cfg, 'AOQuality', 'High'))
        self.catcher = bool(getattr(cfg, 'ShadowCatcher', False))
        self.navigation_mode = str(getattr(cfg, 'WhileNavigating', navigation.DEFAULT_MODE))
        self.navigation_delay = int(getattr(cfg, 'NavigationResumeDelay',
                                            navigation.DEFAULT_DELAY_MS))


def _warn_once(key, message):
    if key not in _warned:
        _warned.add(key)
        FreeCAD.Console.PrintWarning("Usinix (efeitos da vista): " + message + "\n")


def document_lights(doc):
    """[(object, coin light node)] for the lights of ``doc`` that are on screen."""
    lights = []
    for obj in doc.Objects:
        if not getattr(getattr(obj, 'Proxy', None), 'isDisplayToolsLight', False):
            continue
        vobj = getattr(obj, 'ViewObject', None)
        node = getattr(getattr(vobj, 'Proxy', None), 'coinLight', None)
        if node is not None:
            lights.append((obj, node))
    return lights


# -------------------------------------------------------------------- mirrors
class _Mirrors:
    def __init__(self):
        self.ao = coin.SoGroup()            # model + grid (contact shading on the floor)
        self.ao.ref()
        self.casters = coin.SoGroup()       # model only: no gizmos or grid lines in the shadows
        self.casters.ref()
        self.caster_scene = shadows.caster_scene(self.casters)
        self.caster_scene.ref()


def mirrors_of(doc, view):
    """The mirror groups of ``doc``, brought up to date from ``view``."""
    mirrors = _mirrors.get(doc.Name)
    if mirrors is None:
        mirrors = _mirrors[doc.Name] = _Mirrors()
    view_utils.set_children(mirrors.ao, view_utils.geometry_nodes(view, doc, skip=('light',)))
    view_utils.set_children(mirrors.casters, view_utils.geometry_nodes(view, doc))
    return mirrors


def _forget_closed_documents():
    open_names = set(FreeCAD.listDocuments().keys())
    for name in list(_mirrors):
        if name not in open_names:
            mirrors = _mirrors.pop(name)
            for group in (mirrors.ao, mirrors.casters):
                group.removeAllChildren()
            mirrors.caster_scene.removeAllChildren()


# --------------------------------------------------------------------- lights
def _sync_plain_lights(parts, nodes):
    """Place the lights that cast no shadows.

    Without shadows they go inside the selection root, in front of the view
    providers (the node FreeCAD renders for saved images too).  With shadows
    they must stay *outside* the shadow group, right before it: Coin makes a
    shadow caster of every light it finds anywhere inside the group.
    """
    wrapper = _shadow_wrapper(parts)
    outer = _outer_parent(parts, wrapper) if wrapper is not None else None
    host = outer if outer is not None else parts.light_host
    for other in (parts.selection, parts.parent, outer):
        if other is None or view_utils.same_node(other, host):
            continue
        stale = view_utils.find_child(other, LIGHTS_NAME)
        if stale is not None:
            other.removeChild(stale)
    group = view_utils.find_child(host, LIGHTS_NAME)
    if group is None:
        if not nodes:
            return
        group = coin.SoGroup()
        group.setName(LIGHTS_NAME)
        index = host.findChild(wrapper) if outer is not None else 0
        host.insertChild(group, max(index, 0))
    view_utils.set_children(group, nodes)


# -------------------------------------------------------------------- shadows
def _shadow_wrapper(parts):
    if parts.parent is not None and parts.parent.getName().getString() == shadows.GROUP_NAME:
        return parts.parent
    return None


def _outer_parent(parts, wrapper):
    """Node holding the selection root, or the shadow group wrapped around it."""
    if wrapper is None:
        return parts.parent
    search = coin.SoSearchAction()
    search.setNode(wrapper)
    search.setInterest(coin.SoSearchAction.FIRST)
    try:
        root = parts.view.getViewer().getSoRenderManager().getSceneGraph()
    except Exception:
        root = parts.scene
    search.apply(root)
    path = search.getPath()
    if path is None or path.getLength() < 2:
        return None
    return path.getNodeFromTail(1)


def _sync_shadows(parts, settings, nodes, mirrors, doc):
    wrapper = _shadow_wrapper(parts)
    wanted = settings.shadows and bool(nodes) and parts.parent is not None

    if not wanted:
        if wrapper is not None:
            outer = _outer_parent(parts, wrapper)
            if outer is not None:
                selection = parts.selection
                selection.ref()
                wrapper.removeChild(selection)
                outer.replaceChild(wrapper, selection)
                selection.unref()
        return

    if wrapper is None:
        wrapper, light_group = shadows.make_group()
        if wrapper is None:
            return
        selection = parts.selection
        selection.ref()
        parts.parent.replaceChild(selection, wrapper)
        wrapper.addChild(selection)
        selection.unref()
    else:
        light_group = view_utils.find_child(wrapper, shadows.LIGHTS_NAME)
    shadows.apply_settings(wrapper, settings, parts.view)
    box = view_utils.scene_bound_box(parts.view, doc)
    for node in nodes:
        shadows.set_map_scene(node, mirrors.caster_scene)
        shadows.fit_to(node, box)
    if light_group is not None:
        view_utils.set_children(light_group, nodes)


# ---------------------------------------------------------- ambient occlusion
def _auto_ao_radius(view, doc):
    box = view_utils.scene_bound_box(view, doc)
    if box is None:
        return 0.0
    diagonal = ((box[3] - box[0]) ** 2 + (box[4] - box[1]) ** 2 + (box[5] - box[2]) ** 2) ** 0.5
    radius = 0.06 * diagonal
    if radius <= 0:
        return 0.0
    # two significant digits: small model edits must not rebuild the effect
    return float('%.1e' % radius)


def _sync_ao(parts, settings, doc, mirrors):
    wrapper = _shadow_wrapper(parts)
    outer = _outer_parent(parts, wrapper)
    if outer is None:
        return
    existing = view_utils.find_child(outer, ambient_occlusion.ROOT_NAME)

    wanted = settings.ao and ambient_occlusion.available()
    radius = 0.0
    camera = None
    if wanted:
        radius = settings.ao_radius if settings.ao_radius > 0 else _auto_ao_radius(parts.view, doc)
        camera = parts.view.getCameraNode()
        wanted = radius > 0 and camera is not None and settings.ao_intensity > 0
    if not wanted:
        if existing is not None:
            outer.removeChild(existing)
        return

    width, height = view_utils.viewport_size(parts.view)
    if width < 8 or height < 8:
        return
    shrink = min(1.0, float(ambient_occlusion.MAX_TEXTURE) / max(width, height))
    wanted_signature = ambient_occlusion.signature(
        max(int(width * shrink), 8), max(int(height * shrink), 8), camera, mirrors.ao,
        radius, settings.ao_intensity, settings.ao_quality)
    if existing is not None:
        if ambient_occlusion.current_signature(existing) == wanted_signature:
            return
        outer.removeChild(existing)
    outer.addChild(ambient_occlusion.build(width, height, camera, mirrors.ao, radius,
                                           settings.ao_intensity, settings.ao_quality))


# ------------------------------------------------------------- shadow catcher
def _catcher_direction(lights):
    """Direction of the light the catcher's shadow is drawn from."""
    for obj, node in lights:
        try:
            if getattr(obj, 'CastShadows', False) and obj.ViewObject.Visibility:
                d = obj.Direction
                return (d.x, d.y, d.z)
        except Exception:
            pass
    return None


def _sync_catcher(parts, settings, doc, mirrors, lights):
    wrapper = _shadow_wrapper(parts)
    outer = _outer_parent(parts, wrapper)
    if outer is None:
        return
    existing = view_utils.find_child(outer, shadow_catcher.ROOT_NAME)
    box = view_utils.scene_bound_box(parts.view, doc) if settings.catcher else None
    if box is None or not ambient_occlusion.available():
        if existing is not None:
            outer.removeChild(existing)
        return
    wanted = shadow_catcher.signature(
        shadow_catcher.RESOLUTION.get(settings.shadow_quality, 1024), mirrors.caster_scene)
    if existing is not None and shadow_catcher.current_signature(existing) != wanted:
        outer.removeChild(existing)
        existing = None
    if existing is None:
        existing = shadow_catcher.build(mirrors.caster_scene, settings.shadow_quality)
        outer.addChild(existing)
    shadow_catcher.update(existing, box, _catcher_direction(lights),
                          settings.shadow_darkness, settings.shadow_softness)


# ----------------------------------------------------------------- navigation
def _sync_navigation(view, settings):
    """Hand the effect nodes of ``view`` to the navigation watcher."""
    parts = view_utils.SceneParts(view)
    wrapper = _shadow_wrapper(parts)
    outer = _outer_parent(parts, wrapper)
    ao_switch = None
    if outer is not None:
        ao_root = view_utils.find_child(outer, ambient_occlusion.ROOT_NAME)
        if ao_root is not None:
            ao_switch = view_utils.find_child(ao_root, ambient_occlusion.SWITCH_NAME)
    navigation.update(view, settings.navigation_mode, settings.navigation_delay,
                      ao_switch, wrapper, _bridge)


# ----------------------------------------------------------------------- sync
def _view_light_count(parts):
    """Lights FreeCAD itself has switched on in this view (headlight, fill, back...)."""
    try:
        root = parts.view.getViewer().getSoRenderManager().getSceneGraph()
    except Exception:
        root = parts.scene
    search = coin.SoSearchAction()
    search.setType(coin.SoLight.getClassTypeId())
    search.setInterest(coin.SoSearchAction.ALL)
    search.apply(root)
    ours = (LIGHTS_NAME, shadows.LIGHTS_NAME)
    count = 0
    for path in search.getPaths():
        light = path.getTail()
        if not coin.cast(light.getField('on'), 'SoSFBool').getValue():
            continue
        inside = False
        for i in range(path.getLength()):
            node = path.getNode(i)
            if view_utils.same_node(node, parts.selection) or node.getName().getString() in ours:
                inside = True
                break
        if not inside:
            count += 1
    return max(count, 1)


def _within_light_budget(parts, lights):
    """OpenGL (and Coin's shadow shader, which fails to compile beyond it) handles
    8 lights.  Keep the lights that are switched on within what FreeCAD leaves
    free, shadow casters first; hidden lights cost nothing and always stay."""
    budget = MAX_GL_LIGHTS - _view_light_count(parts)
    on = [(o, n) for o, n in lights if bool(n.on.getValue())]
    if len(on) <= budget:
        return lights
    on.sort(key=lambda item: not getattr(item[0], 'CastShadows', False))
    keep = set(o.Name for o, n in on[:budget])
    dropped = [o.Label for o, n in on[budget:]]
    _warn_once('budget:' + ','.join(dropped),
               "too many lights switched on: OpenGL handles %d, FreeCAD uses %d. "
               "Not shown: %s." % (MAX_GL_LIGHTS, MAX_GL_LIGHTS - budget, ', '.join(dropped)))
    return [item for item in lights if not bool(item[1].on.getValue()) or item[0].Name in keep]


def sync_view(view, settings, lights, doc):
    parts = view_utils.SceneParts(view)
    if not parts.valid():
        return
    if lights:
        try:
            from Gizmos import interaction
            interaction.ensure(view, doc)
        except Exception as error:
            FreeCAD.Console.PrintLog("Usinix: efeitos: %s\n" % error)

    use_shadows = settings.shadows and shadows.available()
    if settings.shadows and not use_shadows:
        _warn_once('noshadow', "este programa não tem as sombras do Coin.")

    lights = _within_light_budget(parts, lights)
    plain, casting = [], []
    for obj, node in lights:
        if use_shadows and getattr(obj, 'CastShadows', False):
            casting.append(node)
        else:
            plain.append(node)
    if settings.shadows and use_shadows and not casting:
        _warn_once('nocaster',
                   "shadows are enabled but no directional or spot light has CastShadows set.")

    mirrors = mirrors_of(doc, view)
    _sync_shadows(parts, settings, casting, mirrors, doc)
    _sync_plain_lights(view_utils.SceneParts(view), plain)
    # the scene graph may just have been rearranged: look again
    _sync_catcher(view_utils.SceneParts(view), settings, doc, mirrors, lights)
    _sync_ao(view_utils.SceneParts(view), settings, doc, mirrors)
    _sync_navigation(view, settings)


def sync_document(doc):
    """Bring every 3D view of ``doc`` in line with its lights and effect settings."""
    if not FreeCAD.GuiUp or doc is None:
        return
    try:
        settings = Settings(doc)
        lights = document_lights(doc)
        views = view_utils.views_of(doc)
    except ReferenceError:
        return   # document closed in the meantime
    for view in views:
        try:
            sync_view(view, settings, lights, doc)
        except Exception as error:   # never let a display helper break the application
            FreeCAD.Console.PrintError("Usinix: os efeitos da vista falharam: %s\n" % error)
    _forget_closed_documents()
    _forget_closed_views()
    _update_watch()


def _forget_closed_views():
    views = []
    for doc in FreeCAD.listDocuments().values():
        views += view_utils.views_of(doc)
    navigation.forget_except(views)
    try:
        from Gizmos import interaction
        interaction.forget_except(views)
    except Exception:
        pass


def _run_pending():
    names = list(_pending)
    _pending.clear()
    documents = FreeCAD.listDocuments()
    for name in names:
        doc = documents.get(name)
        if doc is not None:
            sync_document(doc)


def schedule_sync(doc=None):
    """Ask for ``doc`` (default: every open document) to be synced shortly.

    Safe to call from anywhere, any number of times, also from a worker
    thread: the work is done once, later, in the GUI thread.
    """
    if not FreeCAD.GuiUp:
        return
    _ensure_hooks()
    from . import config
    try:
        # Usinix: só os documentos com efeitos são acompanhados (os outros não pagam nada)
        docs = [doc] if doc is not None else list(FreeCAD.listDocuments().values())
        names = [d.Name for d in docs if config.em_uso(d)]
    except ReferenceError:
        return
    if not names:
        return
    _pending.update(names)
    _bridge.wake.emit()


def light_moved(doc):
    """A light changed direction or visibility: the shadow catcher follows."""
    if doc is not None and Settings(doc).catcher:
        schedule_sync(doc)


# ---------------------------------------------------------------------- hooks
class _DocumentObserver:
    """Anything that can add, remove or bring back a light triggers a sync."""

    def slotCreatedObject(self, obj):
        schedule_sync(obj.Document)

    def slotDeletedObject(self, obj):
        from . import config
        config.esquecer(obj.Document)
        schedule_sync(obj.Document)

    def slotUndoDocument(self, doc):
        from . import config
        config.esquecer(doc)
        schedule_sync(doc)

    def slotRedoDocument(self, doc):
        from . import config
        config.esquecer(doc)
        schedule_sync(doc)

    def slotFinishRestoreDocument(self, doc):
        from . import config
        config.esquecer(doc)
        schedule_sync(doc)

    def slotActivateDocument(self, doc):
        schedule_sync(doc)

    def slotChangedObject(self, obj, prop):
        # the model moved or changed: the shadow maps follow it
        if prop in ('Shape', 'Placement', 'Visibility', 'Mesh', 'Points'):
            try:
                doc = obj.Document
                settings = Settings(doc)
                if settings.shadows or settings.catcher:
                    schedule_sync(doc)
            except Exception:
                pass


def _ensure_hooks():
    global _timer, _watch_timer, _observer, _bridge
    if _bridge is not None:
        return
    import FreeCADGui
    from PySide import QtCore

    class Bridge(QtCore.QObject):
        wake = QtCore.Signal()

    main_window = FreeCADGui.getMainWindow()
    _bridge = Bridge(main_window)

    _timer = QtCore.QTimer(_bridge)
    _timer.setSingleShot(True)
    _timer.setInterval(SYNC_DELAY_MS)
    _timer.timeout.connect(_run_pending)
    # queued when emitted from another thread, so the timer is always started in the GUI thread
    _bridge.wake.connect(_timer.start)

    _watch_timer = QtCore.QTimer(_bridge)
    _watch_timer.setInterval(WATCH_INTERVAL_MS)
    _watch_timer.timeout.connect(_watch)

    _observer = _DocumentObserver()
    FreeCAD.addDocumentObserver(_observer)

    # a view opened later ("new 3D view", split view) has to get the lights too
    try:
        from PySide import QtWidgets
        mdi = main_window.findChild(QtWidgets.QMdiArea)
        if mdi is not None:
            mdi.subWindowActivated.connect(_view_activated)
    except Exception:
        pass


def _view_activated(*args):
    schedule_sync()


def _ao_documents():
    """Documents with an effect that needs watching (see _watch)."""
    docs = []
    for doc in FreeCAD.listDocuments().values():
        try:
            settings = Settings(doc)
            if settings.ao or settings.shadows:
                docs.append(doc)
        except Exception:
            pass
    return docs


def _update_watch():
    """The watch timer only runs while some document uses an effect."""
    if _watch_timer is None:
        return
    if _ao_documents():
        if not _watch_timer.isActive():
            _watch_timer.start()
    elif _watch_timer.isActive():
        _watch_timer.stop()


def _watch():
    """Ambient occlusion depends on the size of the view, on its camera node
    (replaced when switching orthographic/perspective) and, with the automatic
    radius, on the size of the scene.  None of these can be observed from
    Python, so they are polled; nothing is touched unless something changed.
    The navigation watcher needs the current camera node too."""
    docs = _ao_documents()
    if not docs:
        _watch_timer.stop()
        return
    for doc in docs:
        try:
            settings = Settings(doc)
            for view in view_utils.views_of(doc):
                if settings.ao:
                    _sync_ao(view_utils.SceneParts(view), settings, doc, mirrors_of(doc, view))
                _sync_navigation(view, settings)
        except Exception:
            pass
