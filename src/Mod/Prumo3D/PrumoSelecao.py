# SPDX-License-Identifier: LGPL-2.1-or-later
"""Um fluxo só para a seleção: função antes ou peça antes, os dois funcionam.

No FreeCAD, algumas bancadas pedem a peça selecionada antes do comando (operações booleanas do
Sólidos, vistas do Desenho) e outras abrem o comando e pedem a seleção depois (Peça). No Usinix,
quando um comando que exige seleção prévia é chamado sem ela, abre um painel que diz o que
selecionar, mostra o que já foi escolhido e roda o comando ao clicar em OK.

- SELECAO_PRIMEIRO: comandos do FreeCAD tratados assim (a faixa mantém o botão ligado);
- pedir(...): painel genérico usado também pelos comandos do Usinix.
"""

import FreeCAD
import FreeCADGui

import PrumoPainel as P


# ------------------------------------------------------------------------------- filtros
def _solidos(obj, subs):
    try:
        if obj.Shape.Solids or obj.Shape.Shells:
            return [(obj.Label, obj)]
    except Exception:
        pass
    return []


def _formas(obj, subs):
    try:
        if not obj.Shape.isNull():
            return [(obj.Label, obj)]
    except Exception:
        pass
    return []


def _pecas(obj, subs):
    import PrumoUtil
    return [(obj.Label, obj)] if PrumoUtil.pecas([obj]) else []


def _esbocos(obj, subs):
    return [(obj.Label, obj)] if obj.isDerivedFrom("Sketcher::SketchObject") else []


def _estruturas(obj, subs):
    import PrumoEstrutura as E
    e = E.estrutura_de(obj)
    return [(e.Label, e)] if e is not None else []


def _barras(obj, subs):
    import PrumoEstrutura as E
    return [(b.Label, b) for b in E.barras_do_item(obj, subs)]


def _tipo_do_elemento(caminho):
    el = (caminho or "").rsplit(".", 1)[-1]
    for t in ("Face", "Edge", "Vertex"):
        if el.startswith(t) and el[len(t):].isdigit():
            return t
    return None


NOMES_ELEMENTO = {"Face": "face", "Edge": "aresta", "Vertex": "ponto"}


def _texto_elemento(raiz, caminho):
    el = caminho.rsplit(".", 1)[-1]
    t = _tipo_do_elemento(caminho)
    try:
        dono = raiz.getSubObject(caminho, retType=1)
        if isinstance(dono, tuple):
            dono = dono[0]
    except Exception:
        dono = None
    return "%s %s (%s)" % (NOMES_ELEMENTO.get(t, "elemento"), el[len(t or ""):], (dono or raiz).Label)


def filtro_elementos(*tipos, condicao=None):
    """Filtro de faces/arestas/pontos com o caminho completo: o valor é (objeto do topo, caminho), que
    devolve a seleção exatamente como foi feita (dentro de corpo, de montagem...)."""
    def f(raiz, caminhos):
        res = []
        for c in (caminhos or ()):
            if _tipo_do_elemento(c) not in tipos:
                continue
            if condicao is not None:
                try:
                    if not condicao(raiz.getSubObject(c)):
                        continue
                except Exception:
                    continue
            res.append((_texto_elemento(raiz, c), (raiz, c)))
        return res
    f.caminho_completo = True
    return f


def _plana(forma):
    import Part
    return isinstance(getattr(forma, "Surface", None), Part.Plane)


def _elementos_ou_pecas(raiz, caminhos):
    """Face, aresta ou ponto; sem elemento, a peça inteira."""
    res = filtro_elementos("Face", "Edge", "Vertex")(raiz, caminhos)
    if not res and not any(_tipo_do_elemento(c) for c in (caminhos or ())):
        alvo = raiz
        for c in (caminhos or ()):
            try:
                o = raiz.getSubObject(c, retType=1)
                alvo = (o[0] if isinstance(o, tuple) else o) or raiz
            except Exception:
                pass
        if hasattr(alvo, "Shape"):
            res = [(alvo.Label, alvo)]
    return res


_elementos_ou_pecas.caminho_completo = True


def _componentes(raiz, caminhos):
    """Componente da montagem (o valor é o caminho até ele: o FreeCAD acha a peça pelo caminho)."""
    import PrumoMontagem as M
    res = []
    for c in (caminhos or ("",)):
        o = M.componente_do_caminho(raiz, c)
        if o is None:
            continue
        partes = c.split(".")
        pref = ".".join(partes[:partes.index(o.Name) + 1]) + "." if o.Name in partes else c
        if all(v != (raiz, pref) for _t, v in res):
            res.append((o.Label, (raiz, pref)))
    return res


_componentes.caminho_completo = True


def _formas_ou_elementos(raiz, caminhos):
    """Operação, peça ou uma face dela (o comando acha a operação pela face)."""
    res = filtro_elementos("Face", "Edge")(raiz, caminhos)
    if res:
        return res[:1]
    return _elementos_ou_pecas(raiz, caminhos)


_formas_ou_elementos.caminho_completo = True


def _perfis_2d(obj, subs):
    for t in ("Sketcher::SketchObject", "PartDesign::ShapeBinder", "PartDesign::SubShapeBinder",
              "Part::Part2DObjectPython"):
        if obj.isDerivedFrom(t):
            return [(obj.Label, obj)]
    return []


def _objetos(obj, subs):
    if obj.isDerivedFrom("TechDraw::DrawPage") or obj.TypeId.startswith("TechDraw::"):
        return []
    return [(obj.Label, obj)]


