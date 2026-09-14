from dataclasses import dataclass

from app.aplicacion.dtos import ResultadoDePartnerDTO, TrabajoDTO
from app.aplicacion.mapeo import trabajo_a_dto
from app.aplicacion.puertos import AdaptadorDePartner, CatalogoDePartners
from app.dominio.errores import TrabajoDuplicadoError
from app.dominio.trabajo import CanalDeOrigen
from app.dominio.trabajo.trabajo_repository import TrabajoRepository

from .crear_trabajo import CrearTrabajoCommand, CrearTrabajoHandler


@dataclass(frozen=True)
class CrearTrabajoDesdePartnerCommand:
    partner_id: str
    contenido: str


class CrearTrabajoDesdePartnerHandler:
    """Crea un trabajo a partir de la solicitud de cualquier partner B2B2C.

    Depende del puerto `AdaptadorDePartner`, no de la API de un partner concreto:
    el adaptador traduce y resuelve las reglas, y la creación es la misma que usa
    Marketplace. Por eso incorporar un partner no toca este caso de uso.
    """

    def __init__(
        self,
        repo: TrabajoRepository,
        catalogo: CatalogoDePartners,
        crear: CrearTrabajoHandler,
    ) -> None:
        self._repo = repo
        self._catalogo = catalogo
        self._crear = crear

    def ejecutar(self, comando: CrearTrabajoDesdePartnerCommand) -> ResultadoDePartnerDTO:
        adaptador = self._catalogo.obtener(comando.partner_id)
        solicitud = adaptador.traducir_solicitud(comando.contenido)

        # Un partner reintenta cuando no recibe respuesta: la misma referencia no
        # debe producir un segundo trabajo.
        existente = self._repo.obtener_por_referencia_de_partner(
            adaptador.partner_id, solicitud.referencia_externa
        )
        if existente is not None:
            return self._resultado(adaptador, trabajo_a_dto(existente), creado=False)

        try:
            dto = self._crear.ejecutar(
                CrearTrabajoCommand(
                    descripcion=solicitud.descripcion,
                    urgencia=solicitud.urgencia,
                    pais=solicitud.pais,
                    ciudad=solicitud.ciudad,
                    direccion=solicitud.direccion,
                    sub_trabajos=solicitud.sub_trabajos,
                    moneda=solicitud.moneda,
                    canal=CanalDeOrigen.PARTNER.value,
                    partner_id=adaptador.partner_id,
                    referencia_externa=solicitud.referencia_externa,
                    condiciones=solicitud.condiciones,
                )
            )
        except TrabajoDuplicadoError:
            # Dos reintentos simultáneos: otro ganó la carrera y se responde con su trabajo.
            existente = self._repo.obtener_por_referencia_de_partner(
                adaptador.partner_id, solicitud.referencia_externa
            )
            if existente is None:
                raise
            return self._resultado(adaptador, trabajo_a_dto(existente), creado=False)
        return self._resultado(adaptador, dto, creado=True)

    @staticmethod
    def _resultado(
        adaptador: AdaptadorDePartner, trabajo: TrabajoDTO, creado: bool
    ) -> ResultadoDePartnerDTO:
        return ResultadoDePartnerDTO(
            trabajo_id=trabajo.id,
            creado=creado,
            respuesta=adaptador.traducir_estado(trabajo),
        )
