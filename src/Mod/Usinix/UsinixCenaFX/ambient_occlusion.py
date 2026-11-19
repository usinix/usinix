# SPDX-License-Identifier: LGPL-2.1-or-later
# Copyright (c) 2025-2026 OficineRobotica
"""Screen space ambient occlusion for the 3D view, built from stock Coin nodes.

Three passes, all driven by Coin (no direct OpenGL calls):

1. *depth*  -- the scene is rendered into a floating point texture with a
   shader that writes the eye space depth of every pixel;
2. *occlusion* -- a full screen quad computes the occlusion from that depth
   texture ("Scalable Ambient Obscurance" sampling, McGuire et al. 2012);
3. *composite* -- a full screen quad at the end of the normal scene blurs the
   occlusion (depth aware) and darkens the picture with it.

The quads are emitted directly in clip space, and the fragment shaders read
the projection of the view's own camera from ``gl_ProjectionMatrix``, so the
same code serves orthographic and perspective views.

The scene is drawn one more time per frame: on heavy models this costs frame
rate, which is why the effect is opt-in per document.

Crash to avoid
--------------
A scene texture renders its scene with the *view's own* render action.  Some
nodes do not draw during the normal pass but queue a path to be drawn at the
end of the frame (FreeCAD's "selection on top", annotations, transparent
objects).  Queued from inside the depth pass, such a path starts at our node
instead of at the root of the view; Coin later replays all queued paths from
the root of the first one and walks off the end of a child list -> segfault
(seen on FreeCAD 27.1 when selecting a group with ambient occlusion on).
Three things keep it from happening:

* the depth pass only contains the view providers' roots (``scene``, kept up
  to date by view_rig), never FreeCAD's "on top" group or editing root;
* transparency is forced off in the depth pass, so nothing transparent is queued;
* the whole effect sits in an SoAnnotation: it is itself drawn in the
  end-of-frame phase, where nodes draw directly instead of queueing.
"""
from pivy import coin

from . import view_utils

ROOT_NAME = 'DisplayToolsAO'
SWITCH_NAME = ROOT_NAME + 'Switch'

# quality -> (samples, occlusion texture scale, spiral turns)
QUALITY = {'Low': (8, 0.5, 5), 'Medium': (14, 0.5, 7), 'High': (22, 1.0, 11)}

MAX_TEXTURE = 8192   # SoSceneTexture2 sizes are 16 bit

DEPTH_VERTEX = """#version 120
varying float dt_depth;
void main() {
    vec4 eye = gl_ModelViewMatrix * gl_Vertex;
    dt_depth = -eye.z;
    gl_ClipVertex = eye;            // keep FreeCAD's clipping planes working
    gl_Position = ftransform();
}
"""

DEPTH_FRAGMENT = """#version 120
varying float dt_depth;
void main() {
    gl_FragColor = vec4(dt_depth, 0.0, 0.0, 1.0);   // alpha 0 = background
}
"""

QUAD_VERTEX = """#version 120
varying vec2 dt_uv;
void main() {
    dt_uv = gl_Vertex.xy * 0.5 + 0.5;
    gl_Position = vec4(gl_Vertex.xy, 0.0, 1.0);
}
"""

