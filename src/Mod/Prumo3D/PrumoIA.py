# SPDX-License-Identifier: LGPL-2.1-or-later
# Usinix - conexão com assistentes de IA (MCP): ponte local dentro do Usinix + ferramentas de alto nível.
"""Conectar IA.

O assistente (Claude Desktop, editores com IA...) roda o servidor MCP ``usinix_mcp.py`` (só biblioteca padrão do
Python), que conversa com esta ponte por HTTP local. A ponte:

- só escuta em 127.0.0.1, com um código secreto gravado em ``<dados do usuário>/usinix-ia.json``;
- recusa pedidos que um navegador poderia mandar (cabeçalho Origin, tipo que não é JSON);
- vem desligada; liga no botão Usinix › Conectar IA (ou na preferência de ligar ao abrir);
- executa cada ferramenta na linha principal do programa (fila + sinal do Qt) e numa transação: o Desfazer
  desfaz o que a IA fez de uma vez;
- não executa código Python solto, a não ser que o usuário ligue essa opção.

O padrão fila + sinal para levar o pedido da linha da rede à linha da interface segue a ideia do
neka-nat/freecad-mcp (licença MIT); o código aqui é próprio do Usinix.
"""

import base64
import json
import math
import os
import queue
import secrets
import sys
import tempfile
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import FreeCAD
import FreeCADGui

import PrumoUtil

try:
    from PySide import QtCore, QtGui, QtWidgets
except ImportError:  # pragma: no cover
    from PySide2 import QtCore, QtGui, QtWidgets

PARAM = "User parameter:BaseApp/Preferences/Mod/Prumo3D"
PORTA_PADRAO = 47261
TEMPO_MAX = 180.0
VERSAO_PROTOCOLO = 1
_estado = {"servidor": None, "thread": None, "ponte": None, "token": None, "porta": None, "chamadas": 0,
           "ultima": ""}


def arquivo_conexao():
    return os.path.join(FreeCAD.getUserAppDataDir(), "usinix-ia.json")


def script_mcp():
    """Cópia do servidor MCP na pasta de dados do usuário: caminho fixo mesmo no AppImage (que monta o programa numa
    pasta temporária diferente a cada abertura) e depois de reinstalar."""
    import shutil
    origem = os.path.join(os.path.dirname(os.path.abspath(__file__)), "usinix_mcp.py")
    destino = os.path.join(FreeCAD.getUserAppDataDir(), "usinix_mcp.py")
    try:
        if not os.path.isfile(destino) or open(origem, "rb").read() != open(destino, "rb").read():
            shutil.copyfile(origem, destino)
        return destino
    except OSError:
        return origem


def python_do_usinix():
    """Python que o assistente usa para rodar o servidor MCP (o do próprio Usinix no Windows)."""
    if sys.platform.startswith("win"):
        cand = os.path.join(os.path.dirname(sys.executable), "python.exe")
        if os.path.isfile(cand):
            return cand
        cand = os.path.join(FreeCAD.getHomePath(), "bin", "python.exe")
        if os.path.isfile(cand):
            return os.path.normpath(cand)
        return "python"
    return "python3"


def config_cliente():
    """Trecho de configuração do servidor MCP para o Claude Desktop (e clientes no mesmo formato)."""
    return {"mcpServers": {"usinix": {"command": python_do_usinix(),
                                      "args": [script_mcp(), "--conexao", arquivo_conexao()]}}}


def permitir_codigo():
    return FreeCAD.ParamGet(PARAM).GetBool("IAPermitirCodigo", False)


# ============================================================================ linha da interface
class _Despachante(QtCore.QObject):
    """Leva o pedido da linha da rede para a linha da interface (FreeCAD só pode ser mexido nela)."""
    acordar = QtCore.Signal()

    def __init__(self):
        super().__init__()
        self.fila = queue.Queue()
        self.acordar.connect(self._processar, QtCore.Qt.QueuedConnection)

    def chamar(self, funcao, tempo=TEMPO_MAX):
        resposta = queue.Queue(maxsize=1)
        self.fila.put((funcao, resposta))
        self.acordar.emit()
        try:
            ok, valor = resposta.get(timeout=tempo)
        except queue.Empty:
            raise TimeoutError("o Usinix não respondeu em %d s (há uma janela aberta esperando?)" % tempo)
        if not ok:
            raise valor
        return valor

    def _processar(self):
        while True:
            try:
                funcao, resposta = self.fila.get_nowait()
            except queue.Empty:
                return
            try:
                resposta.put((True, funcao()))
            except Exception as exc:     # o erro volta para a IA, com o texto
                resposta.put((False, exc))