# -- Desenho (TechDraw): o que se clica na folha chega como (vista, "Edge3")
def _e_vista(obj):
    return obj is not None and obj.isDerivedFrom("TechDraw::DrawViewPart")


def _vistas(obj, subs):
    return [(obj.Label, obj)] if _e_vista(obj) else []


def filtro_da_vista(*tipos, condicao=None):
    def f(obj, subs):
        if not _e_vista(obj):
            return []
        res = []
        for el in subs or ():
            t = _tipo_do_elemento(el)
            if t not in tipos:
                continue
            if condicao is not None:
                try:
                    if not condicao(obj, el):
                        continue
                except Exception:
                    continue
            res.append(("%s %s (%s)" % (NOMES_ELEMENTO[t], el[len(t):], obj.Label), (obj, el)))
        return res
    return f


def _aresta_circular(vista, el):
    g = vista.getEdgeBySelection(el)
    return "Circle" in type(getattr(g, "Curve", None)).__name__ or "Circle" in str(getattr(g, "Curve", ""))


def _cotas(obj, subs):
    return [(obj.Label, obj)] if obj.isDerivedFrom("TechDraw::DrawViewDimension") else []


def _chamadas(obj, subs):
    if obj.isDerivedFrom("TechDraw::DrawLeaderLine") or obj.isDerivedFrom("TechDraw::DrawWeldSymbol"):
        return [(obj.Label, obj)]
    return []


# -- Simulação
def _tipo_proxy(obj):
    return getattr(getattr(obj, "Proxy", None), "Type", "") or ""


def _malhas_fem(obj, subs):
    return [(obj.Label, obj)] if obj.isDerivedFrom("Fem::FemMeshObject") else []


def _solvers(obj, subs):
    if obj.isDerivedFrom("Fem::FemSolverObject") or _tipo_proxy(obj).startswith("Fem::Solver"):
        return [(obj.Label, obj)]
    return []


def _resultados(obj, subs):
    return [(obj.Label, obj)] if obj.isDerivedFrom("Fem::FemResultObject") else []


def _pos(obj, subs):
    return [(obj.Label, obj)] if obj.isDerivedFrom("Fem::FemPostObject") else []


def _malhas(obj, subs):
    return [(obj.Label, obj)] if obj.isDerivedFrom("Mesh::Feature") else []


FILTROS = {"solidos": _solidos, "formas": _formas, "pecas": _pecas, "esbocos": _esbocos,
           "estruturas": _estruturas, "barras": _barras, "objetos": _objetos, "perfis2d": _perfis_2d,
           "faces": filtro_elementos("Face"), "faces_planas": filtro_elementos("Face", condicao=_plana),
           "arestas": filtro_elementos("Edge"), "pontos": filtro_elementos("Vertex"),
           "faces_arestas": filtro_elementos("Face", "Edge"),
           "elementos": filtro_elementos("Face", "Edge", "Vertex"),
           "elementos_ou_pecas": _elementos_ou_pecas, "formas_ou_elementos": _formas_ou_elementos,
           "componentes": _componentes,
           "vistas": _vistas, "faces_vista": filtro_da_vista("Face"), "arestas_vista": filtro_da_vista("Edge"),
           "pontos_vista": filtro_da_vista("Vertex"), "elementos_vista": filtro_da_vista("Face", "Edge", "Vertex"),
           "circulos_vista": filtro_da_vista("Edge", condicao=_aresta_circular),
           "cotas": _cotas, "chamadas": _chamadas,
           "malhas_fem": _malhas_fem, "solvers": _solvers, "resultados": _resultados, "pos": _pos,
           "malhas": _malhas}

# comando: (título, instrução, [(rótulo da caixa, filtro, mínimo, máximo)])
SELECAO_PRIMEIRO = {
    "Part_Cut": ("Subtrair", "Escolha a peça base e depois a ferramenta (a peça que será retirada da base).",
                 [("Peça base", "solidos", 1, 1), ("Ferramenta", "solidos", 1, 1)]),
    "Part_Fuse": ("Unir", "Escolha as peças que viram uma só.", [("Peças", "solidos", 2, None)]),
    "Part_Common": ("Interseção", "Escolha as peças: fica só o volume comum a todas.",
                    [("Peças", "solidos", 2, None)]),
    "Part_Section": ("Seção", "Escolha as duas formas: o resultado é a linha de interseção entre elas.",
                     [("Primeira forma", "formas", 1, 1), ("Segunda forma", "formas", 1, 1)]),
    "Part_BooleanFragments": ("Fragmentos booleanos", "Escolha as peças.", [("Peças", "solidos", 2, None)]),
    "Part_Slice": ("Fatiar em composto", "Escolha a peça e depois as ferramentas de corte.",
                   [("Peça", "solidos", 1, 1), ("Ferramentas de corte", "formas", 1, None)]),
    "Part_SliceApart": ("Fatiar separado", "Escolha a peça e depois as ferramentas de corte.",
                        [("Peça", "solidos", 1, 1), ("Ferramentas de corte", "formas", 1, None)]),
    "Part_XOR": ("XOR booleano", "Escolha as peças.", [("Peças", "solidos", 2, None)]),
    "Part_JoinConnect": ("Conectar formas", "Escolha as peças.", [("Peças", "solidos", 2, None)]),
    "Part_JoinEmbed": ("Embutir formas", "Escolha a peça base e a peça a embutir.",
                       [("Peça base", "solidos", 1, 1), ("Peça a embutir", "solidos", 1, 1)]),
    "Part_JoinCutout": ("Recortar encaixe", "Escolha a peça a recortar e a peça que encaixa.",
                        [("Peça a recortar", "solidos", 1, 1), ("Peça que encaixa", "solidos", 1, 1)]),
    "Part_CompSolidsBooleans": ("Booleanas", "Escolha as peças.", [("Peças", "solidos", 2, None)]),
    "TechDraw_View": ("Vista no desenho", "Escolha as peças para a vista (com uma folha aberta).",
                      [("Peças", "pecas", 1, None)]),
    "TechDraw_ProjectionGroup": ("Grupo de vistas", "Escolha as peças para as vistas (com uma folha aberta).",
                                 [("Peças", "pecas", 1, None)]),
}

