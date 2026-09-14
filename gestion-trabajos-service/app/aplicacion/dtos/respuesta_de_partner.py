from dataclasses import dataclass


@dataclass(frozen=True)
class RespuestaDePartner:
    """Contenido ya expresado en el formato del partner (JSON propio, SOAP...)."""

    contenido: str
    media_type: str


@dataclass(frozen=True)
class ResultadoDePartnerDTO:
    trabajo_id: str
    creado: bool
    respuesta: RespuestaDePartner