OCCLUSION_FRAGMENT = """#version 120
#define DT_SAMPLES %(samples)d
#define DT_TURNS %(turns)d.0
uniform sampler2D dt_depthTex;
uniform vec2 dt_texel;        // size of a depth texel in uv
uniform float dt_radius;      // world units
uniform float dt_intensity;
varying vec2 dt_uv;

// eye space position of the surface seen at uv; valid = 0 on the background
vec3 positionAt(vec2 uv, out float valid) {
    // read texel centers only: a filtered sample across a silhouette would
    // blend the depths of two unrelated surfaces (or of the background)
    // (the small offset keeps the choice stable when uv falls exactly between
    // two texels, as it does in the half resolution occlusion pass)
    uv = (floor(uv / dt_texel + 0.01) + 0.5) * dt_texel;
    vec4 s = texture2D(dt_depthTex, uv);
    valid = step(0.99, s.a);
    float ze = -s.r;
    float wc = gl_ProjectionMatrix[2][3] * ze + gl_ProjectionMatrix[3][3];
    vec2 ndc = uv * 2.0 - 1.0;
    float xe = (ndc.x * wc - gl_ProjectionMatrix[2][0] * ze - gl_ProjectionMatrix[3][0]) / gl_ProjectionMatrix[0][0];
    float ye = (ndc.y * wc - gl_ProjectionMatrix[2][1] * ze - gl_ProjectionMatrix[3][1]) / gl_ProjectionMatrix[1][1];
    return vec3(xe, ye, ze);
}

void main() {
    float valid;
    vec3 C = positionAt(dt_uv, valid);
    if (valid < 0.5) { gl_FragColor = vec4(1.0); return; }

    // surface normal from the depth neighbours, taking on each axis the side
    // with the smaller depth step so that silhouettes do not bend it
    float vl, vr, vd, vu;
    vec3 L = positionAt(dt_uv - vec2(dt_texel.x, 0.0), vl);
    vec3 R = positionAt(dt_uv + vec2(dt_texel.x, 0.0), vr);
    vec3 D = positionAt(dt_uv - vec2(0.0, dt_texel.y), vd);
    vec3 U = positionAt(dt_uv + vec2(0.0, dt_texel.y), vu);
    vec3 dx = (vr > 0.5 && (vl < 0.5 || abs(R.z - C.z) < abs(C.z - L.z))) ? R - C : C - L;
    vec3 dy = (vu > 0.5 && (vd < 0.5 || abs(U.z - C.z) < abs(C.z - D.z))) ? U - C : C - D;
    vec3 n = normalize(cross(dx, dy));
    if (n.z < 0.0) n = -n;

    // radius of the sampling disc in uv
    float wc = gl_ProjectionMatrix[2][3] * C.z + gl_ProjectionMatrix[3][3];
    vec2 ruv = dt_radius * 0.5 * vec2(gl_ProjectionMatrix[0][0], gl_ProjectionMatrix[1][1]) / max(wc, 1e-6);
    // Seen from very close the disc would cover half the screen, far too much
    // for the few samples taken: shrink the radius instead (limit: 8%% of the view).
    float scale = min(1.0, 0.08 / max(ruv.x, ruv.y));
    ruv *= scale;
    if (max(ruv.x / dt_texel.x, ruv.y / dt_texel.y) < 1.5) { gl_FragColor = vec4(1.0); return; }

    float R2 = dt_radius * dt_radius * scale * scale;
    float bias = 0.02 * dt_radius * scale + 0.0005 * abs(C.z);
    // per pixel rotation of the sampling spiral, repeating every 4x4 pixels:
    // exactly what the 4x4 blur of the composite pass averages away
    vec2 cell = mod(floor(gl_FragCoord.xy), 4.0);
    float spin = 6.2831853 * mod((cell.x * 4.0 + cell.y) * 7.0, 16.0) / 16.0;

    float sum = 0.0;
    for (int i = 0; i < DT_SAMPLES; i++) {
        float a = (float(i) + 0.5) / float(DT_SAMPLES);
        float angle = a * DT_TURNS * 6.2831853 + spin;
        float qv;
        vec3 Q = positionAt(dt_uv + a * vec2(cos(angle), sin(angle)) * ruv, qv);
        vec3 v = Q - C;
        float vv = dot(v, v);
        float vn = dot(v, n);
        float f = max(R2 - vv, 0.0);
        sum += qv * f * f * f * max((vn - bias) / (vv + 1e-4 * R2), 0.0);
    }
    // sum has the dimension length^5: dividing by radius^5 makes the result independent of the model size
    float occlusion = sum * 2.0 * sqrt(R2) / (R2 * R2 * R2 * float(DT_SAMPLES));
    float visibility = clamp(1.0 - dt_intensity * occlusion, 0.0, 1.0);
    gl_FragColor = vec4(visibility, visibility, visibility, 1.0);
}
"""

COMPOSITE_FRAGMENT = """#version 120
uniform sampler2D dt_aoTex;
uniform sampler2D dt_depthTex;
uniform vec2 dt_aoTexel;
uniform float dt_radius;
varying vec2 dt_uv;

void main() {
    vec4 center = texture2D(dt_depthTex, dt_uv);
    if (center.a < 0.5) discard;
    float sum = 0.0;
    float weight = 0.0;
    for (int x = -2; x < 2; x++) {
        for (int y = -2; y < 2; y++) {
            vec2 uv = dt_uv + (vec2(float(x), float(y)) + 0.5) * dt_aoTexel;
            vec4 d = texture2D(dt_depthTex, uv);
            float w = d.a * max(0.0, 1.0 - abs(d.r - center.r) / dt_radius) + 1e-4;
            // stay inside the texture: its border reads as "fully occluded"
            vec2 inside = clamp(uv, 0.5 * dt_aoTexel, 1.0 - 0.5 * dt_aoTexel);
            sum += w * texture2D(dt_aoTex, inside).r;
            weight += w;
        }
    }
    // black, blended over the picture: result = picture * visibility
    gl_FragColor = vec4(0.0, 0.0, 0.0, 1.0 - sum / weight);
}
"""


