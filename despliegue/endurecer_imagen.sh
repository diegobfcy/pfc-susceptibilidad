#!/bin/sh
# Endurecimiento de las imágenes app y worker (DEF-20): elimina paquetes base de Debian 13 que la
# aplicación no usa en ejecución y que tienen CVE altas sin corrección publicada (Trivy, 10/11/2026).
#   util-linux (todos sus paquetes binarios), acl, ncurses, sqlite, systemd/udev y perl.
# libexpat1 de Debian también se quita si está: el worker usa libexpat 2.10.0 compilada (Dockerfile.worker).
# También se borran módulos de la biblioteca estándar que el sistema no usa: los que enlazaban esas
# bibliotecas (_curses, _sqlite3, _uuid y readline; uuid funciona sin _uuid) y pyexpat con
# _elementtree, porque CPython 3.11.18 trae dentro su propia copia de expat 2.9.0, con las mismas
# CVE, que Trivy no detecta. Ningún componente parsea XML. Se ejecuta como root, al final.
set -eu
PAQUETES="util-linux mount login bsdutils libblkid1 libmount1 libsmartcols1 libuuid1 liblastlog2-2 libacl1 libncursesw6 libtinfo6 ncurses-base ncurses-bin
libsqlite3-0 libsystemd0 libudev1 perl-base libexpat1"
instalados=""
for p in $PAQUETES; do
  dpkg-query -W -f='${Status}' "$p" 2>/dev/null | grep -q 'ok installed' && instalados="$instalados $p"
done
# shellcheck disable=SC2086
[ -n "$instalados" ] && dpkg --purge --force-remove-essential --force-remove-protected --force-depends $instalados
DIN=/usr/local/lib/python3.11/lib-dynload
rm -f "$DIN"/_curses*.so "$DIN"/_sqlite3*.so "$DIN"/readline*.so "$DIN"/_uuid*.so \
  "$DIN"/pyexpat*.so "$DIN"/_elementtree*.so
rm -rf /usr/local/lib/python3.11/curses /usr/local/lib/python3.11/sqlite3 /var/lib/apt/lists/* \
  /var/cache/apt/* /var/cache/debconf/*