# ============================================================================ ferramentas
FERRAMENTAS = {}


def ferramenta(nome, descricao, propriedades=None, obrigatorias=(), muda=True):
    """Registra uma função como ferramenta da IA. muda=True: roda numa transação (um Desfazer)."""
    def reg(f):
        FERRAMENTAS[nome] = {"funcao": f, "muda": muda, "def": {
            "name": nome, "description": descricao,
            "inputSchema": {"type": "object", "properties": propriedades or {},
                            "required": list(obrigatorias)}}}
        return f
    return reg


def _doc(nome=None):
    doc = FreeCAD.getDocument(nome) if nome else FreeCAD.ActiveDocument
    if doc is None:
        raise ValueError("não há documento aberto: use novo_documento ou abra um arquivo")
    return doc


def _obj(doc, nome):
    o = doc.getObject(nome) or next((x for x in doc.Objects if x.Label == nome), None)
    if o is None:
        raise ValueError("objeto não encontrado: %s" % nome)
    return o


def _resumo(o):
    import PrumoInserirDesenho as I
    try:
        tipo = I.tipo_legivel(o)
    except Exception:
        tipo = o.TypeId
    return {"nome": o.Name, "rotulo": o.Label, "tipo": tipo, "TypeId": o.TypeId}


@ferramenta("estado", "Situação do Usinix: versão, documento ativo e quantos objetos tem.", muda=False)
def f_estado():
    import PrumoVersao
    doc = FreeCAD.ActiveDocument
    return {"usinix": PrumoVersao.VERSAO, "documento": doc.Name if doc else None,
            "rotulo": doc.Label if doc else None, "objetos": len(doc.Objects) if doc else 0,
            "documentos_abertos": list(FreeCAD.listDocuments()),
            "codigo_python_permitido": permitir_codigo()}


@ferramenta("listar_objetos", "Objetos do documento ativo que podem ir para o desenho (peças, corpos, montagens, "
            "estruturas), com nome interno, rótulo e tipo. todos=true lista tudo.",
            {"todos": {"type": "boolean"}}, muda=False)
def f_listar(todos=False):
    doc = _doc()
    if todos:
        objs = doc.Objects
    else:
        import PrumoInserirDesenho as I
        objs = I.candidatos(doc)
    return [_resumo(o) for o in objs]


@ferramenta("novo_documento", "Cria um documento novo e o deixa ativo.", {"nome": {"type": "string"}})
def f_novo(nome="Projeto"):
    doc = FreeCAD.newDocument(nome.replace(" ", "_") or "Projeto")
    doc.Label = nome
    return {"documento": doc.Name}


@ferramenta("esboco_linhas", "Cria um esboço com linhas retas (para esqueleto de estrutura ou perfil). pontos: lista de "
            "[x, y] em mm no plano escolhido; linhas ligam pontos seguidos; fechado=true liga o último ao primeiro. "
            "segmentos (opcional) substitui pontos: lista de [[x1,y1],[x2,y2]] soltos.",
            {"pontos": {"type": "array", "items": {"type": "array", "items": {"type": "number"}}},
             "segmentos": {"type": "array", "items": {"type": "array"}},
             "plano": {"type": "string", "enum": ["XY", "XZ", "YZ"]},
             "fechado": {"type": "boolean"}, "nome": {"type": "string"}})
