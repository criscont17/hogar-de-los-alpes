from dataclasses import dataclass

from app.aplicacion.dtos import EventoDeTrabajoRecibido
from app.aplicacion.proyeccion import proyectar
from app.aplicacion.puertos import CatalogoDeAdaptadores, TrabajosDePartnerRepository


@dataclass(frozen=True)
class ProcesarEventoDeTrabajoCommand:
    evento: EventoDeTrabajoRecibido


class ProcesarEventoDeTrabajoHandler:
    """Reacciona a un hecho de GestionDeTrabajosBC sobre un trabajo de partner.

    Actualiza la vista que el partner consulta y le entrega la novedad en su formato. La
    entrega es asíncrona: si el core del partner falla, este caso de uso no se entera.
    Los trabajos de Marketplace no llevan `partner_id` y se ignoran.
    """

    def __init__(
        self, trabajos: TrabajosDePartnerRepository, adaptadores: CatalogoDeAdaptadores
    ) -> None:
        self._trabajos = trabajos
        self._adaptadores = adaptadores

    def ejecutar(self, comando: ProcesarEventoDeTrabajoCommand) -> None:
        evento = comando.evento
        partner_id, referencia = evento.partner_id, evento.referencia_externa
        if not partner_id or not referencia:
            return

        actual = self._trabajos.obtener(partner_id, referencia)
        vista = proyectar(actual, evento.nombre, evento.datos)
        if vista is not None and vista != actual:
            self._trabajos.guardar(vista)

        if self._adaptadores.tiene(partner_id):
            self._adaptadores.obtener(partner_id).notificar(evento)
