# SPDX-License-Identifier: LGPL-2.1-or-later
"""Usinix: aba Componentes — modelos prontos que completam o projeto (motor, compressor, válvula, caldeira,
trole, ar comprimido, pessoas, secador e outros).

Não são peças para editar: cada componente é desenhado pelo Usinix a partir do modelo e do tamanho escolhidos
(propriedades Modelo e Tamanho; trocar o tamanho redesenha). Servem para ocupação de espaço, leiaute,
interferência e apresentação.

AS MEDIDAS SÃO REPRESENTATIVAS. Onde há tabela de norma ou catálogo (altura de eixo das carcaças IEC, furação
de flange EN 1092-1 PN 16, palete PBR) os valores foram digitados da memória e estão marcados "a checar" até
serem conferidos na fonte; o resto sai de proporções típicas. Para projeto executivo, confira no catálogo
do fabricante do equipamento escolhido.
"""
import math

import FreeCAD

# ------------------------------------------------------------------ cores (r, g, b)
CORES = {
    "maquina": (0.20, 0.42, 0.62), "verde": (0.24, 0.50, 0.33), "metal": (0.74, 0.76, 0.79),
    "escuro": (0.22, 0.24, 0.27), "amarelo": (0.97, 0.75, 0.0), "vermelho": (0.75, 0.16, 0.14),
    "branco": (0.93, 0.94, 0.95), "cinza": (0.55, 0.58, 0.62), "pele": (0.87, 0.70, 0.56),
    "roupa": (0.17, 0.30, 0.50), "calca": (0.20, 0.22, 0.28), "madeira": (0.72, 0.55, 0.34),
    "laranja": (0.93, 0.47, 0.12), "transparente": (0.80, 0.88, 0.95), "aco": (0.45, 0.47, 0.50),
    "borracha": (0.08, 0.08, 0.09),
}
# acabamento por cor: (brilho 0-1, cor do reflexo) — metal reflete, tinta brilha pouco, borracha quase nada
ACABAMENTO = {"metal": (0.55, (0.9, 0.9, 0.9)), "aco": (0.45, (0.7, 0.7, 0.7)), "transparente": (0.8, (1, 1, 1)),
              "borracha": (0.05, (0.1, 0.1, 0.1)), "madeira": (0.08, (0.2, 0.2, 0.2)), "pele": (0.15, (0.3, 0.3, 0.3)),
              "roupa": (0.05, (0.1, 0.1, 0.1)), "calca": (0.05, (0.1, 0.1, 0.1))}


# ------------------------------------------------------------------ peças básicas
def _V(x, y, z):
    return FreeCAD.Vector(x, y, z)


def caixa(dx, dy, dz, x=0, y=0, z=0, centro=True):
    """Caixa dx × dy × dz com a base em z; centrada em (x, y) quando centro=True."""
    import Part
    if centro:
        x, y = x - dx / 2.0, y - dy / 2.0
    return Part.makeBox(dx, dy, dz, _V(x, y, z))


def cilindro(r, h, base=(0, 0, 0), eixo=(0, 0, 1)):
    import Part
    return Part.makeCylinder(r, h, _V(*base), _V(*eixo))


def cone(r1, r2, h, base=(0, 0, 0), eixo=(0, 0, 1)):
    import Part
    return Part.makeCone(r1, r2, h, _V(*base), _V(*eixo))


def esfera(r, c=(0, 0, 0)):
    import Part
    return Part.makeSphere(r, _V(*c))


def toro(R, r, c=(0, 0, 0), eixo=(0, 0, 1)):
    import Part
    return Part.makeTorus(R, r, _V(*c), _V(*eixo))


# ------------------------------------------------------------------ motores
# carcaça IEC: (H altura do eixo, A entre furos de pé (largura), B entre furos (comprimento), D ponta de eixo,
# E comprimento da ponta, L comprimento total aproximado). H, A, B, D, E: IEC 60072-1, A CHECAR. L: típico.
CARCACAS_IEC = {
    "63": (63, 100, 80, 11, 23, 215), "71": (71, 112, 90, 14, 30, 245), "80": (80, 125, 100, 19, 40, 276),
    "90S": (90, 140, 100, 24, 50, 304), "90L": (90, 140, 125, 24, 50, 329), "100L": (100, 160, 140, 28, 60, 376),
    "112M": (112, 190, 140, 28, 60, 393), "132S": (132, 216, 140, 38, 80, 452),
    "132M": (132, 216, 178, 38, 80, 490), "160M": (160, 254, 210, 42, 110, 598),
    "160L": (160, 254, 254, 42, 110, 642), "180M": (180, 279, 241, 48, 110, 664),
    "180L": (180, 279, 279, 48, 110, 702), "200L": (200, 318, 305, 55, 110, 767),
    "225S/M": (225, 356, 311, 60, 140, 856), "250S/M": (250, 406, 349, 65, 140, 940),
    "280S/M": (280, 457, 419, 75, 140, 1040), "315S/M": (315, 508, 457, 80, 170, 1210),
}


def orientar(sh, base=(0, 0, 0), eixo=(0, 0, 1)):
    """Leva uma forma desenhada em volta do eixo Z (base na origem) para `base`, com o Z apontando para `eixo`."""
    sh = sh.copy()
    rot = FreeCAD.Rotation(_V(0, 0, 1), _V(*eixo))
    sh.Placement = FreeCAD.Placement(_V(*base), rot).multiply(sh.Placement)
    return sh


def revolver(perfil, base=(0, 0, 0), eixo=(0, 0, 1)):
    """Sólido de revolução: `perfil` = [(raio, altura), ...] fechado em volta do eixo Z (o primeiro e o último
    ponto sobre o eixo ou ligados por ele)."""
    import Part
    pts = [_V(r, 0, z) for r, z in perfil]
    if (pts[0] - pts[-1]).Length > 1e-9:
        pts.append(pts[0])
    face = Part.Face(Part.makePolygon(pts))
    sol = face.revolve(_V(0, 0, 0), _V(0, 0, 1), 360)
    if sol.ShapeType != "Solid":
        sol = Part.Solid(Part.Shell(sol.Faces)) if not sol.Solids else sol.Solids[0]
    return orientar(sol, base, eixo)


def arred(sh, r, arestas=None):
    """Arredonda as arestas (todas, ou as escolhidas por um filtro) — volta a forma original se não der."""
    try:
        eds = [e for e in sh.Edges if arestas is None or arestas(e)]
        if not eds:
            return sh
        novo = sh.makeFillet(r, eds)
        return novo if novo.isValid() else sh
    except Exception:
        return sh


def chanfro(sh, d, arestas=None):
    try:
        eds = [e for e in sh.Edges if arestas is None or arestas(e)]
        if not eds:
            return sh
        novo = sh.makeChamfer(d, eds)
        return novo if novo.isValid() else sh
    except Exception:
        return sh


def caixa_r(dx, dy, dz, r, x=0, y=0, z=0, centro=True):
    """Caixa com as arestas arredondadas (raio r)."""
    return arred(caixa(dx, dy, dz, x, y, z, centro), min(r, 0.45 * min(dx, dy, dz)))


def sextavado(s, h, base=(0, 0, 0), eixo=(0, 0, 1)):
    """Prisma sextavado de medida s entre faces (cabeça de parafuso, porca), chanfrado em cima."""
    import Part
    rr = s / math.sqrt(3.0)
    pts = [_V(rr * math.cos(math.radians(60 * i + 30)), rr * math.sin(math.radians(60 * i + 30)), 0)
           for i in range(6)]
    sol = Part.Face(Part.makePolygon(pts + [pts[0]])).extrude(_V(0, 0, h))
    sol = chanfro(sol, min(h * 0.25, s * 0.08), lambda e: abs(e.BoundBox.ZMin - h) < 1e-6 and e.BoundBox.ZLength < 1e-6)
    return orientar(sol, base, eixo)


def furos_em_circulo(n, R, ang0=0.0):
    return [(R * math.cos(ang0 + 2 * math.pi * i / n), R * math.sin(ang0 + 2 * math.pi * i / n)) for i in range(n)]


def tubo(r_ext, r_int, h, base=(0, 0, 0), eixo=(0, 0, 1)):
    return orientar(cilindro(r_ext, h).cut(cilindro(r_int, h)), base, eixo)


def volante(R, r_aro, base, eixo, raios=3):
    """Volante de válvula: aro, cubo e raios."""
    import Part
    partes = [toro(R, r_aro), cilindro(r_aro * 2.2, r_aro * 2.6).translated(_V(0, 0, -r_aro * 1.3))]
    for i in range(raios):
        a = 2 * math.pi * i / raios
        partes.append(cilindro(r_aro * 0.7, R, base=(0, 0, 0), eixo=(math.cos(a), math.sin(a), 0)))
    sol = partes[0]
    for p in partes[1:]:
        sol = sol.fuse(p)
    return orientar(sol.removeSplitter(), base, eixo)


def tampo(r, h, base, eixo):
    """Tampo semielíptico liso (meia esfera achatada), boca no plano da base e convexo para `eixo`."""
    import Part
    meia = esfera(r).common(Part.makeBox(2 * r, 2 * r, r, _V(-r, -r, 0)))
    m = FreeCAD.Matrix()
    m.scale(1, 1, h / r)
    meia = meia.transformGeometry(m)
    rot = FreeCAD.Rotation(_V(0, 0, 1), _V(*eixo))
    meia.Placement = FreeCAD.Placement(_V(*base), rot)
    return meia


def motor_partes(H, A, B, D, E, L, cor="maquina", com_pes=True, z_eixo=None):
    """Motor de carcaça aletada: eixo em X, ponta de eixo para -X. H = altura de eixo da carcaça (dá o tamanho);
    o eixo fica na altura H (com pés, apoiado em z = 0) ou em `z_eixo` (sem pés, para montar em outro conjunto)."""
    rc = H * 0.82                      # raio da carcaça sem as aletas
    H, Hc = (H if z_eixo is None else z_eixo), H
    lc = L - E                         # carcaça + tampa do ventilador
    partes = []
    x0 = 0.0
    # tampa dianteira (com mancal) e traseira, carcaça
    tampa_d = revolver([(0, 0), (rc * 0.98, 0), (rc * 0.98, lc * 0.05), (rc * 0.55, lc * 0.09),
                        (rc * 0.42, lc * 0.09), (rc * 0.42, lc * 0.11), (0, lc * 0.11)][::-1],
                       base=(x0 + lc * 0.11, 0, H), eixo=(-1, 0, 0))
    partes.append((tampa_d, cor))
    carc = cilindro(rc, lc * 0.68, base=(x0 + lc * 0.10, 0, H), eixo=(1, 0, 0))
    partes.append((carc, cor))
    # aletas longitudinais em volta (menos embaixo, onde estão os pés)
    n = 24
    for i in range(n):
        a = 2 * math.pi * i / n
        if com_pes and abs(math.sin(a) + 1) < 0.25:
            continue
        al = caixa(lc * 0.62, rc * 0.035, rc * 0.16, x=lc * 0.43, z=0, centro=True)
        m = _rot_x(a, H, rc * 0.96)
        partes.append((al.transformGeometry(m), cor))
    # tampa do ventilador: chapa estampada com anéis
    xt = x0 + lc * 0.78
    tv = revolver([(0, 0), (rc * 1.02, 0), (rc * 1.02, lc * 0.17), (rc * 0.8, lc * 0.21), (0, lc * 0.21)],
                  base=(xt, 0, H), eixo=(1, 0, 0))
    for k in range(3):
        tv = tv.cut(toro(rc * (0.25 + 0.2 * k), rc * 0.03, c=(xt + lc * 0.21, 0, H), eixo=(1, 0, 0)))
    partes.append((tv, "escuro"))
    # ponta de eixo com rasgo de chaveta
    eixo = cilindro(D / 2.0, E + lc * 0.02, base=(x0 - E, 0, H), eixo=(1, 0, 0))
    eixo = chanfro(eixo, D * 0.06, lambda e: abs(e.BoundBox.XMin - (x0 - E)) < 1e-6 and e.BoundBox.XLength < 1e-6)
    ch = caixa(E * 0.8, D * 0.28, D * 0.2, x=x0 - E * 0.5, z=H + D * 0.4)
    eixo = eixo.cut(ch)
    partes.append((eixo, "metal"))
    partes.append((caixa(E * 0.7, D * 0.26, D * 0.16, x=x0 - E * 0.5, z=H + D * 0.4), "aco"))
    if com_pes:
        # pés com furos para os chumbadores
        pes = Hc * 0.14
        for s in (-1, 1):
            pe = caixa_r(B + 0.45 * Hc, 0.22 * Hc, pes, pes * 0.3, x=lc * 0.45, y=s * A / 2.0, z=0)
            for xx in (lc * 0.45 - B / 2.0, lc * 0.45 + B / 2.0):
                pe = pe.cut(cilindro(Hc * 0.05, pes + 2, base=(xx, s * A / 2.0, -1)))
            partes.append((pe, cor))
        # sapata fundida: une os pés à carcaça
        sap = caixa(lc * 0.52, A + 0.1 * Hc, H - pes, x=lc * 0.45, z=pes * 0.5)
        sap = sap.cut(cilindro(rc * 0.999, lc, base=(0, 0, H), eixo=(1, 0, 0)))
        sap = sap.cut(caixa(lc * 0.6, A - 0.3 * Hc, H * 0.5, x=lc * 0.45, z=-1))
        partes.append((sap, cor))
    # caixa de ligação com tampa aparafusada e prensa-cabo
    cl = rc * 0.75
    zt = H + rc * 0.96
    partes.append((caixa_r(cl, cl, cl * 0.5, cl * 0.08, x=lc * 0.42, z=zt), cor))
    partes.append((caixa_r(cl * 1.06, cl * 1.06, cl * 0.1, cl * 0.05, x=lc * 0.42, z=zt + cl * 0.5), cor))
    for (dx, dy) in ((-1, -1), (-1, 1), (1, -1), (1, 1)):
        partes.append((cilindro(cl * 0.05, cl * 0.04, base=(lc * 0.42 + dx * cl * 0.42, dy * cl * 0.42,
                                                              zt + cl * 0.6)), "metal"))
    partes.append((sextavado(cl * 0.22, cl * 0.12, base=(lc * 0.42, cl * 0.53, zt + cl * 0.25), eixo=(0, 1, 0)),
                   "escuro"))
    partes.append((cilindro(cl * 0.08, cl * 0.2, base=(lc * 0.42, cl * 0.65, zt + cl * 0.25), eixo=(0, 1, 0)),
                   "escuro"))
    # olhal de içamento e placa de identificação
    partes.append((toro(rc * 0.11, rc * 0.03, c=(lc * 0.2, 0, H + rc * 1.12), eixo=(0, 1, 0)), "metal"))
    partes.append((cilindro(rc * 0.05, rc * 0.08, base=(lc * 0.2, 0, H + rc * 0.96)), "metal"))
    partes.append((caixa(lc * 0.18, rc * 0.01, rc * 0.28, x=lc * 0.62, y=-rc - rc * 0.005, z=H - rc * 0.14),
                   "metal"))
    return partes