def f_esboco(pontos=None, segmentos=None, plano="XY", fechado=False, nome="Esboco"):
    import Part
    import Sketcher
    doc = _doc()
    rot = {"XY": FreeCAD.Rotation(), "XZ": FreeCAD.Rotation(FreeCAD.Vector(1, 0, 0), 90),
           "YZ": FreeCAD.Rotation(FreeCAD.Vector(0, 0, 1), 90).multiply(FreeCAD.Rotation(FreeCAD.Vector(1, 0, 0), 90))}
    if plano not in rot:
        raise ValueError("plano deve ser XY, XZ ou YZ")
    sk = doc.addObject("Sketcher::SketchObject", nome)
    sk.Placement = FreeCAD.Placement(FreeCAD.Vector(), rot[plano])
    V = FreeCAD.Vector
    if segmentos:
        pares = [((a[0], a[1]), (b[0], b[1])) for a, b in segmentos]
    else:
        pts = [tuple(p[:2]) for p in (pontos or [])]
        if len(pts) < 2:
            raise ValueError("informe ao menos 2 pontos")
        pares = list(zip(pts, pts[1:])) + ([(pts[-1], pts[0])] if fechado and len(pts) > 2 else [])
    ids = [sk.addGeometry(Part.LineSegment(V(a[0], a[1], 0), V(b[0], b[1], 0))) for a, b in pares]
    if not segmentos:
        for i in range(len(ids) - 1):
            sk.addConstraint(Sketcher.Constraint("Coincident", ids[i], 2, ids[i + 1], 1))
        if fechado and len(ids) > 2:
            sk.addConstraint(Sketcher.Constraint("Coincident", ids[-1], 2, ids[0], 1))
    doc.recompute()
    return {"esboco": sk.Name, "linhas": len(ids)}


@ferramenta("listar_perfis", "Perfis do catálogo do Usinix (W, U, L, tubos, metalon...). busca filtra pelo nome "
            "(ex.: 'W 150', 'U 152', 'tubo'). Use o nome exato em criar_estrutura.",
            {"busca": {"type": "string"}, "limite": {"type": "integer"}}, muda=False)
def f_perfis(busca="", limite=60):
    import PrumoPerfis
    nomes = PrumoPerfis.nomes()
    if busca:
        b = busca.lower()
        nomes = [n for n in nomes if b in n.lower()]
    return {"total": len(nomes), "perfis": nomes[:max(1, int(limite))]}


@ferramenta("criar_estrutura", "Estrutura soldada sobre as linhas de um esboço (esqueleto): uma barra de perfil por "
            "linha, com cantos em meia-esquadria ou de topo. Devolve a estrutura e as barras (índice = linha).",
            {"esqueleto": {"type": "string"}, "perfil": {"type": "string"},
             "uniao": {"type": "string", "enum": ["Meia-esquadria", "Topo"]},
             "giro": {"type": "number", "description": "giro do perfil em graus"},
             "material": {"type": "string"}}, ["esqueleto", "perfil"])
def f_estrutura(esqueleto, perfil, uniao="Meia-esquadria", giro=0.0, material=""):
    import PrumoEstrutura as E
    doc = _doc()
    sk = _obj(doc, esqueleto)
    est = E.criar(doc, sk, perfil, rotacao=float(giro), uniao=uniao, material=material, transacao=False)
    return {"estrutura": est.Name, "barras": [{"indice": b.Indice, "nome": b.Name,
                                               "comprimento_mm": round(b.ComprimentoCorte.Value, 1)}
                                              for b in E.barras_de(est)]}


@ferramenta("trabalhos_na_barra", "Corte das pontas soltas e furos nas barras de uma estrutura. ponta_inicio / "
            "ponta_fim: reto, horizontal ou vertical. furos (opcional): face (Alma, Mesa de cima, Mesa de baixo, "
            "As duas mesas), parafuso (M8..M30) ou diametro, ref (inicio, fim, as_duas), dist, qtd, passo, filas "
            "(1/2), gab (entre filas). por_parafusos=true põe parafuso, arruela e porca.",
            {"estrutura": {"type": "string"}, "barras": {"type": "array", "items": {"type": "integer"}},
             "ponta_inicio": {"type": "string", "enum": ["reto", "horizontal", "vertical"]},
             "ponta_fim": {"type": "string", "enum": ["reto", "horizontal", "vertical"]},
             "furos": {"type": "object"}, "por_parafusos": {"type": "boolean"},
             "aperto": {"type": "number"}}, ["estrutura"])
