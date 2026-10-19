from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy.orm import Session

from app.aplicacion.puertos import RepositorioEventosSalientes
from app.seedwork.aplicacion import IntegrationEvent

from .modelos_orm import EventoSalienteModel

ESTADO_PENDIENTE = "PENDIENTE"
ESTADO_PUBLICADO = "PUBLICADO"
ESTADO_FALLIDO = "FALLIDO"


class SqlAlchemyRepositorioEventosSalientes(RepositorioEventosSalientes):
    """Escribe la bandeja de salida en la sesión del caso de uso.

    Como el repositorio de billeteras, solo hace `flush()`: confirmar es de la
    unidad de trabajo. Esa es justamente la propiedad que hace funcionar el
    patrón —la fila del evento entra en el mismo `commit` que el saldo—, así que
    esta clase nunca debe abrir ni confirmar una transacción propia.
    """

    def __init__(self, session: Session) -> None:
        self._session = session

    def encolar(self, evento: IntegrationEvent, clave_particion: str | None = None) -> None:
        ahora = datetime.now(timezone.utc)
        self._session.add(
            EventoSalienteModel(
                id=uuid4(),
                event_id=evento.event_id,
                tipo=evento.nombre,
                clave_particion=clave_particion,
                payload=evento.como_diccionario(),
                estado=ESTADO_PENDIENTE,
                intentos=0,
                fecha_creacion=ahora,
                # Disponible de inmediato: el backoff solo aparece tras un fallo.
                disponible_desde=ahora,
            )
        )
        self._session.flush()