def motor(tam):
    H, A, B, D, E, L = CARCACAS_IEC[tam]
    partes = motor_partes(H, A, B, D, E, L)
    return partes, {"Carcaça (IEC)": tam, "Altura do eixo H": "%d mm (a checar)" % H,
                    "Ponta de eixo D × E": "%d × %d mm (a checar)" % (D, E), "Comprimento aprox.": "%d mm" % L}


def _rot_x(ang, zc, r):
    """Matriz que leva uma aleta deitada (no chão) para o ângulo `ang` em volta do eixo X na altura zc."""
    m = FreeCAD.Matrix()
    m.move(_V(0, 0, r))
    m2 = FreeCAD.Matrix()
    m2.rotateX(ang)
    m3 = FreeCAD.Matrix()
    m3.move(_V(0, 0, zc))
    return m3.multiply(m2.multiply(m))


def _manometro(r, base, eixo_saida):
    """Manômetro: caixa redonda com visor e conexão."""
    bx, by, bz = base
    ex, ey, ez = eixo_saida
    return [(cilindro(r * 0.18, r * 0.9, base=base, eixo=eixo_saida), "metal"),
            (cilindro(r, r * 0.45, base=(bx + ex * r * 0.9, by + ey * r * 0.9, bz + ez * r * 0.9 + r),
                      eixo=(0, -1, 0) if abs(ey) < 0.5 else (1, 0, 0)), "escuro"),
            (cilindro(r * 0.86, r * 0.02, base=(bx + ex * r * 0.9, by + ey * r * 0.9 - r * 0.02,
                                                  bz + ez * r * 0.9 + r),
                      eixo=(0, -1, 0) if abs(ey) < 0.5 else (1, 0, 0)), "branco")]


# ------------------------------------------------------------------ compressores
def compressor_pistao(volume_l):
    v = float(volume_l) * 1e6                      # mm³
    D = (4 * v / (3 * math.pi)) ** (1 / 3.0)       # tanque com L/D = 3 (típico)
    Lt = 3 * D
    r = D / 2.0
    zc = r + D * 0.25
    partes = [(cilindro(r, Lt, base=(-Lt / 2, 0, zc), eixo=(1, 0, 0)), "vermelho"),
              (tampo(r, r * 0.5, (Lt / 2, 0, zc), (1, 0, 0)), "vermelho"),
              (tampo(r, r * 0.5, (-Lt / 2, 0, zc), (-1, 0, 0)), "vermelho")]
    # cordões de solda das emendas
    for x in (-Lt / 2, Lt / 2):
        partes.append((toro(r, D * 0.006, c=(x, 0, zc), eixo=(1, 0, 0)), "vermelho"))
    # pés em sela e rodas
    for x in (-Lt * 0.33, Lt * 0.33):
        sela = caixa(D * 0.1, D * 0.8, zc, x=x, z=0).cut(cilindro(r * 1.001, D * 0.2, base=(x - D * 0.1, 0, zc),
                                                                eixo=(1, 0, 0)))
        partes.append((sela, "escuro"))
    for s in (-1, 1):
        partes.append((revolver([(0, 0), (D * 0.11, 0), (D * 0.11, D * 0.05), (0, D * 0.05)],
                                base=(-Lt * 0.33, s * D * 0.42, D * 0.11), eixo=(0, s, 0)), "escuro"))
    partes.append((caixa_r(D * 0.12, D * 0.12, D * 0.12, D * 0.02, x=Lt * 0.33, z=0), "borracha"))
    # dreno
    partes.append((cilindro(D * 0.02, D * 0.12, base=(0, 0, zc - r - D * 0.1)), "metal"))
    # plataforma, unidade compressora (bloco + 2 cilindros aletados), motor e protetor de correia
    zt = zc + r
    partes.append((caixa_r(Lt * 0.55, D * 0.75, D * 0.035, D * 0.01, x=0, z=zt), "escuro"))
    zp = zt + D * 0.035
    xb = -Lt * 0.1
    partes.append((caixa_r(D * 0.42, D * 0.36, D * 0.26, D * 0.03, x=xb, z=zp), "escuro"))
    for dy in (-D * 0.09, D * 0.09):
        zb = zp + D * 0.26
        partes.append((cilindro(D * 0.06, D * 0.3, base=(xb, dy, zb)), "cinza"))
        for k in range(7):
            partes.append((cilindro(D * 0.095, D * 0.012, base=(xb, dy, zb + D * 0.02 + k * D * 0.035)), "cinza"))
        partes.append((caixa_r(D * 0.2, D * 0.17, D * 0.06, D * 0.015, x=xb, y=dy, z=zb + D * 0.3), "escuro"))
    # motor (carcaça aletada, sem pés: preso na plataforma)
    k = D / 450.0
    mp = motor_partes(90 * k, 0, 0, 24 * k + 8, 40 * k, 330 * k + 60, cor="maquina", com_pes=False, z_eixo=0)
    for forma, cor in mp:
        forma = forma.copy()
        forma.translate(_V(Lt * 0.1, 0, zp + D * 0.2))
        partes.append((forma, cor))
    # protetor da correia
    partes.append((caixa_r(D * 0.65, D * 0.05, D * 0.42, D * 0.04, x=xb + D * 0.2, y=-D * 0.33,
                           z=zp + D * 0.02), "amarelo"))
    # pressostato, manômetro e válvula de segurança
    partes.append((caixa_r(D * 0.14, D * 0.1, D * 0.12, D * 0.015, x=Lt * 0.22, z=zt + D * 0.035), "cinza"))
    partes += _manometro(D * 0.05, (Lt * 0.3, D * 0.1, zt + D * 0.03), (0, 0, 1))
    partes.append((cilindro(D * 0.018, D * 0.12, base=(Lt * 0.36, -D * 0.1, zt)), "metal"))
    partes.append((toro(D * 0.02, D * 0.005, c=(Lt * 0.36, -D * 0.1, zt + D * 0.14), eixo=(0, 1, 0)), "metal"))
    return partes, {"Reservatório": "%s L" % volume_l, "Diâmetro × comprimento": "%.0f × %.0f mm" % (D, Lt * 1.33),
                    "Medidas": "representativas (L/D = 3)"}


# compressor de parafuso: potência kW -> (comprimento, largura, altura) típicos de gabinete
PARAFUSO_KW = {"7,5": (900, 650, 950), "11": (1000, 700, 1050), "15": (1100, 750, 1150),
               "22": (1300, 850, 1300), "37": (1550, 950, 1500), "55": (1850, 1100, 1650),
               "75": (2100, 1200, 1800)}


def _veneziana(c, a, n, x, y, z, lado):
    """Grade de aletas inclinadas numa face lateral (lado = +1/-1 em Y)."""
    res = []
    for i in range(n):
        al = caixa(c, a * 0.012, a * 0.03, x=x, y=y + lado * a * 0.004, z=z + i * a * 0.045)
        m = FreeCAD.Matrix()
        m.move(_V(-x, -y, -(z + i * a * 0.045)))
        m2 = FreeCAD.Matrix()
        m2.rotateX(math.radians(35 * lado))
        m3 = FreeCAD.Matrix()
        m3.move(_V(x, y, z + i * a * 0.045))
        res.append((al.transformGeometry(m3.multiply(m2.multiply(m))), "escuro"))
    return res


def compressor_parafuso(kw):
    c, l, a = PARAFUSO_KW[kw]
    partes = [(caixa_r(c, l, a * 0.05, a * 0.01, z=0), "escuro")]
    gab = caixa_r(c, l, a * 0.95, a * 0.02, z=a * 0.05)
    # juntas dos painéis removíveis (frisos)
    for x in (-c * 0.17, c * 0.17):
        gab = gab.cut(caixa(c * 0.006, l + 2, a * 0.85, x=x, z=a * 0.1))
    gab = gab.cut(caixa(c + 2, l + 2, a * 0.006, z=a * 0.55))
    partes.append((gab, "branco"))
    # grade de entrada de ar nas duas laterais e saída no teto
    for s in (-1, 1):
        y = s * (l / 2.0 + a * 0.004)
        partes += _veneziana(c * 0.28, a, 9, -c * 0.32, y, a * 0.15, s)
    partes.append((caixa_r(c * 0.42, l * 0.55, a * 0.02, a * 0.006, x=c * 0.18, z=a), "escuro"))
    for k in range(7):
        partes.append((caixa(c * 0.4, l * 0.012, a * 0.025, x=c * 0.18, y=-l * 0.24 + k * l * 0.08, z=a + a * 0.01),
                       "cinza"))
    # painel de comando com tela, botão de emergência e logotipo
    yp = l / 2.0
    partes.append((caixa_r(c * 0.2, l * 0.02, a * 0.16, a * 0.01, x=c * 0.3, y=yp, z=a * 0.68), "escuro"))
    partes.append((caixa(c * 0.12, l * 0.006, a * 0.07, x=c * 0.28, y=yp + l * 0.012, z=a * 0.72), "transparente"))
    partes.append((cilindro(a * 0.018, l * 0.03, base=(c * 0.37, yp, a * 0.75), eixo=(0, 1, 0)), "vermelho"))
    partes.append((cilindro(a * 0.025, l * 0.01, base=(c * 0.37, yp, a * 0.75), eixo=(0, 1, 0)), "amarelo"))
    # saída de ar comprimido com flange
    partes.append((cilindro(a * 0.03, c * 0.06, base=(c / 2.0, -l * 0.3, a * 0.2), eixo=(1, 0, 0)), "metal"))
    partes.append((cilindro(a * 0.055, a * 0.015, base=(c / 2.0 + c * 0.05, -l * 0.3, a * 0.2), eixo=(1, 0, 0)),
                   "metal"))
    return partes, {"Potência": "%s kW" % kw, "Gabinete C × L × A": "%d × %d × %d mm" % (c, l, a),
                    "Medidas": "representativas"}


# ------------------------------------------------------------------ válvulas
# DN -> diâmetro externo do flange EN 1092-1 PN 16 (A CHECAR)
FLANGE_PN16 = {15: 95, 20: 105, 25: 115, 32: 140, 40: 150, 50: 165, 65: 185, 80: 200, 100: 220, 125: 250,
               150: 285, 200: 340, 250: 405, 300: 460}
DNS = sorted(FLANGE_PN16)


def _flanges(dn, face, eixo_x=True):
    """Flanges de face com ressalto e a furação com porcas; corpo em volta do eixo X."""
    Df = FLANGE_PN16[dn]
    e = max(14.0, 0.08 * Df)
    nf = 4 if dn <= 50 else (8 if dn <= 150 else 12)
    pcd = Df * 0.78
    df = max(12.0, Df * 0.07)
    partes = []
    for lado, x in ((-1, -face / 2.0), (1, face / 2.0 - e)):
        fl = cilindro(Df / 2.0, e, base=(x, 0, 0), eixo=(1, 0, 0))
        fl = arred(fl, e * 0.15, lambda ed: ed.BoundBox.YLength > Df * 0.9)
        for (yy, zz) in furos_em_circulo(nf, pcd / 2.0, math.pi / nf):
            fl = fl.cut(cilindro(df / 2.0, e + 2, base=(x - 1, yy, zz), eixo=(1, 0, 0)))
        fl = fl.cut(cilindro(dn / 2.0, e + 2, base=(x - 1, 0, 0), eixo=(1, 0, 0)))
        partes.append((fl, "escuro"))
        # ressalto da face, com a passagem
        xr = -face / 2.0 - 2 if lado < 0 else face / 2.0
        partes.append((tubo(Df * 0.36, dn / 2.0, 2, base=(xr, 0, 0), eixo=(1, 0, 0)), "metal"))
        # porcas do lado de dentro (parafusos passantes)
        xi = x + e if lado < 0 else x - df * 0.8
        for (yy, zz) in furos_em_circulo(nf, pcd / 2.0, math.pi / nf):
            partes.append((sextavado(df * 1.5, df * 0.8, base=(xi, yy, zz), eixo=(1, 0, 0)), "metal"))
    return partes, Df, e