def f_trabalhos(estrutura, barras=None, ponta_inicio=None, ponta_fim=None, furos=None, por_parafusos=False,
                aperto=0.0):
    import PrumoEstrutura as E
    import PrumoTrabalhosBarra as T
    doc = _doc()
    est = _obj(doc, estrutura)
    todas = E.barras_de(est)
    bs = [b for b in todas if barras is None or b.Indice in [int(i) for i in barras]]
    if not bs:
        raise ValueError("nenhuma barra com esses índices")
    pontas = {}
    if ponta_inicio:
        pontas[0] = ponta_inicio
    if ponta_fim:
        pontas[1] = ponta_fim
    grupos, gid = None, None
    if furos:
        f = dict(furos)
        par = f.get("parafuso") or ""
        diam = float(f.get("diametro") or f.get("diam") or (T.diametro_para(par) or 0))
        if diam <= 0:
            raise ValueError("informe o parafuso (M12...) ou o diâmetro do furo")
        base = {"face": f.get("face", "Alma"), "diam": diam, "dist": float(f.get("dist", 50)),
                "qtd": int(f.get("qtd", 1)), "passo": float(f.get("passo", 0)),
                "filas": int(f.get("filas", 1)), "gab": float(f.get("gab", 0)), "desloc": float(f.get("desloc", 0)),
                "parafuso": par}
        ref = f.get("ref", "inicio")
        grupos = [dict(base, ref="inicio"), dict(base, ref="fim")] if ref in ("as_duas", "ambas") else \
            [dict(base, ref="fim" if ref == "fim" else "inicio")]
        gid = "ia-" + secrets.token_hex(4)
    T.aplicar(bs, pontas, grupos, gid)
    for b in todas:
        b.touch()
    doc.recompute()
    if grupos and por_parafusos:
        if not grupos[0]["parafuso"]:
            raise ValueError("para pôr parafusos, informe furos.parafuso (M12...)")
        T.por_parafusos(bs, gid, grupos[0]["parafuso"], float(aperto))
        doc.recompute()
    return [{"indice": b.Indice, "comprimento_mm": round(b.ComprimentoCorte.Value, 1),
             "corte_inicio_graus": round(b.CorteInicio.Value, 1), "corte_fim_graus": round(b.CorteFim.Value, 1),
             "furacao": b.Furacao} for b in bs]


@ferramenta("lista_de_corte", "Lista de corte das estruturas (perfil, comprimento, ângulos, quantidade, furação). "
            "planilha=true grava a planilha no documento.",
            {"estrutura": {"type": "string"}, "planilha": {"type": "boolean"}}, muda=True)
def f_corte(estrutura=None, planilha=False):
    import PrumoEstrutura as E
    doc = _doc()
    objs = [_obj(doc, estrutura)] if estrutura else [o for o in doc.Objects if E.eh_estrutura(o)]
    linhas = E.lista_de_corte(objs)
    if planilha and linhas:
        E.gravar_lista_de_corte(doc, linhas)
    return [{"perfil": l[0], "comprimento_mm": l[1], "corte_a": l[2], "corte_b": l[3], "qtd": l[4],
             "massa_unit_kg": round(l[5], 3), "furacao": l[8] if len(l) > 8 else ""} for l in linhas]


@ferramenta("lista_de_materiais", "Lista de materiais (quantidade, descrição, material, dimensões, massa) do documento "
            "ou dos objetos indicados.", {"objetos": {"type": "array", "items": {"type": "string"}}}, muda=False)
def f_bom(objetos=None):
    import PrumoBOM
    doc = _doc()
    objs = [_obj(doc, n) for n in objetos] if objetos else [o for o in doc.RootObjects]
    return [{"qtd": l.qtd, "descricao": l.denominacao, "material": l.material, "dimensoes": l.dimensoes,
             "massa_kg": None if l.massa is None else round(l.massa, 3), "obs": l.obs}
            for l in PrumoBOM.coletar(objs)]


