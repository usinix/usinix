# SPDX-License-Identifier: LGPL-2.1-or-later
# Usinix - faixa de ferramentas (ribbon) em português para o FreeCAD.
"""Substitui as barras de ferramentas clássicas por uma faixa com abas e grupos.

Os botões reaproveitam as ações (QAction) dos próprios comandos do FreeCAD,
então habilitar/desabilitar, marcar e executar continuam sendo do FreeCAD.
Os rótulos são do Usinix, em português, independentes da tradução instalada.
"""

import FreeCAD
import FreeCADGui

try:
    from PySide import QtCore, QtGui, QtWidgets
except ImportError:  # pragma: no cover
    from PySide2 import QtCore, QtGui, QtWidgets

PARAM_PATH = "User parameter:BaseApp/Preferences/Mod/Usinix"
L, S = "L", "S"  # botão grande / pequeno
ICON_L, ICON_S = 32, 18

# --------------------------------------------------------------------------
# Nomes das bancadas em português
WB_NAMES = {
    "PartDesignWorkbench": "Peça",
    "SketcherWorkbench": "Esboço",
    "PartWorkbench": "Sólidos",
    "AssemblyWorkbench": "Montagem",
    "TechDrawWorkbench": "Desenho técnico",
    "SpreadsheetWorkbench": "Planilha",
    "UsinixWorkbench": "Usinix",
    "SMWorkbench": "Chapa metálica",
    "DraftWorkbench": "Desenho 2D",
    "CAMWorkbench": "Usinagem (CAM)",
    "FemWorkbench": "Simulação (FEM)",
    "InspectionWorkbench": "Inspeção",
    "MaterialWorkbench": "Materiais",
    "MeshWorkbench": "Malhas",
    "OpenSCADWorkbench": "OpenSCAD",
    "PointsWorkbench": "Nuvem de pontos",
    "ReverseEngineeringWorkbench": "Engenharia reversa",
    "RobotWorkbench": "Robótica",
    "SurfaceWorkbench": "Superfícies",
    "TestWorkbench": "Testes",
    "NoneWorkbench": "Nenhuma",
}

