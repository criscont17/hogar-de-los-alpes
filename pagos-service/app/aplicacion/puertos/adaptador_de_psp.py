from abc import ABC, abstractmethod
from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class ResultadoPSP:
    """Respuesta ya normalizada del PSP, sin importar su formato nativo.

    Es exactamente la capa anti-corrupción del escenario de Interoperabilidad #7:
    ningún adaptador concreto expone al dominio el esquema propio de PayU, Wompi
    o MercadoPago. `exitoso=False` es un rechazo de negocio (fondos, fraude);
    un timeout o una caída del PSP se señalizan lanzando una excepción, nunca
    con `exitoso=False`, porque el llamador debe tratarlos distinto (conciliación
    diferida en vez de rechazo definitivo).
    """

    exitoso: bool
    referencia_psp: str | None
    motivo: str | None = None


class AdaptadorDePSP(ABC):
    """Puerto de la capa anti-corrupción hacia una pasarela de pago externa.

    Un PSP nuevo (por ejemplo, para una moneda de un país que aún no opera) es
    una implementación adicional de este puerto: el agregado `Pago` y el caso
    de uso `CrearPagoHandler` no cambian (medida del escenario #7).
    """

    @property
    @abstractmethod
    def psp_id(self) -> str:
        """Identificador estable del PSP, p. ej. `wompi-colombia`."""

    @property
    @abstractmethod
    def moneda(self) -> str:
        """Moneda ISO que este PSP procesa por defecto."""

    @abstractmethod
    def cobrar(self, monto: Decimal, moneda: str, referencia: str) -> ResultadoPSP:
        """Intenta el cobro/pago. Lanza `CircuitoAbiertoError` si el circuito de
        este PSP está abierto, o `TimeoutError` si el PSP no respondió a tiempo."""
