from dataclasses import dataclass


@dataclass(frozen=True)
class MensajeParaPartner:
    """Hecho ya traducido al formato del core del partner, listo para enviarse."""

    operacion: str
    contenido: str
    media_type: str