# --------------------------------------------------------------------------
# Abas. Cada item: (comando, tamanho, rótulo). "\n" quebra o rótulo grande.
TABS = [
    {"id": "inicio", "label": "Início", "wb": None, "panels": [
        ("Arquivo", [
            ("Std_New", L, "Novo"), ("Std_Open", L, "Abrir"), ("Std_Save", L, "Salvar"),
            ("Std_SaveAs", S, "Salvar como"), ("Std_Import", S, "Importar"), ("Std_Export", S, "Exportar"),
            ("Std_PrintPdf", S, "Exportar PDF"), ("Std_Print", S, "Imprimir"), ("Std_ProjectInfo", S, "Info. do projeto"),
            ("Usinix_CopiarProjeto", S, "Copiar projeto"), ("Std_Paste", L, "Colar"),
        ]),
        # sem documento aberto: começar uma peça, um esboço ou uma montagem (somem depois de abrir)
        ("Começar", [
            ("Usinix_NovaPeca", L, "Peça"), ("Usinix_NovoEsbocoAvulso", L, "Esboço"),
            ("Usinix_NovaMontagem", L, "Montagem"),
        ]),
        # Vista: saiu daqui; as vistas ficam na barra flutuante embaixo da vista 3D (UsinixBarraVista)
        ("Ferramentas", [
            ("Part_SelectFilter", S, "Filtro de seleção"),
            ("Std_ToggleClipPlane", S, "Plano de corte"), ("Usinix_Arvore", S, "Árvore do modelo"),
            ("Std_TreeViewActions", S, "Opções da árvore"), ("Usinix_JuntarPainel", S, "Juntar painel lateral"),
            ("Usinix_MedirXYZ", S, "Medir X, Y, Z"), ("Usinix_Isolar", S, "Isolar peça"),
            ("Std_DlgMacroExecute", S, "Macros"), ("Usinix_Preferencias", L, "Preferências"),
        ]),
        ("Estrutura", [
            ("Std_Part", S, "Nova parte"), ("Std_Group", S, "Novo grupo"), ("Part_Datums", S, "Referências"),
            ("Std_LinkActions", S, "Vínculos"), ("Std_VarSet", S, "Variáveis"),
        ]),
    ]},
    {"id": "esboco", "label": "Esboço", "wb": "SketcherWorkbench", "contexto": "esboco", "panels": [
        ("Esboço", [
            ("Sketcher_NewSketch|Usinix_Esboco3D", L, "Novo\nesboço"),
            ("Sketcher_EditSketch", L, "Editar\nesboço"),
            ("Sketcher_LeaveSketch", L, "Concluir\nesboço"),
            ("Sketcher_ViewSketch", S, "Vista normal"), ("Sketcher_ViewSection", S, "Vista em corte"),
            ("Sketcher_MapSketch", S, "Anexar"),
            # usados de vez em quando: num menu só
            ("Sketcher_ValidateSketch|Sketcher_ReorientSketch|Sketcher_MergeSketches|Sketcher_MirrorSketch", S,
             "Mais"),
        ]),
        ("Desenhar", [
            ("Sketcher_CreateLine|Sketcher_CreateConstructionLine|Sketcher_ToggleConstruction", L, "Linha"), ("Sketcher_CompCreateRectangles", L, "Retângulo"),
            ("Sketcher_CompCreateConic", L, "Círculo"), ("Sketcher_CompCreateArc", L, "Arco"),
            ("Sketcher_CreatePolyline", S, "Linha e arco tangente"), ("Sketcher_CreatePoint", S, "Ponto"),
            ("Sketcher_CompCreateRegularPolygon", S, "Polígono"), ("Sketcher_CompSlot", S, "Rasgo"),
            ("Sketcher_CompCreateBSpline", S, "Curva B-spline"),
        ]),
        # as relações (paralela, perpendicular, igual…) ficam no painel lateral, aba do esboço
        ("Cotar", [
            ("Sketcher_CompDimensionTools", L, "Cota"),
        ]),
        ("Modificar", [
            ("Sketcher_CompCurveEdition", L, "Aparar"), ("Sketcher_CompCreateFillets", L, "Arredondar"),
            ("Sketcher_Offset", S, "Offset"), ("Sketcher_Scale", S, "Escala"), ("Sketcher_CarbonCopy", S, "Cópia carbono"),
            ("Sketcher_RemoveAxesAlignment", S, "Remover alinhamento"),
        ]),
        ("Referências", [
            ("Sketcher_CompExternal", S, "Geometria externa"), ("Usinix_ReferenciasAuto", S, "Referências automáticas"),
        ]),
        ("Inserir", [
            ("Usinix_TextoEsboco", L, "Texto"), ("Usinix_ImportarDXF", L, "Importar\nDXF"),
            ("Usinix_MatrizCaminho", L, "Matriz em\ncaminho"),
        ]),
        ("Padrão", [
            ("Sketcher_Translate", L, "Padrão\nlinear"), ("Sketcher_Rotate", L, "Padrão\ncircular"),
            ("Sketcher_Symmetry", L, "Espelhar"),
        ]),
        # Auxiliares: no painel lateral, aba do esboço
    ]},
    {"id": "peca", "label": "Peça", "wb": "PartDesignWorkbench", "wb_extra": ["PartWorkbench"], "panels": [
        ("Corpo", [
            ("PartDesign_Body", L, "Novo\ncorpo"), ("PartDesign_CompSketches|Usinix_Esboco3D", L, "Esboço"),
            # um botão só: subforma (a mais completa), forma e clone no menu da setinha
            ("PartDesign_SubShapeBinder|PartDesign_ShapeBinder|PartDesign_Clone", L, "Vínculo"),
            # referências: só o Novo plano (grupo Ferramentas); o grupo Eixo, ponto, sistema saiu
        ]),
        ("Adicionar material", [
            ("PartDesign_Pad", L, "Extrusão"), ("PartDesign_Revolution", L, "Revolução"),
            ("PartDesign_AdditiveLoft", L, "Loft"), ("PartDesign_AdditivePipe", S, "Varredura"),
            ("Usinix_BarraVarredura", S, "Barra de varredura"),
            ("PartDesign_AdditiveHelix", S, "Hélice"),
            # da antiga Modelagem direta (Extrudar face saiu: a Extrusão já extruda uma face)
            ("Usinix_DesenharNaFace", S, "Desenhar na face"),
            ("Usinix_LinhaGuia", S, "Linha guia"),
        ]),
        ("Remover material", [
            ("PartDesign_Pocket", L, "Cavidade"), ("PartDesign_Hole", L, "Furo"),
            ("PartDesign_Groove", S, "Ranhura"), ("PartDesign_SubtractiveLoft", S, "Loft"),
            ("PartDesign_SubtractivePipe", S, "Varredura"), ("PartDesign_SubtractiveHelix", S, "Hélice"),
            ("PartDesign_CompPrimitiveSubtractive", S, "Sólido"),
        ]),
        ("Acabamento", [
            ("PartDesign_Fillet|Part_Fillet|Usinix_ArredondarAuto", L, "Arredondar"),
            ("PartDesign_Chamfer|Part_Chamfer", L, "Chanfro"),
            ("PartDesign_Thickness|Part_Thickness", S, "Casca"), ("PartDesign_Draft", S, "Ângulo de saída"),
        ]),
        ("Padrões", [
            ("PartDesign_Mirrored|Part_Mirror", L, "Espelhar"), ("PartDesign_LinearPattern|Usinix_MatrizFuracao", S, "Padrão linear"),
            ("PartDesign_PolarPattern", S, "Padrão circular"),
            ("PartDesign_MultiTransform", S, "Multitransformação"),
        ]),
        # Sólidos (bancada Part): só o que não tem igual no PartDesign. Arredondar, chanfro, casca e espelhar
        # de sólido solto ficam no menu dos botões de Acabamento e Padrões (sem botão repetido).
        ("Sólidos", [
            # sólido da peça e, no menu, as primitivas soltas (fora da peça)
            ("PartDesign_CompPrimitiveAdditive|Part_Box|Part_Cylinder|Part_Sphere|Part_Cone|Part_Torus|Part_Tube|"
             "Part_Primitives", L, "Sólido"),
            # Unir também traz a Booleana entre peças (corpos) do PartDesign
            ("Part_Fuse|PartDesign_Boolean", S, "Unir"), ("Part_Cut", S, "Subtrair"), ("Part_Common", S, "Interseção"),
            ("Part_Extrude|Part_Revolve|Part_Loft|Part_Sweep|Part_RuledSurface|Part_MakeFace", S,
             "Extrudar / girar sólido"),
            ("Part_CompJoinFeatures|Part_CompSplitFeatures|Part_CompCompoundTools", S, "Juntar / dividir"),
            ("Part_Section|Part_CrossSections|Part_ProjectionOnSurface", S, "Seção / projeção"),
            ("Part_Scale|Part_CompOffset|Part_Defeaturing", S, "Escala / offset"),
        ]),
        ("Ferramentas", [
            # Recalcular foi para a barra do topo (ao lado de Medir); Verificar geometria fica em Superfícies;
            # Validar esboço, na aba Esboço; Booleana, no menu de Unir
            ("PartDesign_Plane", L, "Novo\nplano"),
        ]),
        ("Dados da peça", [
            ("Usinix_Cotas", L, "Cotas da\noperação"), ("Usinix_Propriedades", L, "Propriedades\nda peça"),
            ("Usinix_Massa", L, "Propriedades\nde massa"), ("Usinix_ListaMateriais", L, "Lista de\nmateriais"),
            ("Usinix_Variantes", S, "Variantes da peça"),
        ]),
    ]},
    {"id": "montagem", "label": "Montagem", "wb": "AssemblyWorkbench", "panels": [
        ("Montagem", [
            ("Assembly_CreateAssembly", L, "Nova\nmontagem"), ("Usinix_EditarMontagem", L, "Abrir\nmontagem"),
            ("Assembly_Insert", L, "Inserir\ncomponente"),
            ("Assembly_InsertNewPart", S, "Nova peça aqui"), ("Usinix_PadraoComponentes", S, "Padrão de componentes"),
            ("Usinix_Posicionar", S, "Posicionar peça"), ("Usinix_MatrizLeve", S, "Matriz leve"),
            ("Usinix_ComponentesDosSolidos", S, "Componentes dos sólidos"),
            ("Assembly_SolveAssembly", S, "Resolver"), ("Assembly_CreateView", S, "Vista explodida"),
            ("Assembly_CreateSimulation", S, "Simulação"), ("Usinix_ListaMateriais", S, "Lista de materiais"),
            ("Usinix_Massa", S, "Propriedades de massa"), ("Usinix_Propriedades", S, "Propriedades da peça"),
        ]),
        # nomes como os das restrições (mates) do SolidWorks/Inventor; a dica diz a junta do FreeCAD
        ("Restrições", [
            ("Usinix_JuntaInteligente", L, "Junta\ninteligente"),
            ("Assembly_ToggleGrounded", L, "Fixar\npeça"), ("Assembly_CreateJointFixed", L, "Travar\n(fixa)"),
            ("Usinix_JuntaCoincidente", L, "Coincidente"), ("Usinix_JuntaTangente", L, "Tangente"),
            ("Assembly_CreateJointDistance", S, "Distância"),
            ("Assembly_CreateJointCylindrical", S, "Concêntrica"), ("Assembly_CreateJointRevolute", S, "Dobradiça"),
            ("Assembly_CreateJointSlider", S, "Deslizante"), ("Assembly_CreateJointParallel", S, "Paralela"),
            ("Assembly_CreateJointPerpendicular", S, "Perpendicular"), ("Assembly_CreateJointAngle", S, "Ângulo"),
            ("Assembly_CreateJointBall", S, "Esférica (rótula)"), ("Usinix_TravarJuntos", S, "Travar juntos"),
        ]),
        ("Mecânicas", [
            ("Usinix_MoverJunta", L, "Mover\njunta"),
            ("Assembly_CreateJointRackPinion", S, "Pinhão e cremalheira"), ("Assembly_CreateJointScrew", S, "Fuso"),
            ("Assembly_CreateJointGearBelt", S, "Engrenagem / correia"),
        ]),
        ("Apresentar", [
            ("Usinix_Explosao", L, "Explosão\nanimada"),
        ]),
        ("Conferir", [
            ("Usinix_Interferencia", L, "Verificar\ninterferência"), ("Usinix_MedirXYZ", S, "Medir X, Y, Z"),
            ("Usinix_Isolar", S, "Isolar peça"),
        ]),
    ]},
    # na ordem do trabalho: folha -> vistas -> cotas -> anotação -> entregar. Sem folha aberta, só aparece o
    # que começa um desenho; as ferramentas raras ficam no "Mais" de cada grupo (ver RAROS)
    {"id": "desenho", "label": "Desenho", "wb": "TechDrawWorkbench", "panels": [
        ("Folha", [
            ("Usinix_InserirDesenho", L, "Inserir peça\nou montagem"),
            ("Usinix_NovaFolha", L, "Folha\nABNT"), ("Usinix_PaletaVistas", L, "Paleta de\nvistas"),
            ("Usinix_AbrirFolha", S, "Abrir folha"), ("Usinix_FolhasLote", S, "Folhas em lote"),
            ("Usinix_FolhasBarras", S, "Folhas das barras"), ("Usinix_FolhaChapa", S, "Folha da chapa"),
            ("Usinix_IsolarSolido", S, "Isolar sólido"), ("Usinix_ListaMateriais", S, "Lista de materiais"),
            ("TechDraw_PageDefault", S, "Folha em branco"), ("TechDraw_PageTemplate", S, "Folha de modelo"),
            ("TechDraw_FillTemplateFields", S, "Preencher carimbo"), ("TechDraw_RedrawPage", S, "Redesenhar"),
        ]),
        ("Vistas", [
            ("TechDraw_View", L, "Vista"), ("TechDraw_SectionGroup", L, "Corte"), ("Usinix_VistaDetalhe", L, "Detalhe"),
            ("TechDraw_GeometricHatch", S, "Hachura"), ("TechDraw_ShowAll", S, "Arestas ocultas"),
            ("TechDraw_BrokenView", S, "Vista interrompida"), ("TechDraw_ActiveView", S, "Vista da tela"),
            ("TechDraw_DraftView", S, "Vista 2D"), ("TechDraw_ClipGroup", S, "Recorte"),
            ("TechDraw_StackGroup", S, "Ordem das vistas"), ("TechDraw_Hatch", S, "Hachura (imagem)"),
            ("TechDraw_ToggleFrame", S, "Molduras"), ("TechDraw_ExtensionLockUnlockView", S, "Travar vista"),
        ]),
        ("Cotas", [
            ("TechDraw_CompDimensionTools", L, "Cota"), ("Usinix_CotasGerais", L, "Cotas\ngerais"),
            ("Usinix_CotasCorte", S, "Cotas do corte"), ("Usinix_TextoCota", S, "Texto da cota"),
            ("Usinix_Baloes", L, "Balões\nda lista"), ("TechDraw_Balloon", S, "Balão avulso"),
            ("TechDraw_AxoLengthDimension", S, "Cota axonométrica"), ("TechDraw_DimensionRepair", S, "Reparar cotas"),
            ("TechDraw_ExtensionInsertPrefixGroup", S, "Prefixo ⌀"),
            ("TechDraw_ExtensionIncreaseDecreaseGroup", S, "Casas decimais"),
        ]),
        ("Anotação", [
            ("TechDraw_Annotation", L, "Texto"), ("Usinix_Solda2D", L, "Solda"),
            ("Usinix_Rugosidade", S, "Rugosidade"), ("Usinix_AjusteFuroEixo", S, "Ajuste furo / eixo"),
            ("TechDraw_LeaderLine", S, "Linha de chamada"),
            ("TechDraw_CenterLineGroup", S, "Linha de centro"),
            ("TechDraw_ExtensionCircleCenterLinesGroup", S, "Centro de círculo"),
            ("TechDraw_ExtensionThreadsGroup", S, "Rosca cosmética"),
            ("TechDraw_RichTextAnnotation", S, "Texto formatado"), ("TechDraw_CosmeticVertexGroup", S, "Vértice cosmético"),
            ("TechDraw_2PointCosmeticLine", S, "Linha cosmética"), ("TechDraw_DecorateLine", S, "Estilo de linha"),
            ("TechDraw_WeldSymbol", S, "Solda (FreeCAD)"), ("TechDraw_SurfaceFinishSymbols", S, "Rugosidade (FreeCAD)"),
        ]),
        ("Entregar", [
            ("Usinix_SalvarPDF", L, "Salvar\nPDF"), ("Usinix_ExportarDXF", S, "Exportar DXF"),
            ("Usinix_ExportarExcel", S, "Exportar para Excel"), ("Usinix_DXFLote", S, "DXF de todas as chapas"),
            ("TechDraw_PrintAll", S, "Imprimir"),
        ]),
    ]},
    {"id": "estruturas", "label": "Estruturas", "wb": None, "panels": [
        ("Estrutura soldada", [
            ("Usinix_Estrutura", L, "Estrutura\nsoldada"), ("Usinix_EditarEstrutura", L, "Editar\nestrutura"),
            ("Usinix_Cantos", L, "Cantos"), ("Usinix_TrabalhosBarra", L, "Trabalhos\nna barra"),
            ("Usinix_CorteEstrutura", L, "Cortar\nbarras"),
            ("Usinix_PecaNaFace", L, "Peça na\nface"),
            ("Usinix_PadraoEstrutura", S, "Padrão de estrutura"),
            ("Usinix_TrocarPerfil", S, "Trocar perfil"), ("Usinix_AtualizarEstrutura", S, "Atualizar estrutura"),
            ("Usinix_SecaoPersonalizada", S, "Seção personalizada"),
        ]),
        ("Reforços e ligações", [
            ("Usinix_Reforco", L, "Reforço"), ("Usinix_Tampa", L, "Tampa de\nextremidade"),
            ("Usinix_PlacaBase", L, "Placa de\nbase"),
        ]),
        ("Pisos e fechamentos", [
            ("Usinix_Piso", L, "Piso e\nfechamento"),
        ]),
        ("Solda", [
            ("Usinix_Solda", L, "Cordão de\nsolda"), ("Usinix_ListaSoldas", S, "Lista de soldas"),
            ("Usinix_ListaDeCorte", S, "Lista de corte"), ("Usinix_TabelaFuros", S, "Tabela de furos"),
            ("Usinix_FolhasBarras", S, "Folhas das barras"), ("Usinix_ExportarExcel", S, "Exportar para Excel"),
        ]),
        # parafusos, porcas e arruelas: na aba Componentes
        ("Calcular", [
            ("Usinix_AssistenteEstrutura", L, "Assistente de\nestruturas"),
            ("Usinix_AnaliseEstrutura", L, "Simular\nestrutura"),
        ]),
        ("Conferir", [
            ("Usinix_Massa", L, "Propriedades\nde massa"), ("Usinix_ListaMateriais", L, "Lista de\nmateriais"),
            ("Usinix_Propriedades", S, "Propriedades da peça"), ("Usinix_Interferencia", S, "Interferência"),
        ]),
        ("Aprender", [("Usinix_TutorialEstrutura", L, "Tutorial")]),
    ]},
    {"id": "tubulacao", "label": "Tubulação", "wb": None, "panels": [
        ("Traçado", [
            ("Usinix_Esboco3D", L, "Esboço\n3D"), ("Sketcher_NewSketch", L, "Esboço\nplano"),
        ]),
        ("Tubulação", [
            ("Usinix_Tubulacao", L, "Tubos e\nconexões"), ("Usinix_IsometricoTubulacao", L, "Folha\nisométrica"),
        ]),
        ("Ar-condicionado (dutos)", [
            ("Usinix_Dutos", L, "Dutos\n(HVAC)"), ("Usinix_EditarDuto", S, "Editar duto"),
        ]),
        ("Conferir", [
            ("Usinix_Interferencia", L, "Verificar\ninterferência"),
            ("Usinix_ListaMateriais", S, "Lista de materiais"),
        ]),
    ]},
    {"id": "componentes", "label": "Componentes", "wb": None, "panels": [
        ("Máquinas", [
            ("Usinix_Componentes_motores", L, "Motores"), ("Usinix_Componentes_compressores", L, "Compressores"),
            ("Usinix_Componentes_caldeiras", L, "Caldeiras"), ("Usinix_Componentes_secadores", L, "Secadores"),
            ("Usinix_Componentes_icamento", L, "Içamento"),
        ]),
        ("Água e utilidades", [
            ("Usinix_Componentes_agua", L, "Reservatórios"), ("Usinix_Componentes_recipientes", L, "Galões e\ntambores"),
            ("Usinix_Componentes_resfriamento", L, "Torres de\nresfriamento"),
        ]),
        ("Tubulação e ar", [
            ("Usinix_Componentes_valvulas", L, "Válvulas"), ("Usinix_Componentes_ar", L, "Ar\ncomprimido"),
        ]),
        ("Fixação e transmissão", [
            ("Usinix_Fixador", L, "Parafuso,\nporca, arruela"), ("Usinix_Componentes_transmissao", L, "Rolamentos"),
        ]),
        ("Segurança e pessoas", [
            ("Usinix_Componentes_altura", L, "Trabalho\nem altura"),
            ("Usinix_Componentes_incendio", L, "Combate a\nincêndio"), ("Usinix_Componentes_pessoas", L, "Pessoas"),
        ]),
        ("Outros", [
            ("Usinix_Componentes_outros", L, "Bombas,\nquadros e mais"), ("Usinix_Componentes", S, "Todos os componentes"),
            # gera placa com furos, flange, suporte em L ou eixo escalonado pelo formulário (saiu da aba Peça)
            ("Usinix_Modelo", S, "Modelo com regras"),
        ]),
    ]},
    {"id": "chapa", "label": "Chapa", "wb": "SMWorkbench", "panels": [
        ("Criar", [
            ("SheetMetal_AddBase", L, "Parede\nbase"), ("SheetMetal_BaseShape", S, "Formas prontas"),
            ("SheetMetal_FromSolid", S, "Chapa de sólido"), ("SheetMetal_SketchOnSheet", S, "Esboço na chapa"),
        ]),
        ("Dobras e abas", [
            ("SheetMetal_AddWall", L, "Aba"), ("SheetMetal_AddFoldWall", L, "Dobrar\npor linha"),
            ("SheetMetal_Extrude", S, "Estender"), ("SheetMetal_ExtendBySketch", S, "Estender por esboço"),
            ("SheetMetal_AddBend", S, "Dobra em aresta"), ("SheetMetal_AddHem", S, "Bainha"),
            ("SheetMetal_AddJunction", S, "Junção (fenda)"),
        ]),
        ("Recortes", [
            ("SheetMetal_AddCutout", L, "Recorte"), ("SheetMetal_AddRelief", S, "Alívio de dobra"),
            ("SheetMetal_AddCornerRelief", S, "Alívio de canto"), ("SheetMetal_Forming", S, "Estampar"),
        ]),
        ("Planificar", [
            ("SheetMetal_Unfold", L, "Planificar"), ("Usinix_ChapaDXF", L, "Planificar\nem DXF"), ("Usinix_FolhaChapa", L, "Folha da\nchapa"), ("Usinix_DXFLote", S, "DXF de todas"),
            ("SheetMetal_UnfoldUpdate", S, "Atualizar planificações"), ("Usinix_TabelaK", S, "Tabela de fator K"),
        ]),
    ]},
    {"id": "planilha", "label": "Planilha", "wb": "SpreadsheetWorkbench", "panels": [
        ("Planilha", [
            ("Spreadsheet_CreateSheet", L, "Nova\nplanilha"), ("Spreadsheet_Import", S, "Importar"),
            ("Spreadsheet_Export", S, "Exportar"), ("Spreadsheet_SetAlias", S, "Apelido"),
        ]),
        ("Células", [
            ("Spreadsheet_MergeCells", S, "Mesclar"), ("Spreadsheet_SplitCell", S, "Dividir"),
            ("Spreadsheet_StyleBold", S, "Negrito"), ("Spreadsheet_StyleItalic", S, "Itálico"),
            ("Spreadsheet_StyleUnderline", S, "Sublinhado"),
        ]),
        ("Alinhamento", [
            ("Spreadsheet_AlignLeft", S, "Esquerda"), ("Spreadsheet_AlignCenter", S, "Centro"),
            ("Spreadsheet_AlignRight", S, "Direita"), ("Spreadsheet_AlignTop", S, "Topo"),
            ("Spreadsheet_AlignVCenter", S, "Meio"), ("Spreadsheet_AlignBottom", S, "Base"),
        ]),
    ]},
    {"id": "simulacao", "label": "Simulação", "wb": "FemWorkbench", "panels": [
        # Na ordem em que a análise precisa ser montada
        ("Assistente", [("Usinix_AssistenteFEM", L, "Assistente\nde simulação"),
                        ("Usinix_AssistenteEstrutura", L, "Assistente de\nestruturas"),
                        ("Usinix_AnaliseEstrutura", S, "Estrutura por barras"),
                        ("Usinix_EsqueletoMEF", S, "Esqueleto da estrutura")]),
        ("1 · Estudo", [("FEM_Analysis", L, "Novo\nestudo"), ("FEM_SolverCalculiXCcxTools", L, "Solver\nCalculiX"),
                        ("Usinix_DuplicarAnalise", S, "Duplicar análise")]),
        ("2 · Material", [("FEM_MaterialSolid", L, "Material\nsólido"), ("FEM_MaterialEditor", S, "Editor de materiais")]),
        ("3 · Fixações", [("FEM_ConstraintFixed", L, "Fixação"), ("FEM_ConstraintDisplacement", S, "Deslocamento imposto"),
                          ("FEM_ConstraintSpring", S, "Mola (apoio elástico)")]),
        ("4 · Cargas", [("FEM_ConstraintForce", L, "Força"), ("FEM_ConstraintPressure", S, "Pressão"),
                        ("Usinix_CargaNaPonta", S, "Carga na ponta"),
                        ("FEM_ConstraintSelfWeight", S, "Peso próprio"), ("FEM_ConstraintCentrif", S, "Centrífuga")]),
        ("5 · Malha", [("FEM_MeshGmshFromShape", L, "Gerar\nmalha"), ("FEM_MeshRegion", S, "Refino local"),
                       ("FEM_MeshDisplayInfo", S, "Dados da malha"), ("FEM_MeshClear", S, "Limpar malha")]),
        ("6 · Calcular", [("FEM_SolverRun", L, "Calcular"), ("FEM_SolverControl", S, "Controle do solver")]),
        ("7 · Resultados", [("FEM_ResultShow", L, "Ver\nresultados"), ("FEM_PostFilterWarp", S, "Deformada"),
                            ("FEM_PostFilterClipScalar", S, "Recorte por valor"), ("FEM_PostFilterDataAlongLine", S, "Gráfico ao longo de linha"),
                            ("FEM_ResultsPurge", S, "Limpar resultados")]),
        ("8 · Relatório", [("Usinix_RelatorioMEF", L, "Relatório\nda análise")]),
    ]},
    {"id": "superficies", "label": "Superfícies", "wb": "SurfaceWorkbench", "wb_extra": ["PartWorkbench"], "panels": [
        ("Superfície", [
            ("Surface_Filling", L, "Preencher"), ("Surface_GeomFillSurface", L, "Pelas\narestas"),
            ("Surface_Sections", S, "Por seções"), ("Surface_ExtendFace", S, "Estender face"),
            ("Surface_BlendCurve", S, "Curva de concordância"), ("Surface_CurveOnMesh", S, "Curva sobre malha"),
        ]),
        # loft, varredura, regrada e face de esboços ficam na aba Peça › Sólidos (um lugar só para cada ferramenta)
        ("Fechar", [
            ("Part_Builder", L, "Sólido das\nfaces"), ("Part_CheckGeometry", S, "Verificar geometria"),
        ]),
    ]},
    {"id": "usinix", "label": "Usinix", "wb": None, "panels": [
        ("Geral", [
            ("Usinix_Inicio", L, "Tela\ninicial"), ("Usinix_AplicarTema", L, "Aplicar\ntema"),
            ("Usinix_TemaEscuro", L, "Tema\nescuro"), ("Usinix_Preferencias", L, "Preferências"),
            ("Usinix_Sobre", L, "Sobre"), ("Usinix_VerificarAtualizacoes", L, "Verificar\natualizações"),
            ("Usinix_Sugestao", L, "Enviar\nsugestão"),
        ]),
        ("Interface", [
            ("Usinix_TemaIcones", S, "Tema de ícones"), ("Usinix_BarrasClassicas", S, "Barras clássicas"),
            ("Usinix_RemoverSplash", S, "Splash original"), ("Usinix_ModoDistribuicao", S, "Modo distribuição"),
        ]),
        ("Aprender", [("Usinix_Tutorial", L, "Tutorial\nprimeira peça"),
                      ("Usinix_TutorialEstrutura", L, "Tutorial\nestrutura"),
                      ("Usinix_GuiaMigracao", L, "Vindo do\nSolidWorks")]),
        ("Inteligência artificial", [("Usinix_ConectarIA", L, "Conectar\nIA")]),
        ("Qualidade", [("Usinix_Testes", L, "Testes\nautomáticos"), ("Usinix_Validacao", L, "Validação\ndo cálculo")]),
    ]},
]


# Abas que só aparecem enquanto a bancada delas está ativa (no lugar da aba temporária): nenhuma por ora.
ABAS_TEMPORARIAS = {}

