"""Circuit breaker genérico para llamadas a sistemas externos.

No sabe nada de partners ni de trabajos: envuelve cualquier invocación y deja de
intentarla mientras el destino se considera caído. Así una dependencia rota falla
rápido en lugar de consumir tiempo e hilos del resto del sistema.
"""

import threading
import time
from collections.abc import Callable
from enum import Enum
from typing import Any, TypeVar

T = TypeVar("T")


class EstadoCircuito(str, Enum):
    CERRADO = "Cerrado"
    ABIERTO = "Abierto"
    SEMI_ABIERTO = "SemiAbierto"


class CircuitoAbiertoError(Exception):
    """La llamada no se intentó porque el circuito está abierto."""


class CircuitBreaker:
    """Máquina de tres estados.

    - Cerrado: las llamadas pasan; `umbral_fallos` fallos consecutivos lo abren.
    - Abierto: las llamadas fallan de inmediato con `CircuitoAbiertoError`.
    - SemiAbierto: pasado `tiempo_recuperacion`, se permite una sola llamada de
      prueba. Si funciona, vuelve a Cerrado; si falla, vuelve a Abierto.

    Recibe el reloj por constructor para poder probar la recuperación sin esperas.
    """

    def __init__(
        self,
        nombre: str,
        *,
        umbral_fallos: int = 3,
        tiempo_recuperacion: float = 10.0,
        reloj: Callable[[], float] = time.monotonic,
    ) -> None:
        if umbral_fallos < 1:
            raise ValueError("umbral_fallos debe ser al menos 1")
        if tiempo_recuperacion <= 0:
            raise ValueError("tiempo_recuperacion debe ser positivo")
        self.nombre = nombre
        self._umbral_fallos = umbral_fallos
        self._tiempo_recuperacion = tiempo_recuperacion
        self._reloj = reloj
        self._lock = threading.Lock()
        self._estado = EstadoCircuito.CERRADO
        self._fallos_consecutivos = 0
        self._abierto_desde = 0.0
        self._prueba_en_curso = False

    @property
    def estado(self) -> EstadoCircuito:
        with self._lock:
            return self._estado_actual()

    @property
    def fallos_consecutivos(self) -> int:
        with self._lock:
            return self._fallos_consecutivos

    def segundos_para_reintento(self) -> float:
        """Cuánto falta para que un circuito abierto admita la llamada de prueba."""

        with self._lock:
            if self._estado_actual() is not EstadoCircuito.ABIERTO:
                return 0.0
            transcurrido = self._reloj() - self._abierto_desde
            return max(0.0, self._tiempo_recuperacion - transcurrido)

    def ejecutar(self, funcion: Callable[..., T], *args: Any, **kwargs: Any) -> T:
        with self._lock:
            estado = self._estado_actual()
            if estado is EstadoCircuito.ABIERTO or (
                estado is EstadoCircuito.SEMI_ABIERTO and self._prueba_en_curso
            ):
                raise CircuitoAbiertoError(f"Circuito '{self.nombre}' abierto")
            if estado is EstadoCircuito.SEMI_ABIERTO:
                self._prueba_en_curso = True
        try:
            resultado = funcion(*args, **kwargs)
        except Exception:
            self._registrar_fallo()
            raise
        self._registrar_exito()
        return resultado

    def _estado_actual(self) -> EstadoCircuito:
        if (
            self._estado is EstadoCircuito.ABIERTO
            and self._reloj() - self._abierto_desde >= self._tiempo_recuperacion
        ):
            self._estado = EstadoCircuito.SEMI_ABIERTO
        return self._estado

    def _registrar_fallo(self) -> None:
        with self._lock:
            self._prueba_en_curso = False
            self._fallos_consecutivos += 1
            if (
                self._estado is EstadoCircuito.SEMI_ABIERTO
                or self._fallos_consecutivos >= self._umbral_fallos
            ):
                self._estado = EstadoCircuito.ABIERTO
                self._abierto_desde = self._reloj()

    def _registrar_exito(self) -> None:
        with self._lock:
            self._prueba_en_curso = False
            self._fallos_consecutivos = 0
            self._estado = EstadoCircuito.CERRADO
