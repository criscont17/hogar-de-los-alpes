from dataclasses import dataclass

from app.aplicacion.dtos import RespuestaDePartner
from app.aplicacion.errores import TrabajoDePartnerNoEncontradoError
from app.aplicacion.puertos import CatalogoDeAdaptadores, TrabajosDePartnerRepository


@dataclass(frozen=True)
class ConsultarTrabajoDePartnerQuery:
    partner_id: str
    referencia_externa: str


class ConsultarTrabajoDePartnerHandler:
    """El partner pregunta con su propia referencia y recibe el estado en su formato."""

    def __init__(
        self, adaptadores: CatalogoDeAdaptadores, trabajos: TrabajosDePartnerRepository
    ) -> None:
        self._adaptadores = adaptadores
        self._trabajos = trabajos

    def ejecutar(self, query: ConsultarTrabajoDePartnerQuery) -> RespuestaDePartner:
        adaptador = self._adaptadores.obtener(query.partner_id)
        trabajo = self._trabajos.obtener(query.partner_id, query.referencia_externa)
        if trabajo is None:
            raise TrabajoDePartnerNoEncontradoError(
                "El partner no tiene un trabajo con esa referencia"
            )
        return adaptador.traducir_estado(trabajo)