STD_TOOLBARS = {"File", "Edit", "Clipboard", "Workbench", "Macro", "View", "Individual Views", "Structure", "Help"}


def _classes_workbench(pasta):
    """Nomes das classes de bancada definidas nos InitGui.py / init_gui.py de uma pasta de complemento."""
    import os
    import re
    nomes = []
    padrao = re.compile(r"^class\s+(\w+)\s*\(\s*(?:FreeCADGui\.|Gui\.)?Workbench\s*\)", re.M)
    for raiz, subpastas, arquivos in os.walk(pasta):
        subpastas[:] = [d for d in subpastas if not d.startswith((".", "__"))]
        if raiz[len(pasta):].count(os.sep) > 3:
            subpastas[:] = []
        for a in arquivos:
            if a in ("InitGui.py", "init_gui.py"):
                try:
                    with open(os.path.join(raiz, a), encoding="utf-8", errors="ignore") as f:
                        nomes += padrao.findall(f.read())
                except OSError:
                    pass
    return nomes


def bancadas_externas():
    """[(nome da bancada, rótulo)] das bancadas instaladas pelo usuário (complementos na pasta Mod dos dados do
    usuário), ligadas e sem aba própria do Usinix. Cada uma ganha uma aba na faixa, sem precisar ativar nada."""
    import os
    try:
        mod = os.path.join(FreeCAD.getUserAppDataDir(), "Mod")
        pastas = [os.path.join(mod, d) for d in sorted(os.listdir(mod)) if os.path.isdir(os.path.join(mod, d))]
    except OSError:
        pastas = []
    try:
        import UsinixGui
        desligadas = set(UsinixGui.bancadas_desligadas())
    except Exception:
        desligadas = set()
    proprias = {t.get("wb") for t in TABS} | {w for t in TABS for w in t.get("wb_extra", ())}
    proprias |= {"UsinixWorkbench", "StartWorkbench", "NoneWorkbench"}
    try:
        registradas = FreeCADGui.listWorkbenches()
    except Exception:
        registradas = {}
    r = []
    for pasta in pastas:
        if os.path.basename(pasta) == "Usinix":
            continue
        for nome in _classes_workbench(pasta):
            if nome in registradas and nome not in desligadas and nome not in proprias and nome not in [x[0] for x in r]:
                wb = registradas[nome]
                r.append((nome, WB_NAMES.get(nome) or getattr(wb, "MenuText", nome) or nome))
    return r

RIBBON_QSS = """
#UsinixRibbon { background: #FFFFFF; }
#UsinixTabRow { background: #F5F8FC; border-bottom: 1px solid #DCE4EC; }
#UsinixTabRow QTabBar { background: transparent; }
#UsinixTabRow QTabBar::tab {
    background: transparent; color: #2E3B4A; border: none;
    padding: 7px 16px 6px 16px; margin: 0 1px; font-size: 10pt;
    border-top: 3px solid transparent;
}
#UsinixTabRow QTabBar::tab:hover { color: #003A70; background: #EAF1F8; }
#UsinixTabRow QTabBar::tab:selected {
    color: #003A70; background: #FFFFFF; font-weight: 600;
    border-top: 3px solid #F7BE00; border-left: 1px solid #DCE4EC; border-right: 1px solid #DCE4EC;
}
#UsinixTabRow[compacto="1"] QTabBar::tab { padding: 7px 11px 6px 11px; }
#UsinixTabRow[compacto="2"] QTabBar::tab { padding: 7px 8px 6px 8px; }
#UsinixTabRow[compacto="3"] QTabBar::tab { padding: 7px 6px 6px 6px; font-size: 9.5pt; }
#UsinixTabRow[compacto="4"] QTabBar::tab { padding: 7px 5px 6px 5px; font-size: 9pt; }
#UsinixTabRow QTabBar QToolButton { background: #FFFFFF; border: 1px solid #C9D5E2; border-radius: 4px;
    width: 18px; margin: 5px 1px; padding: 0; }
#UsinixTabRow QTabBar QToolButton:hover { background: #EAF1F8; border-color: #7FA3C9; }
#UsinixTabRow QTabBar QToolButton:disabled { background: #F5F8FC; border-color: #E3EAF2; }
#UsinixBrand { color: #003A70; font-weight: 700; font-size: 10.5pt; padding: 0 14px 0 8px; }
#UsinixContent { background: #FFFFFF; border: none; border-bottom: 1px solid #DCE4EC; }
#UsinixContent > QWidget, #UsinixPage, #UsinixCol { background: #FFFFFF; }
#UsinixPage QWidget, #UsinixPage QLabel { background: #FFFFFF; color: #1F2A36; }
#UsinixTabRow QLabel { background: transparent; }
#UsinixPage #UsinixPanelTitle { color: #66727F; font-size: 8pt; padding: 1px 0 3px 0; background: transparent; }
#UsinixPage #UsinixSep { background: #DCE4EC; margin: 6px 0 6px 0; }
#UsinixPanel { background: transparent; border: none; }
#UsinixSplit, #UsinixResto { background: #FFFFFF; }
#UsinixSplit::handle:horizontal { background: #FFFFFF; border-left: 1px solid #DCE4EC; margin: 8px 4px 8px 4px; }
#UsinixSplit::handle:horizontal:hover { border-left: 3px solid #7FA3C9; margin: 8px 3px 8px 3px; }
#UsinixGrip { background: #F5F8FC; border-bottom: 1px solid #DCE4EC; }
#UsinixGrip:hover { background: #DCE8F4; }


#UsinixRibbon QToolButton {
    background: transparent; border: 1px solid transparent; border-radius: 5px;
    color: #1F2A36; padding: 2px 4px; font-size: 9pt;
}
#UsinixRibbon QToolButton:hover { background: #EAF1F8; border-color: #C9DAEA; }
#UsinixRibbon QToolButton:pressed, #UsinixRibbon QToolButton:checked { background: #D8E6F3; border-color: #9FBEDD; }
#UsinixRibbon QToolButton:disabled { color: #A3ADB8; }
#UsinixRibbon QToolButton[inativo="true"] { color: #A3ADB8; }
#UsinixRibbon QToolButton[sw_size="L"] { padding: 3px 4px 2px 4px; }
#UsinixRibbon QToolButton[sw_size="L"][popupMode="1"] { padding-bottom: 12px; }
#UsinixRibbon QToolButton[sw_size="L"]::menu-button {
    subcontrol-origin: border; subcontrol-position: bottom center;
    width: 100%; height: 11px; border: none; border-top: 1px solid transparent;
    border-bottom-left-radius: 5px; border-bottom-right-radius: 5px;
}
#UsinixRibbon QToolButton[sw_size="L"]::menu-button:hover { background: #D8E6F3; }
#UsinixRibbon QToolButton[sw_size="S"][popupMode="1"] { padding-right: 14px; }
#UsinixRibbon QToolButton::menu-arrow { width: 7px; height: 7px; }
#UsinixQuick QToolButton { padding: 3px; border-radius: 4px; }
#UsinixTabRow QToolButton#UsinixWbBtn {
    background: #FFFFFF; color: #003A70; font-weight: 600; font-size: 9pt;
    border: 1px solid #C9D5E2; border-radius: 6px; padding: 3px 22px 3px 10px; margin: 0 2px;
}
#UsinixTabRow QToolButton#UsinixWbBtn:hover { background: #EAF1F8; border-color: #7FA3C9; }
#UsinixTabRow QToolButton#UsinixWbBtn::menu-indicator {
    subcontrol-origin: padding; subcontrol-position: center right; right: 7px; width: 9px; height: 9px;
}
#UsinixWbSep { color: #D5DEE8; background: transparent; }
"""

# Estilo global complementar (aplicado sobre o tema do FreeCAD)
GLOBAL_QSS = """
/*USINIX-BEGIN*/
QMenuBar { background: #FFFFFF; border: none; border-bottom: 1px solid #E3EAF2; padding: 2px 6px; }
QMenuBar::item { padding: 4px 10px; border-radius: 4px; color: #1F2A36; background: transparent; }
QMenuBar::item:disabled { color: #9AA7B4; }
QMenuBar::item:selected { background: #EAF1F8; color: #003A70; }
QMenu { background: #FFFFFF; color: #1F2A36; border: 1px solid #D5DEE8; padding: 4px; }
QMenu::item { padding: 5px 26px 5px 26px; border-radius: 4px; color: #1F2A36; background: transparent; }
QMenu::item:disabled { color: #9AA7B4; }
QMenu::item:selected { background: #EAF1F8; color: #003A70; }
QMenu::separator { height: 1px; background: #E3EAF2; margin: 4px 8px; }
QStatusBar { background: #F5F8FC; border-top: 1px solid #E3EAF2; color: #4A5866; }
QDockWidget { font-weight: 600; color: #003A70; }
QDockWidget::title { background: #F5F8FC; padding: 6px 8px; border-bottom: 1px solid #E3EAF2; }
QTabBar::tab:selected { color: #003A70; }
QToolTip { background: #FFFFFF; color: #1F2A36; border: 1px solid #D5DEE8; padding: 8px 10px; }
/*USINIX-END*/
"""


def _params():
    return FreeCAD.ParamGet(PARAM_PATH)


def _clean(text):
    return text.replace("&&", "\x00").replace("&", "").replace("\x00", "&").strip()


def _acoes_de(nomes):
    """Ações de um ou mais comandos ("A|B|C" na faixa vira um botão com menu); de um grupo do FreeCAD
    entram todas as ações de dentro dele, sem separadores e sem repetir."""
    if len(nomes) == 1:
        return _cmd_actions(nomes[0])
    res, vistos = [], set()
    for n in nomes:
        for a in _cmd_actions(n):
            if not a.text() or a.isSeparator():
                continue
            chave = (a.text(), a.whatsThis())
            if chave in vistos:
                continue
            vistos.add(chave)
            res.append(a)
    return res


def _cmd_actions(name):
    try:
        cmd = FreeCADGui.Command.get(name)
    except Exception:
        return []
    if cmd is None:
        return []
    try:
        acts = [a for a in (cmd.getAction() or []) if a is not None]
    except Exception:
        acts = []
    if not acts:
        # comandos Python sem barra nem menu (os do Usinix e os de pacotes externos) só têm ação
        # depois de a bancada usá-los: sem ação o botão some da faixa
        acts = [_own_action(name, cmd)]
    for a in acts:
        # grupos do Python (Inserir componente, Juntar/dividir...) não dizem o nome do comando na ação
        if a is not None and not a.whatsThis() and not a.property("usinix_cmd"):
            a.setProperty("usinix_cmd", name)
    return [a for a in acts if a is not None]


_OWN_ACTIONS = {}


def _own_action(name, cmd):
    """O FreeCAD só cria a QAction de um comando Python quando alguma barra/menu o usa.

    Os comandos Usinix só entram em barras da bancada Usinix, então antes de ela ser
    ativada eles não têm ação. Criamos uma ação própria que executa o comando.
    """
    if name in _OWN_ACTIONS:
        return _OWN_ACTIONS[name]
    try:
        info = cmd.getInfo()
    except Exception:
        info = {}
    import os as _os
    QAction = getattr(QtGui, "QAction", None) or QtWidgets.QAction
    act = QAction(FreeCADGui.getMainWindow())

    def tr(texto):
        # getInfo devolve o texto de origem (inglês): traduz como o FreeCAD faria
        if not texto:
            return texto
        for ctx in (name, cmd.__class__.__name__ if hasattr(cmd, "__class__") else name):
            t = QtCore.QCoreApplication.translate(ctx, texto)
            if t and t != texto:
                return t
        return texto

    act.setText(tr(info.get("menuText")) or name)
    tip = tr(info.get("toolTip") or "")
    act.setToolTip(tip)
    act.setStatusTip(tip)
    pix = info.get("pixmap") or ""
    if pix and _os.path.isfile(pix):
        act.setIcon(QtGui.QIcon(pix))
    elif pix:
        try:
            act.setIcon(FreeCADGui.getIcon(pix))
        except Exception:
            pass
    act.triggered.connect(lambda checked=False, n=name: FreeCADGui.runCommand(n, 0))
    _OWN_ACTIONS[name] = act
    return act


# -------------------------------------------------------------------------- ícones e dicas
import hashlib
import os

_HERE = os.path.dirname(os.path.abspath(__file__))
_DIS_CACHE = {}
_TIP_CACHE = {}


def _t(texto):
    """Cores do tema ativo (claro ou escuro)."""
    try:
        import UsinixEstilo
        return UsinixEstilo.tema(texto)
    except Exception:
        return texto


def _escuro():
    try:
        import UsinixEstilo
        return UsinixEstilo.escuro()
    except Exception:
        return False


def _disabled_pixmap(pm):
    """Versão desabilitada legível: véu cinza-azulado sobre o ícone, 78 % de opacidade."""
    tinted = QtGui.QPixmap(pm.size())
    tinted.fill(QtCore.Qt.transparent)
    p = QtGui.QPainter(tinted)
    p.drawPixmap(0, 0, pm)
    p.setCompositionMode(QtGui.QPainter.CompositionMode_SourceAtop)
    if not _escuro():
        p.fillRect(tinted.rect(), QtGui.QColor(150, 166, 186, 120))
    p.end()
    out = QtGui.QPixmap(pm.size())
    out.fill(QtCore.Qt.transparent)
    p = QtGui.QPainter(out)
    p.setOpacity(0.5 if _escuro() else 0.78)
    p.drawPixmap(0, 0, tinted)
    p.end()
    out.setDevicePixelRatio(pm.devicePixelRatio())
    return out


def _with_disabled(icon, size):
    """Mesmo ícone, com o modo Desabilitado desenhado pelo Usinix."""
    if icon.isNull():
        return icon
    key = (icon.cacheKey(), size)
    if key in _DIS_CACHE:
        return _DIS_CACHE[key]
    dpr = 2.0
    pm = icon.pixmap(QtCore.QSize(size, size) * dpr)
    pm.setDevicePixelRatio(dpr)
    out = QtGui.QIcon()
    out.addPixmap(pm, QtGui.QIcon.Normal)
    out.addPixmap(pm, QtGui.QIcon.Active)
    out.addPixmap(_disabled_pixmap(pm), QtGui.QIcon.Disabled)
    _DIS_CACHE[key] = out
    return out


def _tip_image(icon):
    """Grava o ícone em 44 px para usar na dica rica (o QToolTip só aceita arquivo)."""
    d = os.path.join(FreeCAD.getUserAppDataDir(), "UsinixUI", "dicas")
    key = str(icon.cacheKey())
    if key in _TIP_CACHE:
        return _TIP_CACHE[key]
    try:
        os.makedirs(d, exist_ok=True)
        path = os.path.join(d, hashlib.md5(key.encode()).hexdigest()[:12] + ".png")
        icon.pixmap(88, 88).save(path)
        _TIP_CACHE[key] = path.replace("\\", "/")
    except Exception:
        _TIP_CACHE[key] = None
    return _TIP_CACHE[key]


def _tip_desc(raw, titles):
    """Texto da dica do FreeCAD sem o título repetido e sem o nome interno do comando."""
    if not raw:
        return ""
    doc = QtGui.QTextDocument()
    doc.setHtml(raw) if "<" in raw else doc.setPlainText(raw)
    out = []
    low = {_clean(t).lower() for t in titles if t}
    for line in doc.toPlainText().splitlines():
        t = line.strip()
        if not t or _clean(t).lower() in low:
            continue
        if " " not in t and "_" in t:      # PartDesign_Pad, Std_Open...
            continue
        out.append(t)
    return " ".join(out)


