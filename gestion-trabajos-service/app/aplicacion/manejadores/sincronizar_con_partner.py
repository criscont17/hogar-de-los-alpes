import logging

from app.aplicacion.errores import PartnerNoRegistradoError
from app.aplicacion.puertos import CatalogoDePartners
from app.dominio.trabajo.eventos import EventoDeTrabajo
from app.seedwork.aplicacion import DomainEventHandler
from app.seedwork.dominio import DomainEvent

from .traductores import TRADUCTORES, Traductor

logger = logging.getLogger("trabajos.partners")


class SincronizarConPartnerHandler(DomainEventHandler[DomainEvent]):
    """Lleva al core de cada partner los hechos de los trabajos que él originó.

    Trabaja sobre el contrato público (eventos de integración), no sobre eventos de
    dominio: la capa anti-corrupción de un partner ve lo mismo que vería cualquier
    otro bounded context. Cada adaptador decide qué versiones y qué hechos le
    interesan, y su `notificar` no bloquea: una caída del partner no detiene el
    flujo interno. Los trabajos de Marketplace se ignoran.
    """

    def __init__(
        self,
        catalogo: CatalogoDePartners,
        traductores: dict[type[DomainEvent], tuple[Traductor, ...]] | None = None,
    ) -> None:
        self._catalogo = catalogo
        self._traductores = TRADUCTORES if traductores is None else traductores

    def manejar(self, evento: DomainEvent) -> None:
        if not isinstance(evento, EventoDeTrabajo) or evento.partner_id is None:
            return
        traductores = self._traductores.get(type(evento), ())
        if not traductores:
            return
        try:
            adaptador = self._catalogo.obtener(evento.partner_id)
        except PartnerNoRegistradoError:
            logger.warning(
                "trabajo de un partner que ya no está registrado: partner=%s trabajo=%s",
                evento.partner_id,
                evento.trabajo_id,
            )
            return
        for traducir in traductores:
            adaptador.notificar(traducir(evento))
