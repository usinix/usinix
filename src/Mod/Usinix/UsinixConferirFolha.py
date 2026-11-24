# -*- coding: utf-8 -*-
# Usinix: conferência da folha antes de sair (PDF): escala e material do carimbo contra o modelo, e vista ou
# anotação que invade a legenda ou passa da margem.
import FreeCAD

MARGEM_ESQ = 25.0       # mm (margem de arquivamento)
MARGEM = 10.0
LEGENDA_LARG = 180.0
LEGENDA_ALT = 62.0


def _tamanho(page):
    try:
        return float(page.Template.Width), float(page.Template.Height)
    except Exception:
        return 420.0, 297.0


def caixa_legenda(page):
    larg, _alt = _tamanho(page)
    return (larg - MARGEM - LEGENDA_LARG, MARGEM, larg - MARGEM, MARGEM + LEGENDA_ALT)


def caixa_anotacao(v):
    """Retângulo do texto (o TechDraw põe a anotação pelo centro): largura pela linha mais comprida."""
    linhas = [str(t) for t in (getattr(v, "Text", []) or [])] or [""]
    tam = float(getattr(v, "TextSize", 5.0) or 5.0)
    w = max(len(t) for t in linhas) * tam * 0.58
    h = len(linhas) * tam * 1.35
    x, y = float(v.X), float(v.Y)
    return x - w / 2.0, y - h / 2.0, x + w / 2.0, y + h / 2.0


def caixa_vista(v):
    """Retângulo da vista na folha (sem as cotas), ou None."""
    import UsinixDetalhe as D
    try:
        cx, cy = D._xy_na_folha(v)
        e = float(v.getScale())
        if v.TypeId == "TechDraw::DrawViewDetail":
            r = float(getattr(v.Radius, "Value", v.Radius)) * e
            return cx - r, cy - r, cx + r, cy + r
        x0, x1, y0, y1 = D._caixa_da_vista(v)
        return cx + x0 * e, cy + y0 * e, cx + x1 * e, cy + y1 * e
    except Exception:
        return None


def _cruza(a, b):
    return not (a[2] <= b[0] or a[0] >= b[2] or a[3] <= b[1] or a[1] >= b[3])


def _cotas_por_vista(page):
    cotas = {}
    for v in page.Views:
        if v.TypeId == "TechDraw::DrawViewDimension":
            try:
                cotas.setdefault(v.References2D[0][0].Name, []).append(v)
            except Exception:
                pass
    return cotas


def _com_cotas(v, caixa, cotas):
    """Caixa da vista aumentada até o texto das cotas dela."""
    import UsinixDetalhe as D
    a, b, c, d = caixa
    try:
        cx, cy = D._xy_na_folha(v)
    except Exception:
        return caixa
    for cota in cotas.get(v.Name, []):
        px, py = cx + float(cota.X), cy + float(cota.Y)
        a, b, c, d = min(a, px - 6.0), min(b, py - 3.0), max(c, px + 6.0), max(d, py + 3.0)
    return a, b, c, d


def _grupo(v):
    for o in v.InList:
        if o.TypeId == "TechDraw::DrawProjGroup":
            return o.Name
    return v.Name


def _materiais_do_modelo(page):
    import UsinixMassa
    fontes = []
    for v in page.Views:
        for o in getattr(v, "Source", []) or []:
            if o not in fontes:
                fontes.append(o)
    if not fontes:
        return set()
    try:
        r = UsinixMassa.calcular(fontes)
        return {it[1] for it in r.itens if it[5] and it[1]}
    except Exception:
        return set()


def _tem_pecas(page):
    return any(getattr(v, "Source", None) for v in page.Views)


def _esperar_vistas(page, segundos=60.0):
    """Espera o desenho das vistas na escala atual; devolve as que não ficaram prontas."""
    import UsinixVistas as V
    todas = []
    for v in page.Views:
        for i in (list(v.Views) if v.TypeId == "TechDraw::DrawProjGroup" else [v]):
            if i.isDerivedFrom("TechDraw::DrawViewPart") and i.TypeId != "TechDraw::DrawViewDetail":
                todas.append(i)
    def pronta(i):
        # mesma ideia de V.vista_pronta, com folga: a isométrica (e o contorno de peça redonda) fica menor que a
        # caixa projetada; o desenho velho de outra escala fica 2× maior ou menor (1:50 -> 1:100)
        try:
            vs = V._vertices(i)
            if not vs:
                return False
            esperada = V._largura_esperada(i)
            if not esperada:
                return True
            obtida = max(t[1] for t in vs) - min(t[1] for t in vs)
            if not 0.55 * esperada <= obtida <= 1.05 * esperada + 1e-6:
                # círculos e arcos passam dos vértices (a vista de topo de um eixo só tem o centro e a costura)
                xs = []
                for _n, e in V._arestas(i):
                    import UsinixDetalhe as _D
                    c = _D.caixa_aresta(e)
                    if c is not None:
                        xs += [c[0], c[1]]
                if xs:
                    obtida = max(xs) - min(xs)
            return 0.55 * esperada <= obtida <= 1.05 * esperada + 1e-6
        except Exception:
            return True
    try:
        if not all(pronta(i) for i in todas):
            import time
            from PySide import QtWidgets
            fim, tocar = time.time() + segundos, time.time() + 1.5
            while time.time() < fim and not all(pronta(i) for i in todas):
                if time.time() > tocar:
                    for i in todas:
                        if not pronta(i):
                            i.touch()
                    page.Document.recompute()
                    tocar = time.time() + 3.0
                QtWidgets.QApplication.processEvents()
                time.sleep(0.05)
        return [i for i in todas if not pronta(i)]
    except Exception as exc:
        FreeCAD.Console.PrintLog("Usinix: conferência, espera das vistas: %s\n" % exc)
        return []