def _rich_tip(icon, title, desc, shortcut):
    img = _tip_image(icon) if not icon.isNull() else None
    body = "<div style='font-weight:600; color:#003A70; font-size:10pt'>{}</div>".format(title)
    if desc:
        body += "<div style='color:#4A5866; margin-top:3px'>{}</div>".format(desc)
    if shortcut:
        body += ("<div style='margin-top:6px'><span style='background:#EEF2F8; color:#003A70; "
                 "font-weight:600'>&nbsp;{}&nbsp;</span></div>").format(shortcut)
    body = _t(body)
    if not img:
        return "<div style='max-width:300px'>{}</div>".format(body)
    return ("<table cellspacing='0' cellpadding='0'><tr>"
            "<td valign='top' style='padding-right:10px'><img src='{}' width='44' height='44'></td>"
            "<td valign='top' width='240'>{}</td></tr></table>").format(img, body)


# --------------------------------------------------------------------------
L_ALTURA = 98   # botão grande: ícone + rótulo em até duas linhas (+ seta de menu)
S_ALTURA = 30   # botão pequeno (três por coluna)

# Altura da área dos botões (arrastável pela borda de baixo da faixa; duplo clique volta ao padrão)
ALTURA_PADRAO, ALTURA_MIN, ALTURA_MAX = 136, 112, 200


