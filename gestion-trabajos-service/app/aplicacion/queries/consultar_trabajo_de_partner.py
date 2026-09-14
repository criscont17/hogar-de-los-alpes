from dataclasses import dataclass

from app.aplicacion.dtos import RespuestaDePartner
from app.aplicacion.mapeo import trabajo_a_dto
from app.aplicacion.puertos import CatalogoDePartners
from app.dominio.errores import TrabajoNoEncontradoError
from app.dominio.trabajo.trabajo_repository import TrabajoRepository


@dataclass(frozen=True)
class ConsultarTrabajoDePartnerQuery:
    partner_id: str
    referencia_externa: str


class ConsultarTrabajoDePartnerHandler:
    """El partner pregunta con su propia referencia y recibe el estado en su formato."""

    def __init__(self, repo: TrabajoRepository, catalogo: CatalogoDePartners) -> None:
        self._repo = repo
        self._catalogo = catalogo

    def ejecutar(self, query: ConsultarTrabajoDePartnerQuery) -> RespuestaDePartner:
        adaptador = self._catalogo.obtener(query.partner_id)
        trabajo = self._repo.obtener_por_referencia_de_partner(
            adaptador.partner_id, query.referencia_externa
        )
        if trabajo is None:
            raise TrabajoNoEncontradoError("El partner no tiene un trabajo con esa referencia")
        return adaptador.traducir_estado(trabajo_a_dto(trabajo))