_CONFERE = {"confere": True}      # o comando fica ligado sem seleção e reclama depois: confere antes
_UNICO = {"unico": True}          # só existe um candidato no projeto: ele entra sozinho

SELECAO_PRIMEIRO.update({
    # ---- Peça
    "TechDraw_View": ("Vista no desenho", "Escolha as peças para a vista.", [("Peças", "pecas", 1, None)], _CONFERE),
    "TechDraw_ProjectionGroup": ("Grupo de vistas", "Escolha as peças para as vistas.",
                                 [("Peças", "pecas", 1, None)], _CONFERE),
    "PartDesign_Clone": ("Clonar", "Escolha o corpo (ou a peça) a clonar: o clone acompanha o original.",
                         [("Original", "formas", 1, 1)]),
    "Part_CheckGeometry": ("Verificar geometria", "Escolha as peças a conferir (faces abertas, arestas soltas, "
                           "auto-interseção).", [("Peças", "formas", 1, None)]),
    "Sketcher_ValidateSketch": ("Validar esboço", "Escolha o esboço a validar (pontas soltas, linhas repetidas, "
                                "restrições conflitantes).", [("Esboço", "esbocos", 1, 1)], _CONFERE),
    "Part_CompJoinFeatures": SELECAO_PRIMEIRO["Part_JoinConnect"] + (_CONFERE,),
    "Part_JoinConnect": SELECAO_PRIMEIRO["Part_JoinConnect"] + (_CONFERE,),
    "Part_CrossSections": ("Cortes transversais", "Escolha as peças a cortar em fatias.",
                           [("Peças", "formas", 1, None)]),
    "Part_Offset": ("Offset 3D", "Escolha a peça para o offset.", [("Peça", "formas", 1, 1)]),
    "Part_Offset2D": ("Offset 2D", "Escolha o esboço ou a face para o offset.", [("Forma", "formas", 1, 1)]),
    "Part_Thickness": ("Casca", "Escolha as faces que ficam abertas na casca.", [("Faces", "faces", 1, None)],
                       _CONFERE),
    "Part_MakeFace": ("Face de esboços", "Escolha os esboços fechados que viram face.",
                      [("Esboços", "esbocos", 1, None)], _CONFERE),
    "Part_RuledSurface": ("Superfície regrada", "Escolha as duas arestas (ou linhas) entre as quais vai a "
                          "superfície.", [("Primeira", "arestas", 1, 1), ("Segunda", "arestas", 1, 1)], _CONFERE),
    "Prumo_Cotas": ("Cotas da operação", "Clique numa face do modelo ou numa operação (extrusão, furo, "
                    "arredondamento...): as cotas dela aparecem na tela para editar.",
                    [("Operação ou face", "formas_ou_elementos", 1, 1)]),
    # ---- Estruturas
    "Prumo_AtualizarEstrutura": ("Atualizar estrutura", "Escolha as estruturas a refazer pelo esboço.",
                                 [("Estruturas", "estruturas", 1, None)]),
    # ---- Montagem
    "Assembly_ToggleGrounded": ("Fixar peça", "Escolha as peças que ficam fixas (não se movem ao resolver).",
                                [("Peças", "componentes", 1, None)], _CONFERE),
    "Prumo_MatrizLeve": ("Matriz leve", "Escolha a peça a repetir.", [("Peça", "formas", 1, 1)]),
    "Prumo_Posicionar": ("Posicionar peça", "Clique primeiro na peça que vai se mover (face, aresta ou ponto) "
                         "e depois no destino.", [("Na peça que move", "elementos", 1, 1),
                                                  ("No destino", "elementos", 1, 1)], _CONFERE),
    "Prumo_MedirXYZ": ("Medir X, Y, Z", "Escolha os dois elementos (ponto, aresta, face ou peça inteira): a "
                       "distância aparece separada em X, Y e Z.",
                       [("Primeiro", "elementos_ou_pecas", 1, 1), ("Segundo", "elementos_ou_pecas", 1, 1)],
                       _CONFERE),
    "Prumo_Isolar": ("Isolar peça", "Escolha a peça (ou o conjunto) que quer ver sozinha. Clique em Isolar de "
                     "novo, sem nada escolhido, para ver tudo.", [("Peças", "pecas", 1, None)],
                     {"confere": True, "pular": "isolado"}),
    # ---- Chapa
    "SheetMetal_AddBase": ("Parede base", "Escolha o esboço do perfil (aberto vira chapa dobrada; fechado, "
                           "chapa plana).", [("Esboço", "perfis2d", 1, 1)]),
    "SheetMetal_FromSolid": ("Chapa de sólido", "Escolha o sólido que vira chapa.", [("Sólido", "formas", 1, 1)]),
    "SheetMetal_SketchOnSheet": ("Esboço na chapa", "Escolha a face da chapa e depois o esboço a recortar "
                                 "nela.", [("Face da chapa", "faces", 1, 1), ("Esboço", "esbocos", 1, 1)]),
    "SheetMetal_AddWall": ("Aba", "Escolha as arestas da chapa onde nascem as abas.",
                           [("Arestas", "arestas", 1, None)]),
    "SheetMetal_AddFoldWall": ("Dobrar por linha", "Escolha a face da chapa e depois o esboço com a linha de "
                               "dobra.", [("Face da chapa", "faces", 1, 1), ("Linha de dobra", "esbocos", 1, 1)]),
    "SheetMetal_Extrude": ("Estender", "Escolha as faces da ponta da chapa a estender.",
                           [("Faces", "faces_arestas", 1, None)]),
    "SheetMetal_ExtendBySketch": ("Estender por esboço", "Escolha o esboço desenhado numa face da chapa.",
                                  [("Esboço", "esbocos", 1, 1)]),
    "SheetMetal_AddBend": ("Dobra em aresta", "Escolha as arestas em que as paredes se encontram.",
                           [("Arestas", "arestas", 1, None)]),
    "SheetMetal_AddHem": ("Bainha", "Escolha as arestas da chapa que recebem a bainha.",
                          [("Arestas", "arestas", 1, None)]),
    "SheetMetal_AddJunction": ("Junção (fenda)", "Escolha as arestas de canto onde abre a fenda.",
                               [("Arestas", "arestas", 1, None)]),
    "SheetMetal_AddCutout": ("Recorte", "Escolha a face da chapa e depois o esboço do recorte.",
                             [("Face da chapa", "faces", 1, 1), ("Esboço", "esbocos", 1, 1)]),
    "SheetMetal_AddRelief": ("Alívio de dobra", "Escolha os pontos (cantos) que recebem o alívio.",
                             [("Pontos", "pontos", 1, None)]),
    "SheetMetal_AddCornerRelief": ("Alívio de canto", "Escolha as duas arestas de dobra que se encontram no canto.",
                                   [("Arestas", "arestas", 2, None)]),
    "SheetMetal_Forming": ("Estampar", "Escolha a face da chapa e depois a face da ferramenta de estampo.",
                           [("Face da chapa", "faces", 1, 1), ("Face da ferramenta", "faces", 1, 1)]),
    "SheetMetal_Unfold": ("Planificar", "Escolha a face plana que fica parada na planificação.",
                          [("Face plana", "faces_planas", 1, 1)]),
    # ---- Superfícies
    "Surface_ExtendFace": ("Estender face", "Escolha a face a estender.", [("Face", "faces", 1, 1)]),
    "Surface_BlendCurve": ("Curva de concordância", "Escolha as duas arestas a concordar (perto da ponta que "
                           "vai ligar).", [("Primeira aresta", "arestas", 1, 1), ("Segunda aresta", "arestas", 1, 1)]),
    "Surface_CurveOnMesh": ("Curva sobre malha", "Escolha a malha.", [("Malha", "malhas", 1, 1)]),
    # ---- Simulação
    "FEM_MeshGmshFromShape": ("Gerar malha", "Escolha a peça que vai receber a malha.",
                              [("Peça", "solidos", 1, 1)], _UNICO),
    "FEM_MeshRegion": ("Refino local", "Escolha a malha que recebe o refino.", [("Malha", "malhas_fem", 1, 1)],
                       _UNICO),
    "FEM_MeshDisplayInfo": ("Dados da malha", "Escolha a malha.", [("Malha", "malhas_fem", 1, 1)], _UNICO),
    "FEM_MeshClear": ("Limpar malha", "Escolha a malha a limpar.", [("Malha", "malhas_fem", 1, 1)], _UNICO),
    "FEM_SolverRun": ("Calcular", "Escolha o solver do estudo.", [("Solver", "solvers", 1, 1)], _UNICO),
    "FEM_SolverControl": ("Controle do solver", "Escolha o solver do estudo.", [("Solver", "solvers", 1, 1)],
                          _UNICO),
    "FEM_ResultShow": ("Ver resultados", "Escolha o resultado.", [("Resultado", "resultados", 1, 1)], _UNICO),
    "FEM_PostFilterWarp": ("Deformada", "Escolha o resultado (pós-processamento).", [("Resultado", "pos", 1, 1)],
                           _UNICO),
    "FEM_PostFilterClipScalar": ("Recorte por valor", "Escolha o resultado (pós-processamento).",
                                 [("Resultado", "pos", 1, 1)], _UNICO),
    "FEM_PostFilterDataAlongLine": ("Gráfico ao longo de linha", "Escolha o resultado (pós-processamento).",
                                    [("Resultado", "pos", 1, 1)], _UNICO),
    # ---- Desenho: o FreeCAD deixa a ferramenta ligada e só reclama da seleção depois do clique
    "TechDraw_SectionGroup": ("Corte", "Escolha a vista que vai ser cortada.", [("Vista", "vistas", 1, 1)],
                              _CONFERE),
    "TechDraw_DetailView": ("Detalhe", "Escolha a vista de onde sai o detalhe.", [("Vista", "vistas", 1, 1)],
                            _CONFERE),
    "TechDraw_Hatch": ("Hachura", "Escolha as faces da vista a hachurar.", [("Faces", "faces_vista", 1, None)],
                       _CONFERE),
    "TechDraw_GeometricHatch": ("Hachura geométrica", "Escolha a face da vista a hachurar.",
                                [("Face", "faces_vista", 1, 1)], _CONFERE),
    "TechDraw_ShowAll": ("Mostrar linhas ocultas", "Escolha as vistas.", [("Vistas", "vistas", 1, None)], _CONFERE),
    "TechDraw_DraftView": ("Vista de objeto 2D", "Escolha os objetos (desenho 2D, arquitetura...).",
                           [("Objetos", "objetos", 1, None)], _CONFERE),
    "TechDraw_Balloon": ("Balão", "Escolha a vista; depois clique na folha onde fica o balão.",
                         [("Vista", "vistas", 1, 1)], _CONFERE),
    "TechDraw_AxoLengthDimension": ("Cota isométrica", "Escolha a aresta da vista isométrica.",
                                    [("Arestas", "arestas_vista", 1, 2)], _CONFERE),
    "TechDraw_ExtensionInsertPrefixGroup": ("Prefixo na cota", "Escolha as cotas.", [("Cotas", "cotas", 1, None)],
                                            _CONFERE),
    "TechDraw_ExtensionIncreaseDecreaseGroup": ("Casas decimais", "Escolha as cotas.",
                                                [("Cotas", "cotas", 1, None)], _CONFERE),
    "TechDraw_LeaderLine": ("Linha de chamada", "Escolha a vista de onde sai a chamada.",
                            [("Vista", "vistas", 1, 1)], _CONFERE),
    "TechDraw_CenterLineGroup": ("Linha de centro", "Escolha as faces, as duas arestas ou os dois pontos da vista.",
                                 [("Elementos", "elementos_vista", 1, None)], _CONFERE),
    "TechDraw_ExtensionCircleCenterLinesGroup": ("Centro de círculos", "Escolha os círculos da vista.",
                                                 [("Círculos", "circulos_vista", 1, None)], _CONFERE),
    "TechDraw_ExtensionThreadsGroup": ("Rosca", "Escolha as arestas do furo ou do eixo roscado.",
                                       [("Arestas", "arestas_vista", 1, None)], _CONFERE),
    "TechDraw_CosmeticVertexGroup": ("Ponto cosmético", "Escolha a vista.", [("Vista", "vistas", 1, 1)], _CONFERE),
    "TechDraw_2PointCosmeticLine": ("Linha cosmética", "Escolha os dois pontos da vista.",
                                    [("Primeiro ponto", "pontos_vista", 1, 1), ("Segundo ponto", "pontos_vista", 1, 1)],
                                    _CONFERE),
    "TechDraw_DecorateLine": ("Estilo de linha", "Escolha as linhas da vista.",
                              [("Linhas", "arestas_vista", 1, None)], _CONFERE),
    "TechDraw_WeldSymbol": ("Símbolo de solda", "Escolha a linha de chamada que recebe o símbolo.",
                            [("Linha de chamada", "chamadas", 1, 1)], _CONFERE),
    "TechDraw_ExtensionLockUnlockView": ("Travar vista", "Escolha as vistas a travar ou destravar.",
                                         [("Vistas", "vistas", 1, None)], _CONFERE),
})

