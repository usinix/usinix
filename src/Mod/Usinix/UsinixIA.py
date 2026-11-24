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

import UsinixUtil

try:
    from PySide import QtCore, QtGui, QtWidgets
except ImportError:  # pragma: no cover
    from PySide2 import QtCore, QtGui, QtWidgets

PARAM = "User parameter:BaseApp/Preferences/Mod/Usinix"
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


# ============================================================================ instalar no Claude Desktop
NOME_SERVIDOR = "usinix"
ARQUIVO_CLAUDE = "claude_desktop_config.json"


def pastas_do_claude(sistema=None, ambiente=None, casa=None):
    """Pastas onde o Claude Desktop guarda a configuração, na ordem em que valem.

    Windows: as versões recentes (2026) leem %LOCALAPPDATA%\\Claude-Data\\claude_<código> — é o arquivo que o
    "Editar configuração" do Claude abre; a versão MSIX anterior lia a cópia virtualizada em
    %LOCALAPPDATA%\\Packages\\Claude_<código>\\LocalCache\\Roaming\\Claude; o instalador comum, %APPDATA%\\Claude.
    O Usinix grava em todas as que existirem (as que o Claude não lê não atrapalham).
    macOS: ~/Library/Application Support/Claude. Linux (versões não oficiais): ~/.config/Claude."""
    import glob
    sistema = sistema or sys.platform
    ambiente = os.environ if ambiente is None else ambiente
    casa = casa or os.path.expanduser("~")
    if sistema.startswith("win"):
        res = []
        local = ambiente.get("LOCALAPPDATA") or os.path.join(casa, "AppData", "Local")
        for dados in sorted(glob.glob(os.path.join(local, "Claude-Data", "*"))):
            if os.path.isdir(dados):
                res.append(dados)
        for pac in sorted(glob.glob(os.path.join(local, "Packages", "Claude_*"))):
            res.append(os.path.join(pac, "LocalCache", "Roaming", "Claude"))
        res.append(os.path.join(ambiente.get("APPDATA") or os.path.join(casa, "AppData", "Roaming"), "Claude"))
        return res
    if sistema == "darwin":
        return [os.path.join(casa, "Library", "Application Support", "Claude")]
    return [os.path.join(ambiente.get("XDG_CONFIG_HOME") or os.path.join(casa, ".config"), "Claude")]


def arquivos_do_claude(**kw):
    """Arquivos de configuração do Claude Desktop instalado (a pasta do Claude existe). Vazio se não achar."""
    pastas = pastas_do_claude(**kw)
    achados = [os.path.join(p, ARQUIVO_CLAUDE) for p in pastas if os.path.isdir(p)]
    # arquivo escolhido à mão (Conectar IA › Outro arquivo…) vale primeiro
    if not kw:
        try:
            esc = FreeCAD.ParamGet(PARAM).GetString("IAArquivoClaude", "")
        except Exception:
            esc = ""
        if esc and os.path.isdir(os.path.dirname(esc)):
            achados = [esc] + [a for a in achados if os.path.normcase(a) != os.path.normcase(esc)]
    return achados


def _ler_config(caminho):
    """Configuração atual (dict) ou {} se o arquivo não existe ou está vazio. ValueError se o JSON está quebrado."""
    if not os.path.isfile(caminho):
        return {}
    with open(caminho, "r", encoding="utf-8-sig") as fh:
        texto = fh.read()
    if not texto.strip():
        return {}
    try:
        dados = json.loads(texto)
    except ValueError as exc:
        raise ValueError("O arquivo %s não é um JSON válido (%s). Nada foi alterado: corrija o arquivo ou use "
                         "Copiar configuração." % (caminho, exc))
    if not isinstance(dados, dict):
        raise ValueError("O arquivo %s não tem o formato esperado (um objeto JSON). Nada foi alterado." % caminho)
    if "mcpServers" in dados and not isinstance(dados["mcpServers"], dict):
        raise ValueError("Em %s, \"mcpServers\" não é um objeto. Nada foi alterado." % caminho)
    return dados


def _gravar_config(caminho, dados):
    """Grava num arquivo temporário da mesma pasta, confere o JSON lido de volta e só então troca o arquivo."""
    pasta = os.path.dirname(caminho)
    os.makedirs(pasta, exist_ok=True)
    texto = json.dumps(dados, indent=2, ensure_ascii=False) + "\n"
    fd, tmp = tempfile.mkstemp(prefix=".usinix-", suffix=".json", dir=pasta)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(texto)
        with open(tmp, "r", encoding="utf-8") as fh:
            if json.load(fh) != dados:
                raise ValueError("a conferência do arquivo gravado falhou")
        os.replace(tmp, caminho)
    except Exception:
        try:
            os.remove(tmp)
        except OSError:
            pass
        raise


def _copia_de_seguranca(caminho):
    if not os.path.isfile(caminho):
        return None
    import shutil
    destino = "%s.usinix-%s.bak" % (caminho, time.strftime("%Y%m%d-%H%M%S"))
    n = 1
    while os.path.exists(destino):
        n += 1
        destino = "%s.usinix-%s-%d.bak" % (caminho, time.strftime("%Y%m%d-%H%M%S"), n)
    shutil.copy2(caminho, destino)
    return destino


def instalar_config(caminho, entrada=None, nome=NOME_SERVIDOR):
    """Põe (ou atualiza) a entrada do Usinix em mcpServers, sem mexer no resto do arquivo.

    Devolve {"situacao": "instalado" | "atualizado" | "igual", "arquivo": ..., "copia": caminho da cópia ou None}.
    Arquivo quebrado: ValueError e nada é alterado."""
    entrada = entrada or config_cliente()["mcpServers"][NOME_SERVIDOR]
    dados = _ler_config(caminho)
    servidores = dados.get("mcpServers") or {}
    if servidores.get(nome) == entrada:
        return {"situacao": "igual", "arquivo": caminho, "copia": None}
    situacao = "atualizado" if nome in servidores else "instalado"
    copia = _copia_de_seguranca(caminho)
    servidores = dict(servidores)
    servidores[nome] = entrada
    dados["mcpServers"] = servidores
    _gravar_config(caminho, dados)
    return {"situacao": situacao, "arquivo": caminho, "copia": copia}


def remover_config(caminho, nome=NOME_SERVIDOR):
    """Tira a entrada do Usinix (com cópia de segurança). Devolve True se havia o que tirar."""
    dados = _ler_config(caminho)
    servidores = dados.get("mcpServers") or {}
    if nome not in servidores:
        return False
    _copia_de_seguranca(caminho)
    servidores = dict(servidores)
    del servidores[nome]
    dados["mcpServers"] = servidores
    _gravar_config(caminho, dados)
    return True


