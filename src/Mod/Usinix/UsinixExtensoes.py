# SPDX-License-Identifier: LGPL-2.1-or-later
# Usinix - ponto de encaixe para pacotes que acrescentam ferramentas.
"""Pacotes externos (uma pasta em <dados do usuário>/Mod com o próprio InitGui.py) se registram aqui:

    import UsinixExtensoes as X
    X.registrar("Meu pacote", "1.0.0", iniciar=minha_funcao, minimo="1.19.2")

`iniciar` roda uma vez, depois que os comandos do Usinix foram registrados e antes de a faixa ser montada; é o
lugar de registrar comandos, tipos de escada (UsinixEscada.registrar_tipo), ferramentas da IA (UsinixIA.ferramenta),
o perfil de marca dos relatórios (UsinixMarca.definir) e os botões da faixa (adicionar_painel, adicionar_aba,
substituir_item). Um erro num pacote é avisado no console e não impede o Usinix de abrir.
"""

import FreeCAD

EXTENSOES = []
_ESTADO = {"iniciado": False}


def _versao_tupla(v):
    res = []
    for p in str(v or "0").split("-")[0].split("."):
        try:
            res.append(int(p))
        except ValueError:
            res.append(0)
    return tuple(res + [0] * (3 - len(res)))


def versao_usinix():
    try:
        import UsinixVersao
        return UsinixVersao.VERSAO
    except Exception:
        return "0"


def registrar(nome, versao, iniciar=None, minimo=None):
    """Registra um pacote. Devolve o registro (dict) ou None se o Usinix for mais antigo que `minimo`."""
    for e in EXTENSOES:
        if e["nome"] == nome:
            return e                     # carregado duas vezes (ex.: duas pastas): vale o primeiro
    reg = {"nome": nome, "versao": str(versao), "iniciar": iniciar, "minimo": minimo, "ativo": False, "erro": None}
    if minimo and _versao_tupla(versao_usinix()) < _versao_tupla(minimo):
        reg["erro"] = "precisa do Usinix %s ou mais novo (este é o %s)" % (minimo, versao_usinix())
        FreeCAD.Console.PrintWarning("Usinix: %s %s %s\n" % (nome, versao, reg["erro"]))
        EXTENSOES.append(reg)
        return None
    EXTENSOES.append(reg)
    if _ESTADO["iniciado"]:
        _rodar(reg)
    return reg


def _rodar(reg):
    if reg["ativo"] or reg["erro"]:
        return
    try:
        if reg["iniciar"] is not None:
            reg["iniciar"]()
        reg["ativo"] = True
    except Exception as exc:
        reg["erro"] = str(exc)
        FreeCAD.Console.PrintWarning("Usinix: o pacote %s não carregou: %s\n" % (reg["nome"], exc))


def iniciar_todas():
    """Chamado pelo Usinix depois de registrar os próprios comandos (UsinixGui.startup)."""
    _ESTADO["iniciado"] = True
    for reg in list(EXTENSOES):
        _rodar(reg)


def ativas():
    """[(nome, versão)] dos pacotes carregados."""
    return [(e["nome"], e["versao"]) for e in EXTENSOES if e["ativo"]]


def ativo(nome):
    return any(e["nome"] == nome and e["ativo"] for e in EXTENSOES)


# ---------------------------------------------------------------- faixa (botões)
def _abas():
    import UsinixRibbon
    return UsinixRibbon.TABS


def _aba(aba_id):
    for t in _abas():
        if t.get("id") == aba_id:
            return t
    return None


def adicionar_aba(aba, depois=None):
    """aba: {"id", "label", "wb": None, "panels": [...]} no mesmo formato de UsinixRibbon.TABS."""
    abas = _abas()
    if _aba(aba.get("id")) is not None:
        return
    pos = len(abas)
    if depois is not None:
        for i, t in enumerate(abas):
            if t.get("id") == depois:
                pos = i + 1
                break
    abas.insert(pos, aba)


def adicionar_painel(aba_id, painel, depois=None):
    """painel: (título, [itens]) no formato da faixa; entra depois do painel de título `depois` (ou no fim)."""
    t = _aba(aba_id)
    if t is None:
        raise ValueError("aba %s não existe" % aba_id)
    paineis = t.setdefault("panels", [])
    if any(p[0] == painel[0] for p in paineis):
        return
    pos = len(paineis)
    if depois is not None:
        for i, p in enumerate(paineis):
            if p[0] == depois:
                pos = i + 1
                break
    paineis.insert(pos, painel)


def substituir_item(comando, novo_comando, novo_rotulo=None):
    """Troca o comando de um botão da faixa (ex.: "Usinix_Escada" vira "Usinix_Escada|Outro_Comando",
    um botão com setinha). Devolve quantos botões mudaram."""
    n = 0
    for t in _abas():
        for p in t.get("panels", []):
            itens = p[1]
            for i, it in enumerate(itens):
                if isinstance(it, (tuple, list)) and it and it[0] == comando:
                    novo = list(it)
                    novo[0] = novo_comando
                    if novo_rotulo is not None and len(novo) > 2:
                        novo[2] = novo_rotulo
                    itens[i] = tuple(novo)
                    n += 1
    return n
