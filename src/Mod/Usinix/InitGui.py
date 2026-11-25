# SPDX-License-Identifier: LGPL-2.1-or-later
# Usinix - carregado pelo FreeCAD ao iniciar a interface.

import FreeCAD
import FreeCADGui

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
    UsinixComplemento.executar(_usinix_os.path.join(_usinix_outro, "InitGui.py"), dict(globals()))
else:
    _usinix_erro = None
    try:
        import UsinixGui

        UsinixGui.startup()
    except Exception as exc:  # nunca impedir o FreeCAD de abrir
        _usinix_erro = exc
    _usinix_usuario = False
    try:
        _usinix_usuario = UsinixComplemento.estado()["usuario"]
    except Exception:
        pass
    if _usinix_erro is not None and _usinix_usuario:
        # a cópia atualizada falhou: abre com o complemento do programa (e não tenta mais com ela)
        import os as _usinix_os
        UsinixComplemento.executar(_usinix_os.path.join(UsinixComplemento.falhou(_usinix_erro), "InitGui.py"),
                                  dict(globals()))
    else:
        if _usinix_erro is not None:
            FreeCAD.Console.PrintError("Usinix: falha ao carregar o branding: {}\n".format(_usinix_erro))

        class UsinixWorkbench(Workbench):  # noqa: F821  (Workbench é injetado pelo FreeCAD)
            MenuText = "Usinix"
            ToolTip = "Ferramentas do Usinix"

            def __init__(self):
                import UsinixGui

                self.__class__.Icon = UsinixGui.ICON_PATH

            def Initialize(self):
                import UsinixGui

                self.appendToolbar("Usinix", UsinixGui.COMMANDS)
                self.appendMenu("Usinix", UsinixGui.COMMANDS + ["Separator"] + UsinixGui.MENU_EXTRA)

            def Activated(self):
                pass

            def Deactivated(self):
                pass

            def GetClassName(self):
                return "Gui::PythonWorkbench"

        FreeCADGui.addWorkbench(UsinixWorkbench())
        if _usinix_usuario:
            UsinixComplemento.abriu_bem()
        # cópia do complemento igual ou anterior ao programa instalado: não serve mais (ver UsinixCopiaVelha)
        try:
            import UsinixCopiaVelha
            UsinixCopiaVelha.apagar_depois()
        except Exception as _usinix_exc2:
            FreeCAD.Console.PrintLog("Usinix: cópia antiga do complemento: {}\n".format(_usinix_exc2))
