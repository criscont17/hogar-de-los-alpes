from dataclasses import dataclass

from .evento_de_trabajo import EventoDeTrabajo, Liquidacion


@dataclass(frozen=True, kw_only=True)
class TrabajoEnDisputa(EventoDeTrabajo):
    """El trabajo se ejecutó pero su liquidación no pudo completarse.

    Lleva lo que quedó pendiente de pagar y el estado desde el que se abrió la
    disputa, porque es lo que Operaciones necesita para resolverla a mano: el
    trabajo físico ya ocurrió y por eso no se revierte.
    """

    motivo: str
    estado_anterior: str
    liquidaciones_pendientes: tuple[Liquidacion, ...]
    moneda: str