def valvula(tipo, dn):
    dn = int(dn)
    face = {"esfera": 1.1, "gaveta": 1.25, "globo": 1.45, "retencao": 1.4, "borboleta": 0.35}[tipo] * dn + \
        {"esfera": 100, "gaveta": 120, "globo": 120, "retencao": 110, "borboleta": 30}[tipo]
    partes = []
    if tipo == "borboleta":
        Df = FLANGE_PN16[dn]
        corpo = tubo(Df * 0.42, dn / 2.0, face, base=(-face / 2, 0, 0), eixo=(1, 0, 0))
        corpo = arred(corpo, face * 0.08, lambda ed: ed.BoundBox.YLength > Df * 0.8)
        partes.append((corpo, "escuro"))
        # disco visto pela boca
        partes.append((cilindro(dn / 2.0 - 1, face * 0.25, base=(-face * 0.125, 0, 0), eixo=(1, 0, 0)), "metal"))
        # pescoço, caixa e alavanca dentada
        partes.append((cilindro(dn * 0.08 + 10, Df * 0.25, base=(0, 0, Df * 0.4)), "escuro"))
        partes.append((caixa_r(face * 1.2, face * 1.2, 12, 3, z=Df * 0.65), "escuro"))
        partes.append((cilindro(dn * 0.04 + 6, Df * 0.12, base=(0, 0, Df * 0.65)), "metal"))
        partes.append((caixa_r(Df * 0.55, 22, 14, 5, x=Df * 0.2, z=Df * 0.75), "vermelho"))
        return partes, {"DN": dn, "Entre faces": "%.0f mm (representativa)" % face}
    fl, Df, e = _flanges(dn, face)
    partes += fl
    rc = Df * 0.38
    pesc = face - 2 * e
    if tipo == "esfera":
        corpo = revolver([(0, -pesc / 2), (rc * 0.72, -pesc / 2), (rc * 1.05, -pesc * 0.25), (rc * 1.05, pesc * 0.25),
                          (rc * 0.72, pesc / 2), (0, pesc / 2)], eixo=(1, 0, 0))
        partes.append((corpo, "escuro"))
        # costura do corpo bipartido com parafusos
        partes.append((cilindro(rc * 1.12, pesc * 0.06, base=(pesc * 0.08, 0, 0), eixo=(1, 0, 0)), "escuro"))
        for (yy, zz) in furos_em_circulo(6, rc * 0.95):
            partes.append((sextavado(rc * 0.16, rc * 0.08, base=(pesc * 0.14, yy, zz), eixo=(1, 0, 0)), "metal"))
        # haste, gaxeta e alavanca com punho plástico
        partes.append((cilindro(rc * 0.28, rc * 0.35, base=(0, 0, rc * 0.85)), "escuro"))
        partes.append((cilindro(dn * 0.06 + 6, rc * 0.45, base=(0, 0, rc * 1.1)), "metal"))
        partes.append((sextavado(dn * 0.12 + 14, rc * 0.1, base=(0, 0, rc * 1.45)), "metal"))
        partes.append((caixa_r(Df * 1.15, 24, 10, 4, x=Df * 0.45, z=rc * 1.42), "metal"))
        partes.append((caixa_r(Df * 0.55, 30, 18, 8, x=Df * 0.75, z=rc * 1.38), "vermelho"))
    else:
        pesc_c = revolver([(0, 0), (rc * 0.8, 0), (rc, pesc * 0.12), (rc, pesc * 0.88), (rc * 0.8, pesc), (0, pesc)],
                          base=(-pesc / 2, 0, 0), eixo=(1, 0, 0))
        partes.append((pesc_c, "escuro"))
        if tipo in ("gaveta", "globo"):
            if tipo == "globo":
                corpo = esfera(rc * 1.25)
            else:
                corpo = caixa_r(rc * 1.2, rc * 1.25, rc * 1.4, rc * 0.25, z=-rc * 0.7)
            partes.append((corpo, "escuro"))
            hb = Df * (1.1 if tipo == "gaveta" else 0.8)
            zf = rc * (0.7 if tipo == "gaveta" else 1.0)
            # flange do castelo com parafusos
            partes.append((cilindro(rc * 0.95, rc * 0.18, base=(0, 0, zf)), "escuro"))
            for (xx, yy) in furos_em_circulo(6, rc * 0.78):
                partes.append((sextavado(rc * 0.16, rc * 0.1, base=(xx, yy, zf + rc * 0.18)), "metal"))
            # castelo cônico, sobreposta da gaxeta, haste e volante
            partes.append((cone(rc * 0.6, rc * 0.32, hb * 0.5, base=(0, 0, zf + rc * 0.18)), "escuro"))
            zs = zf + rc * 0.18 + hb * 0.5
            partes.append((caixa_r(rc * 0.9, rc * 0.35, rc * 0.15, rc * 0.05, z=zs), "escuro"))
            partes.append((cilindro(dn * 0.05 + 6, hb * 0.55, base=(0, 0, zs)), "metal"))
            partes.append((volante(Df * 0.35, 6 + dn * 0.02, (0, 0, zs + hb * 0.5), (0, 0, 1)), "vermelho"))
            partes.append((sextavado(dn * 0.1 + 12, rc * 0.12, base=(0, 0, zs + hb * 0.52)), "metal"))
        else:   # retenção: tampa aparafusada em cima, sem volante
            partes.append((caixa_r(rc * 1.4, rc * 1.25, rc * 0.95, rc * 0.2, z=-rc * 0.3), "escuro"))
            partes.append((cilindro(rc * 0.8, rc * 0.18, base=(0, 0, rc * 0.62)), "escuro"))
            for (xx, yy) in furos_em_circulo(6, rc * 0.66):
                partes.append((sextavado(rc * 0.14, rc * 0.09, base=(xx, yy, rc * 0.8)), "metal"))
            # seta do sentido do fluxo
            partes.append((caixa(rc * 0.6, 3, rc * 0.08, x=-rc * 0.1, y=-rc * 0.62, z=0), "branco"))
            partes.append((cone(rc * 0.12, 0.01, rc * 0.2, base=(rc * 0.2, -rc * 0.635, rc * 0.04), eixo=(1, 0, 0)),
                           "branco"))
    # passagem do fluido aberta nas duas pontas (o obturador fica no meio)
    furo = cilindro(dn / 2.0, face * 0.32, base=(-face / 2.0 - 3, 0, 0), eixo=(1, 0, 0)).fuse(
        cilindro(dn / 2.0, face * 0.32, base=(face / 2.0 + 3, 0, 0), eixo=(-1, 0, 0)))
    novas = []
    for forma, cor in partes:
        if forma.BoundBox.intersect(furo.BoundBox) and forma.common(furo).Volume > 1e-6:
            cortada = forma.cut(furo)
            if cortada.isValid() and cortada.Solids:
                forma = cortada
        novas.append((forma, cor))
    partes = novas
    return partes, {"DN": dn, "Flange": "PN 16, Ø %d mm (EN 1092-1, a checar)" % Df,
                    "Entre faces": "%.0f mm (representativa)" % face}


# ------------------------------------------------------------------ caldeiras
# (diâmetro do corpo, comprimento do corpo) típicos de flamotubular horizontal de 3 passes; com berços, válvulas e
# queimador a de 2 000 kg/h fica com cerca de 3 m de altura e 5,5 m de comprimento total (1.15.0: antes saía
# pequena demais). Representativos: confira no fabricante.
CALDEIRA_KGH = {"500": (1500, 3400), "1000": (1800, 4000), "2000": (2200, 4600), "4000": (2600, 5600),
                "6000": (2900, 6400), "10000": (3300, 7600)}


def caldeira(kgh):
    D, L = CALDEIRA_KGH[kgh]
    r = D / 2.0
    zc = r + D * 0.18
    partes = [(cilindro(r, L, base=(-L / 2, 0, zc), eixo=(1, 0, 0)), "branco")]
    # cintas do isolamento térmico
    for i in range(1, 6):
        x = -L / 2 + L * i / 6.0
        partes.append((toro(r, D * 0.006, c=(x, 0, zc), eixo=(1, 0, 0)), "metal"))
    # berços em sela e skid
    for x in (-L * 0.36, L * 0.36):
        sela = caixa(D * 0.15, D * 0.85, zc, x=x, z=0).cut(cilindro(r * 1.001, D * 0.2, base=(x - D * 0.1, 0, zc),
                                                                  eixo=(1, 0, 0)))
        partes.append((sela, "escuro"))
    for s in (-1, 1):
        partes.append((caixa(L * 1.05, D * 0.1, D * 0.06, y=s * D * 0.42, z=0), "escuro"))
    # porta frontal com dobradiças e parafusos, queimador com ventilador
    xf = -L / 2
    partes.append((cilindro(r * 0.97, D * 0.1, base=(xf - D * 0.1, 0, zc), eixo=(1, 0, 0)), "cinza"))
    for (yy, zz) in furos_em_circulo(16, r * 0.9):
        partes.append((sextavado(D * 0.03, D * 0.02, base=(xf - D * 0.1, yy, zc + zz), eixo=(-1, 0, 0)), "metal"))
    for zz in (zc - r * 0.5, zc + r * 0.5):
        partes.append((cilindro(D * 0.025, D * 0.12, base=(xf - D * 0.08, r * 0.98, zz - D * 0.06)), "escuro"))
    xq = xf - D * 0.1
    partes.append((cilindro(D * 0.13, D * 0.15, base=(xq, 0, zc - D * 0.05), eixo=(-1, 0, 0)), "cinza"))
    partes.append((caixa_r(D * 0.32, D * 0.36, D * 0.4, D * 0.04, x=xq - D * 0.31, z=zc - D * 0.25), "vermelho"))
    mq = motor_partes(D * 0.06, 0, 0, 20, 30, D * 0.25, cor="vermelho", com_pes=False, z_eixo=0)
    for forma, cor in mq:
        forma = forma.copy()
        forma.rotate(_V(0, 0, 0), _V(0, 0, 1), 90)
        forma.translate(_V(xq - D * 0.31, D * 0.18, zc - D * 0.12))
        partes.append((forma, cor))
    # câmara traseira e saída dos gases com flange (a chaminé segue à parte, até acima do telhado)
    partes.append((cilindro(r * 0.95, D * 0.1, base=(L / 2, 0, zc), eixo=(1, 0, 0)), "cinza"))
    xc = L / 2 - D * 0.3
    zch = zc + r * 0.9
    partes.append((cilindro(D * 0.14, D * 0.32, base=(xc, 0, zch)), "escuro"))
    fl = cilindro(D * 0.2, D * 0.03, base=(xc, 0, zch + D * 0.32))
    for (xx, yy) in furos_em_circulo(8, D * 0.17):
        fl = fl.cut(cilindro(D * 0.01, D * 0.05, base=(xc + xx, yy, zch + D * 0.31)))
    partes.append((fl, "escuro"))
    # boca de visita, válvulas de segurança com alavanca, tomada de vapor com flange
    partes.append((caixa_r(D * 0.26, D * 0.2, D * 0.06, D * 0.03, x=-L * 0.25, z=zc + r * 0.97), "cinza"))
    for x in (-L * 0.08, L * 0.02):
        partes.append((cilindro(D * 0.035, D * 0.16, base=(x, 0, zc + r * 0.97)), "metal"))
        partes.append((cilindro(D * 0.05, D * 0.02, base=(x, 0, zc + r * 0.97 + D * 0.16)), "metal"))
        partes.append((caixa(D * 0.16, D * 0.012, D * 0.012, x=x + D * 0.06, z=zc + r * 0.97 + D * 0.2), "metal"))
    partes.append((cilindro(D * 0.05, D * 0.2, base=(L * 0.18, 0, zc + r * 0.97)), "escuro"))
    partes.append((cilindro(D * 0.085, D * 0.025, base=(L * 0.18, 0, zc + r * 0.97 + D * 0.2)), "escuro"))
    # indicador de nível (visor entre duas válvulas) e manômetro
    yv = r * 0.82
    partes.append((cilindro(D * 0.02, D * 0.3, base=(-L / 2 + D * 0.1, yv, zc - D * 0.1)), "transparente"))
    for zz in (zc - D * 0.13, zc + D * 0.2):
        partes.append((caixa_r(D * 0.06, D * 0.06, D * 0.04, D * 0.01, x=-L / 2 + D * 0.1, y=yv, z=zz), "metal"))
    partes += _manometro(D * 0.06, (-L / 2 + D * 0.3, 0, zc + r * 0.97), (0, 0, 1))
    return partes, {"Produção de vapor": "%s kg/h" % kgh, "Corpo Ø × comprimento": "%d × %d mm" % (D, L),
                    "Medidas": "representativas (flamotubular horizontal)"}


# ------------------------------------------------------------------ trole (trabalho em altura)
TROLE = {"aba até 150 mm": 150, "aba até 220 mm": 220, "aba até 300 mm": 300}


def _casco(pts):
    """Envoltória convexa de pontos (x, z) — cadeia monótona."""
    pts = sorted(set(pts))
    def cruz(o, a, b):
        return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])
    baixo, cima = [], []
    for p in pts:
        while len(baixo) >= 2 and cruz(baixo[-2], baixo[-1], p) <= 0:
            baixo.pop()
        baixo.append(p)
    for p in reversed(pts):
        while len(cima) >= 2 and cruz(cima[-2], cima[-1], p) <= 0:
            cima.pop()
        cima.append(p)
    return baixo[:-1] + cima[:-1]


def trole(faixa):
    """Trole manual de ancoragem para viga I, no formato do trole de 0,5 t de catálogo (cerca de 200 × 190 mm):
    duas placas em escudo dobradas para dentro embaixo, quatro rodas com aba sobre a aba de baixo da viga (topo da
    aba em z = 0, alma em y = 0), eixo de ajuste com porca e arruela, rebites e o olhal de carga entre as placas."""
    import Part
    bf = TROLE[faixa]
    R, Lr = 30.0, 20.0                       # roda: raio de rolamento e largura
    xr = 64.0                                # entre rodas = 2·xr
    yr = bf / 2.0 - 13                       # roda sobre a aba, perto da borda
    yp = bf / 2.0 + 13                       # placa por fora da borda da aba
    yi = 13.0                                # placa embaixo, encostada no espaçador do olhal
    zb1, zb2 = -32.0, -78.0                  # dobra: começa abaixo da aba e termina perto do olhal
    t = 8.0
    # contorno do escudo: envoltória de um círculo em cada roda e um embaixo
    pts = []
    for cx, cz, rr in ((-xr, R, 36.0), (xr, R, 36.0), (0.0, -128.0, 24.0)):
        for i in range(48):
            a = 2 * math.pi * i / 48
            pts.append((round(cx + rr * math.cos(a), 4), round(cz + rr * math.sin(a), 4)))
    cont = _casco(pts)
    w = Part.makePolygon([_V(x, 0, z) for x, z in cont] + [_V(cont[0][0], 0, cont[0][1])])
    face = Part.Face(w)

    def faixa_z(z0, z1):
        return face.common(Part.makeBox(400, 1, z1 - z0, _V(-200, -0.5, z0))).Faces[0]

    furos = [(-xr, R, 9.0), (xr, R, 9.0), (0.0, -128.0, 11.0), (0.0, -50.0, 12.0)]
    partes = []
    for s in (-1, 1):
        cima = faixa_z(zb1, 200).extrude(_V(0, t, 0))
        cima.translate(_V(0, s * yp - t / 2.0, 0))
        meio = faixa_z(zb2, zb1).extrude(_V(0, t, 0))
        meio.translate(_V(0, -t / 2.0, 0))
        m = FreeCAD.Matrix()
        m.A23 = s * (yp - yi) / (zb1 - zb2)
        m.A24 = s * yi - m.A23 * zb2
        meio = meio.transformGeometry(m)
        baixo = faixa_z(-200, zb2).extrude(_V(0, t, 0))
        baixo.translate(_V(0, s * yi - t / 2.0, 0))
        placa = cima.fuse(meio).fuse(baixo).removeSplitter()
        for (x, z, r) in furos:
            placa = placa.cut(cilindro(r, 400, base=(x, -200, z), eixo=(0, 1, 0)))
        partes.append((placa, "amarelo"))

        def y_em(z):
            if z >= zb1:
                return s * yp
            if z <= zb2:
                return s * yi
            return s * (yi + (yp - yi) * (z - zb2) / (zb1 - zb2))
        # rebites (cabeça abaulada) como na foto: dois no meio da placa e um embaixo
        for (x, z) in ((-38, -10), (38, -10), (0, -105)):
            yy = y_em(z) + s * t / 2.0
            partes.append((esfera(6, c=(x, yy, z)).common(caixa(14, 7, 14, x=x, y=yy + s * 3.5, z=z - 7)), "metal"))
        # rodas com aba (aba por dentro, contra a borda da aba da viga), eixo e porca por fora
        for x in (-xr, xr):
            roda = revolver([(8, 0), (R, 0), (R, Lr - 5), (R + 6, Lr - 3), (R + 6, Lr), (8, Lr)],
                            base=(x, s * (yr + Lr / 2.0), R), eixo=(0, -s, 0))
            roda = arred(roda, 1.5, lambda e: e.BoundBox.YLength < 1e-6 and e.BoundBox.XLength > R)
            partes.append((roda, "escuro"))
            partes.append((tubo(R - 2, R - 9, 2, base=(x, s * (yr - Lr / 2.0) - s * 0.5, R), eixo=(0, -s, 0)),
                           "metal"))
            partes.append((cilindro(8, yp - yr + Lr / 2.0 + t, base=(x, s * (yr - Lr / 2.0), R), eixo=(0, s, 0)),
                           "aco"))
            partes.append((esfera(9, c=(x, s * (yp + t / 2.0), R)).common(
                caixa(20, 9, 20, x=x, y=s * (yp + t / 2.0 + 4.5), z=R - 10)), "metal"))
    # eixo de ajuste da largura: parafuso passante com cabeça, arruelas e porca, espaçadores
    yb = yi + (yp - yi) * (-50 - zb2) / (zb1 - zb2) + t / 2.0
    partes.append((cilindro(11, 2 * yb + 30, base=(0, -yb - 15, -50), eixo=(0, 1, 0)), "aco"))
    for s in (-1, 1):
        partes.append((cilindro(16, 3, base=(0, s * yb, -50), eixo=(0, s, 0)), "metal"))
        partes.append((sextavado(19, 11, base=(0, s * (yb + 3), -50), eixo=(0, s, 0)), "metal"))
    partes.append((tubo(17, 11.5, 2 * (yb - t) - 2, base=(0, -(yb - t) + 1, -50), eixo=(0, 1, 0)), "escuro"))
    # olhal de carga entre as placas (pino de baixo) — o ponto onde engata o conector
    partes.append((cilindro(10.5, 2 * yi + t + 8, base=(0, -yi - t / 2.0 - 4, -128), eixo=(0, 1, 0)), "aco"))
    olhal = toro(24, 8, c=(0, 0, -150), eixo=(0, 1, 0))
    olhal = olhal.fuse(cilindro(12, 2 * yi - t, base=(0, -yi + t / 2.0, -128), eixo=(0, 1, 0))).removeSplitter()
    partes.append((olhal, "escuro"))
    # plaqueta de carga na placa da frente
    partes.append((caixa(34, 1.2, 14, x=0, y=-yp - t / 2.0 - 0.6, z=40), "branco"))
    return partes, {"Faixa de aba": faixa, "Uso": "Ancoragem móvel / trole manual em viga I",
                    "Medidas": "representativas (formato do trole de 0,5 t, cerca de 200 × 190 mm) — confira "
                               "certificação e carga no fabricante"}


