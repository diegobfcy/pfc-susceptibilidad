"""Pico de memoria residente por trabajo (RNF-01, DEF-13).

``ru_maxrss`` guarda el pico de toda la vida del proceso: en un worker que atiende varios
trabajos, un trabajo liviano heredaba el pico de uno anterior. En Linux el pico (VmHWM) se
reinicia escribiendo ``5`` en /proc/self/clear_refs, así que cada trabajo mide el suyo.
"""

from __future__ import annotations

import resource
from pathlib import Path

_ESTADO = Path("/proc/self/status")
_REINICIO = Path("/proc/self/clear_refs")


def reiniciar_pico() -> bool:
    """Lleva el pico de memoria residente al uso actual. False si el sistema no lo permite."""
    try:
        _REINICIO.write_text("5")
    except OSError:
        return False
    return True


def pico_gb() -> float:
    """Pico de memoria residente desde el último reinicio, en GB.

    Sin /proc (otro sistema operativo) devuelve el pico de toda la vida del proceso.
    """
    try:
        for linea in _ESTADO.read_text().splitlines():
            if linea.startswith("VmHWM:"):
                return int(linea.split()[1]) / 1024**2
    except OSError:
        pass
    return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024**2
