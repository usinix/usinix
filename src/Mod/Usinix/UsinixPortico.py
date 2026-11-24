# SPDX-License-Identifier: LGPL-2.1-or-later
"""Cálculo de pórticos espaciais pelo método da rigidez direta (análise linear de 1ª ordem).

Unidades internas: N, mm, MPa (N/mm²). Cargas de entrada: kN, kN/m, kN·m (convertidas aqui).

Barras de Euler-Bernoulli com 6 graus de liberdade por nó (3 deslocamentos e 3 rotações). Eixos
locais da barra: x ao longo da barra; y e z nos eixos principais da seção (para perfis I e U,
z = altura do perfil e y = largura: a flexão "em torno de y" usa a maior inércia).

Hipóteses (vão para a memória de cálculo):
- análise elástica linear de 1ª ordem (sem efeito P-Δ), material elástico;
- barras ligadas rigidamente nos nós, salvo as liberações (rótulas) dadas nas pontas, tratadas
  por condensação estática da matriz da barra;
- as barras ficam sobre as linhas do esqueleto (excentricidades do ponto de fixação desprezadas);
- deformação por cortante desprezada.
"""

import math

import numpy as np

G_GRAV = 9.80665e-3          # N/kg → peso em N por kg (1 kgf = 9,80665 N); massa_kgm·G_GRAV = N/mm

# Gauss-Legendre de 4 pontos: exato até grau 7 (carga linear × funções cúbicas)
GAUSS4 = [(-0.8611363115940526, 0.3478548451374538), (-0.3399810435848563, 0.6521451548625461),
          (0.3399810435848563, 0.6521451548625461), (0.8611363115940526, 0.3478548451374538)]

# fração da rigidez que fica numa barra só de tração comprimida (ver montar, em resolver)
RESTO_TRACAO = 1e-6

# graus locais de cada ponta: 0-2 deslocamentos, 3 torção, 4-5 flexão (giro em y e z)
ROTULA_I = (4, 5)
ROTULA_J = (10, 11)
TRELICA = (4, 5, 10, 11, 9)       # rótula nas duas pontas e a torção solta numa delas


def _q_em(carga, s):
    """Valor (vetor local, N/mm) da carga distribuída linear `carga` = (a, b, q1, q2) em s."""
    a, b, q1, q2 = carga
    t = (s - a) / (b - a) if b > a else 0.0
    return q1 + (q2 - q1) * t


def _gauss(carga, lo, hi):
    """Carga distribuída em [lo, hi] (dentro de [a, b]) como forças concentradas equivalentes
    nos pontos de Gauss: [(s, força N)]. Exata para integrar com polinômios até grau 6."""
    a, b, _q1, _q2 = carga
    lo, hi = max(lo, a), min(hi, b)
    if hi <= lo:
        return []
    m, h = (lo + hi) / 2.0, (hi - lo) / 2.0
    return [(m + h * g, w * h * _q_em(carga, m + h * g)) for g, w in GAUSS4]


def resultante_ate(dist, pont, x):
    """Soma das forças (3) e momento (3) em relação ao ponto x de tudo o que age em [0, x] da
    barra (cargas distribuídas e concentradas), em eixos locais."""
    s = np.zeros(3)
    m = np.zeros(3)
    for carga in dist:
        for xs, P in _gauss(carga, 0.0, x):
            s += P
            m += np.array([0.0, (x - xs) * P[2], -(x - xs) * P[1]])
    for a, P in pont:
        if a < x:
            s += P
            m += np.array([0.0, (x - a) * P[2], -(x - a) * P[1]])
    return s, m


def flecha_particular(dist, pont, x, L, EIz, EIy):
    """(v, w) da barra biengastada sob as cargas no vão (parcela que se soma às funções de forma)."""
    v = w = 0.0
    for carga in dist:
        for lo, hi in ((0.0, x), (x, L)):        # divide no ponto: o integrando muda de forma em x
            for xs, P in _gauss(carga, lo, hi):
                v += _flecha_pontual_biengastada(P[1], xs, x, L, EIz)
                w += _flecha_pontual_biengastada(P[2], xs, x, L, EIy)
    for a, P in pont:
        v += _flecha_pontual_biengastada(P[1], a, x, L, EIz)
        w += _flecha_pontual_biengastada(P[2], a, x, L, EIy)
    return v, w


def _condensar(kk, fe, liberados):
    """Condensação estática dos graus liberados (rótulas): (k', fe', recuperação)."""
    if not liberados:
        return kk, fe, None
    r = sorted(liberados)
    c = [i for i in range(12) if i not in liberados]
    krr = kk[np.ix_(r, r)]
    try:
        inv = np.linalg.inv(krr)
    except np.linalg.LinAlgError:
        inv = np.linalg.pinv(krr)
    krc = kk[np.ix_(r, c)]
    kcr = kk[np.ix_(c, r)]
    k2 = np.zeros((12, 12))
    k2[np.ix_(c, c)] = kk[np.ix_(c, c)] - kcr @ inv @ krc
    f2 = np.zeros(12)
    f2[c] = fe[c] - kcr @ inv @ fe[r]
    return k2, f2, (r, c, inv, krc, fe[r].copy())


class Secao:
    """Rigidez da seção: A, Iy (maior, flexão no plano x-z local), Iz, J em mm."""

    def __init__(self, A, Iy, Iz, J, E=200000.0, Gc=77000.0, massa_kgm=0.0, nome=""):
        self.A, self.Iy, self.Iz, self.J = float(A), float(Iy), float(Iz), float(J)
        self.E, self.G = float(E), float(Gc)
        self.massa_kgm = float(massa_kgm)
        self.nome = nome