@ferramenta("nova_folha", "Folha de desenho ABNT (NBR 16752) com as vistas no 1º diedro na escala que cabe e a "
            "legenda preenchida. arranjo: 3vistas_iso, frontal_superior, frontal, ...",
            {"objetos": {"type": "array", "items": {"type": "string"}},
             "formato": {"type": "string", "enum": ["A4", "A3", "A2", "A1", "A0"]},
             "vertical": {"type": "boolean"}, "titulo": {"type": "string"}, "numero": {"type": "string"},
             "desenhista": {"type": "string"}, "arranjo": {"type": "string"}}, ["objetos"])
def f_folha(objetos, formato="A3", vertical=False, titulo="", numero="", desenhista="", arranjo="3vistas_iso"):
    import PrumoFolhas as F
    doc = _doc()
    objs = [_obj(doc, n) for n in objetos]
    campos = {k: v for k, v in (("titulo", titulo), ("numero", numero), ("desenhista", desenhista)) if v}
    page = F.nova_folha(doc, formato, F.NORMA_PADRAO, bool(vertical), campos, objs, arranjo=arranjo)
    return {"folha": page.Name, "escala": F._texto_escala(page.Scale)}


@ferramenta("cotar_folha", "Cotas gerais (comprimento, altura, profundidade) e furação (n× ⌀ e posição dos furos) "
            "nas vistas de uma folha.", {"folha": {"type": "string"}}, ["folha"])
def f_cotar(folha):
    import PrumoVistas as V
    doc = _doc()
    page = _obj(doc, folha)
    pecas = V.pecas_da_folha(page)
    grupo = V.grupo_da_peca(page, pecas)
    if grupo is None:
        raise ValueError("a folha não tem vista frontal")
    V.esperar_vistas(list(grupo.Views), 30.0)
    cotas = V.cotas_gerais(page, pecas, furos=True)
    return {"cotas": [{"rotulo": d.Label, "valor_mm": round(d.getRawValue(), 2)} for d in cotas]}


@ferramenta("baloes", "Balões numerados nas peças da vista (isométrica), com o número do item da lista de materiais.",
            {"folha": {"type": "string"}}, ["folha"])
def f_baloes(folha):
    import PrumoBaloes as B
    import PrumoFolhaPeca as FP
    doc = _doc()
    page = _obj(doc, folha)
    vista = B.vista_padrao(page)
    if vista is not None:
        FP.esperar_geometria([vista])
    return {"baloes": [{"item": n, "peca": b.PecaUsinix.Label} for b, n in B.criar_baloes(page, vista)]}


@ferramenta("folhas_das_barras", "Uma folha ABNT por barra diferente da estrutura (marcas B01, B02...), com vista "
            "interrompida, seção, comprimento, ângulos, furação cotada e quantidade.",
            {"estrutura": {"type": "string"}, "formato": {"type": "string", "enum": ["A4", "A3", "A2", "A1"]}},
            ["estrutura"])
def f_folhas_barras(estrutura, formato="A3"):
    import PrumoFolhaPeca as FP
    doc = _doc()
    feitas = FP.folhas_das_barras(doc, [_obj(doc, estrutura)], formato)
    return {"folhas": [{"folha": p.Name, "barra": b.Label, "perfil": b.Perfil, "quantidade": q}
                       for p, b, q in feitas]}


@ferramenta("folha_da_chapa", "Folha ABNT de uma peça de chapa: planificação cotada (com furação e linhas de dobra), "
            "isométrica e tabela de dobras.", {"peca": {"type": "string"}}, ["peca"])
def f_folha_chapa(peca):
    import PrumoFolhaPeca as FP
    doc = _doc()
    page = FP.folha_da_chapa(doc, _obj(doc, peca))
    return {"folha": page.Name}


@ferramenta("exportar_excel", "Grava um .xlsx com lista de materiais, lista de corte, lista de soldas e resumo para "
            "orçamento (massa por material, área de pintura, solda). Sem objetos: a montagem ou o documento.",
            {"caminho": {"type": "string"}, "objetos": {"type": "array", "items": {"type": "string"}}}, ["caminho"])