# grupos do Desenho: a faixa chama o subcomando escolhido na setinha, então cada um tem a sua entrada
def _mesma(chaves, *spec):
    for k in chaves:
        SELECAO_PRIMEIRO[k] = spec


SELECAO_PRIMEIRO["TechDraw_SectionView"] = SELECAO_PRIMEIRO["TechDraw_SectionGroup"]
_mesma(("TechDraw_ExtensionInsertDiameter", "TechDraw_ExtensionInsertSquare", "TechDraw_ExtensionInsertRepetition",
        "TechDraw_ExtensionRemovePrefixChar"), "Prefixo na cota", "Escolha as cotas.", [("Cotas", "cotas", 1, None)],
       _CONFERE)
_mesma(("TechDraw_ExtensionIncreaseDecimal", "TechDraw_ExtensionDecreaseDecimal"), "Casas decimais",
       "Escolha as cotas.", [("Cotas", "cotas", 1, None)], _CONFERE)
SELECAO_PRIMEIRO.update({
    "TechDraw_FaceCenterLine": ("Linha de centro das faces", "Escolha as faces da vista.",
                                [("Faces", "faces_vista", 1, None)], _CONFERE),
    "TechDraw_2LineCenterLine": ("Linha de centro entre 2 linhas", "Escolha as duas linhas da vista.",
                                 [("Primeira linha", "arestas_vista", 1, 1), ("Segunda linha", "arestas_vista", 1, 1)],
                                 _CONFERE),
    "TechDraw_2PointCenterLine": ("Linha de centro entre 2 pontos", "Escolha os dois pontos da vista.",
                                  [("Primeiro ponto", "pontos_vista", 1, 1), ("Segundo ponto", "pontos_vista", 1, 1)],
                                  _CONFERE),
    "TechDraw_ExtensionCircleCenterLines": SELECAO_PRIMEIRO["TechDraw_ExtensionCircleCenterLinesGroup"],
    "TechDraw_ExtensionHoleCircle": ("Centro de furação circular", "Escolha os furos (três ou mais círculos) da "
                                     "vista.", [("Círculos", "circulos_vista", 3, None)], _CONFERE),
    "TechDraw_ExtensionThreadHoleSide": ("Rosca de furo (lateral)", "Escolha as duas linhas do furo na vista.",
                                         [("Linhas", "arestas_vista", 2, 2)], _CONFERE),
    "TechDraw_ExtensionThreadBoltSide": ("Rosca de parafuso (lateral)", "Escolha as duas linhas do eixo na vista.",
                                         [("Linhas", "arestas_vista", 2, 2)], _CONFERE),
    "TechDraw_ExtensionThreadHoleBottom": ("Rosca de furo (de topo)", "Escolha os círculos dos furos.",
                                           [("Círculos", "circulos_vista", 1, None)], _CONFERE),
    "TechDraw_ExtensionThreadBoltBottom": ("Rosca de parafuso (de topo)", "Escolha os círculos dos eixos.",
                                           [("Círculos", "circulos_vista", 1, None)], _CONFERE),
    "TechDraw_CosmeticVertex": SELECAO_PRIMEIRO["TechDraw_CosmeticVertexGroup"],
    "TechDraw_Midpoints": ("Pontos médios", "Escolha as arestas da vista.", [("Arestas", "arestas_vista", 1, None)],
                           _CONFERE),
    "TechDraw_Quadrants": ("Quadrantes", "Escolha os círculos da vista.", [("Círculos", "circulos_vista", 1, None)],
                           _CONFERE),
})


