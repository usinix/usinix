# SPDX-License-Identifier: LGPL-2.1-or-later
# Ícones da bancada Simulação (FEM) no estilo do guia ilustrado: estudo, material, apoios, cargas,
# malha, cálculo e resultados.
import math
from nucleo import Icon, SOLID, COPY, BASE, CUT, YEL, OUT, NAVY, STEEL, AMBER, AMBER_FILL, RED, GREEN, SW, SW_GEO

ICONS = {}

# escala de resultado (sóbria): frio → quente
MAPA = ("#2E5E8E", "#3E9C8F", "#E5B000", "#C9735F")
CARGA = AMBER                 # setas de carga
APOIO = NAVY


def icon(*names):
    def deco(fn):
        for n in names:
            ICONS[n] = fn
        return fn
    return deco


def raw(g, s):
    g.items.append(("raw", s))


# ------------------------------------------------------------ peças de desenho
def viga(g, x0=0, x1=12, y0=0, y1=3, z0=0, z1=3, pal=SOLID):
    g.box(x0, x1, y0, y1, z0, z1, pal=pal)


def malha_topo(g, x0, x1, y0, y1, z, nx=3, ny=2, cor="#FFFFFF", sw=1.3):
    """Triângulos da malha na face de cima."""
    for i in range(1, nx):
        x = x0 + (x1 - x0) * i / nx
        g.line((x, y0, z), (x, y1, z), color=cor, sw=sw)
    for j in range(1, ny):
        y = y0 + (y1 - y0) * j / ny
        g.line((x0, y, z), (x1, y, z), color=cor, sw=sw)
    for i in range(nx):
        for j in range(ny):
            xa, xb = x0 + (x1 - x0) * i / nx, x0 + (x1 - x0) * (i + 1) / nx
            ya, yb = y0 + (y1 - y0) * j / ny, y0 + (y1 - y0) * (j + 1) / ny
            g.line((xa, ya, z), (xb, yb, z), color=cor, sw=sw)


def malha_frente(g, x0, x1, y, z0, z1, nx=3, nz=2, cor="#FFFFFF", sw=1.3):
    for i in range(1, nx):
        x = x0 + (x1 - x0) * i / nx
        g.line((x, y, z0), (x, y, z1), color=cor, sw=sw)
    for k in range(1, nz):
        z = z0 + (z1 - z0) * k / nz
        g.line((x0, y, z), (x1, y, z), color=cor, sw=sw)
    for i in range(nx):
        for k in range(nz):
            xa, xb = x0 + (x1 - x0) * i / nx, x0 + (x1 - x0) * (i + 1) / nx
            za, zb = z0 + (z1 - z0) * k / nz, z0 + (z1 - z0) * (k + 1) / nz
            g.line((xa, y, za), (xb, y, zb), color=cor, sw=sw)


def malha_lado(g, x, y0, y1, z0, z1, ny=2, nz=2, cor="#FFFFFF", sw=1.3):
    for j in range(1, ny):
        y = y0 + (y1 - y0) * j / ny
        g.line((x, y, z0), (x, y, z1), color=cor, sw=sw)
    for k in range(1, nz):
        z = z0 + (z1 - z0) * k / nz
        g.line((x, y0, z), (x, y1, z), color=cor, sw=sw)


def bloco_malhado(g, x1=9, y1=6, z1=5, nx=3, ny=2, nz=2):
    g.box(0, x1, 0, y1, 0, z1)
    malha_topo(g, 0, x1, 0, y1, z1, nx, ny)
    malha_frente(g, 0, x1, y1, 0, z1, nx, nz)
    malha_lado(g, x1, 0, y1, 0, z1, ny, nz)


