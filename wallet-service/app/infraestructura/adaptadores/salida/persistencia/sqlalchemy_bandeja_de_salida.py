"""Lado de lectura y despacho de la bandeja de salida.

Lo usa el relay para tomar lo pendiente y anotar el resultado de cada entrega, y
las rutas de observabilidad para mostrar el estado de la bandeja. Escribir en ella
es responsabilidad del caso de uso, no de aquí: ver
`SqlAlchemyRepositorioEventosSalientes`.
"""

from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.seedwork.aplicacion import SobreDeEvento

from .modelos_orm import EventoSalienteModel
from .sqlalchemy_repositorio_eventos_salientes import (
    ESTADO_FALLIDO,
    ESTADO_PENDIENTE,
    ESTADO_PUBLICADO,
)


def sobre_de(modelo: EventoSalienteModel) -> SobreDeEvento:
    """Reconstruye el sobre tal como se guardó, sin rehidratar la clase original.

    El relay publica lo que la base tiene, no lo que el código sabría construir
    hoy: un evento encolado antes de un despliegue debe salir con el contrato con
    el que se guardó, aunque entretanto la clase haya cambiado.
    """

    return SobreDeEvento(
        tipo=modelo.tipo,
        event_id=modelo.event_id,
        clave_particion=modelo.clave_particion,
        payload=modelo.payload,
    )


class SqlAlchemyBandejaDeSalida:
    """Opera sobre la sesión que le entreguen; no abre ni confirma transacciones."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def tomar_pendientes(self, limite: int) -> list[EventoSalienteModel]:
        """Reserva el siguiente lote por publicar, en orden de creación.

        En PostgreSQL toma un bloqueo de fila con `SKIP LOCKED`, de modo que dos
        réplicas del servicio puedan correr su relay a la vez sin publicar el
        mismo evento dos veces: cada una se lleva filas distintas. SQLite no
        soporta la cláusula y tampoco la necesita (una sola conexión escribe).
        """

        consulta = (
            select(EventoSalienteModel)
            .where(
                EventoSalienteModel.estado == ESTADO_PENDIENTE,
                EventoSalienteModel.disponible_desde <= datetime.now(timezone.utc),
            )
            .order_by(EventoSalienteModel.fecha_creacion, EventoSalienteModel.id)
            .limit(limite)
        )
        if self._session.bind is not None and self._session.bind.dialect.name == "postgresql":
            consulta = consulta.with_for_update(skip_locked=True)
        return list(self._session.scalars(consulta))

    def marcar_publicado(self, modelo: EventoSalienteModel) -> None:
        modelo.estado = ESTADO_PUBLICADO
        modelo.fecha_publicacion = datetime.now(timezone.utc)
        modelo.error = None

    def marcar_fallido(
        self,
        modelo: EventoSalienteModel,
        error: str,
        max_intentos: int,
        espera_base_segundos: float,
    ) -> None:
        """Anota el fallo y decide si el evento vuelve a la cola o se abandona.

        Mientras queden intentos el evento sigue `PENDIENTE` con una espera que
        crece de forma exponencial: si el broker está caído, no tiene sentido
        golpearlo cada ciclo. Agotados los intentos pasa a `FALLIDO`, que es un
        estado terminal *para el relay* pero no para el operador: la fila queda
        con su payload intacto y se puede reencolar a mano.
        """

        modelo.intentos += 1
        modelo.error = error[:1000]
        if modelo.intentos >= max_intentos:
            modelo.estado = ESTADO_FALLIDO
            return
        espera = espera_base_segundos * (2 ** (modelo.intentos - 1))
        modelo.estado = ESTADO_PENDIENTE
        modelo.disponible_desde = datetime.now(timezone.utc) + timedelta(seconds=espera)

    def resumen(self) -> dict[str, int]:
        filas = self._session.execute(
            select(EventoSalienteModel.estado, func.count())
            .group_by(EventoSalienteModel.estado)
        ).all()
        conteos = {ESTADO_PENDIENTE: 0, ESTADO_PUBLICADO: 0, ESTADO_FALLIDO: 0}
        conteos.update({estado: total for estado, total in filas})
        return conteos

    def listar(
        self, estado: str | None = None, limite: int = 50
    ) -> list[EventoSalienteModel]:
        consulta = select(EventoSalienteModel)
        if estado:
            consulta = consulta.where(EventoSalienteModel.estado == estado)
        consulta = consulta.order_by(EventoSalienteModel.fecha_creacion.desc()).limit(limite)
        return list(self._session.scalars(consulta))

    def reencolar(self, event_id: UUID) -> bool:
        """Devuelve un evento abandonado a la cola, con los intentos en cero."""

        modelo = self._session.scalar(
            select(EventoSalienteModel).where(EventoSalienteModel.event_id == event_id)
        )
        if modelo is None or modelo.estado == ESTADO_PUBLICADO:
            return False
        modelo.estado = ESTADO_PENDIENTE
        modelo.intentos = 0
        modelo.error = None
        modelo.disponible_desde = datetime.now(timezone.utc)
        return True