def comando_pelo_texto(texto):
    """Os grupos do Python (Juntar/dividir do Sólidos) não dizem o nome do subcomando na ação: acha pelo
    texto do menu."""
    if not texto:
        return ""
    if not _TEXTOS:
        from PySide import QtCore
        for cmd in list(SELECAO_PRIMEIRO) + ["Part_JoinEmbed", "Part_JoinCutout"]:
            try:
                info = FreeCADGui.Command.get(cmd).getInfo() or {}
            except Exception:
                continue
            t = info.get("menuText") or ""
            for ctx in (cmd, "Part_" + cmd.split("_", 1)[-1]):
                tr = QtCore.QCoreApplication.translate(ctx, t)
                if tr:
                    _TEXTOS[tr.replace("&", "")] = cmd
            _TEXTOS[t.replace("&", "")] = cmd
    return _TEXTOS.get(texto.replace("&", ""), "")


_TEXTOS = {}


# Ferramentas que só funcionam dentro de algo aberto (montagem em edição, folha na tela, estudo ativo):
# o clique abre esse algo sozinho (havendo um só; havendo vários, pergunta qual) e segue.
_JUNTAS_USINIX = {"Prumo_JuntaInteligente", "Prumo_JuntaCoincidente", "Prumo_JuntaTangente", "Prumo_MoverJunta"}
_SEM_CONTEXTO = {"Assembly_CreateAssembly", "TechDraw_PageDefault", "TechDraw_PageTemplate", "TechDraw_PrintAll",
                 "TechDraw_ExportPageSVG", "TechDraw_ExportPageDXF", "FEM_Analysis", "FEM_MaterialEditor",
                 "FEM_EquationsDialog"}


