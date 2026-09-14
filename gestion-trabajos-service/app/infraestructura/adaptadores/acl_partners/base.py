"""Piezas comunes a todos los adaptadores de partner."""

import json
from abc import abstractmethod
from collections.abc import Mapping
from decimal import Decimal, InvalidOperation
from typing import Any, ClassVar, TypeVar

from app.aplicacion.errores import SolicitudDePartnerInvalidaError
from app.aplicacion.puertos import AdaptadorDePartner
from app.seedwork.aplicacion import IntegrationEvent

from .mensaje import MensajeParaPartner
from .sincronizacion import SincronizadorDePartner

T = TypeVar("T")


class AdaptadorDePartnerBase(AdaptadorDePartner):
    """Base de los adaptadores concretos.

    Un partner nuevo declara su `PARTNER_ID` y traduce en tres direcciones: la
    solicitud que envía, el estado que consulta y los hechos que quiere recibir.
    El envío resiliente lo aporta el `SincronizadorDePartner` inyectado, así que
    ningún adaptador reimplementa reintentos ni circuit breaker.
    """

    PARTNER_ID: ClassVar[str]

    def __init__(self, sincronizador: SincronizadorDePartner) -> None:
        self._sincronizador = sincronizador

    @property
    def partner_id(self) -> str:
        return self.PARTNER_ID

    def notificar(self, evento: IntegrationEvent) -> None:
        mensaje = self.traducir_evento(evento)
        if mensaje is not None:
            self._sincronizador.encolar(mensaje)

    @abstractmethod
    def traducir_evento(self, evento: IntegrationEvent) -> MensajeParaPartner | None:
        """Mensaje en el formato del partner, o `None` si ese hecho no le interesa."""


def leer_json(contenido: str) -> dict[str, Any]:
    try:
        datos = json.loads(contenido)
    except json.JSONDecodeError as exc:
        raise SolicitudDePartnerInvalidaError(f"JSON inválido: {exc.msg}") from exc
    if not isinstance(datos, dict):
        raise SolicitudDePartnerInvalidaError("Se esperaba un objeto JSON")
    return datos


def campo(datos: Mapping[str, Any], nombre: str, tipo: type = str) -> Any:
    """Lee un campo obligatorio del partner validando su tipo."""

    valor = datos.get(nombre)
    if valor is None or (isinstance(valor, str) and not valor.strip()):
        raise SolicitudDePartnerInvalidaError(f"Falta el campo obligatorio '{nombre}'")
    if not isinstance(valor, tipo):
        raise SolicitudDePartnerInvalidaError(f"El campo '{nombre}' tiene un tipo inválido")
    return valor.strip() if isinstance(valor, str) else valor


def decimal(valor: Any, nombre: str) -> Decimal:
    try:
        numero = Decimal(str(valor).strip())
    except (InvalidOperation, ValueError) as exc:
        raise SolicitudDePartnerInvalidaError(f"'{nombre}' no es un número válido") from exc
    if not numero.is_finite():
        raise SolicitudDePartnerInvalidaError(f"'{nombre}' no es un número válido")
    return numero


def traducir_valor(tabla: Mapping[str, T], valor: str, descripcion: str) -> T:
    try:
        return tabla[valor]
    except KeyError:
        raise SolicitudDePartnerInvalidaError(
            f"{descripcion} sin equivalencia en HdA: {valor}"
        ) from None