def medidas(altura):
    """Tamanhos dos botões e ícones para uma altura da área de botões."""
    altura = max(ALTURA_MIN, min(ALTURA_MAX, int(altura)))
    l_alt = altura - 38
    s_alt = max(26, (l_alt - 6) // 3)
    icon_l = max(24, min(48, int(round(32.0 * l_alt / 98))))
    icon_s = max(16, min(24, int(round(18.0 * s_alt / 30))))
    return {"altura": altura, "L": l_alt, "S": s_alt, "iconL": icon_l, "iconS": icon_s}


_MED = medidas(ALTURA_PADRAO)


def tela_pequena(limite=900):
    """Tela de notebook (altura útil abaixo de ~900 px): começa com a faixa mais baixa."""
    try:
        tela = QtWidgets.QApplication.primaryScreen()
        return tela.availableGeometry().height() < limite
    except Exception:
        return False


def altura_salva():
    # altura travada: mudar a altura não ajudava; o ajuste fica só na largura dos grupos (divisores)
    return ALTURA_MIN if tela_pequena() else ALTURA_PADRAO


def _quebra(texto):
    """Rótulos longos dos botões grandes em duas linhas, quebrando no espaço mais central."""
    if "\n" in texto or len(texto) <= 11 or " " not in texto:
        return texto
    meio = len(texto) / 2.0
    pos = min((i for i, c in enumerate(texto) if c == " "), key=lambda i: abs(i - meio))
    return texto[:pos] + "\n" + texto[pos + 1:]


def ordenar_abas(tabs):
    """As abas na ordem que o usuário deixou (arrastando); as que não estão na ordem gravada (novas) entram ao
    lado da vizinha de sempre."""
    try:
        gravada = [x for x in _params().GetString("OrdemAbas", "").split(",") if x]
    except Exception:
        gravada = []
    if not gravada:
        return tabs
    pos = {tid: k for k, tid in enumerate(gravada)}
    res = [t for t in tabs if t["id"] in pos]
    res.sort(key=lambda t: pos[t["id"]])
    # as novas (ex.: abas de um pacote instalado depois) entram logo depois da aba que vem antes delas na ordem de
    # sempre (Escadas depois de Estruturas, onde quer que o usuário tenha posto Estruturas); sem vizinha, no fim
    for k, t in enumerate(tabs):
        if t["id"] in pos:
            continue
        antes = next((tabs[j] for j in range(k - 1, -1, -1) if tabs[j] in res), None)
        res.insert(res.index(antes) + 1 if antes is not None else len(res), t)
    return res


class RibbonButton(QtWidgets.QToolButton):
    """Botão ligado a uma ou várias QActions de um comando do FreeCAD."""

    def __init__(self, actions, size, label, parent=None):
        super().__init__(parent)
        self._actions = actions
        self._size = size
        self._label = label
        self._current = actions[0]
        self.setProperty("sw_size", size)
        self.setAutoRaise(True)
        self.setFocusPolicy(QtCore.Qt.NoFocus)
        # Política "Minimum" na horizontal: o botão nunca fica mais estreito que o texto (sem "Enq…tudo");
        # se a janela for estreita, a faixa ganha rolagem em vez de cortar os nomes.
        if size == L:
            self.setToolButtonStyle(QtCore.Qt.ToolButtonTextUnderIcon)
            self.setIconSize(QtCore.QSize(_MED["iconL"], _MED["iconL"]))
            self.setMinimumWidth(54)
            self.setFixedHeight(_MED["L"])
            self.setSizePolicy(QtWidgets.QSizePolicy.Minimum, QtWidgets.QSizePolicy.Fixed)
        else:
            self.setToolButtonStyle(QtCore.Qt.ToolButtonTextBesideIcon)
            self.setIconSize(QtCore.QSize(_MED["iconS"], _MED["iconS"]))
            self.setSizePolicy(QtWidgets.QSizePolicy.Minimum, QtWidgets.QSizePolicy.Fixed)
            self.setFixedHeight(_MED["S"])
        if len(actions) > 1:
            menu = QtWidgets.QMenu(self)
            for a in actions:
                menu.addAction(_com_rotulo(_proxy_selecao(a, self) or a, self))
            menu.triggered.connect(self._on_menu)
            self.setMenu(menu)
            self.setPopupMode(QtWidgets.QToolButton.MenuButtonPopup)
        self.clicked.connect(self._on_click)
        for a in actions:
            a.changed.connect(self._sync)
        self._sync()

    def largura_do_texto(self):
        """Largura que o rótulo precisa (o sizeHint do Qt subestima com folha de estilo e Poppins)."""
        self.ensurePolished()
        fm = QtGui.QFontMetrics(self.font())
        linhas = self.text().split("\n") or [""]
        txt = max(fm.horizontalAdvance(l) for l in linhas) if hasattr(fm, "horizontalAdvance") else \
            max(fm.width(l) for l in linhas)
        if self._size == L:
            return max(54, txt + 16, _MED["iconL"] + 16)
        if self.toolButtonStyle() == QtCore.Qt.ToolButtonIconOnly:
            return _MED["iconS"] + 14 + (14 if self.menu() is not None else 0)
        return _MED["iconS"] + txt + 22 + (14 if self.menu() is not None else 0)

    def _ajustar_largura(self):
        self.setMinimumWidth(self.largura_do_texto())

    def setToolButtonStyle(self, estilo):
        super().setToolButtonStyle(estilo)
        if getattr(self, "_size", None) is not None and self.text():
            self._ajustar_largura()

    def _on_menu(self, action):
        self._current = getattr(action, "_original", action)
        self._sync()

    def nome_comando(self, a=None):
        a = a or self._current
        n = a.whatsThis() if a is not None else ""
        if not n and a is not None and len(self._actions) > 1:
            n = _comando_pelo_texto(a.text()) or (a.property("usinix_cmd") or "")
        return n or (getattr(self, "_cmd", "") if len(self._actions) == 1 else "")

    def ativo(self):
        """A ferramenta pode rodar agora (o botão fica clicável mesmo quando não pode, para explicar)."""
        return not bool(self.property("inativo"))

    def _on_click(self):
        a = self._current
        nome = self.nome_comando(a)
        rotulo = self._label.replace("\n", " ") if (self._label and len(self._actions) == 1) else None
        import UsinixAvisoClique as AV
        import UsinixArredondar
        if UsinixArredondar.desviar_para_juncao(nome):
            pass
        elif _pedir_selecao(nome):
            pass
        elif a is not None and a.isEnabled():
            AV.executar(nome, a.trigger, rotulo)
        elif a is not None:
            AV.clique_inativo(nome, rotulo)
        self._sync()

    def _sync(self):
        try:
            self._do_sync()
        except RuntimeError:  # botão ou ação já destruídos
            pass

    def _do_sync(self):
        a = self._current
        icon = a.icon()
        if icon.isNull():
            for x in self._actions:
                if not x.icon().isNull():
                    icon = x.icon()
                    break
        fixo = ICONES_FAIXA.get(self.nome_comando(a) or (a.property("usinix_cmd") or ""))
        if fixo:
            icon = _icone_fixo(fixo)
        self._icone_base = icon
        txt = self._label if self._label else _clean(a.text())
        self.setText(_quebra(txt) if self._size == L else txt)
        self._ajustar_largura()
        action_title = _clean(a.text())
        title = self._label.replace("\n", " ") if (self._label and len(self._actions) == 1) else action_title
        desc = _tip_desc(a.toolTip() or a.statusTip(), (title, action_title))
        sc = a.shortcut().toString(QtGui.QKeySequence.NativeText)
        key = (title, desc, sc, icon.cacheKey())
        if getattr(self, "_tipkey", None) != key:
            self._tipkey = key
            self.setToolTip(_rich_tip(icon, title, desc, sc))
        enabled = any(x.isEnabled() for x in self._actions) if len(self._actions) > 1 else a.isEnabled()
        if not enabled and _selecao_depois(self.nome_comando(a)):
            enabled = True     # sem seleção, o clique abre o painel que pede a seleção
        # A ferramenta que não pode rodar agora fica com cara de desligada, mas o clique continua chegando:
        # assim ele explica por quê (UsinixAvisoClique) em vez de não fazer nada.
        self.setEnabled(True)
        tam = _MED["iconL"] if self._size == L else _MED["iconS"]
        ic = _with_disabled(getattr(self, "_icone_base", icon), tam)
        if not enabled and not ic.isNull():
            ic = QtGui.QIcon(ic.pixmap(QtCore.QSize(tam, tam), QtGui.QIcon.Disabled))
        self.setIcon(ic)
        if bool(self.property("inativo")) != (not enabled):
            self.setProperty("inativo", not enabled)
            self.style().unpolish(self)
            self.style().polish(self)
        # Em grupos (menu), o botão não espelha o estado "marcado" da subopção
        checkable = a.isCheckable() and len(self._actions) == 1
        self.setCheckable(checkable)
        if checkable:
            self.setChecked(a.isChecked())


def _selecao_depois(nome):
    """Comando que exige seleção antes (ou uma montagem/folha/estudo aberto) mas que, no Usinix, abre o que
    falta e pede a seleção depois: o botão fica ligado."""
    try:
        import UsinixSelecao
        return UsinixSelecao.pode_pedir(nome)
    except Exception:
        return False


def _comando_pelo_texto(texto):
    try:
        import UsinixSelecao
        return UsinixSelecao.comando_pelo_texto(texto)
    except Exception:
        return ""


def _pedir_selecao(nome):
    """Se falta o contexto (montagem, folha, estudo) ou a seleção, cuida disso e devolve True: o comando roda
    depois, sozinho."""
    try:
        import UsinixSelecao
        return UsinixSelecao.tratar(nome)
    except Exception as exc:
        FreeCAD.Console.PrintWarning("Usinix: seleção para {}: {}\n".format(nome, exc))
    return False


# ícones do Usinix no lugar do ícone do FreeCAD (o do Recalcular é miúdo perto dos outros)
# ícone próprio na faixa; ":/..." é recurso do FreeCAD. O grupo de referências do PartDesign não tem ícone
# antes de a bancada o usar, e o botão sem ícone mostrava o nome cortado ("E…a") no grupo estreitado.
ICONES_FAIXA = {"Std_Refresh": "recalcular.svg", "PartDesign_CompDatums": ":/icons/PartDesign_Plane.svg"}
_CACHE_ICONES = {}


def _icone_fixo(arq):
    if arq not in _CACHE_ICONES:
        if arq.startswith(":"):
            _CACHE_ICONES[arq] = QtGui.QIcon(arq)
        else:
            import UsinixUtil
            _CACHE_ICONES[arq] = QtGui.QIcon(UsinixUtil.icone(arq))
    return _CACHE_ICONES[arq]


# No menu da setinha, quando a peça (corpo) e o sólido solto têm o mesmo nome, cada um diz para que serve
ROTULOS_MENU = {
    "PartDesign_Fillet": "Arredondar na peça (corpo)", "Part_Fillet": "Arredondar sólido solto",
    "PartDesign_Chamfer": "Chanfro na peça (corpo)", "Part_Chamfer": "Chanfro em sólido solto",
    "PartDesign_Thickness": "Casca na peça (corpo)", "Part_Thickness": "Casca de sólido solto",
    "PartDesign_Mirrored": "Espelhar na peça (corpo)", "Part_Mirror": "Espelhar sólido solto",
    # 1.20.1: botões que juntaram ferramentas (Vínculo, Unir, Sólido)
    "PartDesign_Clone": "Clonar",
    "Part_Fuse": "Unir sólidos soltos", "PartDesign_Boolean": "Booleana entre peças (corpos)",
    "PartDesign_AdditiveBox": "Caixa na peça", "PartDesign_AdditiveCylinder": "Cilindro na peça",
    "PartDesign_AdditiveSphere": "Esfera na peça", "PartDesign_AdditiveCone": "Cone na peça",
    "PartDesign_AdditiveEllipsoid": "Elipsoide na peça", "PartDesign_AdditiveTorus": "Toro na peça",
    "PartDesign_AdditivePrism": "Prisma na peça", "PartDesign_AdditiveWedge": "Cunha na peça",
    "Part_Box": "Caixa solta", "Part_Cylinder": "Cilindro solto", "Part_Sphere": "Esfera solta",
    "Part_Cone": "Cone solto", "Part_Torus": "Toro solto", "Part_Tube": "Tubo solto",
    "Part_Primitives": "Outras primitivas soltas…",
}


def _com_rotulo(a, parent):
    """A ação no menu da setinha com o rótulo de ROTULOS_MENU (cópia que dispara a original)."""
    nome = a.whatsThis() or getattr(getattr(a, "_original", None), "whatsThis", lambda: "")()
    rot = ROTULOS_MENU.get(nome)
    if not rot:
        return a
    if getattr(a, "_original", None) is not None:
        a.setText(rot)
        return a
    QAction = getattr(QtGui, "QAction", None) or QtWidgets.QAction
    px = QAction(a.icon(), rot, parent)
    px.setToolTip(a.toolTip())
    px._original = a
    px.triggered.connect(lambda checked=False, original=a: original.trigger() if original.isEnabled() else
                         _clique_inativo(original))
    return px


def _clique_inativo(a):
    try:
        import UsinixAvisoClique as AV
        AV.clique_inativo(a.whatsThis(), a.text())
    except Exception:
        pass


def _proxy_selecao(a, parent):
    """No menu dos grupos, a ação desligada por falta de seleção vira uma cópia sempre ligada."""
    nome = a.whatsThis()
    if not _nome_selecao(nome):
        return None
    QAction = getattr(QtGui, "QAction", None) or QtWidgets.QAction
    px = QAction(a.icon(), a.text(), parent)
    px.setToolTip(a.toolTip())
    px._original = a

    def disparar(checked=False, original=a, n=nome):
        if not _pedir_selecao(n) and original.isEnabled():
            original.trigger()
    px.triggered.connect(disparar)
    return px


def _nome_selecao(nome):
    try:
        import UsinixSelecao
        return nome in UsinixSelecao.SELECAO_PRIMEIRO or UsinixSelecao.contexto_de(nome) is not None
    except Exception:
        return False


def _largura_estilo(b, estilo):
    atual = b.toolButtonStyle()
    QtWidgets.QToolButton.setToolButtonStyle(b, estilo)
    w = b.largura_do_texto()
    QtWidgets.QToolButton.setToolButtonStyle(b, atual)
    return w


class RibbonPanel(QtWidgets.QFrame):
    def __init__(self, title, parent=None):
        super().__init__(parent)
        self.setObjectName("UsinixPanel")
        outer = QtWidgets.QVBoxLayout(self)
        outer.setContentsMargins(4, 3, 4, 0)
        outer.setSpacing(0)
        self.row = QtWidgets.QHBoxLayout()
        self.row.setSpacing(2)
        self.row.setContentsMargins(0, 0, 0, 0)
        self.row.setAlignment(QtCore.Qt.AlignLeft | QtCore.Qt.AlignTop)
        outer.addLayout(self.row, 1)
        cap = QtWidgets.QLabel(title)
        self._cap = cap
        cap.setObjectName("UsinixPanelTitle")
        cap.setAlignment(QtCore.Qt.AlignCenter)
        cap.setFixedHeight(20)
        outer.addWidget(cap)
        self._col = None
        self.count = 0

    def pequenos(self):
        return [b for b in self.findChildren(QtWidgets.QToolButton) if b.property("sw_size") == S]

    def larguras(self):
        """(natural, compacta): largura com os nomes dos botões pequenos e só com os ícones."""
        nat = comp = 0
        n = 0
        self._colunas = []
        import UsinixUI
        for _i, w in UsinixUI.widgets_do_layout(self.row):
            n += 1
            if isinstance(w, RibbonButton):
                lw = w.largura_do_texto()
                nat += lw
                comp += lw
                continue
            if isinstance(w, QtWidgets.QLabel):
                nat += w.sizeHint().width()
                comp += w.sizeHint().width()
                continue
            bs = [b for b in w.findChildren(QtWidgets.QToolButton) if hasattr(b, "largura_do_texto")]
            if not bs:
                continue
            com = max(_largura_estilo(b, QtCore.Qt.ToolButtonTextBesideIcon) for b in bs)
            sem = max(_largura_estilo(b, QtCore.Qt.ToolButtonIconOnly) for b in bs)
            nat += com
            comp += sem
            self._colunas.append((bs, com - sem))
        extra = self.row.spacing() * max(n - 1, 0) + 8
        cap = self._cap.fontMetrics().boundingRect(self._cap.text()).width() + 16
        self._so_icones = comp + extra
        return max(nat + extra, cap), max(comp + extra, cap)

    def preparar(self):
        self._natural, self._compacta = self.larguras()
        self.setMinimumWidth(self._compacta)

    def compacto(self):
        ps = self.pequenos()
        return bool(ps) and all(b.toolButtonStyle() == QtCore.Qt.ToolButtonIconOnly for b in ps)

    def resizeEvent(self, ev):
        super().resizeEvent(ev)
        nat = getattr(self, "_natural", None)
        if nat is None:
            return
        # Os nomes voltam coluna a coluna, da esquerda para a direita, conforme o espaço dado ao grupo (antes era
        # tudo ou nada: só com a largura inteira, e alargar um pouco não mostrava nome nenhum).
        # Folga de alguns pixels: o divisor arredonda as larguras.
        livre = ev.size().width() - getattr(self, "_so_icones", nat) + 10
        cabe = True
        for bs, ganho in getattr(self, "_colunas", []):
            cabe = cabe and ganho <= livre
            if cabe:
                livre -= ganho
            estilo = QtCore.Qt.ToolButtonTextBesideIcon if cabe else QtCore.Qt.ToolButtonIconOnly
            for b in bs:
                try:
                    if b.toolButtonStyle() != estilo:
                        b.setToolButtonStyle(estilo)
                except RuntimeError:
                    pass

    def add(self, btn, size):
        self.count += 1
        if size == L:
            self._col = None
            self.row.addWidget(btn)
            return
        if self._col is None or self._col.count() >= 3:
            w = QtWidgets.QWidget()
            w.setObjectName("UsinixCol")
            w.setAttribute(QtCore.Qt.WA_StyledBackground, True)
            self._col = QtWidgets.QVBoxLayout(w)
            self._col.setContentsMargins(0, 0, 0, 0)
            self._col.setSpacing(1)
            self._col.setAlignment(QtCore.Qt.AlignTop)
            self.row.addWidget(w)
        self._col.addWidget(btn)


class AlcaAltura(QtWidgets.QWidget):
    """Borda de baixo da faixa: arrastar muda a altura (botões e ícones acompanham); duplo clique
    volta ao padrão."""

    def __init__(self, ribbon):
        super().__init__(ribbon)
        self.ribbon = ribbon
        self.setObjectName("UsinixGrip")
        self.setAttribute(QtCore.Qt.WA_StyledBackground, True)
        self.setFixedHeight(6)
        self.setCursor(QtCore.Qt.SizeVerCursor)
        self.setToolTip("Arraste para aumentar ou diminuir a faixa · duplo clique: altura padrão")
        self._y0 = None

    def mousePressEvent(self, ev):
        if ev.button() == QtCore.Qt.LeftButton:
            self._y0 = ev.globalPosition().y() if hasattr(ev, "globalPosition") else ev.globalY()
            self._h0 = self.ribbon.content.height()

    def mouseMoveEvent(self, ev):
        if self._y0 is None:
            return
        y = ev.globalPosition().y() if hasattr(ev, "globalPosition") else ev.globalY()
        h = max(ALTURA_MIN, min(ALTURA_MAX, int(self._h0 + y - self._y0)))
        self.ribbon.content.setFixedHeight(h)

    def mouseReleaseEvent(self, ev):
        if self._y0 is None:
            return
        self._y0 = None
        self.ribbon.definir_altura(self.ribbon.content.height())

    def mouseDoubleClickEvent(self, ev):
        self.ribbon.definir_altura(ALTURA_PADRAO)


class BarraAbas(QtWidgets.QTabBar):
    """Barra de abas da faixa: as abas marcadas com "destaque" (as de pacotes externos) saem com o cabeçalho
    azul, o nome em branco e o filete amarelo em cima; o conteúdo da aba é igual ao das outras."""

    AZUL, AZUL_CLARO, AMARELO = "#003A70", "#0B4F8F", "#F7BE00"

    def __init__(self, *a):
        super().__init__(*a)
        self.destaques = set()

    def paintEvent(self, ev):
        super().paintEvent(ev)
        if not self.destaques:
            return
        p = QtGui.QPainter(self)
        p.setRenderHint(QtGui.QPainter.TextAntialiasing)
        compacto = str((self.parentWidget().property("compacto") if self.parentWidget() else "") or "")
        tam = {"3": 9.5, "4": 9.0}.get(compacto, 10.0)
        mouse = self.mapFromGlobal(QtGui.QCursor.pos())
        for i in range(self.count()):
            if self.tabData(i) not in self.destaques:
                continue
            r = QtCore.QRectF(self.tabRect(i)).adjusted(1, 0, -1, 0)
            if not r.intersects(QtCore.QRectF(ev.rect())):
                continue
            sel = i == self.currentIndex()
            cor = self.AZUL_CLARO if (not sel and self.tabRect(i).contains(mouse)) else self.AZUL
            p.fillRect(r, QtGui.QColor(cor))
            p.fillRect(QtCore.QRectF(r.x(), r.y(), r.width(), 3.0 if sel else 2.0), QtGui.QColor(self.AMARELO))
            f = QtGui.QFont(self.font())
            f.setPointSizeF(tam)
            f.setWeight(QtGui.QFont.DemiBold if sel else QtGui.QFont.Normal)
            p.setFont(f)
            p.setPen(QtGui.QColor("#FFFFFF"))
            p.drawText(r.adjusted(0, 2, 0, 0), QtCore.Qt.AlignCenter, self.tabText(i))
        p.end()


class UsinixRibbon(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("UsinixRibbon")
        self.setAttribute(QtCore.Qt.WA_StyledBackground, True)
        self.setStyleSheet(_t(RIBBON_QSS))
        self._tabs = ordenar_abas(list(TABS))
        self._dynamic = None  # aba gerada para bancadas sem aba própria
        self._edit_prev = None
        self._ctx_edicao = None
        self._precarregadas = {}
        self._ignorar_sync = False
        self._building = False

        lay = QtWidgets.QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)

        # Linha das abas
        row = QtWidgets.QWidget()
        row.setObjectName("UsinixTabRow")
        row.setAttribute(QtCore.Qt.WA_StyledBackground, True)
        rl = QtWidgets.QHBoxLayout(row)
        rl.setContentsMargins(6, 0, 6, 0)
        rl.setSpacing(4)
        brand = QtWidgets.QLabel()
        brand.setObjectName("UsinixBrand")
        _ic = os.path.join(_HERE, "Resources", "icons", "usinix.svg")
        if os.path.isfile(_ic):
            _pm = QtGui.QIcon(_ic).pixmap(40, 40)
            _pm.setDevicePixelRatio(2.0)
            brand.setText("<table cellspacing='0' cellpadding='0'><tr><td valign='middle'><img src='{}' width='20' height='20'></td>"
                          "<td valign='middle' style='padding-left:6px'>Usinix</td></tr></table>".format(_ic.replace("\\", "/")))
        else:
            brand.setText("Usinix")
        brand.setSizePolicy(QtWidgets.QSizePolicy.Minimum, QtWidgets.QSizePolicy.Preferred)
        rl.addWidget(brand)
        # sem seletor de bancadas: tudo fica nas abas (as bancadas sem aba saem de vista no Usinix)
        rl.addSpacing(4)
        self.tabbar = BarraAbas()
        self.tabbar.setMouseTracking(True)
        self.tabbar.setDrawBase(False)
        self.tabbar.setExpanding(False)
        # tela estreita (notebook com escala de 150–200 %): as abas rolam em vez de impor largura mínima à
        # janela (sem isso a janela pedia ~1500 px e o Windows não conseguia encaixá-la na tela)
        self.tabbar.setUsesScrollButtons(True)
        self.tabbar.setElideMode(QtCore.Qt.ElideNone)
        self.tabbar.setSizePolicy(QtWidgets.QSizePolicy.Preferred, QtWidgets.QSizePolicy.Fixed)
        self.tabbar.setFocusPolicy(QtCore.Qt.NoFocus)
        for t in self._tabs:
            i = self.tabbar.addTab(t["label"])
            self.tabbar.setTabData(i, t["id"])
            if t.get("destaque"):
                self.tabbar.destaques.add(t["id"])
        self.tabbar.currentChanged.connect(self._on_tab_changed)
        self.tabbar.tabBarDoubleClicked.connect(self._toggle_collapse)
        # segurar e arrastar uma aba muda a ordem (fica gravada para a próxima vez)
        self.tabbar.setMovable(True)
        self.tabbar.tabMoved.connect(self._aba_movida)
        # a barra de abas fica com todo o espaço que sobra (as abas continuam à esquerda): a aba ativa, em
        # negrito, cresce sem empurrar a última para fora
        rl.addWidget(self.tabbar, 1)
        self._quick_box = self._build_quick()
        rl.addWidget(self._quick_box)
        lay.addWidget(row)
        # tela estreita: as abas aparecem com o nome inteiro; a linha se compacta por etapas (setas só em
        # janela pequena demais para qualquer arranjo)
        self._row, self._brand, self._brand_html, self._nivel_linha = row, brand, brand.text(), -1
        row.installEventFilter(self)

        # Área de conteúdo
        self.content = QtWidgets.QScrollArea()
        self.content.setObjectName("UsinixContent")
        self.content.setFrameShape(QtWidgets.QFrame.NoFrame)
        self.content.setWidgetResizable(True)
        self.content.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        self.content.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAsNeeded)
        self.content.viewport().setAutoFillBackground(True)
        pal = self.content.viewport().palette()
        pal.setColor(QtGui.QPalette.Window, QtGui.QColor(_t("background: #FFFFFF").split(": ")[1]))
        self.content.viewport().setPalette(pal)
        global _MED
        _MED = medidas(altura_salva())
        self.content.setFixedHeight(_MED["altura"])
        lay.addWidget(self.content)
        self.grip = AlcaAltura(self)
        lay.addWidget(self.grip)
        self.grip.setVisible(False)   # altura travada (só os divisores entre grupos se movem)
        self.content.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        self.content.customContextMenuRequested.connect(self._menu_faixa)
        # tela estreita (notebook): a roda do mouse sobre a faixa rola para os lados
        self._roda = _RodaParaOsLados(self.content)
        self.content.viewport().installEventFilter(self._roda)

    def _menu_faixa(self, pos):
        m = QtWidgets.QMenu(self)
        a1 = m.addAction("Restaurar a largura dos grupos desta aba")
        a2 = m.addAction("Altura padrão da faixa")
        m.addSeparator()
        a3 = m.addAction("Mostrar só as ferramentas do momento")
        a3.setCheckable(True)
        a3.setChecked(faixa_contextual())
        a3.setToolTip("Desmarcado, a faixa mostra todas as ferramentas, com o que não se aplica esmaecido")
        esc = m.exec(self.content.mapToGlobal(pos)) if hasattr(m, "exec") else m.exec_(self.content.mapToGlobal(pos))
        if esc is a1:
            self.restaurar_larguras()
        elif esc is a2:
            self.definir_altura(ALTURA_PADRAO)
        elif esc is a3:
            _params().SetBool("RibbonContextual", a3.isChecked())
            idx = self.tabbar.currentIndex()
            if 0 <= idx < len(self._tabs):
                self.build(self._tabs[idx])

    # ---- (sem seletor de bancadas na faixa: cada bancada usada no Usinix tem sua aba)
    def _rotulo_bancada(self, name):
        b = getattr(self, "_wb_btn", None)
        if b is None:
            return
        try:
            wb = FreeCADGui.getWorkbench(name)
            nome = WB_NAMES.get(name) or getattr(wb, "MenuText", name)
        except Exception:
            nome = WB_NAMES.get(name, name)
        b.setText(nome if name not in ("NoneWorkbench", "StartWorkbench") else "Bancadas")
        b.setToolTip("Bancada ativa: {}. Clique para trocar.".format(nome))

    # ---- barra de acesso rápido (direita)
    def _build_quick(self):
        box = QtWidgets.QWidget()
        box.setObjectName("UsinixQuick")
        hl = QtWidgets.QHBoxLayout(box)
        hl.setContentsMargins(0, 0, 0, 0)
        hl.setSpacing(1)
        # Medir e Recalcular ficam só aqui (vale em todas as abas) e nunca some, nem com a janela estreita
        for name, tip in (("Std_New", "Novo"), ("Std_Open", "Abrir"), ("Std_Save", "Salvar"),
                          ("Std_Undo", "Desfazer"), ("Std_Redo", "Refazer"), ("|", ""),
                          ("Usinix_Medir", "Medir"), ("Std_Refresh", "Recalcular")):
            if name == "|":
                sep = QtWidgets.QFrame(box)
                sep.setFrameShape(QtWidgets.QFrame.VLine)
                sep.setStyleSheet("color: #3A4450;" if _escuro() else "color: #D5DEE8;")
                sep.setFixedHeight(18)
                hl.addSpacing(4)
                hl.addWidget(sep)
                hl.addSpacing(4)
                continue
            acts = _cmd_actions(name)
            if not acts:
                # Comandos padrão também podem ainda não ter QAction quando a faixa
                # é montada; usamos uma ação própria que executa o comando.
                try:
                    cmd = FreeCADGui.Command.get(name)
                except Exception:
                    cmd = None
                if cmd is not None:
                    a = _own_action(name, cmd)
                    if a is not None:
                        a.setToolTip(tip)
                        acts = [a]
            if acts:
                b = RibbonButton(acts[:1], S, "", box)
                b._cmd = name
                b.setProperty("usinix_dispensavel", name in ("Std_Undo", "Std_Redo"))
                b.setToolButtonStyle(QtCore.Qt.ToolButtonIconOnly)
                b.setIconSize(QtCore.QSize(18, 18))
                b.setFixedSize(28, 28)
                hl.addWidget(b)
        hl.addSpacing(6)
        # procurar comando (como a busca do Fusion/SolidCraft): Ctrl+K em qualquer lugar
        busca = QtWidgets.QToolButton(box)
        busca.setObjectName("UsinixBuscaBotao")
        busca.setIcon(QtGui.QIcon(os.path.join(_HERE, "Resources", "icons", "busca.svg")))
        busca.setIconSize(QtCore.QSize(18, 18))
        busca.setFixedSize(28, 28)
        busca.setAutoRaise(True)
        busca.setToolTip("Procurar comando (Ctrl+K): digite parte do nome e tecle Enter")
        busca.clicked.connect(self.procurar_comando)
        busca._cmd = "Usinix_ProcurarComando"      # o "Mostrar onde" do guia acha a lupa por este nome
        self._busca_btn = busca
        hl.addWidget(busca)
        self._atalho_busca = None
        QtCore.QTimer.singleShot(3000, self._instalar_atalho_busca)
        hl.addSpacing(4)
        col = QtWidgets.QToolButton(box)
        col.setArrowType(QtCore.Qt.UpArrow)
        col.setToolTip("Recolher / expandir a faixa (ou duplo clique na aba)")
        col.clicked.connect(self._toggle_collapse)
        self._collapse_btn = col
        hl.addWidget(col)
        return box

    ATALHO_BUSCA = "Ctrl+K"

    def _instalar_atalho_busca(self):
        """Ctrl+K para Procurar comando, se nenhum comando já usa (atalho repetido não funciona em nenhum dos
        dois no Qt). Roda depois que as bancadas carregaram os atalhos delas."""
        if self._atalho_busca is not None:
            return self._atalho_busca
        seq = QtGui.QKeySequence(self.ATALHO_BUSCA)
        mw = FreeCADGui.getMainWindow()
        QAction = getattr(QtGui, "QAction", None) or QtWidgets.QAction
        for a in mw.findChildren(QAction):
            try:
                if any(k == seq for k in a.shortcuts()):
                    FreeCAD.Console.PrintLog("Usinix: Ctrl+K já é de '%s'; Procurar comando fica só na lupa\n"
                                             % a.text())
                    self._busca_btn.setToolTip("Procurar comando: digite parte do nome e tecle Enter")
                    return None
            except RuntimeError:
                continue
        try:
            atalho = (getattr(QtGui, "QShortcut", None) or QtWidgets.QShortcut)(seq, mw)
            atalho.setContext(QtCore.Qt.ApplicationShortcut)
            atalho.activated.connect(self.procurar_comando)
            self._atalho_busca = atalho
        except Exception as exc:
            FreeCAD.Console.PrintLog("Usinix: atalho da busca: %s\n" % exc)
        return self._atalho_busca

    def procurar_comando(self):
        import UsinixBuscaComandos
        if getattr(self, "_busca", None) is None:
            self._busca = UsinixBuscaComandos.BuscaComandos(self, self)
        self._busca.abrir(self._busca_btn if self._busca_btn.isVisible() else self)
        return self._busca

    # ------------------------------------------------------------------ linha das abas em tela estreita
    def eventFilter(self, obj, ev):
        if obj is getattr(self, "_row", None) and ev.type() == QtCore.QEvent.Resize:
            QtCore.QTimer.singleShot(0, self._ajustar_linha)
        return super().eventFilter(obj, ev)

    def _aplicar_nivel(self, n):
        row = self._row
        row.setProperty("compacto", str(n))
        if n >= 2:
            self._brand.setText(self._brand_html.replace("Usinix</td>", "</td>")
                                if "<img" in self._brand_html else "")
            self._brand.setToolTip("Usinix")
        else:
            self._brand.setText(self._brand_html)
        for b in self._quick_box.findChildren(QtWidgets.QToolButton):
            if b.property("usinix_dispensavel"):
                b.setVisible(n < 4)
        for w in (row, self.tabbar):
            w.style().unpolish(w)
            w.style().polish(w)
        self.tabbar.updateGeometry()
        for i in range(self.tabbar.count()):
            self.tabbar.setTabText(i, self.tabbar.tabText(i))      # recalcula a largura das abas
        row.layout().invalidate()

    def _ajustar_linha(self):
        row = getattr(self, "_row", None)
        if row is None or not row.isVisible():
            return
        larg = row.width()
        escolhido = 4
        for n in range(5):
            self._aplicar_nivel(n)
            # folga para a aba ativa (em negrito, mais larga): o nível não muda ao trocar de aba, senão a
            # faixa mudaria de tamanho e a vista 3D pularia debaixo do mouse
            if row.layout().sizeHint().width() + 30 <= larg:
                escolhido = n
                break
        self._nivel_linha = escolhido
        # a linha nunca encolhe de altura (esconder os botões dispensáveis do topo no nível 4 tirava 2 px):
        # a faixa fica com a mesma altura em qualquer aba e largura
        alt = max(getattr(self, "_alt_linha", 0), row.sizeHint().height())
        if alt != getattr(self, "_alt_linha", 0):
            self._alt_linha = alt
            row.setMinimumHeight(alt)
        # setas sempre permitidas: só aparecem se nem o nível mais compacto couber (janela muito
        # estreita). Desligá-las faria a linha das abas impor largura mínima à janela inteira.
        self.tabbar.setUsesScrollButtons(True)

    def _fill_wb_menu(self, menu):
        menu.clear()
        wbs = FreeCADGui.listWorkbenches()
        items = []
        try:
            import UsinixGui
            desligadas = set(UsinixGui.bancadas_desligadas())
        except Exception:
            desligadas = set()
        for key, wb in wbs.items():
            if key in ("NoneWorkbench",) or key in desligadas:
                continue
            label = WB_NAMES.get(key) or getattr(wb, "MenuText", key)
            items.append((label, key, wb))
        for label, key, wb in sorted(items, key=lambda x: x[0].lower()):
            icon = QtGui.QIcon()
            try:
                ic = wb.Icon if hasattr(wb, "Icon") else ""
                if isinstance(ic, str) and ic and not ic.lstrip().startswith("/*"):
                    icon = QtGui.QIcon(ic)
            except Exception:
                pass
            # QAction explicita: a sobrecarga addAction(icone, texto) do PySide às vezes devolve outro tipo
            QAction = getattr(QtGui, "QAction", None) or QtWidgets.QAction
            act = QAction(icon, label, menu)
            act.triggered.connect(lambda checked=False, k=key: FreeCADGui.activateWorkbench(k))
            menu.addAction(act)

    def _toggle_collapse(self, *args):
        vis = not self.content.isVisible()
        self.content.setVisible(vis)
        self._collapse_btn.setArrowType(QtCore.Qt.UpArrow if vis else QtCore.Qt.DownArrow)

    # ---- abas
    def _aba_movida(self, de, para):
        """O usuário arrastou uma aba: a lista interna acompanha a barra e a ordem fica gravada."""
        if 0 <= de < len(self._tabs) and 0 <= para < len(self._tabs):
            t = self._tabs.pop(de)
            self._tabs.insert(para, t)
        ids = [t["id"] for t in self._tabs if t["id"] != "dyn"]
        _params().SetString("OrdemAbas", ",".join(ids))

    def tab_index(self, tab_id):
        for i, t in enumerate(self._tabs):
            if t["id"] == tab_id:
                return i
        return -1

    def _on_tab_changed(self, idx):
        if self._building or idx < 0:
            return
        tab = self._tabs[idx]
        wb = tab.get("wb")
        if wb and self._user_click:
            try:
                if FreeCADGui.activeWorkbench().name() != wb:
                    FreeCADGui.activateWorkbench(wb)  # dispara sync_workbench
                    return
            except Exception as exc:
                FreeCAD.Console.PrintWarning("Usinix: {}\n".format(exc))
        self.build(tab)

    _user_click = True

    def select_tab(self, tab_id, user=False):
        idx = self.tab_index(tab_id)
        if idx < 0:
            return
        self._user_click = user
        try:
            if self.tabbar.currentIndex() == idx:
                self.build(self._tabs[idx])
            else:
                self.tabbar.setCurrentIndex(idx)
        finally:
            self._user_click = True

    def sync_workbench(self, name=None):
        """Chamado quando a bancada ativa muda."""
        if getattr(self, "_ignorar_sync", False):
            return
        try:
            name = name or FreeCADGui.activeWorkbench().name()
        except Exception:
            return
        self._rotulo_bancada(name)
        for t in self._tabs:
            if t.get("wb") == name or name in t.get("wb_extra", ()):
                self.select_tab(t["id"])
                return
        if name == "UsinixWorkbench":
            self.select_tab("usinix")
            return
        if name == "StartWorkbench" or name == "NoneWorkbench":
            self.select_tab("inicio")
            return
        for t in self.atualizar_abas_externas():
            if t["wb"] == name:
                self.select_tab(t["id"])
                return
        self._make_dynamic(name)

    @staticmethod
    def _paineis_da_bancada_ativa():
        """Painéis montados das barras de ferramentas da bancada ativa (as que não são do FreeCAD comum)."""
        try:
            wb = FreeCADGui.activeWorkbench()
            items = wb.getToolbarItems()
        except Exception:
            wb, items = None, {}
        mw = FreeCADGui.getMainWindow()
        panels = []
        for tbname, cmds in items.items():
            if tbname in STD_TOOLBARS:
                continue
            tb = mw.findChild(QtWidgets.QToolBar, tbname)
            title = tb.windowTitle() if tb is not None else tbname
            entries = []
            for c in cmds:
                if c == "Separator":
                    continue
                entries.append((c, L if not entries else S, None))
            if entries:
                panels.append((title, entries))
        return wb, panels

    def atualizar_abas_externas(self):
        """Uma aba para cada bancada instalada pelo usuário (complemento), logo que ela aparece. Devolve as
        abas novas."""
        novas = []
        ja = {t.get("wb") for t in self._tabs}
        for nome, rotulo in bancadas_externas():
            if nome in ja:
                continue
            tab = {"id": "ext:" + nome, "label": rotulo, "wb": nome, "panels": [], "externa": True}
            self._building = True
            try:
                # antes da aba temporária (que fica sempre por último)
                if self._dynamic is not None and self._tabs and self._tabs[-1] is self._dynamic:
                    pos = len(self._tabs) - 1
                    self._tabs.insert(pos, tab)
                    self.tabbar.insertTab(pos, rotulo)
                else:
                    self._tabs.append(tab)
                    self.tabbar.addTab(rotulo)
            finally:
                self._building = False
            novas.append(tab)
        if novas and self._dynamic is not None and any(t["wb"] == self._dynamic.get("wb") for t in novas):
            # a bancada que estava na aba temporária ganhou aba própria: a temporária sai
            i = self._tabs.index(self._dynamic)
            self._building = True
            try:
                self._tabs.pop(i)
                self.tabbar.removeTab(i)
            finally:
                self._building = False
            self._dynamic = None
        return novas

    def _make_dynamic(self, name):
        if name in ABAS_TEMPORARIAS:   # aba montada à mão (ex.: Simulação), só enquanto a bancada está ativa
            tab = dict(ABAS_TEMPORARIAS[name], id="dyn", regras=ABAS_TEMPORARIAS[name]["id"])
            label = tab["label"]
        else:
            wb, panels = self._paineis_da_bancada_ativa()
            label = WB_NAMES.get(name) or getattr(wb, "MenuText", name)
            tab = {"id": "dyn", "label": label, "wb": name, "panels": panels}
        self._building = True
        if self._dynamic is None:
            self._tabs.append(tab)
            self.tabbar.addTab(label)
        else:
            self._tabs[-1] = tab
            self.tabbar.setTabText(len(self._tabs) - 1, label)
        self._dynamic = tab
        self._building = False
        self.select_tab("dyn")

    # ---- construção do conteúdo
    def _precarregar(self, tab):
        """Aba que junta comandos de outra bancada (Peça com os de Sólidos): o FreeCAD só cria as ações
        desses comandos quando a bancada deles é ativada. Ativa uma vez e volta, na primeira montagem."""
        extras = tab.get("wb_extra") or ()
        if not extras or self._precarregadas.get(tab.get("id")):
            return
        self._precarregadas[tab.get("id")] = True
        try:
            atual = FreeCADGui.activeWorkbench().name()
        except Exception:
            atual = None
        self._ignorar_sync = True
        try:
            for wb in extras:
                try:
                    FreeCADGui.activateWorkbench(wb)
                except Exception:
                    pass
            if atual:
                FreeCADGui.activateWorkbench(atual)
        finally:
            self._ignorar_sync = False

    def precarregar_todas(self):
        """Registra de uma vez os comandos de todas as bancadas que a faixa usa (Montagem, Desenho, Chapa,
        Planilha, Superfícies...). O FreeCAD só cria esses comandos quando a bancada deles é ativada; sem isso,
        a busca de comandos, o menu de contexto e os botões fora da aba de origem não achavam a ferramenta.
        Ativa cada uma uma vez, sem trocar a aba, e volta para a bancada em que estava."""
        if getattr(self, "_todas_precarregadas", False):
            return []
        self._todas_precarregadas = True
        try:
            atual = FreeCADGui.activeWorkbench().name()
        except Exception:
            atual = None
        try:
            existentes = set(FreeCADGui.listWorkbenches())
        except Exception:
            existentes = set()
        bancadas = []
        for t in TABS:
            for wb in [t.get("wb")] + list(t.get("wb_extra") or ()):
                if wb and wb not in bancadas and wb != atual and (not existentes or wb in existentes):
                    bancadas.append(wb)
        feitas = []
        self._ignorar_sync = True
        try:
            for wb in bancadas:
                try:
                    FreeCADGui.activateWorkbench(wb)
                    feitas.append(wb)
                except Exception as exc:
                    FreeCAD.Console.PrintLog("Usinix: bancada %s não carregou: %s\n" % (wb, exc))
            if atual:
                try:
                    FreeCADGui.activateWorkbench(atual)
                except Exception:
                    pass
        finally:
            self._ignorar_sync = False
        for t in TABS:
            self._precarregadas[t.get("id")] = True
        try:
            import UsinixI18n        # as bancadas carregadas instalaram tradutores por cima do Usinix
            UsinixI18n.raise_priority()
        except Exception:
            pass
        try:
            idx = self.tabbar.currentIndex()
            if 0 <= idx < len(self._tabs):
                self.build(self._tabs[idx])
        except Exception:
            pass
        return feitas

    def build(self, tab, tudo=False):
        """Monta a aba. tudo=True mostra também o que esta situação esconderia (usado pelo "Mostrar onde"
        do guia e do tutorial); volta ao normal na próxima mudança de situação."""
        self._precarregar(tab)
        if tab.get("externa"):
            try:
                ativa = FreeCADGui.activeWorkbench().name()
            except Exception:
                ativa = None
            if ativa == tab.get("wb"):
                _wb, tab["panels"] = self._paineis_da_bancada_ativa()
        page = QtWidgets.QWidget()
        page.setObjectName("UsinixPage")
        page.setAttribute(QtCore.Qt.WA_StyledBackground, True)
        hl = QtWidgets.QHBoxLayout(page)
        hl.setContentsMargins(6, 2, 6, 0)
        hl.setSpacing(0)
        split = QtWidgets.QSplitter(QtCore.Qt.Horizontal)
        split.setObjectName("UsinixSplit")
        split.setChildrenCollapsible(False)
        split.setHandleWidth(9)
        paineis = []
        editando = editando_esboco()
        self._ctx_edicao = editando
        sit = situacao()
        self._sit = sit
        for title, entries in tab["panels"]:
            panel = RibbonPanel(title)
            raros = []
            for cmd, size, label in entries:
                if not cabe_no_contexto(tab, title, cmd, editando):
                    continue
                nomes = cmd.split("|")
                acts = _acoes_de(nomes)
                if not acts:
                    continue
                como = "sim" if tudo else como_mostrar(tab, cmd, sit, acts)
                if como == "nao":
                    continue
                if como == "raro":
                    raros.append((nomes, acts, label))
                    continue
                btn = RibbonButton(acts, size, label, panel)
                btn._cmd = nomes[0]     # o tutorial acha o botão pelo nome do comando
                btn._cmds = nomes
                panel.add(btn, size)
            if len(raros) == 1:
                # um "Mais" com uma opção só não ajuda: a ferramenta vai direto para o grupo
                nomes, acts, label = raros[0]
                btn = RibbonButton(acts, S, label, panel)
                btn._cmd = nomes[0]
                btn._cmds = nomes
                panel.add(btn, S)
            elif raros:
                mais = BotaoMais(raros, panel)
                panel.add(mais, S)
            if panel.count == 0:
                panel.deleteLater()
                continue
            split.addWidget(panel)
            paineis.append(panel)
        if not paineis:
            vazio = _painel_vazio(tab, sit)
            if vazio is not None:
                split.addWidget(vazio)
                paineis.append(vazio)
        dica = None if tudo else dica_da_aba(tab, sit)
        if dica:
            pd = RibbonPanel("Próximo passo")
            lb = QtWidgets.QLabel(dica)
            lb.setObjectName("UsinixDicaAba")
            lb.setWordWrap(True)
            lb.setFixedWidth(300)
            lb.setStyleSheet("color: #3D4A59; padding: 4px 10px; background: #FFF6D6; border-radius: 6px;")
            pd.row.addWidget(lb)
            pd.count += 1
            split.addWidget(pd)
            paineis.append(pd)
        resto = QtWidgets.QWidget()
        resto.setObjectName("UsinixResto")
        split.addWidget(resto)
        # mede com o estilo (fonte e espaçamentos da folha de estilo) já aplicado
        page.setStyleSheet(page.styleSheet())
        for w in [page] + page.findChildren(QtWidgets.QWidget):
            w.ensurePolished()
        for i, pn in enumerate(paineis):
            pn.preparar()
            split.setStretchFactor(i, 0)
        split.setStretchFactor(len(paineis), 1)
        for i in range(1, split.count()):
            split.handle(i).setToolTip("Arraste para alargar ou estreitar o grupo (duplo clique na aba "
                                       "recolhe a faixa)")
        desejado = self._larguras_salvas(tab, paineis)
        self._fixar_minimo(page, split, desejado[:-1])
        split.setSizes(desejado)
        split.splitterMoved.connect(lambda *_a, t=tab, sp=split, pg=page: self._divisor_movido(t, sp, pg))
        hl.addWidget(split, 1)
        self.split = split
        self.paineis = paineis
        old = self.content.takeWidget()
        self.content.setWidget(page)
        if old is not None:
            old.deleteLater()
        self._acertar_larguras(split, desejado[:-1])
        QtCore.QTimer.singleShot(0, lambda sp=split, d=desejado[:-1]: self._acertar_larguras(sp, d))

    def _divisor_movido(self, tab, split, page):
        """Guarda as larguras e alarga a página se preciso; o espaço novo vai para o fim, não para os grupos."""
        tam = split.sizes()[:-1]
        self._guardar_larguras(tab, split)
        self._fixar_minimo(page, split)
        self._acertar_larguras(split, tam)

    def _acertar_larguras(self, split, tam):
        """Reaplica as larguras dos grupos com o espaço que sobra todo no fim: o QSplitter reparte a diferença entre
        a soma pedida e a largura real proporcionalmente, e os grupos voltavam alguns pixels mais estreitos que o
        arrastado (1.15.0)."""
        try:
            import shiboken6
            if not shiboken6.isValid(split) or split is not getattr(self, "split", None):
                return
            split.parentWidget().layout().activate()
            livre = split.width() - sum(tam) - split.handleWidth() * len(tam)
            split.setSizes(list(tam) + [max(0, livre)])
        except Exception:
            pass

    def _fixar_minimo(self, page, split, tam=None):
        """Janela estreita: a faixa rola em vez de espremer os grupos (que só ficam compactos
        quando o próprio usuário arrasta o divisor)."""
        if tam is None:
            tam = split.sizes()[:-1]
        alvo = sum(tam) + split.handleWidth() * len(tam) + 6 * len(tam) + 40
        page.setMinimumWidth(alvo)

    def _chave_larguras(self, tab):
        suf = "_edicao" if tab.get("contexto") and getattr(self, "_ctx_edicao", False) else ""
        return "RibbonPaineis_" + str(tab.get("id", "x")) + suf

    def _larguras_salvas(self, tab, paineis):
        nat = [pn._natural for pn in paineis]
        txt = _params().GetString(self._chave_larguras(tab), "")
        try:
            salvas = [int(x) for x in txt.split(",") if x.strip()]
        except ValueError:
            salvas = []
        if len(salvas) == len(paineis):
            nat = [max(pn._compacta, w) for pn, w in zip(paineis, salvas)]
        return nat + [2000]

    def _guardar_larguras(self, tab, split):
        tam = split.sizes()[:-1]
        _params().SetString(self._chave_larguras(tab), ",".join(str(int(x)) for x in tam))

    def restaurar_larguras(self):
        """Volta os grupos da aba atual para a largura natural."""
        tab = self._tabs[self.tabbar.currentIndex()]
        _params().RemString(self._chave_larguras(tab))
        self.build(tab)

    # ---- altura da faixa
    def definir_altura(self, altura, guardar=True):
        global _MED
        _MED = medidas(altura)
        self.content.setFixedHeight(_MED["altura"])
        if guardar:
            _params().SetInt("RibbonHeight", _MED["altura"])
        idx = self.tabbar.currentIndex()
        if 0 <= idx < len(self._tabs):
            self.build(self._tabs[idx])
        return _MED["altura"]

    # ---- edição de esboço: mostra a aba Esboço sem trocar de bancada
    def check_edit(self):
        editing = editando_esboco()
        cur = self._tabs[self.tabbar.currentIndex()]["id"] if self.tabbar.currentIndex() >= 0 else None
        if editing and cur != "esboco" and self._edit_prev is None:
            self._edit_prev = cur
            self.select_tab("esboco")
        elif not editing and self._edit_prev is not None:
            prev, self._edit_prev = self._edit_prev, None
            if cur == "esboco":
                self.select_tab(prev)
        # entrou ou saiu da edição sem trocar de aba (bancada Esboço): refaz a faixa no novo contexto
        idx = self.tabbar.currentIndex()
        if 0 <= idx < len(self._tabs):
            tab = self._tabs[idx]
            if tab.get("contexto") and getattr(self, "_ctx_edicao", None) != editing:
                self.build(tab)
            elif getattr(self, "_sit", None) is not None and situacao() != self._sit:
                # abriu/fechou documento, abriu/fechou uma folha: a faixa mostra o que serve agora
                self.build(tab)