# ------------------------------------------------------------------ ar comprimido
ROSCAS = {"1/4\"": 40, "3/8\"": 50, "1/2\"": 60, "3/4\"": 75, "1\"": 90}       # largura do módulo FRL (típica)


def frl(rosca):
    w = ROSCAS[rosca]
    partes = []
    for i, copo in enumerate((True, False, True)):
        x = (i - 1) * (w + 4)
        partes.append((caixa_r(w, w, w * 0.9, w * 0.12, x=x, z=w * 2.0), "escuro"))
        if copo:
            partes.append((revolver([(0, 0), (w * 0.2, 0), (w * 0.36, w * 0.25), (w * 0.36, w * 1.8), (0, w * 1.8)],
                                    base=(x, 0, w * 0.2)), "transparente"))
            partes.append((tubo(w * 0.38, w * 0.36, w * 1.2, base=(x, 0, w * 0.75)), "metal"))
            partes.append((cilindro(w * 0.1, w * 0.2, base=(x, 0, 0)), "metal"))
        else:
            # regulador: manopla raiada e manômetro na frente
            man = cilindro(w * 0.3, w * 0.5, base=(x, 0, w * 2.9))
            for k in range(12):
                a = 2 * math.pi * k / 12
                man = man.cut(cilindro(w * 0.03, w * 0.5, base=(x + w * 0.3 * math.cos(a), w * 0.3 * math.sin(a),
                                                                 w * 2.9)))
            partes.append((arred(man, w * 0.04, lambda e: e.BoundBox.ZMin > w * 3.3), "escuro"))
            partes.append((cilindro(w * 0.3, w * 0.12, base=(x, -w / 2, w * 2.45), eixo=(0, -1, 0)), "escuro"))
            partes.append((cilindro(w * 0.26, w * 0.02, base=(x, -w / 2 - w * 0.12, w * 2.45), eixo=(0, -1, 0)),
                           "branco"))
    for s in (-1, 1):
        partes.append((cilindro(w * 0.22, w * 0.3, base=(s * (1.5 * w + 4), 0, w * 2.45), eixo=(s, 0, 0)), "metal"))
        partes.append((sextavado(w * 0.5, w * 0.12, base=(s * (1.5 * w + 4 + w * 0.3), 0, w * 2.45), eixo=(s, 0, 0)),
                       "metal"))
    return partes, {"Rosca": rosca, "Composição": "Filtro + regulador com manômetro + lubrificador",
                    "Medidas": "representativas"}


def purgador(_t):
    partes = [(revolver([(0, 0), (30, 0), (35, 10), (35, 110), (0, 110)]), "escuro"),
              (caixa_r(90, 70, 60, 8, z=110), "laranja"),
              (caixa(30, 2, 18, x=0, y=-35, z=140), "transparente"),
              (cilindro(10, 30, base=(-45, 0, 140), eixo=(-1, 0, 0)), "metal"),
              (cilindro(8, 25, base=(45, 0, 125), eixo=(1, 0, 0)), "metal"),
              (cilindro(6, 20, base=(0, 0, -20)), "metal")]
    return partes, {"Tipo": "Purgador eletrônico de condensado", "Medidas": "representativas"}


RESERVATORIO_L = ["300", "500", "1000", "2000", "3000"]


def reservatorio(volume_l):
    v = float(volume_l) * 1e6
    D = (4 * v / (2.5 * math.pi)) ** (1 / 3.0)        # vertical, H/D = 2,5 (típico)
    H = 2.5 * D
    r = D / 2.0
    z0 = D * 0.25
    partes = [(cilindro(r, H, base=(0, 0, z0)), "cinza"), (tampo(r, r * 0.5, (0, 0, z0 + H), (0, 0, 1)), "cinza"),
              (tampo(r, r * 0.5, (0, 0, z0), (0, 0, -1)), "cinza")]
    for z in (z0, z0 + H):
        partes.append((toro(r, D * 0.006, c=(0, 0, z)), "cinza"))
    # três pés de tubo com sapata
    for i in range(3):
        a = math.radians(120 * i)
        px, py = r * 0.8 * math.cos(a), r * 0.8 * math.sin(a)
        partes.append((cilindro(D * 0.04, z0 + r * 0.2, base=(px, py, 0)), "escuro"))
        partes.append((caixa_r(D * 0.14, D * 0.14, D * 0.015, D * 0.02, x=px, y=py, z=0), "escuro"))
    # boca de visita, entrada e saída com flange, válvula de segurança, manômetro e dreno
    partes.append((cilindro(D * 0.16, D * 0.08, base=(r * 0.98, 0, z0 + H * 0.35), eixo=(1, 0, 0)), "cinza"))
    for (yy, zz) in furos_em_circulo(8, D * 0.13):
        partes.append((sextavado(D * 0.02, D * 0.012, base=(r * 0.98 + D * 0.08, yy, z0 + H * 0.35 + zz),
                                 eixo=(1, 0, 0)), "metal"))
    for zz, ang in ((z0 + H * 0.2, 150), (z0 + H * 0.75, 210)):
        a = math.radians(ang)
        partes.append((cilindro(D * 0.035, D * 0.12, base=(r * 0.95 * math.cos(a), r * 0.95 * math.sin(a), zz),
                                eixo=(math.cos(a), math.sin(a), 0)), "metal"))
        partes.append((cilindro(D * 0.065, D * 0.02, base=(r * 1.07 * math.cos(a), r * 1.07 * math.sin(a), zz),
                                eixo=(math.cos(a), math.sin(a), 0)), "metal"))
    partes.append((cilindro(D * 0.05, D * 0.2, base=(0, 0, z0 + H + r * 0.45)), "metal"))
    partes.append((cilindro(D * 0.07, D * 0.04, base=(0, 0, z0 + H + r * 0.45 + D * 0.2)), "metal"))
    partes += _manometro(D * 0.06, (0, -r * 0.35, z0 + H + r * 0.35), (0, 0, 1))
    partes.append((cilindro(D * 0.02, D * 0.12, base=(0, 0, z0 - r * 0.6)), "metal"))
    partes.append((caixa(D * 0.25, D * 0.005, D * 0.15, x=-r * 0.2, y=-r - D * 0.0025, z=z0 + H * 0.55), "metal"))
    return partes, {"Volume": "%s L" % volume_l, "Diâmetro × altura do corpo": "%.0f × %.0f mm" % (D, H),
                    "Medidas": "representativas (H/D = 2,5)"}


# ------------------------------------------------------------------ secadores
SECADOR_M3MIN = {"1": (500, 450, 750), "3": (600, 550, 900), "6": (750, 650, 1000), "12": (900, 800, 1250),
                 "25": (1200, 1000, 1500)}


def secador_refrigeracao(vazao):
    c, l, a = SECADOR_M3MIN[vazao]
    gab = caixa_r(c, l, a, a * 0.02, z=0)
    gab = gab.cut(caixa(c + 2, l + 2, a * 0.005, z=a * 0.5))
    partes = [(gab, "branco")]
    for s in (-1, 1):
        partes += _veneziana(c * 0.6, a, 8, 0, s * (l / 2.0 + a * 0.004), a * 0.1, s)
        partes.append((cilindro(a * 0.04, c * 0.12, base=(s * c / 2, 0, a * 0.85), eixo=(s, 0, 0)), "metal"))
        partes.append((sextavado(a * 0.1, a * 0.03, base=(s * (c / 2 + c * 0.12), 0, a * 0.85), eixo=(s, 0, 0)),
                       "metal"))
    partes.append((caixa_r(c * 0.25, l * 0.02, a * 0.12, a * 0.01, x=c * 0.25, y=l / 2.0, z=a * 0.72), "escuro"))
    partes.append((cilindro(a * 0.02, l * 0.03, base=(c * 0.15, l / 2.0, a * 0.65), eixo=(0, 1, 0)), "verde"))
    return partes, {"Vazão": "%s m³/min" % vazao, "Gabinete C × L × A": "%d × %d × %d mm" % (c, l, a),
                    "Medidas": "representativas"}


def secador_adsorcao(vazao):
    c, l, a = SECADOR_M3MIN[vazao]
    r = l * 0.22
    h = a * 1.1
    partes = [(caixa_r(c * 1.1, l, 60, 8, z=0), "escuro")]
    for x in (-c * 0.22, c * 0.22):
        partes += [(cilindro(r, h, base=(x, 0, 60)), "verde"), (tampo(r, r * 0.4, (x, 0, 60 + h), (0, 0, 1)), "verde")]
        partes.append((toro(r, r * 0.02, c=(x, 0, 60 + h)), "verde"))
    for z in (60 + h * 0.08, 60 + h * 0.9):
        partes.append((caixa_r(c * 0.8, r * 0.5, r * 0.5, r * 0.08, z=z), "metal"))
        for x in (-c * 0.32, c * 0.32):
            partes.append((cilindro(r * 0.18, r * 0.3, base=(x, 0, z + r * 0.5)), "escuro"))
    partes.append((caixa_r(c * 0.25, l * 0.3, a * 0.35, a * 0.02, x=0, y=l * 0.35, z=60 + h * 0.3), "cinza"))
    partes.append((caixa(c * 0.15, l * 0.006, a * 0.08, x=0, y=l * 0.5, z=60 + h * 0.45), "transparente"))
    partes += _manometro(r * 0.25, (-c * 0.22, -r * 0.9, 60 + h * 0.6), (0, -1, 0))
    partes += _manometro(r * 0.25, (c * 0.22, -r * 0.9, 60 + h * 0.6), (0, -1, 0))
    return partes, {"Vazão": "%s m³/min" % vazao, "Tipo": "Duas torres (dessecante)", "Medidas": "representativas"}


# ------------------------------------------------------------------ pessoas
ALTURAS = ["1,70 m", "1,60 m", "1,80 m", "1,90 m"]      # 1,70 m é o padrão


def _membro(r, p0, p1, r1=None):
    """Membro arredondado (cápsula) de p0 a p1."""
    a, b = _V(*p0), _V(*p1)
    d = b - a
    L = d.Length
    r1 = r if r1 is None else r1
    corpo = cone(r, r1, L, base=p0, eixo=(d.x, d.y, d.z)) if abs(r - r1) > 1e-6 else \
        cilindro(r, L, base=p0, eixo=(d.x, d.y, d.z))
    return corpo.fuse(esfera(r, c=p0)).fuse(esfera(r1, c=p1)).removeSplitter()