def bloco_resultado(g, x1=12, y1=4, z1=4, faixas=4):
    """Bloco pintado em faixas da escala de cores, do apoio (frio) à ponta (quente)."""
    n = faixas
    for i in range(n):
        xa, xb = x1 * i / n, x1 * (i + 1) / n
        c = MAPA[min(i, len(MAPA) - 1)]
        g.poly([(xa, y1, 0), (xb, y1, 0), (xb, y1, z1), (xa, y1, z1)], c, sw=1.0)
        g.poly([(xa, 0, z1), (xb, 0, z1), (xb, y1, z1), (xa, y1, z1)], c, sw=1.0, opacity=0.8)
    g.poly([(x1, 0, 0), (x1, y1, 0), (x1, y1, z1), (x1, 0, z1)], MAPA[-1], sw=SW)
    # contorno do bloco por cima das faixas
    g.poly([(0, y1, 0), (x1, y1, 0), (x1, y1, z1), (0, y1, z1)], "none", sw=SW)
    g.poly([(0, 0, z1), (x1, 0, z1), (x1, y1, z1), (0, y1, z1)], "none", sw=SW)


def engrenagem(g, cx, cy, r, dentes=8, cor=STEEL, furo=YEL[0]):
    pts = []
    n = dentes * 4
    for i in range(n):
        a = 2 * math.pi * i / n
        rr = r if (i % 4) in (0, 1) else r * 0.78
        pts.append((cx + rr * math.cos(a + math.pi / n), cy + rr * math.sin(a + math.pi / n)))
    g.poly2(pts, g.grad(SOLID[0], SOLID[2]), OUT, SW)
    g.circle2((cx, cy), r * 0.36, furo, OUT, SW)


def chao(g, x0, x1, y, n=5, cor=OUT):
    """Linha de apoio com hachura embaixo (2D)."""
    g.line2((x0, y), (x1, y), cor, SW_GEO * 0.9)
    passo = (x1 - x0) / n
    for i in range(n + 1):
        x = x0 + passo * i
        g.line2((x, y + 0.5), (x - passo * 0.8, y + passo * 0.9), cor, SW * 0.8)


def placa_iso(g, x0, x1, y0, y1, z):
    """Chão hachurado em isométrico, embaixo da peça."""
    g.rect3(x0, x1, y0, y1, z, BASE[1])
    passo = (x1 - x0) / 6
    for i in range(1, 6):
        x = x0 + passo * i
        g.line((x, y1, z), (x - passo, y1 + passo, z - passo * 0.9), color=OUT, sw=SW * 0.7)


def selo_play(g, where="br"):
    cx, cy = {"br": (50, 50), "tr": (50, 14)}[where]
    raw(g, '<circle cx="%d" cy="%d" r="12" fill="%s" stroke="%s" stroke-width="2"/>'
           '<path d="M %d %d l 10 6 l -10 6 z" fill="#FFFFFF" stroke="#FFFFFF" stroke-width="1.6" '
           'stroke-linejoin="round"/>' % (cx, cy, GREEN, OUT, cx - 4, cy - 6))


def selo_i(g):
    raw(g, '<circle cx="50" cy="50" r="12" fill="%s" stroke="%s" stroke-width="2"/>'
           '<circle cx="50" cy="44" r="2" fill="#FFFFFF"/><path d="M 50 49 v 8" stroke="#FFFFFF" '
           'stroke-width="3.6" stroke-linecap="round"/>' % (NAVY, OUT))


# ------------------------------------------------------------ estudo
@icon("FEM_Analysis", "FemWorkbench")
def analise():
    g = Icon()
    bloco_malhado(g)
    g.arrow3((4.5, 3, 11), (4.5, 3, 5.6), color=CARGA)
    return g


@icon("FEM_SolverCalculiXCcxTools", "FEM_SolverStandard", "FEM_SolverCalculiX", "FEM_SolverCcxTools")
def solver():
    g = Icon()
    g.fixed = (0, 0, 64, 64)
    engrenagem(g, 32, 32, 27)
    return g


@icon("FEM_SolverRun")
def calcular():
    g = Icon()
    g.fixed = (0, 0, 64, 64)
    engrenagem(g, 26, 26, 22)
    selo_play(g)
    return g


@icon("FEM_SolverControl")
def controle_solver():
    g = Icon()
    g.fixed = (0, 0, 64, 64)
    engrenagem(g, 26, 26, 22)
    g.badge("pencil")
    return g


# ------------------------------------------------------------ material e seção
def bloco_material(g):
    g.box(0, 9, 0, 6, 0, 5)
    for i in range(1, 6):
        t = i / 6.0
        g.line((9 * t, 0, 5), (0, 6 * t, 5), color=OUT, sw=1.2)
        g.line((9, 6 * t, 5), (9 * t, 6, 5), color=OUT, sw=1.2)