def f_excel(caminho, objetos=None):
    import PrumoBOM
    import PrumoFabrica
    doc = _doc()
    objs = [_obj(doc, n) for n in objetos] if objetos else PrumoBOM._objetos_alvo()
    PrumoFabrica.exportar_excel(objs, caminho)
    r = PrumoFabrica.resumo_orcamento(objs)
    return {"arquivo": caminho, "massa_total_kg": round(r["massa_total"], 3),
            "area_pintura_m2": round(r["area_pintura_m2"], 3),
            "materiais": [{"material": m, "massa_kg": round(kg, 3)} for m, kg in r["materiais"]]}


@ferramenta("dxf_das_chapas", "Um DXF por chapa diferente (contorno, furos, dobras e texto com espessura, material e "
            "quantidade) na pasta indicada, para corte a laser ou plasma.",
            {"pasta": {"type": "string"}, "objetos": {"type": "array", "items": {"type": "string"}}}, ["pasta"])
def f_dxf_lote(pasta, objetos=None):
    import PrumoBOM
    import PrumoFabrica
    doc = _doc()
    objs = [_obj(doc, n) for n in objetos] if objetos else PrumoBOM._objetos_alvo()
    feitos = PrumoFabrica.exportar_dxf_lote(objs, pasta)
    return {"arquivos": [{"arquivo": c, "peca": o.Label, "quantidade": q, "espessura_mm": t}
                         for c, o, q, t in feitos]}


@ferramenta("capturar_vista", "Imagem da vista 3D (PNG) para conferir o que foi feito. vista: iso, frente, topo, "
            "direita, atual.", {"vista": {"type": "string"}, "largura": {"type": "integer"}}, muda=False)
def f_captura(vista="iso", largura=900):
    gd = FreeCADGui.ActiveDocument
    if gd is None:
        raise ValueError("não há documento aberto")
    v = gd.ActiveView
    acao = {"iso": "viewIsometric", "frente": "viewFront", "topo": "viewTop", "direita": "viewRight"}.get(vista)
    if acao and hasattr(v, acao):
        getattr(v, acao)()
        v.fitAll()
    larg = max(200, min(int(largura), 1600))
    alt = int(larg * 0.65)
    caminho = os.path.join(tempfile.gettempdir(), "usinix_ia_%s.png" % secrets.token_hex(4))
    v.saveImage(caminho, larg, alt, "Current")
    with open(caminho, "rb") as fh:
        dados = base64.b64encode(fh.read()).decode("ascii")
    try:
        os.remove(caminho)
    except OSError:
        pass
    return {"_imagem": dados}


@ferramenta("desfazer", "Desfaz a última ação no documento ativo (cada ferramenta da IA é uma ação).", muda=False)
def f_desfazer():
    doc = _doc()
    nomes = list(doc.UndoNames)
    if not nomes:
        return {"desfeito": None}
    doc.undo()
    doc.recompute()
    return {"desfeito": nomes[0]}


@ferramenta("executar_python", "Executa código Python no Usinix (FreeCAD, Part, Sketcher...). Só funciona se o usuário "
            "ligou 'Permitir código Python' em Conectar IA. A variável 'resultado' volta como resposta.",
            {"codigo": {"type": "string"}}, ["codigo"])
def f_python(codigo):
    if not permitir_codigo():
        raise PermissionError("código Python solto está desligado. Use as ferramentas do Usinix, ou peça ao usuário "
                              "para ligar 'Permitir código Python' em Usinix › Conectar IA.")
    ns = {"FreeCAD": FreeCAD, "App": FreeCAD, "FreeCADGui": FreeCADGui, "Gui": FreeCADGui}
    exec(compile(codigo, "<ia>", "exec"), ns)
    r = ns.get("resultado")
    try:
        json.dumps(r)
        return {"resultado": r}
    except (TypeError, ValueError):
        return {"resultado": repr(r)}


def executar(nome, argumentos):
    """Roda a ferramenta (na linha da interface), numa transação quando muda o documento."""
    t = FERRAMENTAS.get(nome)
    if t is None:
        raise ValueError("ferramenta desconhecida: %s" % nome)
    argumentos = dict(argumentos or {})
    doc = FreeCAD.ActiveDocument if t["muda"] else None
    if doc is not None:
        doc.openTransaction("IA: %s" % nome)
    try:
        r = t["funcao"](**argumentos)
    except Exception:
        if doc is not None:
            doc.abortTransaction()
        raise
    if doc is not None:
        doc.commitTransaction()
    _estado["chamadas"] += 1
    _estado["ultima"] = nome
    return r