def pessoa(altura, sentado=False, capacete=True):
    h = float(altura.replace(" m", "").replace(",", ".")) * 1000
    u = h / 8.0                                   # cânone de 8 cabeças
    partes = []
    perna_r, braco_r = u * 0.2, u * 0.15
    if sentado:
        zq = u * 3.3                              # quadril na altura de uma cadeira
        for s in (-1, 1):
            y = s * u * 0.3
            partes.append((_membro(perna_r * 1.1, (0, y, zq), (u * 1.85, y, zq), perna_r), "calca"))
            partes.append((_membro(perna_r, (u * 1.9, y, zq), (u * 1.9, y, u * 0.35), perna_r * 0.75), "calca"))
            partes.append((caixa_r(u * 0.95, u * 0.36, u * 0.3, u * 0.1, x=u * 2.05, y=y, z=0), "escuro"))
        # cadeira: assento sob as coxas, encosto atrás, quatro pés
        partes.append((caixa_r(u * 2.0, u * 2.0, u * 0.22, u * 0.08, x=u * 0.7, z=zq - u * 0.44), "madeira"))
        partes.append((caixa_r(u * 0.18, u * 2.0, u * 2.0, u * 0.07, x=-u * 0.45, z=zq), "madeira"))
        for px in (-u * 0.2, u * 1.6):
            for py in (-u * 0.9, u * 0.9):
                partes.append((cilindro(u * 0.07, zq - u * 0.44, base=(px, py, 0)), "escuro"))
        base = zq
    else:
        for s in (-1, 1):
            y = s * u * 0.3
            partes.append((_membro(perna_r * 1.15, (0, y, u * 3.9), (0, y, u * 2.0), perna_r), "calca"))
            partes.append((_membro(perna_r, (0, y, u * 2.0), (0, y, u * 0.4), perna_r * 0.72), "calca"))
            partes.append((caixa_r(u * 0.95, u * 0.36, u * 0.3, u * 0.1, x=u * 0.2, y=y, z=0), "escuro"))
        base = u * 3.85
    # tronco arredondado com colete refletivo, braços, mãos, pescoço, cabeça e capacete
    tronco = revolver([(0, 0), (u * 0.62, 0), (u * 0.66, u * 1.2), (u * 0.74, u * 2.6), (u * 0.5, u * 2.95),
                       (0, u * 2.95)], base=(0, 0, base))
    m = FreeCAD.Matrix()
    m.scale(0.62, 1.0, 1.0)
    partes.append((tronco.transformGeometry(m), "roupa"))
    for z in (base + u * 1.0, base + u * 1.6):
        faixa = revolver([(0, 0), (u * 0.72, 0), (u * 0.72, u * 0.12), (0, u * 0.12)], base=(0, 0, z))
        partes.append((faixa.transformGeometry(m), "amarelo"))
    for s in (-1, 1):
        ombro = (0, s * u * 0.82, base + u * 2.65)
        cotovelo = (u * 0.15, s * u * 0.9, base + u * 1.45)
        mao = (u * 0.3, s * u * 0.9, base + u * 0.35)
        partes.append((_membro(braco_r * 1.1, ombro, cotovelo, braco_r), "roupa"))
        partes.append((_membro(braco_r, cotovelo, mao, braco_r * 0.8), "roupa"))
        partes.append((esfera(braco_r * 1.0, c=(u * 0.32, s * u * 0.9, base + u * 0.15)), "pele"))
    partes.append((cilindro(u * 0.19, u * 0.35, base=(0, 0, base + u * 2.85)), "pele"))
    cab = base + u * 3.2 + u * 0.45
    m2 = FreeCAD.Matrix()
    m2.scale(1.0, 0.86, 1.12)
    partes.append((esfera(u * 0.42).transformGeometry(m2).translated(_V(0, 0, cab)), "pele"))
    partes.append((esfera(u * 0.07, c=(u * 0.4, 0, cab - u * 0.05)), "pele"))      # nariz
    if capacete:
        import Part
        cap = esfera(u * 0.5, c=(0, 0, cab + u * 0.08)).common(
            Part.makeBox(u * 1.2, u * 1.2, u * 0.6, _V(-u * 0.6, -u * 0.6, cab + u * 0.08)))
        cap = cap.fuse(caixa(u * 0.7, u * 0.07, u * 0.09, z=cab + u * 0.48).common(esfera(u * 0.6, c=(0, 0, cab + u * 0.08)))).removeSplitter()
        partes.append((cap, "amarelo"))
        aba = revolver([(0, 0), (u * 0.62, 0), (u * 0.62, u * 0.035), (0, u * 0.035)], base=(u * 0.06, 0, cab + u * 0.06))
        partes.append((aba, "amarelo"))
    info = {"Altura": altura, "Postura": "sentado" if sentado else "em pé",
            "EPI": "capacete" if capacete else "—", "Uso": "escala e ergonomia do leiaute"}
    return partes, info


# ------------------------------------------------------------------ outros
BOMBA_DN = ["32", "40", "50", "65", "80", "100"]


def bomba(dn):
    dn = int(dn)
    k = dn / 50.0
    partes = []
    # base em perfil U com furos de chumbador
    base = caixa(900 * k, 300 * k, 60 * k, x=150 * k, z=0).cut(caixa(880 * k, 280 * k, 52 * k, x=150 * k, z=-1))
    for xx in (-280 * k, 580 * k):
        for yy in (-120 * k, 120 * k):
            base = base.cut(cilindro(9 * k, 70 * k, base=(xx, yy, -2)))
    partes.append((base, "escuro"))
    zc = 60 * k + 160 * k
    # voluta em caracol (anel excêntrico) e tampa
    vol = cilindro(150 * k, 110 * k, base=(-120 * k, 0, zc), eixo=(1, 0, 0))
    vol = vol.fuse(cilindro(170 * k, 110 * k, base=(-120 * k, 0, zc + 25 * k), eixo=(1, 0, 0))).removeSplitter()
    vol = arred(vol, 12 * k, lambda e: e.BoundBox.XLength < 1e-6)
    partes.append((vol, "maquina"))
    partes.append((revolver([(0, 0), (155 * k, 0), (140 * k, 25 * k), (0, 25 * k)], base=(-120 * k, 0, zc),
                            eixo=(-1, 0, 0)), "maquina"))
    # bocais com flange e parafusos
    sx = -145 * k
    partes.append((cilindro(dn / 2.0 + 8, 140 * k, base=(sx, 0, zc), eixo=(-1, 0, 0)), "maquina"))
    Dfs = dn * 1.9 + 60
    fl = cilindro(Dfs / 2.0, 16 * k, base=(sx - 140 * k, 0, zc), eixo=(-1, 0, 0))
    for (yy, zz) in furos_em_circulo(4, Dfs * 0.39, math.pi / 4):
        fl = fl.cut(cilindro(8 * k, 20 * k, base=(sx - 135 * k, yy, zc + zz), eixo=(-1, 0, 0)))
    partes.append((fl, "maquina"))
    zr = zc + 170 * k
    partes.append((cilindro(dn * 0.4 + 8, 90 * k, base=(-65 * k, 0, zr)), "maquina"))
    Dfr = dn * 1.6 + 60
    fl = cilindro(Dfr / 2.0, 16 * k, base=(-65 * k, 0, zr + 90 * k))
    for (xx, yy) in furos_em_circulo(4, Dfr * 0.39, math.pi / 4):
        fl = fl.cut(cilindro(8 * k, 20 * k, base=(-65 * k + xx, yy, zr + 88 * k)))
    partes.append((fl, "maquina"))
    # suporte de mancal, protetor do acoplamento e motor aletado
    partes.append((caixa_r(110 * k, 130 * k, 150 * k, 10 * k, x=30 * k, z=60 * k), "maquina"))
    partes.append((revolver([(0, 0), (75 * k, 0), (75 * k, 110 * k), (0, 110 * k)], base=(90 * k, 0, zc),
                            eixo=(1, 0, 0)).cut(caixa(120 * k, 200 * k, 100 * k, x=145 * k, z=zc - 160 * k)),
                   "amarelo"))
    mp = motor_partes(160 * k, 210 * k, 200 * k, 28 * k, 60 * k, 560 * k, cor="verde")
    for forma, cor in mp:
        forma = forma.copy()
        forma.translate(_V(260 * k, 0, zc - 160 * k))
        partes.append((forma, cor))
    return partes, {"Bocal de sucção": "DN %d" % dn, "Tipo": "Motobomba centrífuga em base",
                    "Medidas": "representativas"}


# Rolamentos rígidos de esferas, uma carreira (séries 60, 62 e 63): furo d, diâmetro externo D e largura B
# em mm. Medidas de contorno conferidas em duas fontes cada (10/11/2026):
#   séries 60 e 62: Emerson Bearing (tabelas das séries 6000 e 6200) e catálogo das séries 6000 e 6200
#   (cdn.shopify.com/.../6000_series.pdf e 6200_series.pdf); série 63: Emerson Bearing (série 6300) e
#   MRO Supply (ball bearings size chart). A tabela da MRO Supply tinha erros nas séries 60/62 (6205 com furo
#   47, 6208 com largura 15): nesses casos valeu a concordância das outras duas fontes.
# O desenho é simplificado (anéis e esferas representativos); a massa não vem do catálogo.
ROLAMENTOS = {
    "6000": (10, 26, 8), "6001": (12, 28, 8), "6002": (15, 32, 9), "6003": (17, 35, 10), "6004": (20, 42, 12),
    "6005": (25, 47, 12), "6006": (30, 55, 13), "6007": (35, 62, 14), "6008": (40, 68, 15), "6009": (45, 75, 16),
    "6010": (50, 80, 16), "6011": (55, 90, 18), "6012": (60, 95, 18),
    "6200": (10, 30, 9), "6201": (12, 32, 10), "6202": (15, 35, 11), "6203": (17, 40, 12), "6204": (20, 47, 14),
    "6205": (25, 52, 15), "6206": (30, 62, 16), "6207": (35, 72, 17), "6208": (40, 80, 18), "6209": (45, 85, 19),
    "6210": (50, 90, 20), "6211": (55, 100, 21), "6212": (60, 110, 22),
    "6300": (10, 35, 11), "6301": (12, 37, 12), "6302": (15, 42, 13), "6303": (17, 47, 14), "6304": (20, 52, 15),
    "6305": (25, 62, 17), "6306": (30, 72, 19), "6307": (35, 80, 21), "6308": (40, 90, 23), "6309": (45, 100, 25),
    "6310": (50, 110, 27), "6311": (55, 120, 29), "6312": (60, 130, 31),
}
TAMANHOS_ROLAMENTO = ["%s  (%d × %d × %d)" % (k, d, D, B) for k, (d, D, B) in ROLAMENTOS.items()]


def rolamento(tam):
    """Rolamento rígido de esferas com o eixo em Z, face de baixo em z = 0 e centro em (0, 0): anéis com
    pista e cantos arredondados, gaiola e esferas."""
    cod = tam.split()[0]
    d, D, B = ROLAMENTOS[cod]
    e = (D - d) / 2.0                         # altura da seção
    esp = e * 0.28                            # parede de cada anel (representativa)
    import Part
    rp = (D + d) / 4.0                        # círculo das esferas
    re = min(e - 2 * esp, B) * 0.48
    rc = min(B, e) * 0.08                     # raio dos cantos
    ext = revolver([(D / 2.0 - esp, 0), (D / 2.0 - rc, 0), (D / 2.0, rc), (D / 2.0, B - rc), (D / 2.0 - rc, B),
                    (D / 2.0 - esp, B)])
    inn = revolver([(d / 2.0, rc), (d / 2.0 + rc, 0), (d / 2.0 + esp, 0), (d / 2.0 + esp, B),
                    (d / 2.0 + rc, B), (d / 2.0, B - rc)])
    pista = toro(rp, re * 1.02, c=(0, 0, B / 2.0))
    ext = ext.cut(pista)
    inn = inn.cut(pista)
    n = max(6, int(math.pi * rp / (re * 1.25)))
    esferas = [esfera(re, (rp * math.cos(2 * math.pi * i / n), rp * math.sin(2 * math.pi * i / n), B / 2.0))
               for i in range(n)]
    gaiola = tubo(rp + re * 0.25, rp - re * 0.25, re * 0.5, base=(0, 0, B / 2.0 - re * 1.05))
    for i in range(n):
        gaiola = gaiola.cut(esfera(re * 1.02, (rp * math.cos(2 * math.pi * i / n),
                                               rp * math.sin(2 * math.pi * i / n), B / 2.0)))
    return [(ext, "metal"), (inn, "metal"), (Part.makeCompound(esferas), "aco"), (gaiola, "laranja")], {
        "Rolamento": cod, "Furo d": "%d mm" % d, "Diâmetro externo D": "%d mm" % D, "Largura B": "%d mm" % B,
        "Medidas": "d, D e B conferidas em duas fontes; desenho simplificado"}


TALHA_T = {"0,5 t": 0.5, "1 t": 1.0, "2 t": 2.0, "5 t": 5.0}


def talha(cap):
    k = TALHA_T[cap] ** 0.33
    partes = [(caixa_r(300 * k, 240 * k, 280 * k, 30 * k, z=0), "amarelo"),
              (revolver([(0, 0), (120 * k, 0), (120 * k, 150 * k), (90 * k, 175 * k), (0, 175 * k)],
                        base=(150 * k, 0, 140 * k), eixo=(1, 0, 0)), "amarelo"),
              (revolver([(0, 0), (110 * k, 0), (110 * k, 30 * k), (0, 30 * k)], base=(-150 * k, 0, 140 * k),
                        eixo=(-1, 0, 0)), "escuro")]
    for kk in range(10):
        a = 2 * math.pi * kk / 10
        partes.append((caixa(130 * k, 6 * k, 18 * k, x=230 * k, z=0).transformGeometry(_rot_x(a, 140 * k, 112 * k)),
                       "amarelo"))
    # gancho de suspensão com trava, corrente de elos e moitão com gancho
    partes.append((toro(35 * k, 10 * k, c=(0, 0, 330 * k), eixo=(0, 1, 0)), "metal"))
    partes.append((cilindro(14 * k, 40 * k, base=(0, 0, 280 * k)), "metal"))
    elo = 22 * k
    for i in range(int(1200 * k / elo)):
        ex = (1, 0, 0) if i % 2 == 0 else (0, 1, 0)
        partes.append((toro(elo * 0.45, elo * 0.12, c=(0, 0, -i * elo * 0.9), eixo=ex), "metal"))
    zm = -1200 * k
    partes.append((caixa_r(90 * k, 70 * k, 110 * k, 15 * k, z=zm - 110 * k), "amarelo"))
    import Part
    gancho = toro(40 * k, 12 * k, c=(0, 0, zm - 160 * k), eixo=(0, 1, 0)).cut(
        Part.makeBox(60 * k, 40 * k, 50 * k, _V(-10 * k, -20 * k, zm - 175 * k)))
    partes.append((gancho, "escuro"))
    # botoeira pendente
    partes.append((cilindro(3 * k, 900 * k, base=(80 * k, 0, -900 * k)), "escuro"))
    partes.append((caixa_r(60 * k, 50 * k, 180 * k, 15 * k, x=80 * k, z=-1080 * k), "amarelo"))
    for zz in (-930 * k, -980 * k):
        partes.append((cilindro(12 * k, 8 * k, base=(80 * k, -25 * k, zz), eixo=(0, -1, 0)), "escuro"))
    return partes, {"Capacidade": cap, "Tipo": "Talha elétrica de corrente (gancho)", "Medidas": "representativas"}