@icon("FEM_MaterialSolid", "FEM_MaterialCommon", "FEM_MaterialMechanicalNonlinear")
def material():
    g = Icon()
    bloco_material(g)
    return g


@icon("FEM_MaterialEditor", "Arch_Material_Group")
def editor_material():
    g = Icon()
    bloco_material(g)
    g.badge("pencil")
    return g


@icon("FEM_ElementGeometry1D", "FEM_ElementGeometry2D")
def secao():
    g = Icon()
    g.box(0, 12, 0, 4, 0, 5, pal=COPY)
    # seção caixão em destaque na ponta
    g.poly([(12, 0, 0), (12, 4, 0), (12, 4, 5), (12, 0, 5)], YEL[0])
    g.poly([(12, 0.9, 0.9), (12, 3.1, 0.9), (12, 3.1, 4.1), (12, 0.9, 4.1)], "#FFFFFF", sw=SW * 0.8)
    return g


# ------------------------------------------------------------ apoios
@icon("FEM_ConstraintFixed")
def fixacao():
    g = Icon()
    placa_iso(g, -1, 10, -1, 7, 0)
    g.box(1, 8, 1, 5, 0, 6)
    for x in (1, 8):
        for y in (1, 5):
            g.dot2(g.p(x, y, 0), 2.6, fill=APOIO)
    return g


@icon("FEM_ConstraintDisplacement")
def deslocamento():
    g = Icon()
    g.box(0, 7, 0, 5, 0, 4, pal=("none", "none", "none"), dash="3,3")
    g.box(4, 11, 0, 5, 0, 4)
    g.arrow3((0.5, 2.5, 6.5), (6, 2.5, 6.5), color=APOIO)
    return g


@icon("FEM_ConstraintSpring")
def mola():
    g = Icon()
    g.fixed = (0, 0, 64, 64)
    raw(g, '<rect x="10" y="6" width="44" height="12" rx="2" fill="%s" stroke="%s" stroke-width="2.2"/>'
        % (SOLID[1], OUT))
    zig = "M 32 18 L 32 22 L 22 26 L 42 31 L 22 36 L 42 41 L 32 45 L 32 50"
    raw(g, '<path d="%s" fill="none" stroke="%s" stroke-width="3.4" stroke-linecap="round" '
           'stroke-linejoin="round"/>' % (zig, APOIO))
    chao(g, 12, 52, 51)
    return g


# ------------------------------------------------------------ cargas
@icon("FEM_ConstraintForce")
def forca():
    g = Icon()
    g.box(0, 10, 0, 6, 0, 4)
    g.arrow3((5, 3, 12), (5, 3, 4.4), color=CARGA, sw=SW_GEO * 1.2, head=1.2)
    return g


@icon("FEM_ConstraintPressure")
def pressao():
    g = Icon()
    g.box(0, 10, 0, 6, 0, 3)
    for x in (1.8, 5, 8.2):
        g.arrow3((x, 3, 9), (x, 3, 3.4), color=CARGA, sw=SW_GEO, head=0.9)
    g.line((1.8, 3, 9), (8.2, 3, 9), color=CARGA, sw=SW_GEO)
    return g


@icon("FEM_ConstraintSelfWeight")
def peso_proprio():
    g = Icon()
    g.box(0, 8, 0, 6, 3, 8)
    g.dot2(g.p(4, 3, 5.5), 3.4, fill=YEL[0])
    g.arrow3((4, 3, 5.5), (4, 3, -2.5), color=CARGA, sw=SW_GEO * 1.1)
    a, b = g.p(4, 3, -1)
    g.text2(a + 3.2, b - 0.5, "g", 3.6, color=OUT)
    return g


@icon("FEM_ConstraintCentrif")
def centrifuga():
    g = Icon()
    g.cyl(0, 0, 5, 0, 4)
    g.line((0, 0, -2), (0, 0, 9), color=NAVY, sw=SW, dash="6,3,1,3")
    pts = [g.p(7.5 * math.cos(math.radians(a)), 7.5 * math.sin(math.radians(a)), 6.5) for a in range(-60, 210, 10)]
    g.path2(pts[:-1], color=CARGA, sw=SW_GEO)
    g.arrow2(pts[-2], pts[-1], color=CARGA)
    return g