def available():
    return all(hasattr(coin, name) for name in
               ('SoSceneTexture2', 'SoShaderProgram', 'SoFragmentShader', 'SoVertexShader',
                'SoShaderParameter1f', 'SoShaderParameter2f', 'SoShaderParameter1i',
                'SoTextureUnit', 'SoDepthBuffer', 'SoTransparencyType'))


def signature(width, height, camera, scene, radius, intensity, quality):
    """Everything the node tree depends on; a different signature means "rebuild"."""
    return '%dx%d|%x|%x|%.6g|%.4g|%s' % (width, height, view_utils.node_address(camera),
                                          view_utils.node_address(scene),
                                          radius, intensity, quality)


def current_signature(root):
    info = view_utils.find_child(root, ROOT_NAME + 'Info')
    return info.string.getValue().getString() if info is not None else None


def _program(vertex, fragment, parameters):
    vs = coin.SoVertexShader()
    vs.sourceType = coin.SoShaderObject.GLSL_PROGRAM
    vs.sourceProgram = vertex
    fs = coin.SoFragmentShader()
    fs.sourceType = coin.SoShaderObject.GLSL_PROGRAM
    fs.sourceProgram = fragment
    for i, parameter in enumerate(parameters):
        fs.parameter.set1Value(i, parameter)
    program = coin.SoShaderProgram()
    program.shaderObject.set1Value(0, vs)
    program.shaderObject.set1Value(1, fs)
    return program


def _float(name, value):
    p = coin.SoShaderParameter1f()
    p.name = name
    p.value = float(value)
    return p


def _vec2(name, x, y):
    p = coin.SoShaderParameter2f()
    p.name = name
    p.value = coin.SbVec2f(float(x), float(y))
    return p


def _sampler(name, unit):
    p = coin.SoShaderParameter1i()
    p.name = name
    p.value = int(unit)
    return p


def _quad():
    coords = coin.SoCoordinate3()
    coords.point.setValues(0, 4, [(-1, -1, 0), (1, -1, 0), (1, 1, 0), (-1, 1, 0)])
    face = coin.SoFaceSet()
    face.numVertices.setValue(4)
    group = coin.SoGroup()
    group.addChild(coords)
    group.addChild(face)
    return group


def _depth(enabled):
    """Depth test/write switch.

    A scene texture renders (and clears!) its buffers with the depth settings
    in force at the place it sits in the graph: with depth writing off its
    depth buffer is never cleared and nothing gets drawn.  So the "off" node
    of a quad always comes *after* the texture nodes that quad uses.
    """
    node = coin.SoDepthBuffer()
    node.test = enabled
    node.write = enabled
    return node


def _hide_lines():
    """Keeps edges out of the depth pass: occlusion is about surfaces, and the
    edge lines FreeCAD draws slightly in front of the faces would show up as
    dark specks.  An all-zero line pattern, forced on everything below."""
    style = coin.SoDrawStyle()
    style.linePattern = 0
    for name in ('style', 'pointSize', 'lineWidth'):
        style.getField(name).setIgnored(True)       # leave these to the scene
    style.setOverride(True)
    return style


def _no_transparency():
    """Everything opaque, drawn at once: nothing gets queued for later."""
    node = coin.SoTransparencyType()
    node.value = coin.SoTransparencyType.NONE
    node.setOverride(True)
    return node


def _texture(width, height, texture_type, scene):
    tex = coin.SoSceneTexture2()
    tex.size = coin.SbVec2s(int(width), int(height))
    tex.type = texture_type
    tex.backgroundColor = coin.SbVec4f(0, 0, 0, 0)
    tex.transparencyFunction = coin.SoSceneTexture2.NONE
    tex.wrapS = coin.SoSceneTexture2.CLAMP
    tex.wrapT = coin.SoSceneTexture2.CLAMP
    tex.scene = scene
    return tex