def instalado_no_claude():
    """Algum Claude Desktop desta máquina já tem a entrada do Usinix igual à atual?"""
    entrada = config_cliente()["mcpServers"][NOME_SERVIDOR]
    for arq in arquivos_do_claude():
        try:
            if (_ler_config(arq).get("mcpServers") or {}).get(NOME_SERVIDOR) == entrada:
                return True
        except (OSError, ValueError):
            continue
    return False


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
    import UsinixInserirDesenho as I
    try:
        tipo = I.tipo_legivel(o)
    except Exception:
        tipo = o.TypeId
    return {"nome": o.Name, "rotulo": o.Label, "tipo": tipo, "TypeId": o.TypeId}


@ferramenta("estado", "Situação do Usinix: versão, documento ativo e quantos objetos tem.", muda=False)
def f_estado():
    import UsinixVersao
    doc = FreeCAD.ActiveDocument
    return {"usinix": UsinixVersao.VERSAO, "documento": doc.Name if doc else None,
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
        import UsinixInserirDesenho as I
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


@ferramenta("grupo_das_barras", "Põe barras de uma estrutura num grupo, escolhendo pela barra (nome como Barra015 ou "
            "rótulo), não pelo índice da linha. grupo: nome de grupo existente ou novo; para grupo novo, perfil, giro "
            "(graus), fixacao (Centro, Centroide, Sup. centro, Meio direito...) e espelhar; o que faltar vem do grupo "
            "padrão.",
            {"barras": {"type": "array", "items": {"type": "string"}}, "grupo": {"type": "string"},
             "perfil": {"type": "string"}, "giro": {"type": "number"}, "fixacao": {"type": "string"},
             "espelhar": {"type": "boolean"}, "estrutura": {"type": "string"}}, ("barras", "grupo"))
def f_grupo_das_barras(barras, grupo, perfil=None, giro=None, fixacao=None, espelhar=None, estrutura=None):
    import UsinixEstrutura as E
    doc = _doc()
    if not barras:
        raise ValueError("nenhuma barra informada: passe os nomes (Barra015) ou rótulos das barras do grupo")
    if estrutura:
        est = doc.getObject(estrutura) or (doc.getObjectsByLabel(estrutura) or [None])[0]
    else:
        b0 = doc.getObject(barras[0]) or (doc.getObjectsByLabel(barras[0]) or [None])[0] if barras else None
        est = E.estrutura_de(b0) if b0 is not None else None
    if est is None or not E.eh_estrutura(est):
        raise ValueError("estrutura não encontrada")
    k = E.mover_para_grupo(est, barras, grupo, perfil, giro, fixacao, espelhar)
    return {"estrutura": est.Name, "grupo": k,
            "barras": {b.Name: E.parametros(est, b.Indice)["perfil"] for b in E.barras_de(est)
                       if E.grupo_da_barra(est, b.Indice) == k}}


@ferramenta("esqueleto_mef", "Cria (ou atualiza) o esqueleto de barras da estrutura para o estudo de vigas no MEF: "
            "linhas das barras partidas nos cruzamentos, ligadas à estrutura (mudou a estrutura, o esqueleto acompanha "
            "e a simulação avisa que a malha e o resultado ficaram velhos).",
            {"estrutura": {"type": "string"}})
def f_esqueleto_mef(estrutura=None):
    import UsinixEstrutura as E
    import UsinixEsqueletoMEF as M
    doc = _doc()
    if estrutura:
        est = doc.getObject(estrutura) or (doc.getObjectsByLabel(estrutura) or [None])[0]
    else:
        ests = [o for o in doc.Objects if E.eh_estrutura(o)]
        est = ests[0] if len(ests) == 1 else None
    if est is None or not E.eh_estrutura(est):
        raise ValueError("informe a estrutura (há %s no documento)" % (
            len([o for o in doc.Objects if E.eh_estrutura(o)]) or "nenhuma"))
    o = M.criar(est)
    return {"objeto": o.Name, "rotulo": o.Label, "linhas": len(o.Shape.Edges), "nos": len(o.Shape.Vertexes)}


@ferramenta("conferir_folha", "Confere uma folha de desenho antes de sair: escala do carimbo contra as vistas (e se "
            "estão na série normalizada), material do carimbo contra o modelo, vista ou anotação que invade a legenda "
            "ou passa da margem. corrigir_escala=true escreve no carimbo a escala das vistas (\"INDICADA\" quando há "
            "mais de uma).", {"folha": {"type": "string"}, "corrigir_escala": {"type": "boolean"}})
def f_conferir_folha(folha=None, corrigir_escala=False):
    import UsinixConferirFolha as C
    import UsinixFolhas as F
    doc = _doc()
    if folha:
        page = doc.getObject(folha) or (doc.getObjectsByLabel(folha) or [None])[0]
    else:
        pgs = [o for o in doc.Objects if o.TypeId == "TechDraw::DrawPage"]
        page = pgs[0] if len(pgs) == 1 else None
    if page is None or page.TypeId != "TechDraw::DrawPage":
        raise ValueError("informe a folha")
    corrigida = F.escrever_escala(page) if corrigir_escala else False
    return {"folha": page.Name, "avisos": C.conferir(page), "escala_corrigida": bool(corrigida)}


@ferramenta("isolar_solido", "Num corpo com vários sólidos (peças iguais modeladas juntas), cria uma cópia ligada de um "
            "só sólido para pôr na folha, sem esconder o corpo na árvore. indice: 0 = primeiro sólido; ou ponto [x, y, "
            "z] perto do sólido. Use o objeto devolvido em nova_folha.",
            {"peca": {"type": "string"}, "indice": {"type": "integer"},
             "ponto": {"type": "array", "items": {"type": "number"}}, "rotulo": {"type": "string"}}, ("peca",))
def f_isolar_solido(peca, indice=None, ponto=None, rotulo=None):
    import UsinixIsolarSolido as I
    doc = _doc()
    base = doc.getObject(peca) or (doc.getObjectsByLabel(peca) or [None])[0]
    if base is None:
        raise ValueError("peça não encontrada: %s" % peca)
    o = I.isolar(base, indice, FreeCAD.Vector(*ponto) if ponto else None, rotulo)
    return {"objeto": o.Name, "rotulo": o.Label, "solido": o.Indice, "solidos": len(base.Shape.Solids),
            "iguais": o.Iguais}


@ferramenta("memoria_analise_barras", "Memória de cálculo em PDF da análise por barras (NBR 8800), na identidade da "
            "empresa. responsavel, crea e art saem na capa; sem eles, o responsável e o registro da identidade e a "
            "ART em branco, para preencher à mão.",
            {"analise": {"type": "string"}, "caminho": {"type": "string"}, "responsavel": {"type": "string"},
             "crea": {"type": "string"}, "art": {"type": "string"}}, ("analise", "caminho"))
def f_memoria_analise_barras(analise, caminho, responsavel=None, crea=None, art=None):
    import UsinixAnaliseEstrutura as A
    import UsinixAnaliseRelatorio as R
    doc = _doc()
    a = doc.getObject(analise) or (doc.getObjectsByLabel(analise) or [None])[0]
    if a is None or not isinstance(getattr(a, "Proxy", None), A.Analise):
        raise ValueError("análise por barras não encontrada: %s" % analise)
    R.gerar_pdf(a, caminho, responsavel=responsavel, crea=crea, art=art)
    return {"arquivo": caminho, "situacao": a.Situacao, "taxa_maxima": a.TaxaMaxima}


@ferramenta("duplicar_analise", "Copia uma análise de simulação (material, seções, apoios, cargas, malha e solver) sobre a "
            "mesma geometria, para outro caso de carga ou de apoio. Os rótulos ficam iguais no relatório; a cópia "
            "nasce sem resultado.", {"analise": {"type": "string"}, "rotulo": {"type": "string"}}, ("analise",))
def f_duplicar_analise(analise, rotulo=None):
    import UsinixFEMBancada as B
    doc = _doc()
    a = doc.getObject(analise) or (doc.getObjectsByLabel(analise) or [None])[0]
    if a is None or not a.isDerivedFrom("Fem::FemAnalysis"):
        raise ValueError("análise não encontrada: %s" % analise)
    n = B.duplicar_analise(a, rotulo)
    return {"analise": n.Name, "rotulo": n.Label, "objetos": [(o.Name, B.rotulo(o)) for o in n.Group]}


@ferramenta("salvar", "Salva o documento ativo (ou o indicado), tentando de novo se o arquivo estiver preso por "
                "um instante pela sincronização do Drive/OneDrive. caminho: salva como (obrigatório em documento "
                "novo, que ainda não tem arquivo; termina em .FCStd).",
             {"documento": {"type": "string"}, "caminho": {"type": "string"}}, muda=False)
def f_salvar(documento=None, caminho=None):
    doc = _doc(documento)
    if caminho:
        caminho = os.path.abspath(os.path.expanduser(str(caminho)))
        if not caminho.lower().endswith(".fcstd"):
            caminho += ".FCStd"
        pasta = os.path.dirname(caminho)
        if not os.path.isdir(pasta):
            raise ValueError("a pasta não existe: %s" % pasta)
        doc.saveAs(caminho)
        return {"arquivo": doc.FileName, "tentativas": 1}
    if not doc.FileName:
        raise ValueError("o documento ainda não tem arquivo: informe caminho (pasta e nome do arquivo .FCStd)")
    n = UsinixUtil.salvar(doc)
    return {"arquivo": doc.FileName, "tentativas": n}


@ferramenta("carga_ponto_mais_distante", "Na análise de simulação (modelo de barras), aplica uma força vertical para "
            "baixo de massa_kg × 9,80665 N no ponto mais distante dos apoios, num nó ou no meio de uma barra (o esqueleto "
            "MEF é partido ali), como uma pessoa com carga na ponta de uma plataforma. A massa é informada por quem calcula, conforme a norma aplicável.",
            {"analise": {"type": "string"}, "massa_kg": {"type": "number"}, "rotulo": {"type": "string"}},
            ("analise", "massa_kg"))
def f_carga_ponto_mais_distante(analise, massa_kg, rotulo=None):
    import UsinixFEMBancada as B
    doc = _doc()
    a = doc.getObject(analise) or (doc.getObjectsByLabel(analise) or [None])[0]
    if a is None or not a.isDerivedFrom("Fem::FemAnalysis"):
        raise ValueError("análise não encontrada: %s" % analise)
    c, p, d = B.carga_no_ponto_mais_distante(a, massa_kg, rotulo)
    return {"carga": c.Name, "rotulo": c.Label, "forca_N": round(float(massa_kg) * B.G, 2),
            "ponto_mm": [round(p.x, 1), round(p.y, 1), round(p.z, 1)], "distancia_ao_apoio_mm": round(d, 1)}


@ferramenta("grupo_de_vistas", "Acrescenta um grupo de vistas (1º diedro) de outra peça numa folha que já existe, na "
            "posição x, y (mm da folha) e na escala dada (ex.: 0.2 = 1:5; sem escala, a da folha). projecoes: Front, "
            "Top, Right, Left, Bottom, Rear. Use no lugar de criar DrawProjGroup por script: com a folha aberta, o grupo "
            "criado à mão só aparecia certo depois de fechar e reabrir a página.",
            {"folha": {"type": "string"}, "objetos": {"type": "array", "items": {"type": "string"}},
             "projecoes": {"type": "array", "items": {"type": "string"}}, "x": {"type": "number"},
             "y": {"type": "number"}, "escala": {"type": "number"}}, ("folha", "objetos"))
def f_grupo_de_vistas(folha, objetos, projecoes=None, x=None, y=None, escala=None):
    import UsinixFolhas as F
    import UsinixVistas as V
    doc = _doc()
    page = doc.getObject(folha) or (doc.getObjectsByLabel(folha) or [None])[0]
    if page is None or page.TypeId != "TechDraw::DrawPage":
        raise ValueError("folha não encontrada: %s" % folha)
    fontes = []
    for n in objetos:
        o = doc.getObject(n) or (doc.getObjectsByLabel(n) or [None])[0]
        if o is None:
            raise ValueError("objeto não encontrado: %s" % n)
        fontes.append(o)
    if escala and F.escala_normal(float(escala)) != float(escala):
        raise ValueError("escala fora da série normalizada; use %s" % F._texto_escala(F.escala_normal(float(escala))))
    g = V.grupo_na_folha(page, fontes, tuple(projecoes or ("Front", "Right")), x, y, escala)
    F.escrever_escala(page)
    return {"grupo": g.Name, "vistas": [(v.Name, v.Type) for v in g.Views],
            "escala_legenda": dict(page.Template.EditableTexts).get("escala")}


@ferramenta("listar_perfis", "Perfis do catálogo do Usinix (W, U, L, tubos, metalon...). busca filtra pelo nome "
            "(ex.: 'W 150', 'U 152', 'tubo'). Use o nome exato em criar_estrutura.",
            {"busca": {"type": "string"}, "limite": {"type": "integer"}}, muda=False)
def f_perfis(busca="", limite=60):
    import UsinixPerfis
    nomes = UsinixPerfis.nomes()
    if busca:
        b = busca.lower()
        nomes = [n for n in nomes if b in n.lower()]
    return {"total": len(nomes), "perfis": nomes[:max(1, int(limite))]}


@ferramenta("criar_estrutura", "Estrutura soldada sobre as linhas de um esboço (esqueleto): uma barra de perfil por "
            "linha, com cantos em meia-esquadria ou de topo. Devolve a estrutura e as barras (índice = linha).",
            {"esqueleto": {"type": "string"}, "perfil": {"type": "string"},
             "uniao": {"type": "string", "enum": ["Meia-esquadria", "Topo"]},
             "giro": {"type": "number", "description": "giro do perfil em graus"},
             "material": {"type": "string", "description": "nome da biblioteca de materiais (ex.: ASTM A36)"},
             "fixacao": {"type": "string", "description": "ponto do perfil que fica sobre a linha: Centro, Centroide, "
                         "Sup. esquerdo, Sup. centro, Sup. direito, Meio esquerdo, Meio direito, Inf. esquerdo, "
                         "Inf. centro, Inf. direito (vigas apoiadas nas colunas: Sup. centro)"}},
            ["esqueleto", "perfil"])
def f_estrutura(esqueleto, perfil, uniao="Meia-esquadria", giro=0.0, material="", fixacao="Centro"):
    import UsinixEstrutura as E
    import UsinixFEM
    doc = _doc()
    sk = _obj(doc, esqueleto)
    if material:
        d = UsinixFEM.achar_material(material)
        if d is None:
            sug = UsinixFEM.parecidos(material)
            raise ValueError("material \"%s\" não está na biblioteca%s" % (
                material, (". Parecidos: " + ", ".join(sug)) if sug else ""))
        material = d["nome"]
    fixacao = fixacao or "Centro"
    if fixacao not in E.FIXACOES:
        raise ValueError("fixação \"%s\" desconhecida; use uma de: %s" % (fixacao, ", ".join(E.FIXACOES)))
    est = E.criar(doc, sk, perfil, rotacao=float(giro), alinhamento=fixacao, uniao=uniao, material=material,
                  transacao=False)
    return {"estrutura": est.Name, "barras": [{"indice": b.Indice, "nome": b.Name,
                                               "comprimento_mm": round(b.ComprimentoCorte.Value, 1)}
                                              for b in E.barras_de(est)]}


def _simples(txt):
    """Texto sem acento, minúsculo e sem espaços nas pontas (para achar nomes digitados de outro jeito)."""
    import unicodedata
    t = unicodedata.normalize("NFKD", str(txt or ""))
    return "".join(c for c in t if not unicodedata.combining(c)).strip().lower()


def _barras_pedidas(todas, barras):
    """Barras da estrutura por índice (0, "3") ou por nome/rótulo; erro claro com o que existe."""
    if barras is None:
        return list(todas)
    if not isinstance(barras, (list, tuple)):
        barras = [barras]
    por_ind = {b.Indice: b for b in todas}
    res, ruins = [], []
    for x in barras:
        b = None
        if isinstance(x, (int, float)) or (isinstance(x, str) and x.strip().lstrip("-").isdigit()):
            b = por_ind.get(int(x))
        else:
            t = _simples(x)
            b = next((o for o in todas if _simples(o.Name) == t or _simples(o.Label) == t), None)
        if b is None:
            ruins.append(str(x))
        elif b not in res:
            res.append(b)
    if ruins:
        exemplos = ", ".join("%d (%s)" % (b.Indice, b.Label) for b in sorted(todas, key=lambda o: o.Indice)[:8])
        raise ValueError("barra(s) não encontrada(s): %s. Use o índice ou o nome; nesta estrutura: %s%s"
                         % (", ".join(ruins), exemplos, "..." if len(todas) > 8 else ""))
    return res


@ferramenta("trabalhos_na_barra", "Corte das pontas soltas e furos nas barras de uma estrutura. ponta_inicio / "
            "ponta_fim: reto, horizontal ou vertical. furos (opcional): face (Alma, Mesa de cima, Mesa de baixo, "
            "As duas mesas), parafuso (M8..M30) ou diametro, ref (inicio, fim, as_duas), dist, qtd, passo, filas "
            "(1/2), gab (entre filas). por_parafusos=true põe parafuso, arruela e porca.",
            {"estrutura": {"type": "string"},
             "barras": {"type": "array", "items": {"type": ["integer", "string"]},
                        "description": "índices das barras (0, 1...) ou nomes/rótulos (Barra001)"},
             "ponta_inicio": {"type": "string", "enum": ["reto", "horizontal", "vertical"]},
             "ponta_fim": {"type": "string", "enum": ["reto", "horizontal", "vertical"]},
             "furos": {"type": "object"}, "por_parafusos": {"type": "boolean"},
             "aperto": {"type": "number"},
             "classe_parafuso": {"type": "string", "description": "ex.: Aço classe 8.8 zincado (padrão 8.8)"}},
            ["estrutura"])
def f_trabalhos(estrutura, barras=None, ponta_inicio=None, ponta_fim=None, furos=None, por_parafusos=False,
                aperto=0.0, classe_parafuso=""):
    import UsinixEstrutura as E
    import UsinixTrabalhosBarra as T
    doc = _doc()
    est = _obj(doc, estrutura)
    todas = E.barras_de(est)
    bs = _barras_pedidas(todas, barras)
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
        pfs = T.por_parafusos(bs, gid, grupos[0]["parafuso"], float(aperto), classe_parafuso or "")
        doc.recompute()
    else:
        pfs = []
    res = []
    eds = E.arestas(est.Esqueleto)
    for b in bs:
        r = {"indice": b.Indice, "comprimento_mm": round(b.ComprimentoCorte.Value, 1),
             "corte_inicio_graus": round(b.CorteInicio.Value, 1), "corte_fim_graus": round(b.CorteFim.Value, 1),
             "furacao": b.Furacao}
        pf = [o for o in pfs if o.Barra == b]
        if pf:
            # furos do grupo que cabem na barra × filas × lados, para conferir com os parafusos postos
            e = eds[b.Indice]
            esperados = 0
            for g in grupos:
                n_pos = len([x for x in E._pos_furos(e, g) if -1e-6 <= x <= e.Length + 1e-6])
                esperados += n_pos * (2 if int(g.get("filas", 1)) >= 2 else 1) * \
                    (2 if g.get("face") == "As duas mesas" else 1)
            r["parafusos"] = int(pf[0].Quantidade)
            if r["parafusos"] < esperados:
                p0 = e.valueAt(e.FirstParameter)
                r["aviso"] = ("%d parafuso(s) para %d furo(s) do grupo: parte dos furos não existe na barra (a "
                              "ponta cortada ou outra peça os tirou). A ponta de início desta barra é a do ponto "
                              "(%.0f; %.0f; %.0f) mm; se os furos eram na outra ponta, use ref='fim'."
                              % (r["parafusos"], esperados, p0.x, p0.y, p0.z))
            r["aviso_junta"] = ("o comprimento do parafuso considera só o material da barra; acrescente a chapa ou "
                                "a cantoneira da ligação em 'aperto' (mm)") if not aperto else ""
        res.append(r)
    return res


@ferramenta("lista_de_corte", "Lista de corte das estruturas (perfil, comprimento, ângulos, quantidade, furação). "
            "planilha=true grava a planilha no documento.",
            {"estrutura": {"type": "string"}, "planilha": {"type": "boolean"}}, muda=True)
def f_corte(estrutura=None, planilha=False):
    import UsinixEstrutura as E
    doc = _doc()
    objs = [_obj(doc, estrutura)] if estrutura else [o for o in doc.Objects if E.tem_lista_de_corte(o)]
    linhas = E.lista_de_corte(objs)
    if planilha and linhas:
        E.gravar_lista_de_corte(doc, linhas)
    return [{"perfil": l[0], "comprimento_mm": l[1], "corte_a": l[2], "corte_b": l[3], "qtd": l[4],
             "massa_unit_kg": round(l[5], 3), "furacao": l[8] if len(l) > 8 else ""} for l in linhas]


@ferramenta("lista_de_materiais", "Lista de materiais (quantidade, descrição, material, dimensões, massa) do documento "
            "ou dos objetos indicados.", {"objetos": {"type": "array", "items": {"type": "string"}}}, muda=False)
def f_bom(objetos=None):
    import UsinixBOM
    doc = _doc()
    objs = [_obj(doc, n) for n in objetos] if objetos else UsinixBOM.raizes(doc)
    return [{"qtd": l.qtd, "descricao": l.denominacao, "material": l.material, "dimensoes": l.dimensoes,
             "massa_kg": None if l.massa is None else round(l.massa, 3), "obs": l.obs}
            for l in UsinixBOM.coletar(objs)]


@ferramenta("nova_folha", "Folha de desenho ABNT (NBR 16752) com as vistas no 1º diedro na escala que cabe e a "
            "legenda preenchida. arranjo: 3vistas_iso, frontal_superior, frontal, ...",
            {"objetos": {"type": "array", "items": {"type": "string"}},
             "formato": {"type": "string", "enum": ["A4", "A3", "A2", "A1", "A0"]},
             "vertical": {"type": "boolean"}, "titulo": {"type": "string"}, "numero": {"type": "string"},
             "desenhista": {"type": "string"}, "arranjo": {"type": "string"}}, ["objetos"])
def f_folha(objetos, formato="A3", vertical=False, titulo="", numero="", desenhista="", arranjo="3vistas_iso"):
    import UsinixFolhas as F
    doc = _doc()
    objs = [_obj(doc, n) for n in objetos]
    campos = {k: v for k, v in (("titulo", titulo), ("numero", numero), ("desenhista", desenhista)) if v}
    campos.update(SEM_REVISAO)
    page = F.nova_folha(doc, formato, F.NORMA_PADRAO, bool(vertical), campos, objs, arranjo=arranjo)
    try:
        import UsinixVistas
        UsinixVistas.folha_desenhada(page)        # a folha já aberta sai certa no PDF, mesmo exportada direto
    except Exception as exc:
        FreeCAD.Console.PrintLog("Usinix: abrir a folha nova: %s\n" % exc)
    return {"folha": page.Name, "escala": F._texto_escala(page.Scale)}


@ferramenta("cotar_folha", "Cotas gerais (comprimento, altura, profundidade) e furação (n× ⌀ e posição dos furos) "
            "nas vistas de uma folha.", {"folha": {"type": "string"}}, ["folha"])
def f_cotar(folha):
    import UsinixVistas as V
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
    import UsinixBaloes as B
    import UsinixFolhaPeca as FP
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
    import UsinixFolhaPeca as FP
    doc = _doc()
    feitas = FP.folhas_das_barras(doc, [_obj(doc, estrutura)], formato, campos_extra=SEM_REVISAO)
    return {"folhas": [{"folha": p.Name, "barra": b.Label, "perfil": b.Perfil, "quantidade": q}
                       for p, b, q in feitas]}


@ferramenta("fixador", "Parafuso, porca ou arruela num furo existente, como o painel Peças padronizadas: o "
            "fixador vai para o furo, apoiado na face, com o corpo entrando no material. peca e aresta: o objeto e "
            "a aresta circular do furo (ex.: Edge12); tipo: sextavado, allen, porca ou arruela; rosca: M8, M10... "
            "(sem rosca, a maior que passa no furo; em furo roscado, informe a rosca); comprimento em mm.",
            {"peca": {"type": "string"}, "aresta": {"type": "string"},
             "tipo": {"type": "string", "enum": ["sextavado", "allen", "porca", "arruela"]},
             "rosca": {"type": "string"}, "comprimento": {"type": "number"},
             "material": {"type": "string", "description": "classe e acabamento, ex.: aço classe 8.8, zincado"}},
            ["peca", "aresta", "tipo"])
def f_fixador(peca, aresta, tipo, rosca=None, comprimento=0.0, material=""):
    import UsinixFixadores as F
    doc = _doc()
    o = _obj(doc, peca)
    apelidos = {"sextavado": "sextavado", "hexagonal": "sextavado", "parafuso": "sextavado",
                "parafuso sextavado": "sextavado", "allen": "allen", "parafuso allen": "allen", "cilindrico": "allen",
                "porca": "porca", "porca sextavada": "porca", "arruela": "arruela", "arruela lisa": "arruela"}
    t = apelidos.get(_simples(tipo))
    if t is None or t not in F.TIPOS:
        raise ValueError("tipo de fixador '%s' não existe; use: sextavado, allen, porca ou arruela" % tipo)
    tipo = t
    pl, diam = F.posicao_no_furo(o, aresta)
    if pl is None:
        raise ValueError("a aresta %s de %s não é a borda de um furo (precisa ser um círculo fechado com parede "
                         "côncava; arco de canto arredondado não vale)" % (aresta, o.Label))
    m = rosca or F.diametro_para_furo(diam)
    if m not in F.diametros(tipo):
        raise ValueError("rosca %s não existe para %s; opções: %s" % (m, F.TIPOS[tipo], ", ".join(F.diametros(tipo))))
    if F.tem_comprimento(tipo) and not comprimento:
        raise ValueError("informe o comprimento do parafuso (mm)")
    f = F.criar(doc, tipo, m, float(comprimento or 0.0), pl, material or F.classe_equivalente("", tipo))
    return {"objeto": f.Name, "rotulo": f.Label, "denominacao": f.Denominacao,
            "furo_mm": round(float(diam or 0.0), 2),
            "posicao_mm": [round(c, 2) for c in (f.Placement.Base.x, f.Placement.Base.y, f.Placement.Base.z)]}


# a folha feita pela IA não sai como verificada nem aprovada: esses campos ficam para quem revisar
SEM_REVISAO = {"verificado": "", "aprovado": ""}


@ferramenta("folha_da_chapa", "Folha ABNT de uma peça de chapa: planificação cotada (com furação e linhas de dobra), "
            "isométrica e tabela de dobras.", {"peca": {"type": "string"}}, ["peca"])
def f_folha_chapa(peca):
    import UsinixFolhaPeca as FP
    doc = _doc()
    page = FP.folha_da_chapa(doc, _obj(doc, peca), campos=dict(SEM_REVISAO))
    return {"folha": page.Name}


@ferramenta("exportar_excel", "Grava um .xlsx com lista de materiais, lista de corte, lista de soldas e resumo para "
            "orçamento (massa por material, área de pintura, solda). Sem objetos: a montagem ou o documento.",
            {"caminho": {"type": "string"}, "objetos": {"type": "array", "items": {"type": "string"}}}, ["caminho"])
def f_excel(caminho, objetos=None):
    import UsinixBOM
    import UsinixFabrica
    doc = _doc()
    objs = [_obj(doc, n) for n in objetos] if objetos else UsinixBOM._objetos_alvo(usar_selecao=False)
    linhas = UsinixBOM.coletar(objs)
    UsinixFabrica.exportar_excel(objs, caminho, linhas)
    r = UsinixFabrica.resumo_orcamento(objs, linhas)
    extra = {} if r.get("massa_tubulacao_instalada") is None else \
        {"massa_tubulacao_montada_kg": round(r["massa_tubulacao_instalada"], 3)}
    return {**extra, "arquivo": caminho, "massa_total_kg": round(r["massa_total"], 3),
            "area_pintura_m2": round(r["area_pintura_m2"], 3),
            "materiais": [{"material": m, "massa_kg": round(kg, 3)} for m, kg in r["materiais"]]}


@ferramenta("dxf_das_chapas", "Um DXF por chapa diferente (contorno, furos, dobras e texto com espessura, material e "
            "quantidade) na pasta indicada, para corte a laser ou plasma.",
            {"pasta": {"type": "string"}, "objetos": {"type": "array", "items": {"type": "string"}}}, ["pasta"])
def f_dxf_lote(pasta, objetos=None):
    import UsinixBOM
    import UsinixFabrica
    doc = _doc()
    objs = [_obj(doc, n) for n in objetos] if objetos else UsinixBOM._objetos_alvo(usar_selecao=False)
    feitos = UsinixFabrica.exportar_dxf_lote(objs, pasta)
    return {"arquivos": [{"arquivo": c, "peca": o.Label, "quantidade": q, "espessura_mm": t}
                         for c, o, q, t in feitos]}


@ferramenta("capturar_vista", "Imagem da vista 3D (PNG) para conferir o que foi feito. vista: iso, frente, topo, "
            "direita, atual.", {"vista": {"type": "string"}, "largura": {"type": "integer"}}, muda=False)
def f_captura(vista="iso", largura=900):
    gd = FreeCADGui.ActiveDocument
    if gd is None:
        raise ValueError("não há documento aberto")
    v = gd.ActiveView
    if not hasattr(v, "saveImage"):
        # a aba ativa é uma folha, planilha ou texto: volta para a vista 3D do documento
        vistas = list(gd.mdiViewsOfType("Gui::View3DInventor")) if hasattr(gd, "mdiViewsOfType") else []
        if not vistas:
            raise ValueError("o documento não tem vista 3D aberta para capturar")
        v = vistas[0]
        try:
            mw = FreeCADGui.getMainWindow()
            from PySide import QtWidgets
            area = mw.findChild(QtWidgets.QMdiArea)
            alvo = getattr(v, "graphicsView", lambda: None)()
            for sub in (area.subWindowList() if area else []):
                if alvo is not None and sub.isAncestorOf(alvo):
                    area.setActiveSubWindow(sub)
                    break
        except Exception:
            pass
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


TEMPO_PYTHON = 60.0


class TempoEsgotado(Exception):
    pass


@ferramenta("executar_python", "Executa código Python no Usinix (FreeCAD, Part, Sketcher...). Só funciona se o usuário "
            "ligou 'Permitir código Python' em Conectar IA. A variável 'resultado' volta como resposta. "
            "tempo_max_s (padrão 60, até 170): o código é interrompido quando passa do tempo, para o Usinix e a "
            "conexão não ficarem presos (uma operação longa do próprio FreeCAD, como um recálculo, termina antes de "
            "parar).",
            {"codigo": {"type": "string"}, "tempo_max_s": {"type": "number"}}, ["codigo"])
def f_python(codigo, tempo_max_s=TEMPO_PYTHON):
    import sys
    import time
    if not permitir_codigo():
        raise PermissionError("código Python solto está desligado. Use as ferramentas do Usinix, ou peça ao usuário "
                              "para ligar 'Permitir código Python' em Usinix › Conectar IA.")
    limite = time.time() + max(1.0, min(float(tempo_max_s or TEMPO_PYTHON), TEMPO_MAX - 10.0))
    ns = {"FreeCAD": FreeCAD, "App": FreeCAD, "FreeCADGui": FreeCADGui, "Gui": FreeCADGui}
    anterior = sys.gettrace()

    def vigia(frame, evento, arg):
        if time.time() > limite:
            raise TempoEsgotado("o código passou de %.0f s e foi interrompido (aumente tempo_max_s ou divida "
                                "o trabalho)" % float(tempo_max_s or TEMPO_PYTHON))
        return vigia if frame.f_code.co_filename == "<ia>" else None

    sys.settrace(vigia)
    try:
        exec(compile(codigo, "<ia>", "exec"), ns)
    finally:
        sys.settrace(anterior)
    r = ns.get("resultado")
    try:
        json.dumps(r)
        return {"resultado": r}
    except (TypeError, ValueError):
        return {"resultado": repr(r)}


def _refazer_formas(doc):
    """Depois de desfazer uma ferramenta que falhou: as propriedades voltam, mas a forma calculada no meio
    do erro pode ter ficado (peça "corrompida"). Marca e recalcula o que ficou inválido ou pendente."""
    try:
        sujos = [o for o in doc.Objects
                 if "Invalid" in (o.State or []) or "Touched" in (o.State or []) or o.isError()]
        for o in sujos:
            try:
                o.touch()
            except Exception:
                pass
        if sujos:
            doc.recompute()
    except Exception as exc:
        FreeCAD.Console.PrintLog("Usinix IA: recálculo depois do desfazer: %s\n" % exc)


def executar(nome, argumentos):
    """Roda a ferramenta (na linha da interface), numa transação quando muda o documento."""
    t = FERRAMENTAS.get(nome)
    if t is None:
        raise ValueError("ferramenta desconhecida: %s" % nome)
    argumentos = dict(argumentos or {})
    doc = FreeCAD.ActiveDocument if t["muda"] else None
    nome_doc = doc.Name if doc is not None else None
    uid = getattr(doc, "Uid", None) if doc is not None else None
    if doc is not None:
        doc.openTransaction("IA: %s" % nome)

    def aberto():
        # a ferramenta pode ter fechado o documento (executar_python com closeDocument), e até aberto outro
        # com o mesmo nome na mesma chamada: só vale o mesmo documento, ainda vivo
        try:
            d = FreeCAD.listDocuments().get(nome_doc) if nome_doc is not None else None
            return d is not None and getattr(d, "Uid", None) == uid
        except Exception:
            return False
    try:
        r = t["funcao"](**argumentos)
    except Exception:
        if aberto():
            try:
                doc.abortTransaction()
                _refazer_formas(doc)
            except Exception as exc:
                FreeCAD.Console.PrintLog("Usinix IA: desfazer: %s\n" % exc)
        raise
    if aberto():
        try:
            doc.commitTransaction()
        except Exception as exc:
            # a transação já foi fechada pelo próprio código (ex.: documento fechado e reaberto): não é erro
            FreeCAD.Console.PrintLog("Usinix IA: fechar a transação: %s\n" % exc)
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
            lista = [t["def"] for t in FERRAMENTAS.values()]
            gravar_lista_ferramentas(lista)
            return self._responder(200, {"ferramentas": lista, "protocolo": VERSAO_PROTOCOLO})
        if caminho == "/chamar":
            nome = pedido.get("ferramenta")
            args = pedido.get("argumentos") or {}
            try:
                r = _estado["ponte"].chamar(lambda: executar(nome, args))
                return self._responder(200, {"ok": True, "resultado": r})
            except Exception as exc:
                return self._responder(200, {"ok": False, "erro": "%s" % exc})
        return self._responder(404, {"erro": "caminho desconhecido"})


def arquivo_ferramentas():
    """Lista de ferramentas guardada para o servidor MCP mostrar mesmo com o Usinix fechado."""
    return os.path.join(os.path.dirname(arquivo_conexao()), "usinix-ia-ferramentas.json")


def gravar_lista_ferramentas(lista=None):
    """Grava a lista completa (inclusive as do Pro) quando muda; o assistente costuma pedir a lista uma vez só,
    ao abrir, e com o Usinix ainda fechado ficaria só com 'estado'."""
    if lista is None:
        lista = [t["def"] for t in FERRAMENTAS.values()]
    caminho = arquivo_ferramentas()
    try:
        with open(caminho, encoding="utf-8") as fh:
            if json.load(fh).get("ferramentas") == lista:
                return False
    except Exception:
        pass
    try:
        with open(caminho, "w", encoding="utf-8") as fh:
            json.dump({"ferramentas": lista}, fh, ensure_ascii=False)
        return True
    except OSError:
        return False


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
    gravar_lista_ferramentas()
    script_mcp()      # o servidor que o assistente roda é uma cópia: sem isto ficava a da 1ª conexão, sem as correções
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


def claude_aberto():
    """O Claude Desktop está rodando? (ele pode regravar a configuração ao sair). None se não deu para saber."""
    import subprocess
    try:
        if sys.platform.startswith("win"):
            sai = subprocess.run(["tasklist", "/FI", "IMAGENAME eq claude.exe", "/NH"], capture_output=True,
                                 text=True, timeout=10, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            return "claude.exe" in sai.stdout.lower()
        sai = subprocess.run(["pgrep", "-x", "Claude" if sys.platform == "darwin" else "claude"],
                             capture_output=True, text=True, timeout=10)
        return sai.returncode == 0
    except Exception:
        return None


def escolher_arquivo_claude(pai=None):
    """Pede o claude_desktop_config.json (o que o "Editar configuração" do Claude abre) e guarda a escolha."""
    inicio = os.path.dirname(FreeCAD.ParamGet(PARAM).GetString("IAArquivoClaude", "")) or os.path.expanduser("~")
    arq, _f = QtWidgets.QFileDialog.getOpenFileName(pai or FreeCADGui.getMainWindow(),
                                                    "Arquivo de configuração do Claude Desktop", inicio,
                                                    "Configuração do Claude (claude_desktop_config.json);;"
                                                    "JSON (*.json)")
    if arq:
        FreeCAD.ParamGet(PARAM).SetString("IAArquivoClaude", os.path.normpath(arq))
    return arq or None


def instalar_no_claude_desktop(janela=None):
    """Botão "Instalar no Claude Desktop": acha o arquivo, avisa se o Claude está aberto, instala e explica o resto."""
    caixa = QtWidgets.QMessageBox
    pai = janela or FreeCADGui.getMainWindow()
    arquivos = arquivos_do_claude()
    if not arquivos:
        r = caixa.question(pai, "Instalar no Claude Desktop",
                           "Não achei o Claude Desktop neste computador (pasta de configuração do Claude).\n\n"
                           "Instale e abra o Claude Desktop uma vez e clique de novo. Se ele está instalado em outro "
                           "lugar, escolha o arquivo claude_desktop_config.json.\n\nEscolher o arquivo agora?",
                           caixa.Yes | caixa.No, caixa.No)
        if r != caixa.Yes:
            return None
        arq = escolher_arquivo_claude(pai)
        if not arq:
            return None
        arquivos = [arq]
    if claude_aberto():
        r = caixa.question(pai, "Instalar no Claude Desktop",
                           "Parece que o Claude Desktop está aberto. Ele pode regravar a configuração ao fechar e apagar a "
                           "entrada do Usinix.\n\nFeche o Claude Desktop pelo ícone perto do relógio › Sair (fechar a "
                           "janela não basta) e clique em Repetir. Se ele já está fechado, clique em Ignorar.",
                           caixa.Retry | caixa.Ignore | caixa.Cancel, caixa.Retry)
        if r == caixa.Cancel:
            return None
        if r == caixa.Retry:
            return instalar_no_claude_desktop(janela)
    feitos, erros = [], []
    for arq in arquivos:
        try:
            feitos.append(instalar_config(arq))
        except (OSError, ValueError) as exc:
            erros.append("%s\n%s" % (arq, exc))
    if erros and not feitos:
        caixa.warning(pai, "Instalar no Claude Desktop", "Não foi possível instalar.\n\n" + "\n\n".join(erros))
        return None
    linhas = []
    for r in feitos:
        txt = {"instalado": "Instalado em", "atualizado": "Atualizado em", "igual": "Já estava instalado em"}[
            r["situacao"]]
        linhas.append("%s:\n%s" % (txt, r["arquivo"]))
        if r["copia"]:
            linhas.append("Cópia do arquivo anterior:\n%s" % r["copia"])
    linhas.append("Agora abra o Claude Desktop (se estava aberto, saia pelo ícone perto do relógio e abra de novo). "
                  "Confira em Configurações › Desenvolvedor: o \"usinix\" tem de aparecer em Servidores MCP locais. "
                  "Se não aparecer, clique lá em Editar configuração para ver qual arquivo o Claude usa e escolha "
                  "esse arquivo em Conectar IA › Outro arquivo….")
    if erros:
        linhas.append("Não deu em:\n" + "\n\n".join(erros))
    texto = "\n\n".join(linhas)
    if not ligada():
        r = caixa.question(pai, "Instalar no Claude Desktop", texto + "\n\nO Claude só alcança o Usinix com a conexão "
                           "ligada. Ligar agora e sempre que abrir o Usinix?", caixa.Yes | caixa.No, caixa.Yes)
        if r == caixa.Yes:
            FreeCAD.ParamGet(PARAM).SetBool("IALigarAoAbrir", True)
            try:
                ligar()
            except Exception as exc:
                caixa.warning(pai, "Conectar IA", "A conexão não ligou: %s" % exc)
    else:
        caixa.information(pai, "Instalar no Claude Desktop", texto)
    return feitos


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
        claude = QtWidgets.QHBoxLayout()
        self.bt_claude = QtWidgets.QPushButton("Instalar no Claude Desktop")
        self.bt_claude.setObjectName("UsinixPrimario")
        self.bt_claude.setToolTip("Acrescenta o Usinix na configuração do Claude Desktop (claude_desktop_config.json), "
                                  "com cópia de segurança, sem mexer no resto do arquivo.")
        self.bt_claude.clicked.connect(self._instalar_claude)
        claude.addWidget(self.bt_claude)
        outro = QtWidgets.QPushButton("Outro arquivo…")
        outro.setToolTip("Escolha o arquivo que o Claude abre em Configurações › Desenvolvedor › Editar configuração, "
                         "se o Usinix não achou o certo. A escolha fica guardada.")
        outro.clicked.connect(self._outro_arquivo)
        claude.addWidget(outro)
        self.st_claude = QtWidgets.QLabel()
        claude.addWidget(self.st_claude, 1)
        lay.addLayout(claude)
        lay.addWidget(QtWidgets.QLabel("Outros assistentes, ou para colocar à mão (Claude Desktop: Configurações › "
                                       "Desenvolvedor › Editar configuração):"))
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

    def _outro_arquivo(self):
        if escolher_arquivo_claude(self):
            self._instalar_claude()

    def _instalar_claude(self):
        instalar_no_claude_desktop(self)
        self._atualizar()

    def _atualizar(self):
        try:
            ok = instalado_no_claude()
        except Exception:
            ok = False
        self.st_claude.setText("✓ instalado no Claude Desktop" if ok else "")
        self.ao_abrir.blockSignals(True)
        self.ao_abrir.setChecked(FreeCAD.ParamGet(PARAM).GetBool("IALigarAoAbrir", False))
        self.ao_abrir.blockSignals(False)
        self.bt_claude.setText("Atualizar no Claude Desktop" if ok else "Instalar no Claude Desktop")
        if ligada():
            self.status.setText("● Ligada — porta local %d. Chamadas: %d%s" % (
                _estado["porta"], _estado["chamadas"], (" (última: %s)" % _estado["ultima"]) if _estado["ultima"] else ""))
            self.botao.setText("Desligar")
        else:
            self.status.setText("○ Desligada")
            self.botao.setText("Ligar a conexão")


class CmdConectarIA:
    def GetResources(self):
        return {"Pixmap": UsinixUtil.icone("conectar_ia.svg"), "MenuText": "Conectar IA",
                "ToolTip": "Liga a conexão local para um assistente de IA (MCP) usar as ferramentas do Usinix e "
                           "instala o Usinix no Claude Desktop com um clique."}

    def IsActive(self):
        return True

    def Activated(self):
        JanelaIA().exec_() if hasattr(QtWidgets.QDialog, "exec_") else JanelaIA().exec()


def registrar_comandos():
    FreeCADGui.addCommand("Usinix_ConectarIA", CmdConectarIA())
    if FreeCAD.ParamGet(PARAM).GetBool("IALigarAoAbrir", False):
        QtCore.QTimer.singleShot(3000, lambda: _seguro(ligar))


def _seguro(f):
    try:
        f()
    except Exception as exc:
        FreeCAD.Console.PrintWarning("Usinix: conexão de IA não ligou: %s\n" % exc)