# ------------------------------------------------------------ malha
@icon("FEM_MeshGmshFromShape", "fem-femmesh-from-shape", "FEM_MeshFromShape", "FEM_FemMesh",
      "FEM_MeshNetgenFromShape")
def malha():
    g = Icon()
    bloco_malhado(g)
    return g


@icon("FEM_MeshRegion")
def refino():
    g = Icon()
    bloco_malhado(g)
    # canto refinado em amarelo
    g.poly([(6, 0, 5), (9, 0, 5), (9, 3, 5), (6, 3, 5)], YEL[0], sw=1.6)
    for t in (7, 8):
        g.line((t, 0, 5), (t, 3, 5), color=OUT, sw=1.0)
    for t in (1, 2):
        g.line((6, t, 5), (9, t, 5), color=OUT, sw=1.0)
    return g


@icon("FEM_MeshDisplayInfo")
def info_malha():
    g = Icon()
    bloco_malhado(g)
    selo_i(g)
    return g


@icon("FEM_MeshClear")
def limpar_malha():
    g = Icon()
    bloco_malhado(g)
    g.badge("x")
    return g


# ------------------------------------------------------------ resultados
@icon("FEM_ResultShow", "FEM_ResultMechanical", "FEM_PostPipelineFromResult", "FEM_PostField")
def resultados():
    g = Icon()
    bloco_resultado(g)
    return g


@icon("FEM_ResultsPurge")
def limpar_resultados():
    g = Icon()
    bloco_resultado(g)
    g.badge("x")
    return g


@icon("FEM_PostFilterWarp")
def deformada():
    g = Icon()
    g.fixed = (0, 0, 64, 64)
    raw(g, '<rect x="6" y="16" width="52" height="9" fill="none" stroke="%s" stroke-width="2" '
           'stroke-dasharray="4,3"/>' % "#9FB1C4")
    raw(g, '<path d="M 6 16 Q 32 52 58 16 L 58 25 Q 32 61 6 25 Z" fill="%s" stroke="%s" stroke-width="2.2" '
           'stroke-linejoin="round"/>' % (SOLID[1], OUT))
    raw(g, '<path d="M 6 10 v 22 M 58 10 v 22" stroke="%s" stroke-width="3.4" stroke-linecap="round"/>' % APOIO)
    return g


@icon("FEM_PostFilterClipScalar", "FEM_PostFilterClipRegion")
def recorte_valor():
    g = Icon()
    bloco_resultado(g, x1=8, y1=6, z1=5, faixas=2)
    # parte recortada só em contorno tracejado
    g.box(8, 12, 0, 6, 0, 5, pal=("none", "none", "none"), dash="3,3")
    return g


@icon("FEM_PostFilterDataAlongLine", "FEM_PostFilterDataAtPoint", "FEM_PostLineplot")
def grafico_linha():
    g = Icon()
    g.fixed = (0, 0, 64, 64)
    raw(g, '<rect x="5" y="6" width="54" height="50" rx="3" fill="#FFFFFF" stroke="%s" stroke-width="2.2"/>' % OUT)
    raw(g, '<path d="M 13 13 V 48 H 52" fill="none" stroke="%s" stroke-width="2.2" stroke-linecap="round"/>' % OUT)
    raw(g, '<path d="M 14 44 C 22 42 26 20 34 22 S 44 38 51 18" fill="none" stroke="%s" stroke-width="3.4" '
           'stroke-linecap="round"/>' % NAVY)
    raw(g, '<circle cx="34" cy="22" r="3.4" fill="%s" stroke="%s" stroke-width="1.6"/>' % (YEL[0], OUT))
    return g


@icon("FEM_PostFilterContours")
def contornos():
    g = Icon()
    g.fixed = (0, 0, 64, 64)
    for i, (r, c) in enumerate(((26, MAPA[0]), (19, MAPA[1]), (12, MAPA[2]), (5, MAPA[3]))):
        raw(g, '<ellipse cx="32" cy="34" rx="%d" ry="%.1f" fill="%s" stroke="%s" stroke-width="1.8"/>'
            % (r, r * 0.8, c, OUT))
    return g
