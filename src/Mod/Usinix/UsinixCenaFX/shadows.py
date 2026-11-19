# SPDX-License-Identifier: LGPL-2.1-or-later
# Copyright (c) 2025-2026 OficineRobotica
"""Real-time shadows, with Coin's own SoShadowGroup.

pivy has no Python classes for the shadow nodes, so they are created from
their type names and configured through the generic field interface.

The shadow group replaces the fixed-function lighting of everything inside it
with a per-pixel lighting shader.  Lights inside the group cast shadows
(SoShadowDirectionalLight and spot lights only: Coin cannot do point light
shadows), lights outside of it still light the scene but cast none.
"""
from pivy import coin

from . import view_utils

GROUP_NAME = 'DisplayToolsShadows'
LIGHTS_NAME = 'DisplayToolsShadowLights'

# shadow map size (pixels) for each quality level
MAP_SIZE = {'Low': 1024, 'Medium': 2048, 'High': 4096}

_max_texture_size = None


def available():
    return not coin.SoType.fromName('SoShadowGroup').isBad()


def max_texture_size(view=None):
    """GL_MAX_TEXTURE_SIZE of the 3D view (Coin sizes the shadow map as a fraction of it)."""
    global _max_texture_size
    if _max_texture_size:
        return _max_texture_size
    size = 0
    try:
        from PySide import QtGui
        # FreeCAD normally leaves the context of its 3D view current
        context = QtGui.QOpenGLContext.currentContext()
        if context is not None:
            size = int(context.functions().glGetIntegerv(0x0D33))   # GL_MAX_TEXTURE_SIZE
    except Exception:
        size = 0
    if size < 1024:
        return 16384    # what practically every desktop GPU reports; not cached, try again later
    _max_texture_size = size
    return size


def caster_scene(mirror):
    """Scene the shadow maps are rendered from.

    By default Coin renders the shadow maps from the whole shadow group, with
    the view's own render action, which crashes FreeCAD for the same reason
    explained in ambient_occlusion.py.  The maps are drawn from the view
    providers' roots instead (``mirror``), with transparency off.
    """
    scene = coin.SoSeparator()
    transparency = coin.SoTransparencyType()
    transparency.value = coin.SoTransparencyType.NONE
    transparency.setOverride(True)
    scene.addChild(transparency)
    scene.addChild(mirror)
    return scene


def set_map_scene(light, scene):
    field = light.getField('shadowMapScene')
    if field is None:
        return
    field = coin.cast(field, 'SoSFNode')
    if not view_utils.same_node(field.getValue(), scene):
        field.setValue(scene)


def fit_to(light, box):
    """Aim the shadow map of a directional light at ``box`` (the model only).

    Left alone, Coin sizes it on everything in the shadow group, grid and
    gizmos included, and the shadows lose most of their resolution.
    """
    if light.getField('bboxSize') is None:
        return          # spot lights work it out from their cone
    if box is None:
        center, size = (0.0, 0.0, 0.0), (-1.0, -1.0, -1.0)     # Coin: "automatic"
    else:
        center = tuple((box[i] + box[i + 3]) / 2.0 for i in range(3))
        # a little margin, and never flat (a plate seen edge-on still casts)
        extent = max(box[3] - box[0], box[4] - box[1], box[5] - box[2], 1e-3)
        size = tuple(max(box[i + 3] - box[i], 0.02 * extent) * 1.05 for i in range(3))
    for name, value in (('bboxCenter', center), ('bboxSize', size)):
        field = light.getField(name)
        current = field.get()
        current = current.getString() if hasattr(current, 'getString') else str(current)
        wanted = '%g %g %g' % value
        try:
            if all(abs(float(a) - float(b)) <= 1e-6 * max(1.0, abs(float(b)))
                   for a, b in zip(current.split(), wanted.split())):
                continue
        except ValueError:
            pass
        field.set(wanted)


def make_group():
    """ShadowGroup [ Group(shadow casting lights) ] -- the scene is added by the caller."""
    group = view_utils.new_node('SoShadowGroup')
    if group is None:
        return None, None
    group.setName(GROUP_NAME)
    view_utils.set_field(group, 'quality', 1.0)          # per-pixel lighting
    view_utils.set_field(group, 'threshold', 0.1)
    # Coin's default (0.00001) leaves dark smudges on lit faces next to their
    # own edges ("shadow acne"); checked on FreeCAD 26.3 that this cleans them up
    view_utils.set_field(group, 'epsilon', 0.0003)
    lights = coin.SoGroup()
    lights.setName(LIGHTS_NAME)
    group.addChild(lights)
    return group, lights


def _set_float(node, name, value):
    """Set a float field by name, without touching it (and redrawing) if unchanged."""
    field = node.getField(name)
    if field is None:
        return
    try:
        current = field.get()
        current = current.getString() if hasattr(current, 'getString') else str(current)
        if abs(float(current) - value) < 1e-6:
            return
    except Exception:
        pass
    field.set(repr(float(value)))


def apply_settings(group, settings, view=None):
    """Push the scene configuration values to an existing shadow group."""
    _set_float(group, 'intensity', min(max(settings.shadow_darkness, 0.0), 1.0))
    _set_float(group, 'smoothBorder', min(max(settings.shadow_softness, 0.0), 1.0))
    target = MAP_SIZE.get(settings.shadow_quality, MAP_SIZE['Medium'])
    # Coin rounds precision * max size up to a power of two: stay just below the target
    precision = min(1.0, (target - 1.0) / float(max_texture_size(view)))
    _set_float(group, 'precision', precision)