def contexto_de(cmd):
    """"montagem", "folha", "estudo" ou None."""
    if cmd in _SEM_CONTEXTO:
        return None
    if cmd in _JUNTAS_USINIX or cmd.startswith("Assembly_"):
        return "montagem"
    if cmd.startswith("TechDraw_"):
        return "folha"
    if cmd.startswith("FEM_"):
        return "estudo"
    return None


def contexto_ativo(ctx):
    if ctx == "montagem":
        try:
            import UtilsAssembly
            return UtilsAssembly.activeAssembly() is not None
        except Exception:
            return False
    if ctx == "folha":
        import PrumoRibbon
        return PrumoRibbon.folha_aberta()
    if ctx == "estudo":
        try:
            import FemGui
            return FemGui.getActiveAnalysis() is not None
        except Exception:
            return False
    return True


def alvos_do_contexto(ctx, doc=None):
    doc = doc or FreeCAD.ActiveDocument
    if doc is None:
        return []
    tipos = {"montagem": ("Assembly::AssemblyObject",), "folha": ("TechDraw::DrawPage",),
             "estudo": ("Fem::FemAnalysis",)}.get(ctx, ())
    return [o for o in doc.Objects if any(o.isDerivedFrom(t) for t in tipos)]


def existe_contexto(ctx):
    """Há no projeto o que abrir (sem varrer o documento a cada redesenho: usa o cache da faixa)."""
    doc = FreeCAD.ActiveDocument
    if doc is None:
        return False
    try:
        import PrumoRibbon
        return ctx in PrumoRibbon._tipos_no_doc(doc)
    except Exception:
        return bool(alvos_do_contexto(ctx, doc))


def ativar_contexto(ctx, alvo):
    if ctx == "montagem":
        import PrumoMontagem
        PrumoMontagem.abrir_montagem(alvo)
    elif ctx == "folha":
        import PrumoFolhas
        PrumoFolhas._abrir_folha(alvo)
    elif ctx == "estudo":
        import FemGui
        FemGui.setActiveAnalysis(alvo)


NOMES_CONTEXTO = {"montagem": "montagem", "folha": "folha de desenho", "estudo": "estudo de simulação"}
COMO_CRIAR = {"montagem": "Crie uma em Nova montagem (aba Montagem).",
              "folha": "Crie uma em Inserir peça ou montagem ou Folha ABNT (aba Desenho).",
              "estudo": "Crie um em Novo estudo ou pelo Assistente de simulação (aba Simulação)."}


def motivo_sem_contexto(cmd):
    """Texto do aviso quando a ferramenta precisa de algo que o projeto não tem (None = não é o caso)."""
    ctx = contexto_de(cmd)
    if ctx is None or FreeCAD.ActiveDocument is None or contexto_ativo(ctx) or alvos_do_contexto(ctx):
        return None
    return "Esta ferramenta trabalha dentro de uma %s, e o projeto ainda não tem uma. %s" % (
        NOMES_CONTEXTO[ctx], COMO_CRIAR[ctx])


def _alvo_pela_selecao(ctx, alvos):
    sel = [s.Object for s in FreeCADGui.Selection.getSelectionEx("", 0)]
    for a in alvos:
        for o in sel:
            if o is a or a in getattr(o, "InListRecursive", []):
                return a
    return None


