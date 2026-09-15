"""Piezas comunes a todos los adaptadores de PSP."""

from typing import ClassVar

from app.aplicacion.puertos import AdaptadorDePSP, ResultadoPSP
from app.seedwork.infraestructura import CircuitBreaker

from .cliente_simulado import ClientePSPSimulado


class AdaptadorDePSPBase(AdaptadorDePSP):
    """Base de los adaptadores concretos.

    Un PSP nuevo declara su `PSP_ID` y `MONEDA`, y traduce el resultado crudo
    del cliente al contrato canónico `ResultadoPSP`. El circuit breaker es
    propio de cada instancia: la caída de un PSP nunca abre el circuito de
    otro, aunque ambos sirvan la misma moneda.
    """

    PSP_ID: ClassVar[str]
    MONEDA: ClassVar[str]

    def __init__(self, cliente: ClientePSPSimulado, breaker: CircuitBreaker) -> None:
        self._cliente = cliente
        self._breaker = breaker

    @property
    def psp_id(self) -> str:
        return self.PSP_ID

    @property
    def moneda(self) -> str:
        return self.MONEDA

    def cobrar(self, monto, moneda: str, referencia: str) -> ResultadoPSP:
        # El circuit breaker envuelve la llamada, no la decisión de negocio: un
        # rechazo (`aprobado=False`) es una respuesta válida del PSP y no cuenta
        # como fallo del circuito; solo `ConnectionError`/`TimeoutError` lo abren.
        respuesta = self._breaker.ejecutar(self._cliente.cobrar, monto, moneda, referencia)
        return self._traducir(respuesta)

    def _traducir(self, respuesta: dict) -> ResultadoPSP:
        if respuesta["aprobado"]:
            return ResultadoPSP(exitoso=True, referencia_psp=f"{self.PSP_ID}:{respuesta['referencia']}")
        return ResultadoPSP(
            exitoso=False, referencia_psp=None, motivo=f"{self.PSP_ID} rechazó la operación"
        )
