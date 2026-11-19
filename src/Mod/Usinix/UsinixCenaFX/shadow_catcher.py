# SPDX-License-Identifier: LGPL-2.1-or-later
# Copyright (c) 2025-2026 OficineRobotica
"""Shadow catcher: the soft shadow of the model on an invisible ground.

The model is drawn from above into a texture, sheared along the direction of
the light so that every point lands where its shadow falls on the ground
(the lowest point of the scene).  A quad on the ground then shows the blurred
silhouette as a transparent dark stain.

It does not depend on the camera of the view: the texture is redrawn only
when the model or the light changes, so it costs nothing while navigating.
It is independent of the real-time shadows, and can be used with or without.
"""
import math

from pivy import coin

from . import view_utils
from . import ambient_occlusion as fx

ROOT_NAME = 'DisplayToolsCatcher'
RESOLUTION = {'Low': 512, 'Medium': 1024, 'High': 2048}
DEFAULT_DIRECTION = (0.25, 0.35, -1.0)
MIN_SLOPE = 0.25        # the light is never taken lower than this: shadows stay finite
MARGIN = 0.12           # of the footprint, room for the blur
FLATTEN = 1e-3

VERTEX = """#version 120
varying vec2 dt_uv;
void main() {
    dt_uv = gl_MultiTexCoord0.xy;
    gl_Position = ftransform();
}
"""

FRAGMENT = """#version 120
uniform sampler2D dt_tex;
uniform float dt_blur;
uniform float dt_dark;
varying vec2 dt_uv;
void main() {
    float cover = 0.0;
    for (int x = -3; x <= 3; x++) {
        for (int y = -3; y <= 3; y++) {
            cover += texture2D(dt_tex, dt_uv + vec2(float(x), float(y)) * dt_blur / 3.0).a;
        }
    }
    cover /= 49.0;
    if (cover < 0.004) discard;
    gl_FragColor = vec4(0.0, 0.0, 0.0, dt_dark * cover);
}
"""


def signature(resolution, caster_scene):
    return '%d|%x' % (resolution, view_utils.node_address(caster_scene))


def current_signature(root):
    info = view_utils.find_child(root, ROOT_NAME + 'Info')
    return info.string.getValue().getString() if info is not None else None


def _named(node, suffix):
    node.setName(ROOT_NAME + suffix)
    return node


def build(caster_scene, quality):
    resolution = RESOLUTION.get(quality, RESOLUTION['Medium'])

    scene = coin.SoSeparator()
    scene.addChild(fx._depth(False))
    scene.addChild(fx._depth(True))
    scene.addChild(_named(coin.SoOrthographicCamera(), 'Camera'))
    flat = coin.SoLightModel()
    flat.model = coin.SoLightModel.BASE_COLOR
    flat.setOverride(True)
    scene.addChild(flat)
    scene.addChild(fx._hide_lines())
    scene.addChild(_named(coin.SoMatrixTransform(), 'Matrix'))
    scene.addChild(caster_scene)
    texture = fx._texture(resolution, resolution, coin.SoSceneTexture2.RGBA8, scene)
    texture.setName(ROOT_NAME + 'Texture')

    root = coin.SoSeparator()
    root.setName(ROOT_NAME)
    info = coin.SoInfo()
    info.setName(ROOT_NAME + 'Info')
    info.string = signature(resolution, caster_scene)
    root.addChild(info)
    root.addChild(_named(coin.SoInfo(), 'State'))

    pick = coin.SoPickStyle()
    pick.style = coin.SoPickStyle.UNPICKABLE
    root.addChild(pick)
    light_model = coin.SoLightModel()
    light_model.model = coin.SoLightModel.BASE_COLOR
    root.addChild(light_model)
    style = coin.SoDrawStyle()
    style.style = coin.SoDrawStyle.FILLED
    root.addChild(style)
    blend = coin.SoTransparencyType()
    blend.value = coin.SoTransparencyType.BLEND
    root.addChild(blend)
    material = coin.SoMaterial()
    material.diffuseColor = (0, 0, 0)
    material.transparency = 0.5         # only there to make Coin enable blending
    root.addChild(material)
    root.addChild(fx._unit(0))
    root.addChild(texture)
    # after the texture (see ambient_occlusion._depth): hidden by the model in
    # front of it, but not hiding anything itself
    depth = coin.SoDepthBuffer()
    depth.test = True
    depth.write = False
    root.addChild(depth)
    blur = _named(fx._float('dt_blur', 0.0), 'Blur')
    dark = _named(fx._float('dt_dark', 0.0), 'Dark')
    root.addChild(fx._program(VERTEX, FRAGMENT, [fx._sampler('dt_tex', 0), blur, dark]))
    root.addChild(blur)     # also as children, so that they can be found again by name
    root.addChild(dark)
    uv = coin.SoTextureCoordinate2()
    uv.point.setValues(0, 4, [(0, 0), (1, 0), (1, 1), (0, 1)])
    root.addChild(uv)
    root.addChild(_named(coin.SoCoordinate3(), 'Quad'))
    face = coin.SoFaceSet()
    face.numVertices.setValue(4)
    root.addChild(face)
    return root