def pode_pedir(cmd):
    """O botão fica com cara de ligado: o clique resolve o que falta (abre o contexto e/ou pede a seleção)."""
    if FreeCAD.ActiveDocument is None:
        return False
    ctx = contexto_de(cmd)
    if ctx is not None and not contexto_ativo(ctx):
        return existe_contexto(ctx) and (cmd in SELECAO_PRIMEIRO or _ativa_no_contexto(cmd))
    return cmd in SELECAO_PRIMEIRO


def _ativa_no_contexto(cmd):
    # com o contexto aberto ela liga sozinha (as juntas, inserir, resolver...): basta abrir
    return contexto_de(cmd) is not None


def tratar(cmd):
    """Clique numa ferramenta: abre o contexto que falta e/ou o painel que pede a seleção.
    Devolve True se cuidou do clique (o comando roda depois, sozinho); False para rodar normalmente."""
    if FreeCAD.ActiveDocument is None:
        return False
    ctx = contexto_de(cmd)
    if ctx is not None and not contexto_ativo(ctx):
        alvos = alvos_do_contexto(ctx)
        if not alvos:
            return False
        alvo = alvos[0] if len(alvos) == 1 else _alvo_pela_selecao(ctx, alvos)

        def seguir(a):
            try:
                ativar_contexto(ctx, a)
            except Exception as ex:
                FreeCAD.Console.PrintWarning("Usinix: não abriu %s: %s\n" % (a.Label, ex))
                return
            from PySide import QtCore
            QtCore.QTimer.singleShot(150, lambda: _depois_do_contexto(cmd))
        if alvo is not None:
            seguir(alvo)
        else:
            _escolher(alvos, seguir, "Abrir qual %s?" % NOMES_CONTEXTO[ctx])
        return True
    if precisa_de_painel(cmd):
        _pedir_ou_rodar(cmd)
        return True
    return False


def _pedir_ou_rodar(cmd):
    """Abre o painel de seleção; se ele já nasce completo (único candidato no projeto), roda direto."""
    p = pedir_para_comando(cmd, mostrar=False)
    if p.auto and p.completa():
        listas = [c.valores() for c in p.caixas]
        p.close()
        return rodar_com_selecao(cmd, *listas)
    return p.mostrar()


def _escolher(alvos, seguir, titulo):
    from PySide import QtGui, QtWidgets
    m = QtWidgets.QMenu(FreeCADGui.getMainWindow())
    m.setObjectName("PrumoEscolherContexto")
    m.addSection(titulo)
    for a in alvos:
        acao = m.addAction(a.Label)
        acao.triggered.connect(lambda _=False, a=a: seguir(a))
    m.popup(QtGui.QCursor.pos())
    _ESTADO["menu"] = m
    return m


_ESTADO = {"menu": None}


def _depois_do_contexto(cmd):
    if precisa_de_painel(cmd):
        _pedir_ou_rodar(cmd)
        return
    try:
        if FreeCADGui.Command.get(cmd).isActive():
            FreeCADGui.runCommand(cmd, 0)
    except Exception as ex:
        FreeCAD.Console.PrintWarning("Usinix: %s: %s\n" % (cmd, ex))


def _spec(cmd):
    e = SELECAO_PRIMEIRO[cmd]
    return e[0], e[1], e[2], (e[3] if len(e) > 3 else {})


def _filtro(f):
    return FILTROS.get(f, f) if isinstance(f, str) else f


def distribuir_selecao(caixas, selecao=None):
    """Como o painel encheria as caixas com a seleção atual: [valores de cada caixa]."""
    vals = [[] for _ in caixas]
    sel = FreeCADGui.Selection.getSelectionEx("", 0) if selecao is None else selecao
    for s in sel:
        for obj, els, caminhos in P.agrupar_selecao(s.Object, s.SubElementNames):
            for i, (_r, filtro, _mn, mx) in enumerate(caixas):
                f = _filtro(filtro)
                if getattr(f, "caminho_completo", False):
                    alvo, subs = s.Object, caminhos
                else:
                    alvo, subs = obj, els
                try:
                    itens = f(alvo, tuple(subs or ()))
                except Exception:
                    itens = []
                novos = [v for _t, v in itens or [] if v not in vals[i]]
                if mx is not None:
                    novos = novos[:max(mx - len(vals[i]), 0)]
                if novos:
                    vals[i] += novos
                    break
    return vals


def satisfeita(cmd):
    """A seleção atual já basta para o comando (pelas caixas do painel)."""
    caixas = _spec(cmd)[2]
    vals = distribuir_selecao(caixas)
    return all(len(v) >= c[2] for v, c in zip(vals, caixas))


def _pular(opcoes):
    p = opcoes.get("pular")
    if p == "isolado":
        try:
            import PrumoDireto
            return PrumoDireto.isolado() and not FreeCADGui.Selection.getSelection()
        except Exception:
            return False
    return bool(p() if callable(p) else False)


def precisa_de_painel(cmd):
    """True se o comando é do tipo 'seleção antes' e a seleção atual não basta: ele está desligado ou (nos que
    ficam ligados e reclamam depois do clique) a seleção não serve."""
    if cmd not in SELECAO_PRIMEIRO or FreeCAD.ActiveDocument is None:
        return False
    opcoes = _spec(cmd)[3]
    if _pular(opcoes):
        return False
    try:
        ativo = FreeCADGui.Command.get(cmd).isActive()
    except Exception:
        ativo = False
    if not ativo:
        return True
    if opcoes.get("confere"):
        return not satisfeita(cmd)
    return False