# --------------------------------------------------------------------------
# Faixa contextual: na aba Esboço, só aparecem as ferramentas que servem para o momento.
# Fora da edição: criar, editar, anexar, validar...; dentro da edição: desenhar, restringir, modificar.
# Ferramentas que só dependem da seleção (Offset, Rotacionar...) continuam visíveis, só esmaecidas.
ESBOCO_FORA_DA_EDICAO = {
    "Sketcher_NewSketch", "Usinix_Esboco3D", "Sketcher_EditSketch", "Sketcher_MapSketch", "Sketcher_ReorientSketch",
    "Sketcher_ValidateSketch", "Sketcher_MergeSketches", "Sketcher_MirrorSketch",
}
ESBOCO_SO_NA_EDICAO_PAINEL = {"Desenhar", "Restrições", "Modificar", "Referências", "Padrão", "Auxiliares"}
ESBOCO_SO_NA_EDICAO = {"Sketcher_LeaveSketch", "Sketcher_ViewSketch", "Sketcher_ViewSection"}


# Situação: a faixa esconde o que depende de uma situação que ainda não existe (sem documento, sem folha
# aberta) e manda as ferramentas raras para o "Mais" do grupo. O que depende só da seleção continua no lugar
# (esmaecido) para a faixa não mudar de tamanho a cada clique.
SEM_DOCUMENTO_SEMPRE = {"Std_New", "Std_Open", "Usinix_Preferencias", "Std_DlgMacroExecute",
                        "Usinix_NovaPeca", "Usinix_NovoEsbocoAvulso", "Usinix_NovaMontagem"}