def _unit(index):
    unit = coin.SoTextureUnit()
    unit.unit = index
    return unit


def build(width, height, camera, scene, radius, intensity, quality):
    """Node tree of the effect, to be added right after the scene in the view."""
    samples, ao_scale, turns = QUALITY.get(quality, QUALITY['Medium'])
    shrink = min(1.0, float(MAX_TEXTURE) / max(width, height, 1))
    width = max(int(width * shrink), 8)
    height = max(int(height * shrink), 8)
    ao_w = max(int(width * ao_scale), 8)
    ao_h = max(int(height * ao_scale), 8)

    # pass 1: eye depth of the scene, seen through the view's own camera
    depth_scene = coin.SoSeparator()
    # off then on: SoAnnotation switches depth testing off behind Coin's back,
    # a change of value is what makes Coin switch it on again for real
    depth_scene.addChild(_depth(False))
    depth_scene.addChild(_depth(True))
    depth_scene.addChild(_no_transparency())
    depth_scene.addChild(camera)
    depth_scene.addChild(_hide_lines())
    depth_scene.addChild(_program(DEPTH_VERTEX, DEPTH_FRAGMENT, []))
    depth_scene.addChild(scene)
    depth_tex = _texture(width, height, coin.SoSceneTexture2.RGBA32F, depth_scene)

    # pass 2: occlusion.  The camera is there only to load its projection matrix.
    ao_scene = coin.SoSeparator()
    ao_scene.addChild(camera)
    ao_scene.addChild(_unit(0))
    ao_scene.addChild(depth_tex)
    ao_scene.addChild(_depth(False))    # only after the texture: see _depth()
    ao_scene.addChild(_program(QUAD_VERTEX,
                               OCCLUSION_FRAGMENT % {'samples': samples, 'turns': turns},
                               [_sampler('dt_depthTex', 0),
                                _vec2('dt_texel', 1.0 / width, 1.0 / height),
                                _float('dt_radius', radius),
                                _float('dt_intensity', intensity)]))
    ao_scene.addChild(_quad())
    ao_tex = _texture(ao_w, ao_h, coin.SoSceneTexture2.RGBA8, ao_scene)

    # pass 3: composite over the picture
    root = coin.SoAnnotation()          # drawn in the end-of-frame phase, see above
    root.setName(ROOT_NAME)
    root.renderCulling = coin.SoSeparator.OFF
    root.pickCulling = coin.SoSeparator.OFF

    info = coin.SoInfo()
    info.setName(ROOT_NAME + 'Info')
    info.string = signature(width, height, camera, scene, radius, intensity, quality)
    root.addChild(info)

    # switched off while the view is navigated, see navigation.py
    switch = coin.SoSwitch()
    switch.setName(SWITCH_NAME)
    switch.whichChild = coin.SO_SWITCH_ALL
    root.addChild(switch)

    body = view_utils.skip_bounding_group()     # keep the quad out of "fit all"
    switch.addChild(body)

    pick = coin.SoPickStyle()
    pick.style = coin.SoPickStyle.UNPICKABLE
    body.addChild(pick)
    light_model = coin.SoLightModel()
    light_model.model = coin.SoLightModel.BASE_COLOR
    body.addChild(light_model)
    draw_style = coin.SoDrawStyle()
    draw_style.style = coin.SoDrawStyle.FILLED
    body.addChild(draw_style)
    blend = coin.SoTransparencyType()
    blend.value = coin.SoTransparencyType.BLEND
    body.addChild(blend)
    material = coin.SoMaterial()
    material.diffuseColor = (0, 0, 0)
    material.transparency = 0.5         # only there to make Coin enable blending
    body.addChild(material)
    body.addChild(_unit(1))
    body.addChild(depth_tex)
    body.addChild(_unit(0))
    body.addChild(ao_tex)
    body.addChild(_depth(False))        # only after the textures: see _depth()
    body.addChild(_program(QUAD_VERTEX, COMPOSITE_FRAGMENT,
                           [_sampler('dt_aoTex', 0),
                            _sampler('dt_depthTex', 1),
                            _vec2('dt_aoTexel', 1.0 / ao_w, 1.0 / ao_h),
                            _float('dt_radius', radius)]))
    body.addChild(_quad())
    return root