def quadro(tam):
    a, l, p = {"600 × 400": (600, 400, 200), "800 × 600": (800, 600, 250), "1200 × 800": (1200, 800, 300),
               "2000 × 800": (2000, 800, 600)}[tam]
    z0 = 0 if a >= 2000 else 900
    partes = [(caixa_r(p, l, a, 6, z=z0), "cinza"),
              (caixa_r(14, l * 0.96, a * 0.96, 5, x=-p / 2 - 6, z=z0 + a * 0.02), "cinza")]
    # dobradiças, fecho, plaqueta de advertência, sinaleiros e botões; ventilação e base soleira
    for zz in (z0 + a * 0.15, z0 + a * 0.8):
        partes.append((cilindro(7, a * 0.06, base=(-p / 2 - 10, -l * 0.48, zz)), "escuro"))
    partes.append((caixa_r(22, 30, a * 0.08, 6, x=-p / 2 - 22, y=l * 0.38, z=z0 + a * 0.46), "escuro"))
    partes.append((caixa(2, l * 0.25, l * 0.12, x=-p / 2 - 14, y=0, z=z0 + a * 0.78), "amarelo"))
    for i, cor in enumerate(("verde", "vermelho", "amarelo")):
        partes.append((cilindro(14, 18, base=(-p / 2 - 13, -l * 0.25 + i * l * 0.12, z0 + a * 0.6), eixo=(-1, 0, 0)),
                       cor))
    partes.append((cilindro(20, 20, base=(-p / 2 - 13, l * 0.18, z0 + a * 0.6), eixo=(-1, 0, 0)), "vermelho"))
    partes.append((caixa(4, l * 0.3, a * 0.08, x=p / 2 + 2, y=0, z=z0 + a * 0.1), "escuro"))
    if a >= 2000:
        partes.append((caixa_r(p + 20, l + 20, 100, 4, z=-100), "escuro"))
        partes[0] = (caixa_r(p, l, a - 100, 6, z=0), "cinza")
    return partes, {"Altura × largura": tam + " mm", "Instalação": "piso" if a >= 2000 else "parede (base a 900 mm)",
                    "Medidas": "representativas"}


def extintor(tipo):
    m = {"PQS 4 kg": (75, 470), "PQS 6 kg": (80, 520), "PQS 12 kg": (95, 620), "CO2 6 kg": (75, 650),
         "Água 10 L": (90, 600)}[tipo]
    r, h = m
    corpo = revolver([(0, 0), (r * 0.9, 0), (r, r * 0.12), (r, h), (r * 0.8, h + r * 0.5), (r * 0.35, h + r * 0.85),
                      (r * 0.35, h + r * 0.95), (0, h + r * 0.95)])
    partes = [(corpo, "vermelho"),
              (tubo(r * 1.005, r * 0.95, h * 0.25, base=(0, 0, h * 0.35)), "branco"),       # rótulo
              (cilindro(r * 0.3, r * 0.4, base=(0, 0, h + r * 0.95)), "metal"),
              (caixa_r(r * 1.6, 22, 14, 5, x=r * 0.6, z=h + r * 1.3), "escuro"),
              (caixa_r(r * 1.4, 20, 10, 4, x=r * 0.5, z=h + r * 1.62), "escuro"),
              (cilindro(r * 0.12, r * 0.25, base=(-r * 0.15, 0, h + r * 1.35)), "amarelo")]   # lacre
    partes += _manometro(r * 0.22, (0, -r * 0.3, h + r * 1.05), (0, -1, 0)) if "CO2" not in tipo else []
    # mangueira descendo pela lateral e esguicho
    partes.append((cilindro(r * 0.11, h * 0.6, base=(r * 0.35, r * 1.05, h * 0.3)), "borracha"))
    partes.append((cone(r * 0.12, r * 0.07, r * 0.8, base=(r * 0.35, r * 1.05, h * 0.3), eixo=(0, 0, -1)),
                   "escuro"))
    partes.append((caixa(r * 0.3, r * 0.3, r * 0.15, x=r * 0.35, y=r * 0.9, z=h * 0.25), "escuro"))
    return partes, {"Tipo": tipo, "Medidas": "representativas"}


def palete(tipo):
    c, l, a = {"PBR 1200 × 1000": (1200, 1000, 140), "Europeu 1200 × 800": (1200, 800, 144)}[tipo]
    partes = []
    for i in range(7):
        tabua = chanfro(caixa(c, 100, 20, y=-l / 2 + 50 + i * (l - 100) / 6.0, z=a - 20), 3,
                        lambda e: e.BoundBox.ZMin > a - 1)
        partes.append((tabua, "madeira"))
    for y in (-l / 2 + 50, 0, l / 2 - 50):
        for x in (-c / 2 + 50, 0, c / 2 - 50):
            partes.append((chanfro(caixa(100, 100, a - 40, x=x, y=y, z=20), 4,
                                   lambda e: e.BoundBox.ZLength > a - 50), "madeira"))
            for dx in (-25, 25):
                partes.append((cilindro(5, 3, base=(x + dx, y, a)), "aco"))
        partes.append((chanfro(caixa(c, 100, 20, y=y, z=0), 3, lambda e: e.BoundBox.ZMax < 1), "madeira"))
    return partes, {"Tipo": tipo, "C × L × A": "%d × %d × %d mm (a checar)" % (c, l, a)}


def ventilador(diam):
    d = int(diam)
    zc = d * 0.8
    # caixa em caracol: anel crescente aproximado por três trechos de raio crescente
    import Part
    car = cilindro(d * 0.62, d * 0.45, base=(0, -d * 0.225, zc), eixo=(0, 1, 0))
    car = car.fuse(cilindro(d * 0.68, d * 0.45, base=(d * 0.05, -d * 0.225, zc + d * 0.05), eixo=(0, 1, 0)))
    car = car.fuse(cilindro(d * 0.75, d * 0.45, base=(d * 0.1, -d * 0.225, zc + d * 0.08), eixo=(0, 1, 0)))
    car = car.fuse(caixa(d * 0.75, d * 0.45, d * 0.75, x=d * 0.47, z=zc + d * 0.08)).removeSplitter()
    car = arred(car, d * 0.03, lambda e: e.BoundBox.YLength < 1e-6 and e.BoundBox.ZLength > d * 0.1)
    partes = [(car, "cinza")]
    # boca de descarga com flange, cone de aspiração com tela, base e motor
    partes.append((caixa_r(d * 0.85, d * 0.55, d * 0.06, d * 0.02, x=d * 0.47, z=zc + d * 0.83), "cinza"))
    partes.append((cone(d * 0.32, d * 0.5, d * 0.25, base=(d * 0.1, d * 0.225, zc + d * 0.08), eixo=(0, 1, 0)), "cinza"))
    tela = tubo(d * 0.5, d * 0.47, d * 0.02, base=(d * 0.1, d * 0.475, zc + d * 0.08), eixo=(0, 1, 0))
    for k in range(5):
        tela = tela.fuse(cilindro(d * 0.006, d * 0.96, base=(d * 0.1 - d * 0.48 + k * d * 0.24, d * 0.48,
                                                             zc + d * 0.08 - d * 0.48 * 0), eixo=(0, 0, 1)
                                  ).translated(_V(0, 0, -d * 0.48)))
    partes.append((tela, "escuro"))
    partes.append((caixa_r(d * 1.8, d * 0.6, d * 0.08, d * 0.02, x=d * 0.2, z=0), "escuro"))
    partes.append((caixa(d * 0.6, d * 0.5, zc - d * 0.75 + d * 0.08 - d * 0.08, x=d * 0.1, z=d * 0.08), "escuro"))
    mp = motor_partes(d * 0.32, d * 0.38, d * 0.3, d * 0.05 + 10, d * 0.1, d * 0.85, cor="verde")
    for forma, cor in mp:
        forma = forma.copy()
        forma.rotate(_V(0, 0, 0), _V(0, 0, 1), 90)
        forma.translate(_V(d * 0.1, -d * 0.23 - d * 0.95, d * 0.08))
        partes.append((forma, cor))
    return partes, {"Diâmetro do rotor": "%d mm" % d, "Tipo": "Ventilador centrífugo", "Medidas": "representativas"}


# ------------------------------------------------------------------ combate a incêndio
# Posições e medidas representativas: alturas de instalação, diâmetros e tipos vêm da NBR 13714 e da instrução
# técnica do Corpo de Bombeiros de cada estado — a checar no projeto de incêndio aprovado.
NOTA_INCENDIO = "representativas — confira o projeto de incêndio (NBR 13714 e IT do Corpo de Bombeiros, a checar)"
HIDRANTES = ["Simples 1½\"", "Simples 2½\"", "Duplo 2½\""]


def _storz(r, base, eixo, tampa=True):
    """Engate rápido tipo Storz com tampão e corrente."""
    bx, by, bz = base
    ex, ey, ez = eixo
    partes = [(cilindro(r * 1.25, r * 0.7, base=base, eixo=eixo), "metal")]
    if tampa:
        partes.append((cilindro(r * 1.2, r * 0.35, base=(bx + ex * r * 0.7, by + ey * r * 0.7, bz + ez * r * 0.7),
                                eixo=eixo), "metal"))
        partes.append((cilindro(r * 0.4, r * 0.2, base=(bx + ex * r * 1.05, by + ey * r * 1.05, bz + ez * r * 1.05),
                                eixo=eixo), "metal"))
    return partes


def hidrante(tam):
    """Hidrante de parede: tubo vindo do piso, válvula angular de 45° com volante e engate Storz tampado
    (duplo: duas saídas, uma de cada lado)."""
    dn = 65.0 if "2" in tam else 40.0
    r = dn / 2.0
    duplo = tam.startswith("Duplo")
    zv = 1300.0                                    # altura da válvula (representativa)
    partes = [(cilindro(r + 6, zv, base=(0, 0, 0)), "vermelho"),
              (caixa_r(r * 5, r * 5, 12, 3, z=0), "vermelho")]
    for zz in (zv * 0.35, zv * 0.75):              # braçadeiras na parede
        partes.append((tubo(r + 12, r + 6, 25, base=(0, 0, zz)), "metal"))
        partes.append((caixa(30, r + 20, 25, x=0, y=(r + 20) / 2.0, z=zz), "metal"))
    saidas = [(-1, 0)] if not duplo else [(-1, 0), (1, 0)]
    if duplo:
        partes.append((cilindro(r + 6, 2 * r * 3, base=(-r * 3, 0, zv), eixo=(1, 0, 0)), "vermelho"))
    for sx, _ in saidas:
        x0 = sx * (r * 3 if duplo else 0)
        corpo = esfera(r * 1.5, c=(x0, 0, zv + r * 1.2))
        partes.append((corpo, "vermelho"))
        partes.append((cilindro(r + 4, r * 1.2, base=(x0, 0, zv)), "vermelho"))
        # saída a 45° para a frente/baixo, com engate e tampão
        d = (0, -math.cos(math.radians(45)), -math.sin(math.radians(45)))
        b0 = (x0, -r * 1.2, zv + r * 1.0)
        partes.append((cilindro(r + 3, r * 1.4, base=b0, eixo=d), "vermelho"))
        b1 = (x0 + d[0] * r * 1.4, -r * 1.2 + d[1] * r * 1.4, zv + r * 1.0 + d[2] * r * 1.4)
        partes += _storz(r, b1, d)
        # castelo, haste e volante
        partes.append((cilindro(r * 0.6, r * 1.6, base=(x0, 0, zv + r * 2.4)), "vermelho"))
        partes.append((cilindro(r * 0.2, r * 1.0, base=(x0, 0, zv + r * 3.9)), "metal"))
        partes.append((volante(r * 1.6, 5, (x0, 0, zv + r * 4.6), (0, 0, 1)), "escuro"))
    return partes, {"Tipo": "Hidrante de parede %s" % tam.lower(), "Válvula": "angular 45° com engate Storz",
                    "Altura da válvula": "%d mm (representativa)" % zv, "Medidas": NOTA_INCENDIO}


ABRIGOS = {"Simples 70 × 50 × 17 cm": (700, 500, 170, 1), "Duplo 90 × 60 × 17 cm": (900, 600, 170, 2),
           "Duplo 120 × 90 × 17 cm": (1200, 900, 170, 2)}


def abrigo(tam):
    """Abrigo de mangueira de sobrepor: caixa de chapa com porta de vidro, mangueira(s) aduchada(s), esguicho,
    chave de mangueira e faixa "INCÊNDIO"; fundo encostado na parede (y = 0), base a 1,0 m."""
    a, l, p, n = ABRIGOS[tam]
    z0 = 1000.0
    cx = caixa_r(l, p, a, 8, z=z0, y=-p / 2.0)
    cx = cx.cut(caixa(l - 30, p - 15, a - 30, y=-p / 2.0 - 8, z=z0 + 15))        # aberta na frente
    partes = [(cx, "vermelho")]
    # porta: moldura vermelha e vidro, dobradiças, fecho
    mold = caixa_r(l, 18, a, 6, y=-p - 9, z=z0).cut(caixa(l - 80, 30, a - 80, y=-p - 9, z=z0 + 40))
    partes.append((mold, "vermelho"))
    partes.append((caixa(l - 80, 4, a - 80, y=-p - 6, z=z0 + 40), "transparente"))
    partes.append((caixa(l * 0.55, 2, a * 0.1, y=-p - 19, z=z0 + a * 0.82), "branco"))          # faixa INCÊNDIO
    for zz in (z0 + a * 0.15, z0 + a * 0.75):
        partes.append((cilindro(6, a * 0.08, base=(-l / 2 + 4, -p - 18, zz)), "metal"))
    partes.append((caixa_r(16, 22, 50, 4, x=l / 2 - 25, y=-p - 25, z=z0 + a * 0.45), "escuro"))
    # mangueiras aduchadas (rolo plano em pé), esguicho e chave de mangueira
    for i in range(n):
        xm = (i - (n - 1) / 2.0) * (l / n)
        rr = min(a, l / n) * 0.33
        rolo = tubo(rr, rr * 0.35, p * 0.45, base=(xm, -p * 0.25, z0 + a * 0.42), eixo=(0, -1, 0))
        for k in range(1, 5):
            rolo = rolo.cut(tubo(rr * (0.35 + 0.16 * k) + 1.2, rr * (0.35 + 0.16 * k) - 1.2, p * 0.5,
                                 base=(xm, -p * 0.2, z0 + a * 0.42), eixo=(0, -1, 0)))
        partes.append((rolo, "branco"))
        partes.append((cone(14, 8, 220, base=(xm - rr * 0.6, -p * 0.75, z0 + 60), eixo=(1, 0, 0.15)), "metal"))
    partes.append((caixa(160, 10, 18, x=l / 2 - 120, y=-p * 0.7, z=z0 + 25), "escuro"))
    return partes, {"Abrigo": tam, "Instalação": "de sobrepor, base a 1 000 mm (representativa)",
                    "Mangueiras": "%d" % n, "Medidas": NOTA_INCENDIO}


