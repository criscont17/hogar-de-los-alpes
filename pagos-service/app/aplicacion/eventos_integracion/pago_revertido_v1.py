from dataclasses import dataclass

from .evento_de_integracion_de_pago import EventoDeIntegracionDePago


@dataclass(frozen=True, kw_only=True)
class PagoRevertidoV1(EventoDeIntegracionDePago):
    monto: str
    moneda: str
    psp: str
    motivo: str