# ============================================================================ servidor HTTP local
class _Pedido(BaseHTTPRequestHandler):
    server_version = "UsinixIA/%d" % VERSAO_PROTOCOLO

    def log_message(self, *_a):
        pass

    def _responder(self, codigo, dados):
        corpo = json.dumps(dados, ensure_ascii=False).encode("utf-8")
        self.send_response(codigo)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(corpo)))
        self.end_headers()
        self.wfile.write(corpo)

    def _autorizado(self):
        if self.headers.get("Origin") or self.headers.get("Referer"):
            return False                        # pedido vindo de página web: recusado
        if not (self.headers.get("Content-Type") or "").startswith("application/json"):
            return False
        token = self.headers.get("X-Usinix-Token", "")
        return bool(_estado["token"]) and secrets.compare_digest(token, _estado["token"])

    def do_GET(self):
        self._responder(405, {"erro": "use POST"})

    def do_POST(self):
        if not self._autorizado():
            return self._responder(403, {"erro": "não autorizado"})
        try:
            n = int(self.headers.get("Content-Length", "0"))
            pedido = json.loads(self.rfile.read(min(n, 5_000_000)).decode("utf-8") or "{}")
        except Exception:
            return self._responder(400, {"erro": "pedido inválido"})
        caminho = self.path.rstrip("/")
        if caminho == "/ferramentas":
            return self._responder(200, {"ferramentas": [t["def"] for t in FERRAMENTAS.values()],
                                         "protocolo": VERSAO_PROTOCOLO})
        if caminho == "/chamar":
            nome = pedido.get("ferramenta")
            args = pedido.get("argumentos") or {}
            try:
                r = _estado["ponte"].chamar(lambda: executar(nome, args))
                return self._responder(200, {"ok": True, "resultado": r})
            except Exception as exc:
                return self._responder(200, {"ok": False, "erro": "%s" % exc})
        return self._responder(404, {"erro": "caminho desconhecido"})


def ligar(porta=None):
    """Liga a ponte (127.0.0.1) e grava porta e código em usinix-ia.json. Devolve a porta."""
    if _estado["servidor"] is not None:
        return _estado["porta"]
    porta = int(porta or FreeCAD.ParamGet(PARAM).GetInt("IAPorta", PORTA_PADRAO))
    _estado["ponte"] = _Despachante()
    _estado["token"] = secrets.token_urlsafe(24)
    srv = None
    for p in (porta, 0):                         # porta ocupada: o sistema escolhe outra
        try:
            srv = ThreadingHTTPServer(("127.0.0.1", p), _Pedido)
            break
        except OSError:
            continue
    if srv is None:
        raise OSError("não foi possível abrir a ponte local")
    srv.daemon_threads = True
    _estado["servidor"] = srv
    _estado["porta"] = srv.server_address[1]
    th = threading.Thread(target=srv.serve_forever, name="UsinixIA", daemon=True)
    th.start()
    _estado["thread"] = th
    caminho = arquivo_conexao()
    with open(caminho, "w", encoding="utf-8") as fh:
        json.dump({"porta": _estado["porta"], "token": _estado["token"], "pid": os.getpid()}, fh)
    try:
        os.chmod(caminho, 0o600)
    except OSError:
        pass
    FreeCAD.Console.PrintMessage("Usinix: IA conectável na porta local %d.\n" % _estado["porta"])
    return _estado["porta"]


def desligar():
    srv = _estado["servidor"]
    if srv is None:
        return False
    _estado["servidor"] = None
    try:
        srv.shutdown()
        srv.server_close()
    except Exception:
        pass
    _estado["token"] = None
    try:
        os.remove(arquivo_conexao())
    except OSError:
        pass
    FreeCAD.Console.PrintMessage("Usinix: conexão de IA desligada.\n")
    return True


def ligada():
    return _estado["servidor"] is not None