CARRETAS = {"PQS 20 kg": (130, 650), "PQS 50 kg": (180, 850), "Água 75 L": (200, 900), "CO2 25 kg": (120, 1100)}


def extintor_carreta(tipo):
    """Extintor sobre rodas (carreta): cilindro em pé num carrinho com duas rodas, alça e mangueira com
    esguicho/difusor."""
    r, h = CARRETAS[tipo]
    z0 = 200.0
    corpo = revolver([(0, 0), (r * 0.9, 0), (r, r * 0.15), (r, h), (r * 0.75, h + r * 0.5), (r * 0.3, h + r * 0.75),
                      (0, h + r * 0.75)], base=(0, 0, z0))
    partes = [(corpo, "vermelho"), (tubo(r * 1.005, r * 0.96, h * 0.3, base=(0, 0, z0 + h * 0.35)), "branco"),
              (cilindro(r * 0.28, r * 0.35, base=(0, 0, z0 + h + r * 0.75)), "metal"),
              (caixa_r(r * 0.9, 20, 16, 5, x=r * 0.3, z=z0 + h + r * 1.1), "escuro")]
    # carrinho: berço, eixo, rodas de borracha com aro, alça tubular e pé de apoio
    partes.append((caixa_r(r * 2.2, r * 2.4, 25, 6, x=0, z=z0 - 30), "escuro"))
    ye = r * 1.25 + 40
    partes.append((cilindro(15, 2 * ye, base=(-r * 0.6, -ye, z0 - 40), eixo=(0, 1, 0)), "aco"))
    for s in (-1, 1):
        roda = revolver([(20, 0), (z0 - 40 - 2, 0), (z0 - 40, 10), (z0 - 40, 50), (z0 - 40 - 2, 60), (20, 60)],
                        base=(-r * 0.6, s * (ye - 60) if s > 0 else -ye, z0 - 40), eixo=(0, 1, 0))
        partes.append((roda, "borracha"))
        partes.append((tubo(z0 * 0.45, 22, 62, base=(-r * 0.6, s * (ye - 61) if s > 0 else -ye - 1, z0 - 40),
                            eixo=(0, 1, 0)), "metal"))
        partes.append((cilindro(14, h + r * 0.4, base=(-r * 1.15, s * r * 0.9, z0 - 20)), "escuro"))
    partes.append((cilindro(14, r * 1.8, base=(-r * 1.15, -r * 0.9, z0 + h + r * 0.38), eixo=(0, 1, 0)), "escuro"))
    partes.append((caixa(30, r * 1.6, z0 - 30, x=r * 0.85, z=0), "escuro"))
    # mangueira enrolada no suporte e esguicho
    partes.append((toro(r * 0.55, 14, c=(-r * 1.3, 0, z0 + h * 0.55), eixo=(1, 0, 0)), "borracha"))
    partes.append((cone(18, 10, 260, base=(-r * 1.3, r * 0.6, z0 + h * 0.8), eixo=(0, 0, 1)), "escuro"))
    return partes, {"Tipo": "Extintor sobre rodas %s" % tipo, "Medidas": NOTA_INCENDIO}


def extintor_suporte(tipo):
    """Extintor portátil no suporte de piso com a placa de sinalização em cima."""
    partes, info = extintor(tipo)
    sobe = 200.0
    mov = []
    for forma, cor in partes:
        f = forma.copy()
        f.translate(_V(0, 0, sobe))
        mov.append((f, cor))
    r = 100.0
    mov.append((caixa_r(2 * r + 120, 2 * r + 120, 20, 6, z=0), "vermelho"))
    mov.append((tubo(r + 6, r - 2, 60, base=(0, 0, sobe - 50)), "vermelho"))
    for s in (-1, 1):
        mov.append((cilindro(10, sobe + 1500, base=(-r - 30, s * (r + 30), 20)), "vermelho"))
    mov.append((caixa(4, 2 * r + 80, 280, x=-r - 30, z=sobe + 1250), "branco"))
    mov.append((caixa(5, 2 * r, 200, x=-r - 31, z=sobe + 1290), "vermelho"))
    info = dict(info, Instalação="suporte de piso com placa de sinalização")
    info["Medidas"] = NOTA_INCENDIO
    return mov, info


TALHA_CABO_T = {"1 t": 1.0, "2 t": 2.0, "3,2 t": 3.2, "5 t": 5.0, "10 t": 10.0}


def talha_cabo(cap):
    """Talha elétrica de cabo de aço com trole motorizado: tambor entre o motor e a caixa de redução, cabo
    descendo ao moitão com gancho, painel e botoeira."""
    k = TALHA_CABO_T[cap] ** 0.3
    Lt, Rt = 520 * k, 115 * k
    zc = -200 * k
    partes = []
    # tambor ranhurado
    tamb = cilindro(Rt, Lt, base=(-Lt / 2, 0, zc), eixo=(1, 0, 0))
    for i in range(1, 16):
        tamb = tamb.cut(toro(Rt, 5 * k, c=(-Lt / 2 + i * Lt / 16.0, 0, zc), eixo=(1, 0, 0)))
    partes.append((tamb, "metal"))
    # motor de elevação aletado de um lado, redutor do outro
    mp = motor_partes(110 * k, 0, 0, 30 * k, 10, 420 * k, cor="amarelo", com_pes=False, z_eixo=0)
    for forma, cor in mp:
        forma = forma.copy()
        forma.translate(_V(Lt / 2 + 20 * k, 0, zc))
        partes.append((forma, cor))
    partes.append((caixa_r(110 * k, 300 * k, 320 * k, 25 * k, x=-Lt / 2 - 55 * k, z=zc - 170 * k), "amarelo"))
    # quadro estrutural e trole motorizado em cima (rodas na aba da viga)
    partes.append((caixa_r(Lt + 40 * k, 30 * k, 40 * k, 6 * k, y=-160 * k, z=zc + Rt + 10 * k), "amarelo"))
    partes.append((caixa_r(Lt + 40 * k, 30 * k, 40 * k, 6 * k, y=160 * k, z=zc + Rt + 10 * k), "amarelo"))
    for s in (-1, 1):
        placa = caixa_r(420 * k, 14 * k, 200 * k, 30 * k, y=s * 140 * k, z=zc + Rt + 40 * k)
        partes.append((placa, "amarelo"))
        for x in (-140 * k, 140 * k):
            partes.append((revolver([(10, 0), (48 * k, 0), (48 * k, 22 * k), (54 * k, 22 * k), (54 * k, 28 * k),
                                     (10, 28 * k)], base=(x, s * 125 * k, zc + Rt + 180 * k), eixo=(0, -s, 0)),
                           "escuro"))
    partes.append((caixa_r(180 * k, 120 * k, 120 * k, 15 * k, x=0, y=-210 * k, z=zc + Rt + 80 * k), "amarelo"))
    # painel elétrico
    partes.append((caixa_r(260 * k, 90 * k, 220 * k, 12 * k, x=0, y=-200 * k, z=zc - 110 * k), "cinza"))
    # cabo de aço (dois ramais) e moitão com polia e gancho com trava
    zm = zc - 1500 * k
    for dy in (-25 * k, 25 * k):
        partes.append((cilindro(6 * k, 1500 * k - Rt, base=(0, dy, zm), eixo=(0, 0, 1)), "aco"))
    partes.append((caixa_r(110 * k, 90 * k, 170 * k, 30 * k, z=zm - 120 * k), "amarelo"))
    partes.append((cilindro(48 * k, 40 * k, base=(0, -20 * k, zm - 30 * k), eixo=(0, 1, 0)), "metal"))
    import Part
    gancho = toro(55 * k, 18 * k, c=(0, 0, zm - 210 * k), eixo=(0, 1, 0)).cut(
        Part.makeBox(80 * k, 60 * k, 70 * k, _V(-10 * k, -30 * k, zm - 230 * k)))
    partes.append((gancho, "escuro"))
    partes.append((cilindro(20 * k, 50 * k, base=(0, 0, zm - 165 * k)), "escuro"))
    partes.append((caixa(4 * k, 15 * k, 60 * k, x=35 * k, z=zm - 225 * k), "metal"))
    # botoeira pendente
    partes.append((cilindro(4 * k, 1300 * k, base=(0, -200 * k, zc - 1440 * k)), "escuro"))
    partes.append((caixa_r(70 * k, 60 * k, 220 * k, 18 * k, y=-200 * k, z=zc - 1660 * k), "amarelo"))
    for i in range(4):
        partes.append((cilindro(12 * k, 8 * k, base=(0, -230 * k, zc - 1480 * k - i * 40 * k), eixo=(0, -1, 0)),
                       "vermelho" if i == 0 else "escuro"))
    return partes, {"Capacidade": cap, "Tipo": "Talha elétrica de cabo de aço com trole motorizado",
                    "Curso do gancho": "%d mm (representativo)" % (1500 * k),
                    "Medidas": "representativas — confira no fabricante"}


TALHA_MANUAL_T = {"0,5 t": 0.5, "1 t": 1.0, "2 t": 2.0, "3 t": 3.0, "5 t": 5.0}


def talha_manual(cap):
    """Talha manual de corrente (catraca de corrente de mão): corpo redondo com a roda de corrente de mão."""
    k = TALHA_MANUAL_T[cap] ** 0.3
    partes = []
    corpo = revolver([(0, 0), (85 * k, 0), (95 * k, 15 * k), (95 * k, 95 * k), (85 * k, 110 * k), (0, 110 * k)],
                     base=(-55 * k, 0, 0), eixo=(1, 0, 0))
    partes.append((corpo, "vermelho"))
    roda = tubo(120 * k, 108 * k, 22 * k, base=(55 * k, 0, 0), eixo=(1, 0, 0))
    for i in range(6):
        a = 2 * math.pi * i / 6
        roda = roda.fuse(cilindro(5 * k, 108 * k, base=(66 * k, 0, 0), eixo=(0, math.cos(a), math.sin(a))))
    partes.append((roda.removeSplitter(), "escuro"))
    partes.append((revolver([(0, 0), (70 * k, 0), (70 * k, 25 * k), (0, 25 * k)], base=(78 * k, 0, 0),
                            eixo=(1, 0, 0)), "vermelho"))
    # gancho de suspensão, corrente de carga com gancho e corrente de mão (laço)
    import Part
    partes.append((toro(32 * k, 10 * k, c=(0, 0, 150 * k), eixo=(0, 1, 0)), "escuro"))
    partes.append((cilindro(12 * k, 40 * k, base=(0, 0, 100 * k)), "escuro"))
    elo = 20 * k
    for i in range(int(1300 * k / elo)):
        ex = (1, 0, 0) if i % 2 == 0 else (0, 1, 0)
        partes.append((toro(elo * 0.45, elo * 0.12, c=(-20 * k, 0, -110 * k - i * elo * 0.9), eixo=ex), "metal"))
    zg = -110 * k - 1300 * k * 0.9
    gancho = toro(38 * k, 12 * k, c=(-20 * k, 0, zg - 60 * k), eixo=(0, 1, 0)).cut(
        Part.makeBox(60 * k, 40 * k, 50 * k, _V(-30 * k, -20 * k, zg - 75 * k)))
    partes.append((gancho, "escuro"))
    for y in (-110 * k, 110 * k):
        partes.append((cilindro(4 * k, 1500 * k, base=(66 * k, y, -1500 * k)), "metal"))
    partes.append((toro(110 * k, 4 * k, c=(66 * k, 0, -1500 * k), eixo=(1, 0, 0)).common(
        Part.makeBox(20 * k, 300 * k, 120 * k, _V(56 * k, -150 * k, -1620 * k))), "metal"))
    return partes, {"Capacidade": cap, "Tipo": "Talha manual de corrente", "Medidas": "representativas"}


# ------------------------------------------------------------------ catálogo
# categoria -> [(id do modelo, nome, tamanhos, função(tamanho) -> (partes, informações))]
CATALOGO = [
    ("motores", "Motores", [
        ("motor_iec", "Motor elétrico trifásico (pés, IEC)", list(CARCACAS_IEC), motor),
    ]),
    ("compressores", "Compressores", [
        ("compressor_pistao", "Compressor de pistão com reservatório", ["50", "100", "200", "360", "500"],
         compressor_pistao),
        ("compressor_parafuso", "Compressor de parafuso (gabinete)", list(PARAFUSO_KW), compressor_parafuso),
    ]),
    ("valvulas", "Válvulas", [
        ("valvula_esfera", "Válvula esfera flangeada", [str(d) for d in DNS], lambda t: valvula("esfera", t)),
        ("valvula_gaveta", "Válvula gaveta flangeada", [str(d) for d in DNS], lambda t: valvula("gaveta", t)),
        ("valvula_globo", "Válvula globo flangeada", [str(d) for d in DNS], lambda t: valvula("globo", t)),
        ("valvula_retencao", "Válvula de retenção flangeada", [str(d) for d in DNS],
         lambda t: valvula("retencao", t)),
        ("valvula_borboleta", "Válvula borboleta (wafer)", [str(d) for d in DNS if d >= 50],
         lambda t: valvula("borboleta", t)),
    ]),
    ("caldeiras", "Caldeiras", [
        ("caldeira_flamotubular", "Caldeira flamotubular horizontal", list(CALDEIRA_KGH), caldeira),
    ]),
    ("incendio", "Combate a incêndio", [
        ("extintor", "Extintor de incêndio portátil", ["PQS 4 kg", "PQS 6 kg", "PQS 12 kg", "CO2 6 kg", "Água 10 L"],
         extintor),
        ("extintor_suporte", "Extintor no suporte de piso com placa", ["PQS 4 kg", "PQS 6 kg", "PQS 12 kg",
                                                                        "CO2 6 kg", "Água 10 L"], extintor_suporte),
        ("extintor_carreta", "Extintor sobre rodas (carreta)", list(CARRETAS), extintor_carreta),
        ("hidrante", "Hidrante de parede (simples ou duplo)", HIDRANTES, hidrante),
        ("abrigo", "Abrigo de mangueira", list(ABRIGOS), abrigo),
    ]),
    ("icamento", "Içamento", [
        ("talha", "Talha elétrica de corrente", list(TALHA_T), talha),
        ("talha_cabo", "Talha elétrica de cabo de aço (com trole)", list(TALHA_CABO_T), talha_cabo),
        ("talha_manual", "Talha manual de corrente", list(TALHA_MANUAL_T), talha_manual),
    ]),
    ("altura", "Trabalho em altura", [
        ("trole", "Trole para viga I (ancoragem móvel)", list(TROLE), trole),
    ]),
    ("ar", "Ar comprimido", [
        ("frl", "Conjunto filtro, regulador e lubrificador (FRL)", list(ROSCAS), frl),
        ("purgador", "Purgador eletrônico de condensado", ["padrão"], purgador),
        ("reservatorio", "Reservatório vertical de ar", RESERVATORIO_L, reservatorio),
    ]),
    ("secadores", "Secadores", [
        ("secador_refrigeracao", "Secador por refrigeração", list(SECADOR_M3MIN), secador_refrigeracao),
        ("secador_adsorcao", "Secador por adsorção (duas torres)", list(SECADOR_M3MIN), secador_adsorcao),
    ]),
    ("pessoas", "Pessoas", [
        ("pessoa_pe", "Funcionário em pé (com capacete)", ALTURAS, lambda t: pessoa(t)),
        ("pessoa_sentado", "Funcionário sentado", ALTURAS, lambda t: pessoa(t, sentado=True, capacete=False)),
    ]),
    ("transmissao", "Transmissão", [
        ("rolamento_esferas", "Rolamento rígido de esferas (uma carreira)", TAMANHOS_ROLAMENTO, rolamento),
    ]),
    ("outros", "Outros", [
        ("bomba", "Motobomba centrífuga", BOMBA_DN, bomba),
        ("ventilador", "Ventilador centrífugo", ["250", "400", "630", "800"], ventilador),
        ("quadro", "Quadro elétrico", ["600 × 400", "800 × 600", "1200 × 800", "2000 × 800"], quadro),
        ("palete", "Palete", ["PBR 1200 × 1000", "Europeu 1200 × 800"], palete),
    ]),
]
UNIDADE_TAMANHO = {"compressor_pistao": "L", "compressor_parafuso": "kW", "caldeira_flamotubular": "kg/h de vapor",
                   "secador_refrigeracao": "m³/min", "secador_adsorcao": "m³/min", "reservatorio": "L",
                   "valvula_esfera": "DN", "valvula_gaveta": "DN", "valvula_globo": "DN", "valvula_retencao": "DN",
                   "valvula_borboleta": "DN", "bomba": "DN", "ventilador": "mm", "motor_iec": "carcaça",
                   "rolamento_esferas": "série"}
