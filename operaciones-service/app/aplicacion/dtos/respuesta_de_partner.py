from dataclasses import dataclass


@dataclass(frozen=True)
class RespuestaDePartner:
    """Contenido ya expresado en el formato del partner (JSON propio, SOAP, texto...)."""

    contenido: str
    media_type: str


@dataclass(frozen=True)
class ResultadoDeSolicitudDTO:
    nueva: bool
    respuesta: RespuestaDePartner