class Barra:
    """Barra entre os nós i e j. eixo_z: vetor que dá a direção do eixo local z (altura da seção)."""

    def __init__(self, i, j, secao, eixo_z, nome="", origem=None, liberados=(), so_tracao=False):
        self.liberados = tuple(sorted(set(liberados)))   # graus locais soltos (rótulas): 4, 5, 9, 10, 11
        self.so_tracao = bool(so_tracao)                 # contraventamento: sai do modelo se comprimir
        self.i, self.j = int(i), int(j)
        self.secao = secao
        self.eixo_z = np.array(eixo_z, dtype=float)
        self.nome = nome
        self.origem = origem            # (índice da barra do Usinix, x inicial ao longo dela em mm)


class Caso:
    """Caso de carga: cargas nos nós, distribuídas e concentradas nas barras."""

    def __init__(self, nome, tipo="permanente", peso_proprio=False):
        self.nome = nome
        self.tipo = tipo
        self.peso_proprio = bool(peso_proprio)
        self.nos = []          # (nó, [Fx, Fy, Fz] kN, [Mx, My, Mz] kN·m) — eixos globais
        self.distribuidas = []  # (barra, [qx, qy, qz] kN/m, global=True[, a, b, [q2]]): linear de a a b (mm)
        self.pontuais = []      # (barra, a em mm a partir do nó i, [Px, Py, Pz] kN, global=True)