MODELOS = {m[0]: (cat, m) for cat, _n, ms in CATALOGO for m in ms}


def gerar(modelo, tamanho):
    """(forma, cores por face, informações) do modelo no tamanho."""
    import Part
    _cat, (_id, _nome, tamanhos, fn) = MODELOS[modelo]
    if tamanho not in tamanhos:
        raise ValueError("%s não tem o tamanho %s" % (_nome, tamanho))
    partes, info = fn(tamanho)
    solidos, cores, nomes = [], [], []
    for forma, cor in partes:
        forma = forma.copy()          # peças independentes: nenhuma face compartilhada entre elas
        solidos.append(forma)
        cores += [CORES[cor]] * len(forma.Faces)
        nomes += [cor] * len(forma.Faces)
    comp = Part.makeCompound(solidos)
    if len(comp.Faces) != len(cores):
        # face repetida dentro de uma peça: recalcula a cor pela peça de cada face do conjunto
        cores, nomes = [], []
        mapa = {}
        for forma, (_f, cor) in zip(solidos, partes):
            for fc in forma.Faces:
                mapa[fc.hashCode()] = cor
        nomes = [mapa.get(fc.hashCode(), "cinza") for fc in comp.Faces]
        cores = [CORES[n] for n in nomes]
    _NOMES[(modelo, tamanho)] = nomes
    return comp, cores, info


_NOMES = {}


def acabamentos(modelo, tamanho):
    """Nome da cor de cada face (na ordem das faces), para o brilho do material."""
    if (modelo, tamanho) not in _NOMES:
        gerar(modelo, tamanho)
    return _NOMES[(modelo, tamanho)]


# ------------------------------------------------------------------ objeto no documento
class Componente:
    """Componente pronto: Modelo e Tamanho escolhem o desenho; a geometria não é para editar."""

    def __init__(self, obj, modelo, tamanho):
        obj.Proxy = self
        self._props(obj)
        obj.Modelo = modelo
        cat, m = MODELOS[modelo]
        obj.Tamanho = list(m[2])
        obj.Tamanho = tamanho
        obj.Categoria = dict((c[0], c[1]) for c in CATALOGO)[cat]
        obj.Nome = m[1]

    def _props(self, obj):
        def add(tipo, nome, dica, ro=False):
            if nome not in obj.PropertiesList:
                obj.addProperty(tipo, nome, "Componente", dica)
            if ro:
                obj.setEditorMode(nome, 1)
        add("App::PropertyString", "Modelo", "Identificador do modelo", True)
        add("App::PropertyEnumeration", "Tamanho", "Tamanho (trocar redesenha o componente)")
        add("App::PropertyString", "Categoria", "Categoria do catálogo", True)
        add("App::PropertyString", "Nome", "Descrição para a lista de materiais", True)
        add("App::PropertyStringList", "Dados", "Medidas principais (representativas)", True)

    def execute(self, obj):
        if not obj.Modelo or obj.Modelo not in MODELOS:
            return
        forma, cores, info = gerar(obj.Modelo, obj.Tamanho)
        pl = obj.Placement
        obj.Shape = forma
        obj.Placement = pl
        obj.Dados = ["%s: %s" % (k, v) for k, v in info.items()]
        self.cores = cores

    def onDocumentRestored(self, obj):
        self._props(obj)

    def dumps(self):
        return None

    def loads(self, state):
        return None


class VPComponente:
    def __init__(self, vobj):
        vobj.Proxy = self

    def attach(self, vobj):
        self.Object = vobj.Object

    def updateData(self, obj, prop):
        if prop == "Shape":
            aplicar_cores(obj)

    def getIcon(self):
        import PrumoUtil
        return PrumoUtil.icone("componentes.svg")

    def dumps(self):
        return None

    def loads(self, state):
        return None


def aplicar_cores(obj):
    try:
        cores = getattr(obj.Proxy, "cores", None)
        if not cores or (obj.Modelo, obj.Tamanho) not in _NOMES:
            _f, cores, _i = gerar(obj.Modelo, obj.Tamanho)
        if len(cores) == len(obj.Shape.Faces):
            import FreeCADGui  # noqa: F401
            nomes = acabamentos(obj.Modelo, obj.Tamanho)
            mats = []
            for c, nome in zip(cores, nomes):
                m = FreeCAD.Material()
                m.DiffuseColor = c
                m.AmbientColor = tuple(x * 0.35 for x in c)
                brilho, refl = ACABAMENTO.get(nome, (0.25, (0.35, 0.35, 0.35)))
                m.Shininess = brilho
                m.SpecularColor = refl
                if nome == "transparente":
                    m.Transparency = 0.55
                mats.append(m)
            obj.ViewObject.ShapeAppearance = mats
    except Exception:
        pass


def inserir(doc, modelo, tamanho, posicao=None):
    o = doc.addObject("Part::FeaturePython", "Componente")
    Componente(o, modelo, tamanho)
    o.Label = MODELOS[modelo][1][1].split(" (")[0] + " " + tamanho
    if FreeCAD.GuiUp:
        VPComponente(o.ViewObject)
    if posicao is not None:
        o.Placement.Base = posicao
    doc.recompute()
    if FreeCAD.GuiUp:
        aplicar_cores(o)
    return o


# ------------------------------------------------------------------ janela e comandos
ICONE_CATEGORIA = {"incendio": "comp_extintor.svg", "icamento": "comp_talha.svg", "motores": "comp_motor.svg", "compressores": "comp_compressor.svg",
                   "valvulas": "comp_valvula.svg", "caldeiras": "comp_caldeira.svg", "altura": "comp_trole.svg",
                   "ar": "comp_ar.svg", "secadores": "comp_secador.svg", "pessoas": "comp_pessoa.svg",
                   "transmissao": "comp_rolamento.svg", "outros": "comp_outros.svg"}


def ponto_da_selecao():
    """Onde inserir: o vértice, o centro da aresta/face selecionada ou o ponto clicado; senão a origem."""
    try:
        import FreeCADGui
        for so in FreeCADGui.Selection.getSelectionEx():
            if so.PickedPoints:
                return so.PickedPoints[0]
            for sub in so.SubObjects:
                if sub.ShapeType == "Vertex":
                    return sub.Point
                return sub.CenterOfMass if hasattr(sub, "CenterOfMass") else sub.BoundBox.Center
    except Exception:
        pass
    return None


if FreeCAD.GuiUp:
    import FreeCADGui
    from PySide import QtCore, QtGui, QtWidgets

    class JanelaComponentes(QtWidgets.QDialog):
        def __init__(self, categoria=None, parent=None):
            super().__init__(parent or FreeCADGui.getMainWindow())
            import PrumoUI as UI
            import PrumoUtil
            self.setObjectName("PrumoUI")
            self.setStyleSheet(UI.qss())
            self.setWindowTitle("Componentes")
            self.resize(760, 480)
            lay = QtWidgets.QHBoxLayout(self)
            self.cats = QtWidgets.QListWidget()
            self.cats.setObjectName("PrumoComponentesCategorias")
            self.cats.setIconSize(QtCore.QSize(28, 28))
            self.cats.setFixedWidth(200)
            for cid, nome, _ms in CATALOGO:
                it = QtWidgets.QListWidgetItem(QtGui.QIcon(PrumoUtil.icone(ICONE_CATEGORIA[cid])), nome)
                it.setData(QtCore.Qt.UserRole, cid)
                self.cats.addItem(it)
            lay.addWidget(self.cats)
            meio = QtWidgets.QVBoxLayout()
            self.modelos = QtWidgets.QListWidget()
            self.modelos.setObjectName("PrumoComponentesModelos")
            meio.addWidget(self.modelos, 1)
            linha = QtWidgets.QHBoxLayout()
            self.rot_tam = QtWidgets.QLabel("Tamanho")
            self.tamanho = QtWidgets.QComboBox()
            linha.addWidget(self.rot_tam)
            linha.addWidget(self.tamanho, 1)
            meio.addLayout(linha)
            self.info = QtWidgets.QLabel("")
            self.info.setWordWrap(True)
            self.info.setTextFormat(QtCore.Qt.RichText)
            self.info.setMinimumHeight(110)
            self.info.setAlignment(QtCore.Qt.AlignTop)
            meio.addWidget(self.info)
            nota = QtWidgets.QLabel("Componentes para leiaute e apresentação: medidas representativas. "
                                    "Selecione um ponto ou face antes para inserir ali.")
            nota.setObjectName("PrumoSub")
            nota.setWordWrap(True)
            meio.addWidget(nota)
            bts = QtWidgets.QHBoxLayout()
            bts.addStretch(1)
            fechar = QtWidgets.QPushButton("Fechar")
            fechar.clicked.connect(self.reject)
            self.bt_inserir = QtWidgets.QPushButton("Inserir")
            self.bt_inserir.setObjectName("PrumoPrimario")
            self.bt_inserir.setDefault(True)
            self.bt_inserir.clicked.connect(self.inserir)
            bts.addWidget(fechar)
            bts.addWidget(self.bt_inserir)
            meio.addLayout(bts)
            lay.addLayout(meio, 1)
            self.cats.currentRowChanged.connect(self._categoria)
            self.modelos.currentRowChanged.connect(self._modelo)
            self.modelos.itemDoubleClicked.connect(lambda _i: self.inserir())
            self.tamanho.currentIndexChanged.connect(lambda _i: self._mostrar())
            ids = [c[0] for c in CATALOGO]
            self.cats.setCurrentRow(ids.index(categoria) if categoria in ids else 0)
            self.inseridos = []

        def _categoria(self, i):
            self.modelos.clear()
            if i < 0:
                return
            for mid, nome, _t, _f in CATALOGO[i][2]:
                it = QtWidgets.QListWidgetItem(nome)
                it.setData(QtCore.Qt.UserRole, mid)
                self.modelos.addItem(it)
            self.modelos.setCurrentRow(0)

        def modelo(self):
            it = self.modelos.currentItem()
            return it.data(QtCore.Qt.UserRole) if it is not None else None

        def _modelo(self, _i):
            mid = self.modelo()
            self.tamanho.blockSignals(True)
            self.tamanho.clear()
            if mid:
                self.tamanho.addItems(MODELOS[mid][1][2])
                self.rot_tam.setText("Tamanho (%s)" % UNIDADE_TAMANHO.get(mid, "modelo"))
            self.tamanho.blockSignals(False)
            self._mostrar()

        def _mostrar(self):
            mid, tam = self.modelo(), self.tamanho.currentText()
            if not mid or not tam:
                self.info.setText("")
                return
            try:
                _p, info = MODELOS[mid][1][3](tam)
                self.info.setText("<b>%s</b><br>%s" % (MODELOS[mid][1][1], "<br>".join(
                    "%s: %s" % (k, v) for k, v in info.items())))
            except Exception as exc:
                self.info.setText("Não foi possível montar: %s" % exc)

        def inserir(self):
            mid, tam = self.modelo(), self.tamanho.currentText()
            if not mid:
                return None
            doc = FreeCAD.ActiveDocument or FreeCAD.newDocument()
            doc.openTransaction("Inserir componente")
            try:
                o = inserir(doc, mid, tam, ponto_da_selecao())
            finally:
                doc.commitTransaction()
            self.inseridos.append(o)
            try:
                FreeCADGui.Selection.clearSelection()
                FreeCADGui.Selection.addSelection(o)
                if len(doc.Objects) == 1:
                    FreeCADGui.SendMsgToActiveView("ViewFit")
            except Exception:
                pass
            return o

    _JANELA = {"j": None}

    def abrir(categoria=None):
        j = JanelaComponentes(categoria)
        _JANELA["j"] = j
        j.show()
        return j

    class CmdComponentes:
        def __init__(self, categoria=None, nome="Componentes"):
            self.categoria, self.nome = categoria, nome

        def GetResources(self):
            import PrumoUtil
            ic = ICONE_CATEGORIA.get(self.categoria, "componentes.svg")
            return {"Pixmap": PrumoUtil.icone(ic), "MenuText": self.nome,
                    "ToolTip": "Inserir %s pronto no projeto (modelo para leiaute; medidas representativas, exceto as de "
                               "contorno dos rolamentos, conferidas em catálogo)."
                               % (self.nome.lower() if self.categoria else "componente")}

        def IsActive(self):
            return True

        def Activated(self):
            abrir(self.categoria)

    def registrar_comandos():
        FreeCADGui.addCommand("Prumo_Componentes", CmdComponentes())
        for cid, nome, _ms in CATALOGO:
            FreeCADGui.addCommand("Prumo_Componentes_" + cid, CmdComponentes(cid, nome))