def _find(root, suffix):
    """A named node of the catcher: a child of its root or of the texture's scene
    (a search action does not look inside the scene of a scene texture)."""
    node = view_utils.find_child(root, ROOT_NAME + suffix)
    if node is None:
        texture = view_utils.find_child(root, ROOT_NAME + 'Texture')
        if texture is not None:
            node = view_utils.find_child(texture.scene.getValue(), ROOT_NAME + suffix)
    return node


def light_slopes(direction):
    """(sx, sy): how far a shadow moves in x and y per unit of height."""
    dx, dy, dz = direction if direction is not None else DEFAULT_DIRECTION
    length = math.sqrt(dx * dx + dy * dy + dz * dz) or 1.0
    dx, dy, dz = dx / length, dy / length, dz / length
    if dz > -MIN_SLOPE:
        dz = -MIN_SLOPE
    return dx / -dz, dy / -dz


def update(root, box, direction, darkness, softness):
    """Fit the catcher to the model (``box``) and to the light. Cheap if nothing changed."""
    state = '%s|%s|%.4g|%.4g' % (','.join('%.6g' % v for v in box),
                                 ','.join('%.5g' % v for v in (direction or DEFAULT_DIRECTION)),
                                 darkness, softness)
    info = view_utils.find_child(root, ROOT_NAME + 'State')
    if info is None or info.string.getValue().getString() == state:
        return
    info.string = state

    x0, y0, z0, x1, y1, z1 = box
    sx, sy = light_slopes(direction)
    height = max(z1 - z0, 0.0)
    # footprint of the shadow: the box itself plus the box shifted by its height
    fx0, fx1 = min(x0, x0 + sx * height), max(x1, x1 + sx * height)
    fy0, fy1 = min(y0, y0 + sy * height), max(y1, y1 + sy * height)
    side = max(fx1 - fx0, fy1 - fy0, 1e-6) * (1.0 + 2.0 * MARGIN)
    cx, cy = (fx0 + fx1) / 2.0, (fy0 + fy1) / 2.0
    half = side / 2.0

    # p -> (x + sx (z - z0), y + sy (z - z0), z0 + FLATTEN (z - z0)), Coin's row vectors
    matrix = _find(root, 'Matrix')
    matrix.matrix.setValue(coin.SbMatrix(1, 0, 0, 0,
                                         0, 1, 0, 0,
                                         sx, sy, FLATTEN, 0,
                                         -sx * z0, -sy * z0, z0 * (1 - FLATTEN), 1))
    camera = _find(root, 'Camera')
    distance = side + height
    camera.position.setValue(cx, cy, z0 + distance)
    camera.orientation.setValue(coin.SbRotation())          # looking down, +Y up
    camera.aspectRatio = 1.0
    camera.height = side
    camera.nearDistance = distance * 0.5
    camera.farDistance = distance * 1.5
    camera.focalDistance = distance

    quad = _find(root, 'Quad')
    quad.point.setValues(0, 4, [(cx - half, cy - half, z0), (cx + half, cy - half, z0),
                                (cx + half, cy + half, z0), (cx - half, cy + half, z0)])
    _find(root, 'Blur').value = 0.002 + 0.03 * min(max(softness, 0.0), 1.0)
    _find(root, 'Dark').value = min(max(darkness, 0.0), 1.0)