# só antes de abrir um documento (o grupo Começar do Início)
SO_SEM_DOCUMENTO = {"Usinix_NovaPeca", "Usinix_NovoEsbocoAvulso", "Usinix_NovaMontagem"}

# Abas que dependem de "estar dentro" de algo: sem isso aberto, só aparece o que começa (ou abre) esse algo.
# aba: (chave da situação, o que aparece sem ela, dica do primeiro passo)
INICIO_DA_ABA = {
    "desenho": ("folha", {"Usinix_InserirDesenho", "Usinix_NovaFolha", "Usinix_PaletaVistas", "Usinix_AbrirFolha", "Usinix_FolhasLote",
                          "Usinix_ListaMateriais"},
                "Comece em Inserir peça ou montagem: escolha o que desenhar e a folha sai com as vistas na "
                "escala que cabe. As cotas e anotações aparecem com a folha aberta."),
    "montagem": ("montagem", {"Assembly_CreateAssembly", "Usinix_EditarMontagem", "Usinix_ListaMateriais",
                              "Usinix_Massa", "Usinix_Interferencia", "Usinix_ComponentesDosSolidos"},
                 "Crie uma montagem ou abra a que já existe: as restrições aparecem com a montagem aberta."),
    "simulacao": ("estudo", {"Usinix_AssistenteFEM", "Usinix_AssistenteEstrutura", "Usinix_AnaliseEstrutura",
                             "FEM_Analysis"},
                  "Comece pelo assistente ou crie um estudo: material, fixações, cargas e malha aparecem "
                  "depois, na ordem."),
    "planilha": ("planilha", {"Spreadsheet_CreateSheet", "Spreadsheet_Import"},
                 "Crie ou abra uma planilha: formatação e alinhamento aparecem com ela aberta."),
}
# compatibilidade (testes e quem lia a lista antiga)
DESENHO_SEM_FOLHA = INICIO_DA_ABA["desenho"][1]
# comandos de "abrir o que já existe": só aparecem quando há o que abrir
ABRIR_EXISTENTE = {"Usinix_AbrirFolha", "Usinix_EditarMontagem"}

# ferramentas raras: ficam no "Mais" do grupo (e no Procurar comando), não na frente
RAROS = {
    "desenho": {
        "TechDraw_PageDefault", "TechDraw_PageTemplate", "TechDraw_FillTemplateFields", "TechDraw_RedrawPage",
        "TechDraw_BrokenView", "TechDraw_ActiveView", "TechDraw_DraftView", "TechDraw_ClipGroup",
        "TechDraw_StackGroup", "TechDraw_AxoLengthDimension", "TechDraw_DimensionRepair",
        "TechDraw_ExtensionInsertPrefixGroup", "TechDraw_ExtensionIncreaseDecreaseGroup",
        "TechDraw_RichTextAnnotation", "TechDraw_CosmeticVertexGroup", "TechDraw_2PointCosmeticLine",
        "TechDraw_Hatch", "TechDraw_ToggleFrame", "TechDraw_ExtensionLockUnlockView", "TechDraw_DecorateLine",
        "TechDraw_WeldSymbol", "TechDraw_SurfaceFinishSymbols",
    },
    "peca": {
        "Part_CompJoinFeatures|Part_CompSplitFeatures|Part_CompCompoundTools",
        "Part_Section|Part_CrossSections|Part_ProjectionOnSurface",
        "Part_Scale|Part_CompOffset|Part_Defeaturing|Part_Builder",
    },
    "montagem": {"Assembly_SolveAssembly", "Usinix_Propriedades"},
    "estruturas": {"Usinix_AtualizarEstrutura", "Usinix_SecaoPersonalizada", "Usinix_Propriedades"},
    "simulacao": {
        "FEM_MaterialEditor", "FEM_ConstraintDisplacement", "FEM_ConstraintCentrif", "FEM_MeshRegion",
        "FEM_MeshDisplayInfo", "FEM_MeshClear", "FEM_SolverControl", "FEM_PostFilterClipScalar",
        "FEM_PostFilterDataAlongLine", "FEM_ResultsPurge",
    },
    "planilha": {"Spreadsheet_SetAlias", "Spreadsheet_SplitCell"},
    "usinix": {"Usinix_TemaIcones", "Usinix_BarrasClassicas", "Usinix_RemoverSplash", "Usinix_ModoDistribuicao"},
}


def _janela_ativa():
    try:
        mw = FreeCADGui.getMainWindow()
        area = mw.findChild(QtWidgets.QMdiArea)
        sub = area.activeSubWindow() if area is not None else None
        w = sub.widget() if sub is not None else None
        return w.metaObject().className() if w is not None else ""
    except Exception:
        return ""


def folha_aberta():
    """A janela ativa é uma folha de desenho (TechDraw)."""
    return "MDIViewPage" in _janela_ativa()


def planilha_aberta():
    return "SheetView" in _janela_ativa()


def montagem_aberta():
    """Há uma montagem em edição (as restrições do FreeCAD só funcionam nela)."""
    import sys
    if "UtilsAssembly" not in sys.modules:
        return False
    try:
        return sys.modules["UtilsAssembly"].activeAssembly() is not None
    except Exception:
        return False


_cache_folhas = {}


def _tipos_no_doc(doc):
    """{"folha", "montagem", "estudo", "planilha"} presentes no documento (guardado pelo nº de objetos)."""
    objs = doc.Objects
    chave = (doc.Name, len(objs))
    if _cache_folhas.get("chave") != chave:
        tipos = set()
        for o in objs:
            t = o.TypeId
            if t == "TechDraw::DrawPage" or o.isDerivedFrom("TechDraw::DrawPage"):
                tipos.add("folha")
            elif t == "Assembly::AssemblyObject":
                tipos.add("montagem")
            elif t == "Fem::FemAnalysis" or t == "Fem::FemAnalysisPython":
                tipos.add("estudo")
            elif t == "Spreadsheet::Sheet":
                tipos.add("planilha")
        _cache_folhas["chave"] = chave
        _cache_folhas["tipos"] = frozenset(tipos)
    return _cache_folhas["tipos"]


def situacao():
    """Tupla do que está aberto agora: muda a faixa quando muda.

    (tem documento, folha aberta, documento tem folhas, montagem aberta, tem montagem, tem estudo,
     planilha aberta)"""
    doc = FreeCAD.ActiveDocument
    if doc is None:
        return (False, False, False, False, False, False, False)
    try:
        tipos = _tipos_no_doc(doc)
    except Exception:
        tipos = frozenset()
    return (True, folha_aberta(), "folha" in tipos, montagem_aberta(), "montagem" in tipos, "estudo" in tipos,
            planilha_aberta())


def _dentro(chave, sit):
    # montagem ou folha que já existe conta como "dentro": o clique na ferramenta abre a montagem/folha sozinho
    return {"folha": sit[1] or sit[2], "montagem": sit[3] or sit[4], "estudo": sit[5],
            "planilha": sit[6]}.get(chave, True)


def _ativo(nome, acts):
    try:
        return FreeCADGui.Command.get(nome).isActive()
    except Exception:
        return any(a.isEnabled() for a in acts)


def como_mostrar(tab, cmd, sit, acts=()):
    """"sim" (na frente), "raro" (no Mais do grupo) ou "nao" (escondido nesta situação)."""
    nome = cmd.split("|")[0]
    if not faixa_contextual():
        return "sim"
    if not sit[0]:
        return "sim" if nome in SEM_DOCUMENTO_SEMPRE or _ativo(nome, acts) else "nao"
    if nome in SO_SEM_DOCUMENTO:
        return "nao"
    ini = INICIO_DA_ABA.get(tab.get("regras", tab.get("id")))
    if ini is not None and not _dentro(ini[0], sit):
        if nome not in ini[1]:
            return "nao"
        return "sim" if nome not in ABRIR_EXISTENTE or _ativo(nome, acts) else "nao"
    if nome in ABRIR_EXISTENTE:
        return "sim" if _ativo(nome, acts) else "nao"    # já aberta: "abrir" não serve
    if cmd in RAROS.get(tab.get("regras", tab.get("id")), ()) or nome in RAROS.get(tab.get("regras", tab.get("id")), ()):
        return "raro"
    return "sim"