class Modelo:
    def __init__(self):
        self.nos = []           # np.array([x, y, z]) mm
        self.barras = []
        self.apoios = {}        # nó: [6 bools] (ux, uy, uz, rx, ry, rz) travados
        self.molas = {}         # nó: [6 rigidezes] N/mm (deslocamentos) e N·mm/rad (giros), eixos globais
        self.massas = {}        # nó: massa concentrada extra (t = 1000 kg), nos três deslocamentos

    def no(self, p, tol=1e-3):
        p = np.array(p, dtype=float)
        for k, q in enumerate(self.nos):
            if np.linalg.norm(q - p) < tol:
                return k
        self.nos.append(p)
        return len(self.nos) - 1

    # ------------------------------------------------------------ geometria da barra
    def eixos(self, b):
        """Matriz 3×3 com as linhas x, y, z locais (em coordenadas globais) e o comprimento."""
        pi, pj = self.nos[b.i], self.nos[b.j]
        x = pj - pi
        L = np.linalg.norm(x)
        if L < 1e-9:
            raise ValueError("barra %s com comprimento zero" % b.nome)
        x = x / L
        z = b.eixo_z - x * np.dot(b.eixo_z, x)
        if np.linalg.norm(z) < 1e-9:
            z = np.array([0.0, 0.0, 1.0]) if abs(x[2]) < 0.99 else np.array([1.0, 0.0, 0.0])
            z = z - x * np.dot(z, x)
        z = z / np.linalg.norm(z)
        y = np.cross(z, x)
        return np.vstack([x, y, z]), L

    @staticmethod
    def rigidez_local(s, L):
        E, G, A, Iy, Iz, J = s.E, s.G, s.A, s.Iy, s.Iz, s.J
        k = np.zeros((12, 12))
        ea = E * A / L
        gj = G * J / L
        k[0, 0] = k[6, 6] = ea
        k[0, 6] = k[6, 0] = -ea
        k[3, 3] = k[9, 9] = gj
        k[3, 9] = k[9, 3] = -gj
        # flexão no plano x-y (em torno de z): v, θz
        a, b, c, d = 12 * E * Iz / L ** 3, 6 * E * Iz / L ** 2, 4 * E * Iz / L, 2 * E * Iz / L
        for (r, cc, val) in ((1, 1, a), (1, 5, b), (1, 7, -a), (1, 11, b), (5, 5, c), (5, 7, -b), (5, 11, d),
                             (7, 7, a), (7, 11, -b), (11, 11, c)):
            k[r, cc] = k[cc, r] = val
        # flexão no plano x-z (em torno de y): w, θy
        a, b, c, d = 12 * E * Iy / L ** 3, 6 * E * Iy / L ** 2, 4 * E * Iy / L, 2 * E * Iy / L
        for (r, cc, val) in ((2, 2, a), (2, 4, -b), (2, 8, -a), (2, 10, -b), (4, 4, c), (4, 8, b), (4, 10, d),
                             (8, 8, a), (8, 10, b), (10, 10, c)):
            k[r, cc] = k[cc, r] = val
        return k

    @staticmethod
    def rigidez_geometrica(N, L):
        """Matriz geométrica (consistente) da barra com força normal N (tração +), eixos locais."""
        kg = np.zeros((12, 12))
        if N == 0:
            return kg
        c = N / L
        A = np.array([[6 / 5, L / 10, -6 / 5, L / 10], [L / 10, 2 * L * L / 15, -L / 10, -L * L / 30],
                      [-6 / 5, -L / 10, 6 / 5, -L / 10], [L / 10, -L * L / 30, -L / 10, 2 * L * L / 15]]) * c
        B = np.array([[6 / 5, -L / 10, -6 / 5, -L / 10], [-L / 10, 2 * L * L / 15, L / 10, -L * L / 30],
                      [-6 / 5, L / 10, 6 / 5, L / 10], [-L / 10, -L * L / 30, L / 10, 2 * L * L / 15]]) * c
        for M, idx in ((A, (1, 5, 7, 11)), (B, (2, 4, 8, 10))):
            for a, ia in enumerate(idx):
                for b, ib in enumerate(idx):
                    kg[ia, ib] += M[a, b]
        return kg

    @staticmethod
    def _T(R):
        T = np.zeros((12, 12))
        for n in range(4):
            T[3 * n:3 * n + 3, 3 * n:3 * n + 3] = R
        return T

    # ------------------------------------------------------------ cargas na barra (locais)
    def _cargas_locais(self, caso, nb, b, R, L):
        """[(a, b, q1, q2) distribuída linear local N/mm], [(a, P local N)] da barra nb no caso."""
        dist, pont = [], []
        if caso.peso_proprio and b.secao.massa_kgm:
            q = R @ np.array([0.0, 0.0, -b.secao.massa_kgm * G_GRAV])      # N/mm (kg/m · g)
            dist.append((0.0, L, q, q.copy()))
        for item in caso.distribuidas:
            k, q, glob = item[0], item[1], item[2]
            if k != nb:
                continue
            q1 = np.array(q, dtype=float)          # kN/m = N/mm
            a = float(item[3]) if len(item) > 3 and item[3] is not None else 0.0
            bb = float(item[4]) if len(item) > 4 and item[4] is not None else L
            q2 = np.array(item[5], dtype=float) if len(item) > 5 and item[5] is not None else q1.copy()
            a, bb = max(0.0, min(a, L)), max(0.0, min(bb, L))
            if bb <= a:
                continue
            if glob:
                q1, q2 = R @ q1, R @ q2
            dist.append((a, bb, q1, q2))
        for (k, a, P, glob) in caso.pontuais:
            if k == nb:
                P = np.array(P, dtype=float) * 1000.0
                pont.append((float(a), R @ P if glob else P))
        return dist, pont

    @staticmethod
    def _engaste_perfeito(dist, pont, L):
        """Forças de engaste perfeito (12) em eixos locais: cargas distribuídas lineares (pelos pontos
        de Gauss, exato) e concentradas."""
        f = np.zeros(12)
        tudo = list(pont)
        for carga in dist:
            tudo += _gauss(carga, 0.0, L)
        for a, P in tudo:
            a = min(max(a, 0.0), L)
            b = L - a
            Px, Py, Pz = P
            f[0] += -Px * b / L
            f[6] += -Px * a / L
            f[1] += -Py * b * b * (3 * a + b) / L ** 3
            f[7] += -Py * a * a * (a + 3 * b) / L ** 3
            f[5] += -Py * a * b * b / L ** 2
            f[11] += Py * a * a * b / L ** 2
            f[2] += -Pz * b * b * (3 * a + b) / L ** 3
            f[8] += -Pz * a * a * (a + 3 * b) / L ** 3
            f[4] += Pz * a * b * b / L ** 2
            f[10] += -Pz * a * a * b / L ** 2
        return f

    @staticmethod
    def massa_local(m, L, r2):
        """Matriz de massa consistente (12) da barra: m em t/mm, r2 = (Iy + Iz)/A para a torção."""
        M = np.zeros((12, 12))
        a = m * L
        M[0, 0] = M[6, 6] = a / 3.0
        M[0, 6] = M[6, 0] = a / 6.0
        M[3, 3] = M[9, 9] = a * r2 / 3.0
        M[3, 9] = M[9, 3] = a * r2 / 6.0
        c = a / 420.0
        # flexão no plano x-y (v, θz): graus 1, 5, 7, 11
        for (i, j, v) in ((1, 1, 156), (1, 5, 22 * L), (1, 7, 54), (1, 11, -13 * L), (5, 5, 4 * L * L),
                          (5, 7, 13 * L), (5, 11, -3 * L * L), (7, 7, 156), (7, 11, -22 * L), (11, 11, 4 * L * L)):
            M[i, j] = M[j, i] = c * v
        # flexão no plano x-z (w, θy): graus 2, 4, 8, 10 (sinais trocados nos giros)
        for (i, j, v) in ((2, 2, 156), (2, 4, -22 * L), (2, 8, 54), (2, 10, 13 * L), (4, 4, 4 * L * L),
                          (4, 8, -13 * L), (4, 10, -3 * L * L), (8, 8, 156), (8, 10, 22 * L), (10, 10, 4 * L * L)):
            M[i, j] = M[j, i] = c * v
        return M

    def modos(self, n=6, massas_dist=None):
        """Frequências naturais (Hz) e formas modais [(f, vetor de deslocamentos ndof)].
        Massa: peso próprio das barras (massa linear da seção) + massas_dist {barra: t/mm} (cargas
        permanentes convertidas em massa) + massas concentradas dos nós (self.massas)."""
        from scipy.linalg import eigh
        ndof = 6 * len(self.nos)
        K = np.zeros((ndof, ndof))
        M = np.zeros((ndof, ndof))
        for nb, b in enumerate(self.barras):
            R, L = self.eixos(b)
            T = self._T(R)
            k = self.rigidez_local(b.secao, L)
            k2, _f2, _rec = _condensar(k, np.zeros(12), b.liberados)
            m = b.secao.massa_kgm * 1e-6 + (massas_dist or {}).get(nb, 0.0)
            r2 = (b.secao.Iy + b.secao.Iz) / b.secao.A
            ml = self.massa_local(m, L, r2)
            idx = list(range(6 * b.i, 6 * b.i + 6)) + list(range(6 * b.j, 6 * b.j + 6))
            K[np.ix_(idx, idx)] += T.T @ k2 @ T
            M[np.ix_(idx, idx)] += T.T @ ml @ T
        for no, ks in self.molas.items():
            for g in range(6):
                K[6 * no + g, 6 * no + g] += float(ks[g])
        for no, mt in self.massas.items():
            for g in range(3):
                M[6 * no + g, 6 * no + g] += float(mt)
        presos = np.zeros(ndof, dtype=bool)
        for no, travas in self.apoios.items():
            for g in range(6):
                if travas[g]:
                    presos[6 * no + g] = True
        diag = np.abs(np.diag(K))
        tol = 1e-9 * max(1.0, diag.max())
        for g in range(ndof):
            if not presos[g] and diag[g] < tol and g % 6 >= 3:
                presos[g] = True
        livres = ~presos
        molas = self._molas_de_giro(K, livres)
        if molas is not None:
            K = K + molas
        Kf = K[np.ix_(livres, livres)]
        Mf = M[np.ix_(livres, livres)]
        # giros sem inércia (nó só de pontas rotuladas): um pouquinho de inércia para a matriz ser positiva
        dm = np.diag(Mf).copy()
        pequeno = dm <= 1e-12 * max(1e-30, dm.max())
        Mf[np.diag_indices_from(Mf)] += np.where(pequeno, 1e-9 * dm.max(), 0.0)
        n = min(n, Kf.shape[0])
        w2, vec = eigh(Kf, Mf, subset_by_index=[0, n - 1])
        res = []
        for k in range(n):
            phi = np.zeros(ndof)
            phi[livres] = vec[:, k]
            f = math.sqrt(max(w2[k], 0.0)) / (2 * math.pi)
            res.append((f, phi))
        return res

    def _pares_em_x(self, grupos):
        """Pares de barras só de tração que se cruzam (as duas diagonais de um X)."""
        pontas = {}
        for ch, membros in grupos.items():
            nos = [self.barras[nb].i for nb in membros] + [self.barras[nb].j for nb in membros]
            pts = [np.array(self.nos[q], dtype=float) for q in nos]
            d = pts[1] - pts[0] if len(pts) > 1 else np.zeros(3)
            d = d / max(float(np.linalg.norm(d)), 1e-12)
            proj = [float(p @ d) for p in pts]
            pontas[ch] = (pts[int(np.argmin(proj))], pts[int(np.argmax(proj))])
        chs = list(grupos)
        pares = []
        for a in range(len(chs)):
            for b in range(a + 1, len(chs)):
                (a0, a1), (b0, b1) = pontas[chs[a]], pontas[chs[b]]
                if _cruzam(a0, a1, b0, b1):
                    pares.append((chs[a], chs[b]))
        return pares

    def _texto_mecanismo(self, Kff, livres):
        """Mensagem do mecanismo apontando o nó e a direção que se movem sem resistência."""
        txt = "a estrutura é instável (mecanismo): faltam apoios ou travamentos"
        try:
            w, v = np.linalg.eigh((Kff + Kff.T) / 2.0)
            modo = v[:, 0]
            ids = np.where(livres)[0]
            trans = [(abs(modo[k]), ids[k]) for k in range(len(ids)) if ids[k] % 6 < 3]
            giros = [(abs(modo[k]), ids[k]) for k in range(len(ids)) if ids[k] % 6 >= 3]
            if giros and (not trans or max(giros)[0] > 3.0 * max(trans)[0]):
                # modo de giro puro: a barra gira em torno de um eixo (torção da viga apoiada, rótulas demais)
                _a, g = max(giros)
                q = self.nos[g // 6]
                eixo = "XYZ"[g % 6 - 3]
                return txt + (": o nó (%.0f; %.0f; %.0f) gira em torno de %s sem nada que o segure. Se for uma viga "
                              "apoiada girando no próprio eixo (torção), use \"Apoio simples (garfo)\" num apoio, "
                              "que segura esse giro; senão, confira as rótulas." % (q[0], q[1], q[2], eixo))
            if trans and max(trans)[0] > 1e-3:
                _a, g = max(trans)
                q = self.nos[g // 6]
                txt += ": o nó (%.0f; %.0f; %.0f) se move em %s sem nada que o segure" % (q[0], q[1], q[2],
                                                                                        "XYZ"[g % 6])
            else:
                g = ids[int(np.argmax(np.abs(modo)))]
                q = self.nos[g // 6]
                txt += ": o nó (%.0f; %.0f; %.0f) gira sem nada que o segure (rótulas demais?)" % (q[0], q[1], q[2])
        except Exception:
            pass
        return txt

    def _molas_de_giro(self, K, livres):
        """Matriz de molas fracas nos modos só de giro sem rigidez (nós de barras rotuladas)."""
        if not any(b.liberados for b in self.barras):
            return None
        chave = (len(self.nos), tuple(b.liberados for b in self.barras),
                 tuple(sorted((k, tuple(v)) for k, v in self.apoios.items())))
        if getattr(self, "_molas_chave", None) == chave:
            return self._molas_cache
        # todos os giros livres: a rótula de uma barra pode soltar o giro de outra (ex.: pilar
        # rotulado na base com as vigas rotuladas nele gira em torno do próprio eixo)
        sub = [g for g in range(K.shape[0]) if g % 6 >= 3 and livres[g]]
        molas = None
        if sub:
            Ks = K[np.ix_(sub, sub)]
            w, v = np.linalg.eigh((Ks + Ks.T) / 2.0)
            escala = max(1.0, float(np.max(np.abs(np.diag(K)))))
            for k in range(len(w)):
                if w[k] > 1e-9 * escala:
                    break
                vec = np.zeros(K.shape[0])
                vec[sub] = v[:, k]
                if np.linalg.norm(K @ vec) > 1e-6 * escala:
                    continue                      # o modo mexe com outros graus: não é só giro solto
                if molas is None:
                    molas = np.zeros_like(K)
                molas += 1e-6 * escala * np.outer(vec, vec)
        self._molas_chave = chave
        self._molas_cache = molas
        return molas

    # ------------------------------------------------------------ solução
    def cargas_gravitacionais(self, caso_ou_combinacao):
        """Carga vertical para baixo (N) que chega a cada nó na combinação: cargas nodais mais as
        reações de engaste perfeito das barras (cada barra entrega a sua carga às duas pontas)."""
        partes = caso_ou_combinacao if isinstance(caso_ou_combinacao, (list, tuple)) else [(caso_ou_combinacao, 1.0)]
        Fz = np.zeros(len(self.nos))
        for nb, b in enumerate(self.barras):
            R, L = self.eixos(b)
            T = self._T(R)
            fe = np.zeros(12)
            for caso, fator in partes:
                dist, pont = self._cargas_locais(caso, nb, b, R, L)
                dist = [(a, bb, q1 * fator, q2 * fator) for a, bb, q1, q2 in dist]
                pont = [(a, P * fator) for a, P in pont]
                fe += self._engaste_perfeito(dist, pont, L)
            g = -(T.T @ fe)
            Fz[b.i] += g[2]
            Fz[b.j] += g[8]
        for caso, fator in partes:
            for (no, forca, _m) in caso.nos:
                Fz[no] += float(forca[2]) * 1000.0 * fator
        return np.maximum(-Fz, 0.0)

    def resolver(self, caso_ou_combinacao, segunda_ordem=False, rigidez=1.0):
        """Resolve um caso ou uma combinação [(caso, fator)]. Retorna Resultado.

        segunda_ordem=True: análise P-Δ (rigidez geométrica, iterada até convergir); o resultado
        traz o fator de amplificação dos deslocamentos (2ª ordem / 1ª ordem).
        rigidez: fator sobre a rigidez elástica das barras (0,8 na média deslocabilidade, NBR 8800:2024
        4.10.7); a rigidez geométrica e as molas não mudam."""
        partes = caso_ou_combinacao if isinstance(caso_ou_combinacao, (list, tuple)) else [(caso_ou_combinacao, 1.0)]
        n = len(self.nos)
        ndof = 6 * n
        F_nos = np.zeros(ndof)
        info = []
        for nb, b in enumerate(self.barras):
            R, L = self.eixos(b)
            T = self._T(R)
            k = self.rigidez_local(b.secao, L) * float(rigidez)
            idx = list(range(6 * b.i, 6 * b.i + 6)) + list(range(6 * b.j, 6 * b.j + 6))
            dist_t, pont_t, fe_t = [], [], np.zeros(12)
            for caso, fator in partes:
                dist, pont = self._cargas_locais(caso, nb, b, R, L)
                dist = [(a, bb, q1 * fator, q2 * fator) for a, bb, q1, q2 in dist]
                pont = [(a, P * fator) for a, P in pont]
                fe_t += self._engaste_perfeito(dist, pont, L)
                dist_t += dist
                pont_t += pont
            info.append((R, L, T, k, fe_t, dist_t, pont_t, idx, b.liberados))
        for caso, fator in partes:
            for (no, forca, momento) in caso.nos:
                F_nos[6 * no:6 * no + 3] += np.array(forca, dtype=float) * 1000.0 * fator
                F_nos[6 * no + 3:6 * no + 6] += np.array(momento, dtype=float) * 1e6 * fator

        ativos = [True] * len(info)

        def montar(kgs):
            K = np.zeros((ndof, ndof))
            F = F_nos.copy()
            cond = []
            for nb, (R, L, T, k, fe, _d, _p, idx, lib) in enumerate(info):
                k2, f2, rec = _condensar(k + kgs[nb], fe, lib)
                if not ativos[nb]:
                    # barra só de tração comprimida: sai o esforço normal (o peso dela ainda vai aos nós). Fica a
                    # flexão (a barra continua lá e segura de lado o nó do cruzamento de um X, que senão vira
                    # mecanismo quando a diagonal comprimida é a contínua) e um resto da rigidez axial
                    # (RESTO_TRACAO), para as duas diagonais comprimidas juntas só pelo peso não soltarem o
                    # quadro. Com carga lateral, a diagonal tracionada volta inteira.
                    ax = np.ix_([0, 6], [0, 6])
                    k2i = k2.copy()
                    k2i[ax] *= RESTO_TRACAO
                    K[np.ix_(idx, idx)] += T.T @ k2i @ T
                    F[idx] -= T.T @ f2
                    k2r = k2.copy()
                    k2r[[0, 6], :] = 0.0                            # normal nulo; a flexão do peso continua
                    cond.append((k2r, f2, rec))
                    continue
                K[np.ix_(idx, idx)] += T.T @ k2 @ T
                F[idx] -= T.T @ f2
                cond.append((k2, f2, rec))
            for no, ks in self.molas.items():
                for g in range(6):
                    K[6 * no + g, 6 * no + g] += float(ks[g])
            return K, F, cond

        kgs = [np.zeros((12, 12)) for _ in info]
        K, F, cond = montar(kgs)
        presos = np.zeros(ndof, dtype=bool)
        for no, travas in self.apoios.items():
            for g in range(6):
                if travas[g]:
                    presos[6 * no + g] = True
        if not presos.any() and not any(any(ks) for ks in self.molas.values()):
            raise ValueError("a estrutura não tem apoios: clique nos nós para apoiar")
        # giro de nó onde só chegam pontas rotuladas (ex.: nó de treliça): não tem rigidez e não
        # influi em nada; fica travado. Deslocamento sem rigidez é nó solto: erro.
        diag = np.abs(np.diag(K))
        tol = 1e-9 * max(1.0, diag.max())
        self.giros_travados = []
        for g in range(ndof):
            if not presos[g] and diag[g] < tol:
                if g % 6 >= 3:
                    presos[g] = True
                    self.giros_travados.append(g)
                else:
                    q = self.nos[g // 6]
                    raise ValueError("o nó (%.0f; %.0f; %.0f) se desloca em %s sem nada que o segure: nó solto, ou "
                                     "só barras de treliça chegando nele fora do plano delas (falta travamento)"
                                     % (q[0], q[1], q[2], "XYZ"[g % 6]))
        livres = ~presos
        # rótulas podem deixar giros sem rigidez em direções inclinadas (ex.: barra de treliça girando
        # em torno do próprio eixo): são modos de corpo rígido só de giro, sem carga que os excite.
        # Uma mola fraquinha nesses modos (achados uma vez por modelo) deixa o sistema resolvível.
        molas = self._molas_de_giro(K, livres)
        if molas is not None:
            K = K + molas
            self._molas = molas
        Kff = K[np.ix_(livres, livres)]
        try:
            uf = np.linalg.solve(Kff, F[livres])
        except np.linalg.LinAlgError:
            raise ValueError(self._texto_mecanismo(Kff, livres))
        if not np.all(np.isfinite(uf)) or (Kff.size and np.linalg.cond(Kff) > 1e15):
            raise ValueError(self._texto_mecanismo(Kff, livres))
        u = np.zeros(ndof)
        u[livres] = uf
        # barras só de tração: tira as comprimidas e devolve as que voltam a esticar, até estabilizar
        self.ciclos_tracao = 0
        self.tracao_sem_convergir = False
        self.folgadas = set()
        if any(b.so_tracao for b in self.barras):
            # a barra do Usinix (vários elementos: trechos e divisões) liga e desliga inteira; senão um elemento
            # desligado no meio corta a diagonal tracionada
            grupos = {}
            for nb, b in enumerate(self.barras):
                if b.so_tracao:
                    chave = ("barra", b.origem[0]) if b.origem is not None else ("elem", nb)
                    grupos.setdefault(chave, []).append(nb)
            # duas barras alinhadas que se encontram num nó (meia diagonal de um X partida no cruzamento) são a
            # mesma diagonal: ligam e desligam juntas
            chaves = list(grupos)

            def _dir(ch):
                b0 = self.barras[grupos[ch][0]]
                d = np.array(self.nos[b0.j], dtype=float) - np.array(self.nos[b0.i], dtype=float)
                return d / max(np.linalg.norm(d), 1e-12)

            def _nos(ch):
                return {self.barras[nb].i for nb in grupos[ch]} | {self.barras[nb].j for nb in grupos[ch]}
            juntou = True
            while juntou:
                juntou = False
                for a in range(len(chaves)):
                    for c in range(a + 1, len(chaves)):
                        ka, kc = chaves[a], chaves[c]
                        if abs(float(np.dot(_dir(ka), _dir(kc)))) > 0.9999 and _nos(ka) & _nos(kc):
                            grupos[ka] = grupos[ka] + grupos.pop(kc)
                            chaves.pop(c)
                            juntou = True
                            break
                    if juntou:
                        break
            # a diagonal só sai quando a compressão passa da carga de flambagem dela (Euler, biarticulada, no
            # comprimento todo): o pouco de compressão do encurtamento dos pilares não a tira, e o ciclo
            # liga/desliga fecha. Diagonal que troca de estado mais de 3 vezes fica ligada (lado seguro).
            ncr, trocas = {}, {}
            for chave, membros in grupos.items():
                Ltot = sum(info[nb][1] for nb in membros)
                sec = self.barras[membros[0]].secao
                ncr[chave] = math.pi ** 2 * sec.E * min(sec.Iy, sec.Iz) / max(Ltot, 1e-9) ** 2
                trocas[chave] = 0
            self.tracao_sem_convergir = False
            # X com as duas diagonais folgadas (só o peso: os pilares encurtam e as duas encurtam junto): na prática a
            # que esticar no primeiro deslocamento de lado segura a estrutura; sem nenhuma, o pórtico com base
            # rotulada virava mecanismo. Fica no modelo a que menos encurtou, marcada como folgada: entra na rigidez
            # e na estabilidade, mas a compressão dela (fictícia) sai zerada do resultado
            pares = self._pares_em_x(grupos)
            folgada_de = {}

            def _alonga(ch):
                tot = 0.0
                for nb in grupos[ch]:
                    R, L, T, k, fe, _d, _p, idx, lib = info[nb]
                    tot += (T @ u[idx])[6] - (T @ u[idx])[0]
                return tot

            def _folgas():
                novo = {}
                for ch in list(folgada_de.values()):
                    for nb in grupos[ch]:
                        ativos[nb] = False
                for ka, kb in pares:
                    if ativos[grupos[ka][0]] or ativos[grupos[kb][0]]:
                        continue
                    ch = ka if _alonga(ka) >= _alonga(kb) else kb
                    novo[(ka, kb)] = ch
                for ch in novo.values():
                    for nb in grupos[ch]:
                        ativos[nb] = True
                mudou = novo != folgada_de
                folgada_de.clear()
                folgada_de.update(novo)
                return mudou
            for self.ciclos_tracao in range(1, 31):
                mudou = False
                for chave, membros in grupos.items():
                    if trocas[chave] > 3 or chave in folgada_de.values():
                        continue
                    alonga, normais, kmax = 0.0, [], 1.0
                    for nb in membros:
                        R, L, T, k, fe, _d, _p, idx, lib = info[nb]
                        ul = T @ u[idx]
                        alonga += ul[6] - ul[0]
                        kmax = max(kmax, abs(k[0, 0]))
                        if ativos[nb]:
                            k2, f2, _rec = cond[nb]
                            normais.append(-(k2 @ ul + f2)[0])
                    if ativos[membros[0]]:
                        if normais and sum(normais) / len(normais) < -max(ncr[chave], 1e-6 * kmax):
                            for nb in membros:
                                ativos[nb] = False
                            trocas[chave] += 1
                            mudou = True
                    elif alonga > 1e-9 or trocas[chave] >= 3:
                        for nb in membros:
                            ativos[nb] = True
                        trocas[chave] += 1
                        mudou = True
                if _folgas():
                    mudou = True
                if not mudou:
                    break
                if self.ciclos_tracao == 30:
                    self.tracao_sem_convergir = True
                K, F, cond = montar(kgs)
                if molas is not None:
                    K = K + molas
                Kff = K[np.ix_(livres, livres)]
                try:
                    uf = np.linalg.solve(Kff, F[livres])
                except np.linalg.LinAlgError:
                    raise ValueError(self._texto_mecanismo(Kff, livres))
                if not np.all(np.isfinite(uf)) or (Kff.size and np.linalg.cond(Kff) > 1e15):
                    raise ValueError(self._texto_mecanismo(Kff, livres) + " (com os contraventamentos "
                                     "comprimidos fora do modelo)")
                u = np.zeros(ndof)
                u[livres] = uf
            self.folgadas = {nb for ch in folgada_de.values() for nb in grupos[ch]}
        u1 = u.copy()
        iteracoes = 0
        if segunda_ordem:
            for iteracoes in range(1, 41):
                for nb, (R, L, T, k, fe, _d, _p, idx, lib) in enumerate(info):
                    k2, f2, _rec = cond[nb]
                    f = k2 @ (T @ u[idx]) + f2
                    kgs[nb] = self.rigidez_geometrica(-f[0], L)
                Kt, Ft, cond_t = montar(kgs)
                if molas is not None:
                    Kt = Kt + molas
                Ktf = Kt[np.ix_(livres, livres)]
                try:
                    novo = np.linalg.solve(Ktf, Ft[livres])
                    ok = np.all(np.isfinite(novo))
                except np.linalg.LinAlgError:
                    ok = False
                onde = ""
                if ok:
                    w, vv = np.linalg.eigh((Ktf + Ktf.T) / 2.0)
                    ok = w[0] > 0
                    if not ok:
                        g = int(np.where(livres)[0][int(np.argmax(np.abs(vv[:, 0])))])
                        q = self.nos[g // 6]
                        onde = " (o primeiro a ceder é o nó (%.0f; %.0f; %.0f), em %s)" % (
                            q[0], q[1], q[2], ("X", "Y", "Z", "giro X", "giro Y", "giro Z")[g % 6])
                        self._diag_instab = (g, float(w[0]))
                if not ok:
                    raise ValueError("instabilidade global na análise de 2ª ordem: as cargas passam da carga "
                                     "crítica da estrutura%s. Confira os travamentos fora do plano (um pórtico plano só "
                                     "com apoios na base gira de lado) e os perfis" % onde)
                dif = np.max(np.abs(novo - u[livres])) if novo.size else 0.0
                u[livres] = novo
                cond = cond_t
                K, F = Kt, Ft
                if dif <= 1e-6 * max(1.0, np.max(np.abs(novo))):
                    break
        reac = K @ u - F
        res = Resultado(self, u, reac, presos)
        res.ativos = list(ativos)
        res.folgadas = set(getattr(self, "folgadas", set()))
        res.segunda_ordem = segunda_ordem
        res.iteracoes = iteracoes
        res.amplificacao = amplificacao_horizontal(u1, u, n)
        for nb, (R, L, T, k, fe, dist, pont, idx, lib) in enumerate(info):
            k2, f2, rec = cond[nb]
            ul = T @ u[idx]
            res.extremos.append(k2 @ ul + f2)
            if rec is not None:
                # giro da ponta rotulada (diferente do giro do nó)
                r, c, inv, krc, fer = rec
                ul = ul.copy()
                ul[r] = -inv @ (krc @ ul[c] + fer)
            res.locais.append(ul)
            res.cargas.append((dist, pont))
            res.geo.append((R, L))
        for nb in res.folgadas:
            # diagonal folgada: a compressão que a conta linear dá a ela não existe (a barra fica frouxa)
            res.extremos[nb] = np.zeros_like(res.extremos[nb])
        return res


def _cruzam(a0, a1, b0, b1, tol=1.0):
    """Os segmentos a0-a1 e b0-b1 se cruzam no meio (não só se tocam nas pontas)?"""
    da, db = a1 - a0, b1 - b0
    r = a0 - b0
    A, B, C = float(da @ da), float(da @ db), float(db @ db)
    D, E = float(da @ r), float(db @ r)
    den = A * C - B * B
    if den <= 1e-12 * max(A * C, 1e-12):
        return False
    s = (B * E - C * D) / den
    t = (A * E - B * D) / den
    if not (0.02 < s < 0.98 and 0.02 < t < 0.98):
        return False
    return float(np.linalg.norm((a0 + s * da) - (b0 + t * db))) < tol


def amplificacao_horizontal(u1, u2, n):
    """Maior razão, nó a nó, entre os deslocamentos horizontais (X, Y) de 2ª e de 1ª ordem; só os nós
    com deslocamento de 1ª ordem de pelo menos 10 % do maior entram (evita razão de números pequenos)."""
    h1 = [math.hypot(u1[6 * k], u1[6 * k + 1]) for k in range(n)]
    h2 = [math.hypot(u2[6 * k], u2[6 * k + 1]) for k in range(n)]
    mx = max(h1, default=0.0)
    if mx <= 1e-9:
        return 1.0
    return max([b / a for a, b in zip(h1, h2) if a >= 0.1 * mx] or [1.0])


class Resultado:
    """Deslocamentos (mm, rad), reações (N, N·mm) e esforços nas barras."""

    def __init__(self, modelo, u, reac, presos):
        self.modelo = modelo
        self.u = u
        self.reac = reac
        self.presos = presos
        self.extremos = []      # 12 forças locais nas pontas de cada barra (convenção da matriz)
        self.segunda_ordem = False
        self.iteracoes = 0
        self.amplificacao = 1.0
        self.cargas = []
        self.geo = []
        self.locais = []        # 12 deslocamentos locais de cada barra (giros das pontas rotuladas incluídos)

    def deslocamento(self, no):
        return self.u[6 * no:6 * no + 3]

    def reacao(self, no):
        """(Fx, Fy, Fz) em kN, (Mx, My, Mz) em kN·m."""
        r = self.reac[6 * no:6 * no + 6]
        return r[:3] / 1000.0, r[3:] / 1e6

    def esforcos(self, nb, x):
        """Esforços internos na seção x (mm a partir do nó i) da barra nb, em N e N·mm.

        Face positiva da seção (normal +x local): N > 0 é tração. My > 0 traciona o lado -z da seção
        (a fibra de baixo, com z para cima: viga biapoiada com carga para baixo tem My > 0); Mz > 0
        traciona o lado -y. Vy, Vz e T seguem a regra da mão direita na face positiva."""
        f = self.extremos[nb]
        dist, pont = self.cargas[nb]
        sc, mc = resultante_ate(dist, pont, x)
        sx, sy, sz = f[0] + sc[0], f[1] + sc[1], f[2] + sc[2]
        smy = f[4] + x * f[2] + mc[1]
        smz = f[5] - x * f[1] + mc[2]
        return {"N": -sx, "Vy": -sy, "Vz": -sz, "T": -f[3], "My": smy, "Mz": -smz}

    def diagrama(self, nb, pontos=11):
        R, L = self.geo[nb]
        xs = [L * k / (pontos - 1) for k in range(pontos)]
        for a, _P in self.cargas[nb][1]:
            for xa in (a - 1e-6, a + 1e-6):
                if 0 < xa < L:
                    xs.append(xa)
        for a, b, _q1, _q2 in self.cargas[nb][0]:
            for xa in (a, b):
                if 1e-6 < xa < L - 1e-6:
                    xs.append(xa)
        xs.sort()
        return [(x, self.esforcos(nb, x)) for x in xs]

    def maximos(self, nb, pontos=21):
        """Maiores valores absolutos de cada esforço na barra (N, N·mm)."""
        m = {}
        for _x, e in self.diagrama(nb, pontos):
            for k, v in e.items():
                if abs(v) > abs(m.get(k, 0.0)):
                    m[k] = v
        return m

    def flecha_local(self, nb, pontos=21):
        """Maior deslocamento transversal relativo à corda (mm), no plano de cada eixo: (y, z)."""
        _R, L = self.geo[nb]
        maxy = maxz = 0.0
        for k in range(1, pontos - 1):
            v, w = _deslocamento_no_vao(self, nb, L * k / (pontos - 1))
            maxy = max(maxy, abs(v))
            maxz = max(maxz, abs(w))
        return maxy, maxz


def deslocamento_local(r, nb, x):
    """(u, v, w) locais da barra nb na posição x (mm): funções de forma com os deslocamentos das
    pontas (giros das pontas rotuladas incluídos) mais a parcela das cargas no vão."""
    b = r.modelo.barras[nb]
    _R, L = r.geo[nb]
    ul = r.locais[nb]
    di, ri, dj, rj = ul[0:3], ul[3:6], ul[6:9], ul[9:12]
    s = b.secao
    dist, pont = r.cargas[nb]
    xi = x / L
    h1, h2 = 1 - 3 * xi ** 2 + 2 * xi ** 3, x * (1 - xi) ** 2
    h3, h4 = 3 * xi ** 2 - 2 * xi ** 3, x * (xi ** 2 - xi)
    u = di[0] + (dj[0] - di[0]) * xi
    v = h1 * di[1] + h2 * ri[2] + h3 * dj[1] + h4 * rj[2]
    w = h1 * di[2] - h2 * ri[1] + h3 * dj[2] - h4 * rj[1]
    pv, pw = flecha_particular(dist, pont, x, L, s.E * s.Iz, s.E * s.Iy)
    return u, v + pv, w + pw


def _deslocamento_no_vao(r, nb, x):
    """(v, w) locais da barra nb na posição x, em relação à reta entre as suas pontas (mm, com sinal)."""
    _R, L = r.geo[nb]
    ul = r.locais[nb]
    xi = x / L
    _u, v, w = deslocamento_local(r, nb, x)
    v -= ul[1] + (ul[7] - ul[1]) * xi
    w -= ul[2] + (ul[8] - ul[2]) * xi
    return v, w


def _flecha_pontual_biengastada(P, a, x, L, EI):
    """Deslocamento em x de uma viga biengastada com carga P em a (Roark)."""
    if P == 0:
        return 0.0
    b = L - a
    if x <= a:
        return P * b * b * x * x * (3 * a * L - x * (3 * a + b)) / (6 * EI * L ** 3)
    xr = L - x
    return P * a * a * xr * xr * (3 * b * L - xr * (3 * b + a)) / (6 * EI * L ** 3)
