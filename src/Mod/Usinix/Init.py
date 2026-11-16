# SPDX-License-Identifier: LGPL-2.1-or-later
# Usinix - carregado antes da janela principal ser montada.

import FreeCAD

# Nome antigo (Prumo, até a 1.20.0): módulos de arquivos antigos, preferências, atalhos e o complemento antigo
# na pasta do usuário (ver UsinixNomeAntigo). Antes de tudo.
try:
    import UsinixNomeAntigo
    UsinixNomeAntigo.ao_iniciar()
except Exception as _usinix_exc0:
    FreeCAD.Console.PrintWarning("Usinix: nome antigo: {}\n".format(_usinix_exc0))

# Complemento atualizado (sem o pacote inteiro): a cópia em <dados do usuário>/Mod/Usinix passa a vez ao
# complemento do programa quando ela ficou para trás ou falhou (ver UsinixComplemento).
_usinix_outro = None
try:
    import inspect as _usinix_inspect
    import UsinixComplemento
    _usinix_outro = UsinixComplemento.ativar(_usinix_inspect.currentframe().f_code.co_filename)
except Exception as _usinix_exc:
    FreeCAD.Console.PrintWarning("Usinix: complemento atualizado: {}\n".format(_usinix_exc))

if _usinix_outro:
    import os as _usinix_os
    UsinixComplemento.executar(_usinix_os.path.join(_usinix_outro, "Init.py"), dict(globals()))
else:
    def _painel_lateral_unico():
        """Árvore e Propriedades como painéis separados (viram abas do painel lateral Usinix).

        Precisa rodar antes da janela principal: é ao montá-la que o FreeCAD lê quais painéis criar.
        A preferência "PainelLateralUnico" desligada devolve o painel "Modelo" do FreeCAD.
        """
        usinix = FreeCAD.ParamGet("User parameter:BaseApp/Preferences/Mod/Usinix")
        dock = FreeCAD.ParamGet("User parameter:BaseApp/Preferences/DockWindows")
        unico = usinix.GetBool("PainelLateralUnico", True)
        usinix.SetBool("PainelLateralUnico", unico)
        if unico:
            dock.GetGroup("TreeView").SetBool("Enabled", True)
            dock.GetGroup("PropertyView").SetBool("Enabled", True)
            dock.GetGroup("ComboView").SetBool("Enabled", False)
            usinix.SetBool("PainelLateralUnicoAplicado", True)
        elif usinix.GetBool("PainelLateralUnicoAplicado", False):
            # o usuário voltou ao painel do FreeCAD: desfaz o que a Usinix mudou
            dock.GetGroup("TreeView").SetBool("Enabled", False)
            dock.GetGroup("PropertyView").SetBool("Enabled", False)
            dock.GetGroup("ComboView").SetBool("Enabled", True)
            usinix.SetBool("PainelLateralUnicoAplicado", False)


    try:
        _painel_lateral_unico()
    except Exception as exc:  # nunca impedir o FreeCAD de abrir
        FreeCAD.Console.PrintWarning("Usinix: painel lateral: {}\n".format(exc))
