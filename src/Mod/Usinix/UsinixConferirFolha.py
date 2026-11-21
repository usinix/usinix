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
    # invasão da legenda e da margem
    larg, alt = _tamanho(page)
    leg = caixa_legenda(page)
    for v in page.Views:
        itens = list(v.Views) if v.TypeId == "TechDraw::DrawProjGroup" else [v]
        for i in itens:
            if i.TypeId == "TechDraw::DrawViewAnnotation":
                c = caixa_anotacao(i)
            elif i.isDerivedFrom("TechDraw::DrawViewPart"):
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

