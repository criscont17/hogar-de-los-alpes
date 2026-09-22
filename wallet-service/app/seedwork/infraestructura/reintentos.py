"""Reintentos con espera exponencial para operaciones que pueden recuperarse solas."""

from collections.abc import Callable
from dataclasses import dataclass, field
from time import sleep
from typing import TypeVar

T = TypeVar("T")


def _siempre_recuperable(_: BaseException) -> bool:
    return True


@dataclass(frozen=True)
class PoliticaDeReintentos:
    """Cuántas veces se reintenta una operación y cuánto se espera entre intentos.

    La espera crece por `factor` en cada intento (backoff exponencial) para no
    golpear en ráfaga un recurso que todavía se está recuperando. `dormir` se
    inyecta para que las pruebas no gasten tiempo real.
    """

    intentos: int = 3
    espera_inicial: float = 0.5
    factor: float = 2.0
    dormir: Callable[[float], None] = field(default=sleep, repr=False)

    def ejecutar(
        self,
        operacion: Callable[[int], T],
        es_recuperable: Callable[[BaseException], bool] = _siempre_recuperable,
        al_fallar_intento: Callable[[int, BaseException, float], None] | None = None,
    ) -> T:
        """Ejecuta `operacion(numero_de_intento)` reintentando los fallos recuperables.

        Un fallo que `es_recuperable` descarta sale de inmediato: reintentar algo que
        no depende del tiempo solo retrasa la respuesta. Si se agotan los intentos se
        propaga el último error, que es el que describe por qué se abandona.
        """

        if self.intentos < 1:
            raise ValueError("La política de reintentos requiere al menos un intento")

        espera = self.espera_inicial
        for intento in range(1, self.intentos + 1):
            try:
                return operacion(intento)
            except Exception as exc:
                if intento >= self.intentos or not es_recuperable(exc):
                    raise
                if al_fallar_intento is not None:
                    al_fallar_intento(intento, exc, espera)
                self.dormir(espera)
                espera *= self.factor
        raise AssertionError("inalcanzable: el bucle siempre retorna o propaga")