def dica_da_aba(tab, sit):
    """Primeiro passo da aba nesta situação (ou None)."""
    if not faixa_contextual() or not sit[0]:
        return None
    ini = INICIO_DA_ABA.get(tab.get("regras", tab.get("id")))
    if ini is not None and not _dentro(ini[0], sit):
        return ini[2]
    return None


def _painel_vazio(tab, sit):
    """Aba sem nada para mostrar agora: diz o primeiro passo, com o botão para dá-lo."""
    if sit[0]:
        return None
    pn = RibbonPanel("Para começar")
    for cmd, rot in (("Std_New", "Novo"), ("Std_Open", "Abrir")):
        acts = _acoes_de([cmd])
        if acts:
            b = RibbonButton(acts, L, rot, pn)
            b._cmd = cmd
            pn.add(b, L)
    txt = QtWidgets.QLabel("Crie ou abra um documento:\nas ferramentas de %s aparecem em seguida." % tab["label"])
    txt.setObjectName("UsinixVazioTexto")
    txt.setStyleSheet("color: #5A6675; padding: 6px 10px;")
    pn.row.addWidget(txt)
    pn.count += 1
    return pn


class BotaoMais(QtWidgets.QToolButton):
    """\"Mais\" do grupo: as ferramentas raras num menu, com os nomes da faixa."""

    def __init__(self, raros, parent=None):
        super().__init__(parent)
        self.setProperty("sw_size", S)
        self.setObjectName("UsinixMais")
        self.setAutoRaise(True)
        self.setFocusPolicy(QtCore.Qt.NoFocus)
        self.setText("Mais ▾")
        self.setStyleSheet("QToolButton#UsinixMais::menu-indicator { image: none; width: 0px; }")
        self.setIcon(QtGui.QIcon(os.path.join(_HERE, "Resources", "icons", "mais.svg")))
        self.setIconSize(QtCore.QSize(_MED["iconS"], _MED["iconS"]))
        self.setToolButtonStyle(QtCore.Qt.ToolButtonTextBesideIcon)
        self.setFixedHeight(_MED["S"])
        self.setSizePolicy(QtWidgets.QSizePolicy.Minimum, QtWidgets.QSizePolicy.Fixed)
        self.setPopupMode(QtWidgets.QToolButton.InstantPopup)
        self.setToolTip("Mais ferramentas deste grupo (menos usadas)")
        menu = QtWidgets.QMenu(self)
        QAction = getattr(QtGui, "QAction", None) or QtWidgets.QAction
        self.acoes = []
        self._cmds = []
        for nomes, acts, label in raros:
            for a in acts:
                rot = " ".join(str(label).split()) if len(acts) == 1 else _clean(a.text())
                px = QAction(a.icon(), rot, menu)
                px.setToolTip(a.toolTip())
                px._original = a
                px._cmd = a.whatsThis() or nomes[0]

                def disparar(checked=False, original=a, n=px._cmd):
                    if not _pedir_selecao(n) and original.isEnabled():
                        original.trigger()
                px.triggered.connect(disparar)

                def sinc(px=px, original=a, n=px._cmd):
                    try:
                        px.setEnabled(original.isEnabled() or _selecao_depois(n))
                    except RuntimeError:
                        pass
                a.changed.connect(sinc)
                sinc()
                menu.addAction(px)
                self.acoes.append(px)
            self._cmds += nomes
        self.setMenu(menu)

    def largura_do_texto(self):
        fm = QtGui.QFontMetrics(self.font())
        t = fm.horizontalAdvance(self.text()) if hasattr(fm, "horizontalAdvance") else fm.width(self.text())
        if self.toolButtonStyle() == QtCore.Qt.ToolButtonIconOnly:
            return _MED["iconS"] + 14
        return _MED["iconS"] + t + 22


def faixa_contextual():
    return _params().GetBool("RibbonContextual", True)


def editando_esboco():
    try:
        gdoc = FreeCADGui.ActiveDocument
        vp = gdoc.getInEdit() if gdoc else None
        return bool(vp) and vp.Object.TypeId.startswith("Sketcher::")
    except Exception:
        return False


def cabe_no_contexto(tab, painel, cmd, editando):
    """O botão aparece no contexto atual? Só a aba marcada com "contexto" é filtrada."""
    if tab.get("contexto") != "esboco" or not faixa_contextual():
        return True
    cmd = cmd.split("|")[0]
    if editando:
        return cmd not in ESBOCO_FORA_DA_EDICAO
    return painel not in ESBOCO_SO_NA_EDICAO_PAINEL and cmd not in ESBOCO_SO_NA_EDICAO


# --------------------------------------------------------------------------
_state = {"bar": None, "ribbon": None, "timer": None}


class _RodaParaOsLados(QtCore.QObject):
    """Converte a roda do mouse em rolagem horizontal da faixa quando ela não cabe na janela."""

    def __init__(self, area):
        super().__init__(area)
        self.area = area

    def eventFilter(self, obj, ev):
        if ev.type() == QtCore.QEvent.Wheel:
            barra = self.area.horizontalScrollBar()
            if barra.maximum() > 0:
                d = ev.angleDelta()
                passo = d.y() if abs(d.y()) >= abs(d.x()) else d.x()
                barra.setValue(barra.value() - passo)
                return True
        return False


def _hide_native_toolbars():
    mw = FreeCADGui.getMainWindow()
    bar = _state["bar"]
    # a faixa nunca fica escondida: um estado da janela salvo com ela oculta (ao restaurar o layout) a
    # sumiria de vez, sem menu para trazer de volta
    if bar is not None and mw.isVisible() and not bar.isVisible() and not mw.isFullScreen():
        bar.show()
    for tb in mw.findChildren(QtWidgets.QToolBar):
        if tb is bar or tb.parent() is not mw:
            continue
        if tb.isVisible():
            tb.hide()


def _force_light_scheme():
    """Fixa o esquema de cores do Qt no tema Usinix (claro ou escuro), independente do Windows."""
    try:
        hints = QtGui.QGuiApplication.styleHints()
        alvo = QtCore.Qt.ColorScheme.Dark if _escuro() else QtCore.Qt.ColorScheme.Light
        if hasattr(hints, "setColorScheme") and hints.colorScheme() != alvo:
            hints.setColorScheme(alvo)
    except Exception:
        pass
    if _escuro() and not _state.get("paleta"):
        _state["paleta"] = True
        try:
            app = QtWidgets.QApplication.instance()
            pal = QtGui.QPalette(app.palette())
            for role, c in ((QtGui.QPalette.Window, "#161A20"), (QtGui.QPalette.Base, "#1F252D"),
                            (QtGui.QPalette.AlternateBase, "#1B2129"), (QtGui.QPalette.Button, "#1F252D"),
                            (QtGui.QPalette.WindowText, "#E6ECF2"), (QtGui.QPalette.Text, "#E6ECF2"),
                            (QtGui.QPalette.ButtonText, "#E6ECF2"), (QtGui.QPalette.ToolTipBase, "#1F252D"),
                            (QtGui.QPalette.ToolTipText, "#E6ECF2"), (QtGui.QPalette.Highlight, "#2F6FB5"),
                            (QtGui.QPalette.HighlightedText, "#F1F4F8"), (QtGui.QPalette.Link, "#8CBCEB"),
                            (QtGui.QPalette.PlaceholderText, "#6B7785")):
                pal.setColor(role, QtGui.QColor(c))
            pal.setColor(QtGui.QPalette.Disabled, QtGui.QPalette.Text, QtGui.QColor("#7D8996"))
            pal.setColor(QtGui.QPalette.Disabled, QtGui.QPalette.WindowText, QtGui.QColor("#7D8996"))
            pal.setColor(QtGui.QPalette.Disabled, QtGui.QPalette.ButtonText, QtGui.QColor("#7D8996"))
            app.setPalette(pal)
        except Exception:
            pass


def _apply_global_qss():
    _force_light_scheme()
    app = QtWidgets.QApplication.instance()
    css = app.styleSheet() or ""
    if "/*USINIX-BEGIN*/" in css:
        return
    extra = ""
    try:
        import UsinixEstilo
        if UsinixEstilo.enabled():
            extra = UsinixEstilo.qss()
    except Exception as exc:
        FreeCAD.Console.PrintWarning("Usinix: estilo das janelas não aplicado: {}\n".format(exc))
    app.setStyleSheet(css + "\n" + _t(GLOBAL_QSS).replace("/*USINIX-END*/", extra + "\n/*USINIX-END*/"))


def _tick():
    if _state["ribbon"] is None:
        return
    _hide_native_toolbars()
    _apply_global_qss()
    _state["ribbon"].check_edit()


def _on_workbench(name):
    rb = _state["ribbon"]
    if rb is None:
        return
    QtCore.QTimer.singleShot(0, _hide_native_toolbars)
    QtCore.QTimer.singleShot(50, lambda: rb.sync_workbench(name))
    QtCore.QTimer.singleShot(80, instalar_menu_ferramentas)


# -------------------------------------------------------------------------- menu Comandos (tudo da faixa)
# O FreeCAD retraduz os menus da barra pelo dado da ação do menu (título = tradução de menuAction().data()):
# por isso cada menu leva o próprio texto como dado.
MENU_FERRAMENTAS = "&Comandos"


def itens_do_menu():
    """[(aba, [(grupo, [(rótulo, [comandos])])])] — o mesmo que a faixa mostra, para o menu Ferramentas."""
    res = []
    for tab in TABS:
        grupos = []
        for painel in tab.get("panels", []):
            nome_p, itens = painel[0], painel[1]
            linhas = []
            for it in itens:
                if not isinstance(it, (tuple, list)) or not it:
                    continue
                nomes = [n for n in str(it[0]).split("|") if n]
                rot = (it[2] if len(it) > 2 and it[2] else nomes[0]).replace("\n", " ")
                linhas.append((rot, nomes))
            if linhas:
                grupos.append((nome_p, linhas))
        if grupos:
            res.append((tab["label"], grupos))
    return res


def _acao_do_menu(menu, rot, nome):
    QAction = getattr(QtGui, "QAction", None) or QtWidgets.QAction
    act = QAction(rot, menu)
    try:
        orig = _cmd_actions(nome)
        if orig:
            act.setIcon(orig[0].icon())
            act.setToolTip(orig[0].toolTip())
            act.setStatusTip(orig[0].statusTip())
    except Exception:
        pass
    act.setData(nome)
    act.triggered.connect(lambda checked=False, n=nome: FreeCADGui.runCommand(n, 0))
    menu.addAction(act)
    return act


def _preencher_aba(menu, grupos):
    menu.clear()
    disponiveis = set(FreeCADGui.listCommands())
    for nome_p, linhas in grupos:
        menu.addSection(nome_p)
        for rot, nomes in linhas:
            nomes = [n for n in nomes if n in disponiveis]
            if not nomes:
                continue
            if len(nomes) == 1:
                _acao_do_menu(menu, rot, nomes[0])
            else:
                sub = menu.addMenu(rot)
                sub.setObjectName(rot)
                sub.menuAction().setData(rot)
                for a in _acoes_de(nomes):
                    sub.addAction(a)
    for a in menu.actions():
        n = a.data()
        if n:
            try:
                a.setEnabled(bool(FreeCADGui.Command.get(n).isActive()))
            except Exception:
                pass


def montar_menu_ferramentas(pai=None):
    """Menu Comandos: uma entrada por aba da faixa (grupos como seções), montado quando abre: todo comando da faixa
    também fica no menu de cima."""
    menu = QtWidgets.QMenu(MENU_FERRAMENTAS, pai or FreeCADGui.getMainWindow())
    menu.setObjectName(MENU_FERRAMENTAS)
    menu.menuAction().setData(MENU_FERRAMENTAS)
    for aba, grupos in itens_do_menu():
        sub = menu.addMenu(aba)
        sub.setObjectName(aba)
        sub.menuAction().setData(aba)
        sub.aboutToShow.connect(lambda m=sub, g=grupos: _preencher_aba(m, g))
    return menu


def instalar_menu_ferramentas():
    """Põe o menu Comandos na barra de menus, antes de Ajuda. A troca de bancada refaz a barra: chamado
    de novo a cada troca."""
    try:
        mw = FreeCADGui.getMainWindow()
        barra = mw.menuBar()
        menu = mw.findChild(QtWidgets.QMenu, MENU_FERRAMENTAS)
        if menu is None:
            menu = montar_menu_ferramentas(mw)
        acao = menu.menuAction()
        acoes = barra.actions()
        if acao in acoes:
            acao.setVisible(True)
            return menu
        ajuda = None
        for a in acoes:
            t = a.text().replace("&", "").lower()
            if t in ("ajuda", "help"):
                ajuda = a
        if ajuda is not None:
            barra.insertMenu(ajuda, menu)
        else:
            barra.addMenu(menu)
        return menu
    except Exception as exc:
        FreeCAD.Console.PrintLog("Usinix: menu Ferramentas: %s\n" % exc)
        return None


def install():
    if _state["ribbon"] is not None:
        return _state["ribbon"]
    mw = FreeCADGui.getMainWindow()
    bar = QtWidgets.QToolBar("Faixa Usinix", mw)
    bar.setObjectName("UsinixRibbonBar")
    bar.setMovable(False)
    bar.setFloatable(False)
    bar.setContextMenuPolicy(QtCore.Qt.PreventContextMenu)
    bar.toggleViewAction().setVisible(False)
    bar.setStyleSheet(_t("QToolBar#UsinixRibbonBar { border: none; padding: 0; margin: 0; spacing: 0; background: #FFFFFF; }"))
    ribbon = UsinixRibbon(bar)
    ribbon.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Fixed)
    bar.addWidget(ribbon)
    mw.addToolBar(QtCore.Qt.TopToolBarArea, bar)
    _state.update(bar=bar, ribbon=ribbon)
    try:
        mw.workbenchActivated.connect(_on_workbench)
    except Exception as exc:
        FreeCAD.Console.PrintWarning("Usinix: sinal workbenchActivated indisponível: {}\n".format(exc))
    timer = QtCore.QTimer(mw)
    timer.setInterval(400)
    timer.timeout.connect(_tick)
    timer.start()
    _state["timer"] = timer
    _hide_native_toolbars()
    _apply_global_qss()
    ribbon.sync_workbench()
    QtCore.QTimer.singleShot(300, instalar_menu_ferramentas)
    # bancadas instaladas pelo usuário ganham aba própria, sem precisar ativar em Preferências
    QtCore.QTimer.singleShot(1500, ribbon.atualizar_abas_externas)
    QtCore.QTimer.singleShot(2500, ribbon.precarregar_todas)
    return ribbon


def uninstall(restore_toolbars=True):
    mw = FreeCADGui.getMainWindow()
    if _state["timer"] is not None:
        _state["timer"].stop()
    try:
        mw.workbenchActivated.disconnect(_on_workbench)
    except Exception:
        pass
    if _state["bar"] is not None:
        mw.removeToolBar(_state["bar"])
        _state["bar"].deleteLater()
    _state.update(bar=None, ribbon=None, timer=None)
    app = QtWidgets.QApplication.instance()
    css = app.styleSheet() or ""
    if "/*USINIX-BEGIN*/" in css:
        a = css.index("/*USINIX-BEGIN*/")
        b = css.index("/*USINIX-END*/") + len("/*USINIX-END*/")
        app.setStyleSheet(css[:a] + css[b:])
    if restore_toolbars:
        for tb in mw.findChildren(QtWidgets.QToolBar):
            if tb.parent() is mw and tb.toggleViewAction().isVisible():
                tb.show()


def reload():
    """Para desenvolvimento: recarrega o módulo e reinstala a faixa."""
    import importlib
    import UsinixRibbon as mod
    mod.uninstall(restore_toolbars=False)
    mod = importlib.reload(mod)
    return mod.install()