def conferir(page):
    """Avisos da folha: [texto]. Vazio = nada a corrigir."""
    import UsinixFolhas
    avisos = []
    try:
        et = dict(page.Template.EditableTexts)
    except Exception:
        et = {}
    # escala do carimbo × vistas
    if "escala" in et:
        certa = UsinixFolhas.texto_escala_legenda(page)
        if et["escala"].strip().upper() != certa.upper():
            avisos.append("Escala do carimbo \"%s\", mas as vistas pedem \"%s\"." % (et["escala"].strip(), certa))
        for e in UsinixFolhas.escalas_das_vistas(page):
            if UsinixFolhas.escala_normal(e) != e:
                avisos.append("Vista em %s, fora da série normalizada (1:2, 1:5, 1:10, 1:20...)."
                              % UsinixFolhas._texto_escala(e))
    # material do carimbo × modelo
    mats = _materiais_do_modelo(page)
    no_carimbo = et.get("material", "").strip()
    if len(mats) == 1 and no_carimbo:
        m = mats.pop()
        if m.lower() not in no_carimbo.lower():
            avisos.append("Material do carimbo \"%s\", mas o modelo usa \"%s\"." % (no_carimbo, m))
    elif not mats and no_carimbo and _tem_pecas(page):
        avisos.append("O carimbo diz \"%s\", mas o modelo não tem material definido (a massa sai pela densidade "
                      "padrão): escolha o material da peça." % no_carimbo)
    # a posição só vale com o desenho calculado na escala atual: logo depois de criar a folha (ou de a escala
    # automática mudar) a vista ainda tem o desenho da escala anterior, e a caixa saía o dobro (falso "em cima de")
    pendentes = _esperar_vistas(page)
    for i in pendentes:
        avisos.append("\"%s\" ainda está sendo desenhada: a posição dela não foi conferida (confira de novo)."
                      % i.Label)
    # vista sobre vista (ou sobre as cotas de outra vista)
    cotas = _cotas_por_vista(page)
    vistas = []
    for v in page.Views:
        for i in (list(v.Views) if v.TypeId == "TechDraw::DrawProjGroup" else [v]):
            if i.isDerivedFrom("TechDraw::DrawViewPart") and i not in pendentes:
                c = caixa_vista(i)
                if c is not None:
                    vistas.append((i, c, _com_cotas(i, c, cotas)))
    ja = set()
    for k, (va, ca, xa) in enumerate(vistas):
        for vb, cb, xb in vistas[k + 1:]:
            if _grupo(va) == _grupo(vb):
                continue
            if _cruza(ca, xb) or _cruza(cb, xa):
                par = tuple(sorted((va.Label, vb.Label)))
                if par not in ja:
                    ja.add(par)
                    avisos.append("\"%s\" fica em cima de \"%s\" (ou das cotas dela)." % par)
    # invasão da legenda e da margem
    larg, alt = _tamanho(page)
    leg = caixa_legenda(page)
    for v in page.Views:
        itens = list(v.Views) if v.TypeId == "TechDraw::DrawProjGroup" else [v]
        for i in itens:
            if i.TypeId == "TechDraw::DrawViewAnnotation":
                c = caixa_anotacao(i)
            elif i.isDerivedFrom("TechDraw::DrawViewPart"):
                if i in pendentes:
                    continue
                c = caixa_vista(i)
            else:
                continue
            if c is None:
                continue
            nome = i.Label
            if _cruza(c, leg):
                avisos.append("\"%s\" invade a legenda." % nome)
            if c[0] < MARGEM_ESQ - 0.5 or c[2] > larg - MARGEM + 0.5 or c[1] < MARGEM - 0.5 or c[3] > alt - MARGEM + 0.5:
                avisos.append("\"%s\" passa da margem da folha." % nome)
    return avisos


def avisar(page):
    """Escreve os avisos no console (usado antes de gravar o PDF). Devolve a lista."""
    avisos = conferir(page)
    for a in avisos:
        FreeCAD.Console.PrintWarning("Usinix: folha \"%s\": %s\n" % (page.Label, a))
    return avisos

