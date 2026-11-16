# SPDX-License-Identifier: LGPL-2.1-or-later
#
# Usinix: módulo de interface embutido no programa (faixa de ferramentas, tradução pt-BR,
# tela inicial, assistentes, tema e ícones) e identidade do aplicativo (branding.xml).

file(GLOB Usinix_SRCS RELATIVE "${CMAKE_CURRENT_SOURCE_DIR}" CONFIGURE_DEPENDS "*.py")
list(APPEND Usinix_SRCS package.xml LICENSE LEIA-ME.md)
SOURCE_GROUP("" FILES ${Usinix_SRCS})

set(Usinix_DIRS
    Resources
    translations
)

ADD_CUSTOM_TARGET(Usinix ALL
    SOURCES ${Usinix_SRCS}
)

# Árvore de compilação: o programa roda direto da pasta build, como os outros módulos
fc_copy_sources(Usinix "${CMAKE_BINARY_DIR}/Mod/Usinix" ${Usinix_SRCS})
FILE(COPY ${Usinix_DIRS} DESTINATION "${CMAKE_BINARY_DIR}/Mod/Usinix")
FILE(COPY extras/branding.xml DESTINATION "${CMAKE_BINARY_DIR}/bin")

INSTALL(
    FILES
        ${Usinix_SRCS}
    DESTINATION
        Mod/Usinix
)

INSTALL(
    DIRECTORY
        ${Usinix_DIRS}
    DESTINATION
        Mod/Usinix
    PATTERN "__pycache__" EXCLUDE
)

# Tema de ícones do Usinix descompactado na instalação: o branding.xml aponta para ele (ProgramIcons)
# e o FreeCAD já usa esses ícones na primeira abertura, sem precisar aplicar e reiniciar.
file(ARCHIVE_EXTRACT
    INPUT "${CMAKE_CURRENT_SOURCE_DIR}/Resources/tema-icones-usinix.zip"
    DESTINATION "${CMAKE_BINARY_DIR}/Mod/Usinix/Resources/icones-tema"
)
INSTALL(
    DIRECTORY
        "${CMAKE_BINARY_DIR}/Mod/Usinix/Resources/icones-tema"
    DESTINATION
        Mod/Usinix/Resources
)

# Nome "Usinix", tela de abertura e pasta de dados do usuário própria (%APPDATA%\Usinix,
# ~/.local/share/Usinix). O FreeCAD procura o branding.xml na pasta bin do programa.
INSTALL(
    FILES
        extras/branding.xml
    DESTINATION
        ${CMAKE_INSTALL_BINDIR}
)