# ============================================================================ janela
class JanelaIA(QtWidgets.QDialog):
    def __init__(self, parent=None):
        super().__init__(parent or FreeCADGui.getMainWindow())
        self.setWindowTitle("Conectar IA")
        self.setMinimumWidth(560)
        lay = QtWidgets.QVBoxLayout(self)
        intro = QtWidgets.QLabel(
            "Deixe um assistente de IA (Claude Desktop e outros compatíveis com MCP) usar as ferramentas do Usinix: "
            "criar esboços e estruturas, trabalhos na barra, listas e folhas ABNT. Tudo fica no Desfazer.")
        intro.setWordWrap(True)
        lay.addWidget(intro)
        self.status = QtWidgets.QLabel()
        lay.addWidget(self.status)
        self.botao = QtWidgets.QPushButton()
        self.botao.clicked.connect(self._alternar)
        lay.addWidget(self.botao)
        g = FreeCAD.ParamGet(PARAM)
        self.ao_abrir = QtWidgets.QCheckBox("Ligar ao abrir o Usinix")
        self.ao_abrir.setChecked(g.GetBool("IALigarAoAbrir", False))
        self.ao_abrir.toggled.connect(lambda on: g.SetBool("IALigarAoAbrir", bool(on)))
        lay.addWidget(self.ao_abrir)
        self.codigo = QtWidgets.QCheckBox("Permitir código Python solto (avançado: a IA pode fazer qualquer coisa no "
                                          "programa)")
        self.codigo.setChecked(permitir_codigo())
        self.codigo.toggled.connect(lambda on: g.SetBool("IAPermitirCodigo", bool(on)))
        lay.addWidget(self.codigo)
        lay.addWidget(QtWidgets.QLabel("Configuração para o assistente (Claude Desktop: Configurações › Desenvolvedor › "
                                       "Editar configuração):"))
        self.cfg = QtWidgets.QPlainTextEdit(json.dumps(config_cliente(), indent=2, ensure_ascii=False))
        self.cfg.setReadOnly(True)
        self.cfg.setMinimumHeight(150)
        lay.addWidget(self.cfg)
        lin = QtWidgets.QHBoxLayout()
        copiar = QtWidgets.QPushButton("Copiar configuração")
        copiar.clicked.connect(lambda: QtWidgets.QApplication.clipboard().setText(self.cfg.toPlainText()))
        lin.addWidget(copiar)
        lin.addStretch(1)
        fechar = QtWidgets.QPushButton("Fechar")
        fechar.clicked.connect(self.accept)
        lin.addWidget(fechar)
        lay.addLayout(lin)
        self._atualizar()

    def _alternar(self):
        try:
            desligar() if ligada() else ligar()
        except Exception as exc:
            QtWidgets.QMessageBox.warning(self, "Conectar IA", str(exc))
        self._atualizar()

    def _atualizar(self):
        if ligada():
            self.status.setText("● Ligada — porta local %d. Chamadas: %d%s" % (
                _estado["porta"], _estado["chamadas"], (" (última: %s)" % _estado["ultima"]) if _estado["ultima"] else ""))
            self.botao.setText("Desligar")
        else:
            self.status.setText("○ Desligada")
            self.botao.setText("Ligar a conexão")


class CmdConectarIA:
    def GetResources(self):
        return {"Pixmap": PrumoUtil.icone("conectar_ia.svg"), "MenuText": "Conectar IA",
                "ToolTip": "Liga a conexão local para um assistente de IA (MCP) usar as ferramentas do Usinix e mostra "
                           "a configuração para o Claude Desktop."}

    def IsActive(self):
        return True

    def Activated(self):
        JanelaIA().exec_() if hasattr(QtWidgets.QDialog, "exec_") else JanelaIA().exec()


def registrar_comandos():
    FreeCADGui.addCommand("Prumo_ConectarIA", CmdConectarIA())
    if FreeCAD.ParamGet(PARAM).GetBool("IALigarAoAbrir", False):
        QtCore.QTimer.singleShot(3000, lambda: _seguro(ligar))


def _seguro(f):
    try:
        f()
    except Exception as exc:
        FreeCAD.Console.PrintWarning("Usinix: conexão de IA não ligou: %s\n" % exc)