class PainelSelecao(P.PainelTarefa):
    """Painel genérico: caixas de seleção e, no OK, a função recebe as listas na ordem das caixas."""

    def __init__(self, titulo, instrucao, caixas, ao_confirmar, icone_cmd=None, adiar=True, auto=None,
                 unico=False):
        self.adiar = adiar
        # caixas de quantidade fixa (uma face, duas arestas...): cheias, o comando segue sem precisar do OK
        self.auto = all(c[3] is not None for c in caixas) if auto is None else auto
        self.unico = unico
        self._auto_feito = False
        self.titulo = titulo
        self.ajuda = instrucao
        self.icone_cmd = icone_cmd
        self._specs = caixas
        self._ao_confirmar = ao_confirmar
        super().__init__()

    def montar(self):
        s = self.form.secao("Seleção", "selecao")
        self.caixas = []
        for rotulo, filtro, minimo, maximo in self._specs:
            f = FILTROS.get(filtro, filtro) if isinstance(filtro, str) else filtro
            self.caixas.append(self.form.caixa(s, rotulo, f, minimo=minimo, maximo=maximo))
        s.texto(self.ajuda)

    def _preencher_com_selecao(self):
        # a seleção anterior vai enchendo as caixas na ordem (base, depois ferramenta...)
        for sel in FreeCADGui.Selection.getSelectionEx("", 0):
            for obj, els, caminhos in P.agrupar_selecao(sel.Object, sel.SubElementNames):
                for c in self.caixas:
                    cheia = c.maximo is not None and len(c.valores()) >= c.maximo
                    if getattr(c.filtro, "caminho_completo", False):
                        alvo, subs = sel.Object, caminhos
                    else:
                        alvo, subs = obj, els
                    if not cheia and c.aceitar(alvo, subs):
                        break
        if self.unico:
            self._candidato_unico()
        for c in self.caixas:
            if not c.pronta():
                self.form.ativar_caixa(c)
                break

    def _candidato_unico(self):
        """Caixa vazia com um só candidato no projeto inteiro (a malha, o solver do estudo): já vem escolhido."""
        doc = FreeCAD.ActiveDocument
        for c in self.caixas:
            if c.valores():
                continue
            cands = []
            for o in (doc.Objects if doc else []):
                try:
                    cands += [v for _t, v in c.filtro(o, ()) if v not in cands]
                except Exception:
                    pass
                if len(cands) > 1:
                    break
            if len(cands) == 1:
                c.aceitar(cands[0] if not isinstance(cands[0], tuple) else cands[0][0], ())

    def completa(self):
        return all(c.maximo is not None and len(c.valores()) >= c.maximo for c in self.caixas)

    def _seguir_sozinho(self):
        if self._auto_feito or not self._vivo() or P._ATIVO.get("painel") is not self:
            return
        if self.completa():
            self._auto_feito = True
            if self.accept():
                self.fechar()
            else:
                self._auto_feito = False

    def distribuir(self, obj, subnomes=(), raiz=None, caminhos=None):
        c = super().distribuir(obj, subnomes, raiz, caminhos)
        # caixa cheia passa a vez para a próxima (como o "próxima seleção" do SolidWorks)
        if c is not None and c.maximo is not None and len(c.valores()) >= c.maximo:
            i = self.caixas.index(c)
            for prox in self.caixas[i + 1:] + self.caixas[:i]:
                if not prox.pronta():
                    self.form.ativar_caixa(prox)
                    break
        if c is not None and self.auto and getattr(self, "aberto", False) and self.completa():
            from PySide import QtCore
            QtCore.QTimer.singleShot(250, self._seguir_sozinho)
        return c

    def executar(self):
        listas = [c.valores() for c in self.caixas]
        if self.adiar:
            # depois que o painel fechar: o passo seguinte costuma abrir outra janela ou painel
            from PySide import QtCore
            QtCore.QTimer.singleShot(0, lambda: self._ao_confirmar(*listas))
            return None
        return self._ao_confirmar(*listas)

    def accept(self):
        # sem transação própria: o comando chamado abre a dele
        falta = self.pendencia()
        if falta:
            self.form.mensagem.mostrar(falta, "erro")
            return False
        try:
            self.resultado = self.executar()
        except Exception as ex:
            self.form.mensagem.mostrar(str(ex), "erro")
            return False
        self._parar()
        return True


def pedir(titulo, instrucao, caixas, ao_confirmar, mostrar=True, adiar=True, auto=None, unico=False):
    """Abre o painel de seleção. ao_confirmar(lista1, lista2, ...) roda no OK (logo depois de o painel
    fechar, se adiar=True). auto: com as caixas de quantidade fixa cheias, segue sem o OK."""
    p = PainelSelecao(titulo, instrucao, caixas, ao_confirmar, adiar=adiar, auto=auto, unico=unico)
    if mostrar:
        p.mostrar()
    return p


def rodar_com_selecao(cmd, *listas):
    """Põe a seleção na ordem das caixas e roda o comando do FreeCAD."""
    selecionar(*listas)
    FreeCADGui.runCommand(cmd, 0)
    return True


def selecionar(*listas):
    """Refaz a seleção na ordem das caixas: objeto inteiro ou (objeto do topo, caminho do elemento)."""
    FreeCADGui.Selection.clearSelection()
    for lst in listas:
        for v in lst:
            if isinstance(v, tuple):
                o, sub = v
                FreeCADGui.Selection.addSelection(o.Document.Name, o.Name, sub)
            else:
                FreeCADGui.Selection.addSelection(v)


def pedir_para_comando(cmd, mostrar=True, adiar=True):
    titulo, instrucao, caixas, opcoes = _spec(cmd)
    return pedir(titulo, instrucao, caixas, lambda *ls: rodar_com_selecao(cmd, *ls), mostrar, adiar,
                 unico=bool(opcoes.get("unico")))
