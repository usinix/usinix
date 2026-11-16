#!/usr/bin/env python3
# SPDX-License-Identifier: LGPL-2.1-or-later
# Usinix - servidor MCP (stdio) que liga um assistente de IA ao Usinix aberto. Só biblioteca padrão do Python.
"""Servidor MCP do Usinix.

O assistente (ex.: Claude Desktop) inicia este programa e conversa com ele por JSON-RPC na entrada/saída padrão.
Cada ferramenta é repassada à ponte local do Usinix (ligada em Usinix › Conectar IA), que grava porta e código
secreto em usinix-ia.json na pasta de dados do Usinix.

Uso: python usinix_mcp.py --conexao <caminho do usinix-ia.json>
"""

import json
import os
import sys
import urllib.error
import urllib.request

VERSAO = "1.0"
PROTOCOLOS = ("2025-06-18", "2025-03-26", "2024-11-05")
AVISO_DESLIGADO = ("O Usinix não está com a conexão de IA ligada. Abra o Usinix e clique em Usinix › Conectar IA › "
                   "Ligar a conexão; depois tente de novo.")


def _arquivo_conexao():
    if "--conexao" in sys.argv:
        i = sys.argv.index("--conexao")
        if i + 1 < len(sys.argv):
            return sys.argv[i + 1]
    base = os.environ.get("APPDATA") or os.path.join(os.path.expanduser("~"), ".local", "share")
    return os.path.join(base, "Usinix", "usinix-ia.json")


def _ponte(caminho, dados, tempo=200):
    with open(_arquivo_conexao(), encoding="utf-8") as fh:
        con = json.load(fh)
    req = urllib.request.Request("http://127.0.0.1:%d%s" % (int(con["porta"]), caminho),
                                 data=json.dumps(dados).encode("utf-8"), method="POST",
                                 headers={"Content-Type": "application/json", "X-Usinix-Token": con["token"]})
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))   # sempre direto, sem proxy
    with opener.open(req, timeout=tempo) as r:
        return json.loads(r.read().decode("utf-8"))


def _ferramentas():
    try:
        return _ponte("/ferramentas", {}, tempo=10)["ferramentas"]
    except Exception:
        return [{"name": "estado", "description": "Situação da conexão com o Usinix. " + AVISO_DESLIGADO,
                 "inputSchema": {"type": "object", "properties": {}}}]


def _chamar(nome, args):
    try:
        r = _ponte("/chamar", {"ferramenta": nome, "argumentos": args or {}})
    except (OSError, urllib.error.URLError, ValueError, KeyError):
        return {"content": [{"type": "text", "text": AVISO_DESLIGADO}], "isError": True}
    if not r.get("ok"):
        return {"content": [{"type": "text", "text": "Erro no Usinix: %s" % r.get("erro")}], "isError": True}
    res = r.get("resultado")
    if isinstance(res, dict) and "_imagem" in res:
        return {"content": [{"type": "image", "data": res["_imagem"], "mimeType": "image/png"}]}
    return {"content": [{"type": "text", "text": json.dumps(res, ensure_ascii=False, indent=1)}]}


def _resposta(ident, resultado=None, erro=None):
    m = {"jsonrpc": "2.0", "id": ident}
    if erro is not None:
        m["error"] = erro
    else:
        m["result"] = resultado
    sys.stdout.write(json.dumps(m, ensure_ascii=False) + "\n")
    sys.stdout.flush()


def tratar(msg):
    """Trata uma mensagem JSON-RPC; devolve True se respondeu."""
    metodo, ident, par = msg.get("method"), msg.get("id"), msg.get("params") or {}
    if ident is None:                 # notificação (ex.: notifications/initialized): sem resposta
        return False
    if metodo == "initialize":
        pedido = par.get("protocolVersion")
        _resposta(ident, {"protocolVersion": pedido if pedido in PROTOCOLOS else PROTOCOLOS[0],
                          "capabilities": {"tools": {"listChanged": False}},
                          "serverInfo": {"name": "usinix", "version": VERSAO},
                          "instructions": "Ferramentas do Usinix (CAD mecânico brasileiro, base FreeCAD). Medidas em "
                                          "mm. Para estruturas: esboco_linhas → criar_estrutura → trabalhos_na_barra → "
                                          "lista_de_corte / nova_folha. Confira com capturar_vista."})
    elif metodo == "ping":
        _resposta(ident, {})
    elif metodo == "tools/list":
        _resposta(ident, {"tools": _ferramentas()})
    elif metodo == "tools/call":
        _resposta(ident, _chamar(par.get("name"), par.get("arguments")))
    else:
        _resposta(ident, erro={"code": -32601, "message": "método não suportado: %s" % metodo})
    return True


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stdin.reconfigure(encoding="utf-8")
    except Exception:
        pass
    for linha in sys.stdin:
        linha = linha.strip()
        if not linha:
            continue
        try:
            msg = json.loads(linha)
        except ValueError:
            _resposta(None, erro={"code": -32700, "message": "JSON inválido"})
            continue
        try:
            tratar(msg)
        except Exception as exc:     # nunca derruba o servidor
            if msg.get("id") is not None:
                _resposta(msg.get("id"), erro={"code": -32603, "message": str(exc)})


if __name__ == "__main__":
    main()
