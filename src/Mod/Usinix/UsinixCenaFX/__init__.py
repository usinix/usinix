# SPDX-License-Identifier: LGPL-2.1-or-later
"""Efeitos da vista 3D do Usinix: sombra no chão, realce de cantos (oclusão ambiente) e texturas.

O motor vem do ShowRoom, de OficineRobotica (https://github.com/oficinerobotica/ShowRoom), LGPL-2.1-or-later,
que por sua vez nasceu do Display Tools (MIT; aviso em LICENSES/MIT-DisplayTools.txt). Os módulos
ambient_occlusion, shadow_catcher, shadows, navigation, view_rig, textures e view_utils são os do ShowRoom
1.0.1, com as importações ajustadas para este pacote, as mensagens em português e a configuração lida de
config.py (um objeto simples do documento, sem classe Python, para o arquivo abrir em qualquer FreeCAD).
As luzes, os conjuntos de luz, a grade e os painéis do ShowRoom não vieram.
"""
