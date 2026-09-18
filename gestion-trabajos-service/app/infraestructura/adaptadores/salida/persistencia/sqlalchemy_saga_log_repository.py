from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from .modelos_orm import SagaInstanciaModel, SagaPasoModel


class SqlAlchemySagaLogRepository:
    """Repositorio para consultar y persistir el Saga Log en PostgreSQL."""

    def __init__(self, session_factory):
        self._session_factory = session_factory

    def registrar_inicio_saga(
        self,
        saga_id: UUID,
        tipo_saga: str,
        trabajo_id: UUID,
        payload_inicial: dict[str, Any],
    ) -> SagaInstanciaModel:
        ahora = datetime.now(timezone.utc)
        instancia = SagaInstanciaModel(
            id=uuid4(),
            saga_id=saga_id,
            tipo_saga=tipo_saga,
            trabajo_id=trabajo_id,
            estado_global="INICIADA",
            paso_actual="INICIO",
            payload_inicial=payload_inicial,
            fecha_creacion=ahora,
            fecha_actualizacion=ahora,
        )
        with self._session_factory() as session:
            session.add(instancia)
            session.commit()
            session.refresh(instancia)
            return instancia

    def registrar_paso_iniciado(
        self,
        saga_id: UUID,
        paso_numero: int,
        nombre_paso: str,
        servicio_participante: str,
        comando_enviado: dict[str, Any] | None = None,
    ) -> None:
        ahora = datetime.now(timezone.utc)
        with self._session_factory() as session:
            # Actualizar instancia
            stmt = select(SagaInstanciaModel).where(SagaInstanciaModel.saga_id == saga_id)
            instancia = session.execute(stmt).scalar_one_or_none()
            if instancia:
                instancia.paso_actual = nombre_paso
                instancia.estado_global = "EN_PROCESO"
                instancia.fecha_actualizacion = ahora

            paso = SagaPasoModel(
                id=uuid4(),
                saga_id=saga_id,
                paso_numero=paso_numero,
                nombre_paso=nombre_paso,
                servicio_participante=servicio_participante,
                estado_paso="EN_PROCESO",
                comando_enviado=comando_enviado,
                fecha_inicio=ahora,
            )
            session.add(paso)
            session.commit()

    def registrar_paso_completado(
        self,
        saga_id: UUID,
        paso_numero: int,
        evento_recibido: dict[str, Any] | None = None,
    ) -> None:
        ahora = datetime.now(timezone.utc)
        with self._session_factory() as session:
            stmt = select(SagaPasoModel).where(
                SagaPasoModel.saga_id == saga_id,
                SagaPasoModel.paso_numero == paso_numero,
            )
            paso = session.execute(stmt).scalar_one_or_none()
            if paso:
                paso.estado_paso = "EXITOSO"
                paso.evento_recibido = evento_recibido
                paso.fecha_fin = ahora

            stmt_inst = select(SagaInstanciaModel).where(SagaInstanciaModel.saga_id == saga_id)
            instancia = session.execute(stmt_inst).scalar_one_or_none()
            if instancia:
                instancia.fecha_actualizacion = ahora

            session.commit()

    def registrar_paso_fallido(
        self,
        saga_id: UUID,
        paso_numero: int,
        error: str,
        evento_recibido: dict[str, Any] | None = None,
    ) -> None:
        ahora = datetime.now(timezone.utc)
        with self._session_factory() as session:
            stmt = select(SagaPasoModel).where(
                SagaPasoModel.saga_id == saga_id,
                SagaPasoModel.paso_numero == paso_numero,
            )
            paso = session.execute(stmt).scalar_one_or_none()
            if paso:
                paso.estado_paso = "FALLIDO"
                paso.error = error
                paso.evento_recibido = evento_recibido
                paso.fecha_fin = ahora

            stmt_inst = select(SagaInstanciaModel).where(SagaInstanciaModel.saga_id == saga_id)
            instancia = session.execute(stmt_inst).scalar_one_or_none()
            if instancia:
                instancia.estado_global = "COMPENSANDO"
                instancia.error = error
                instancia.fecha_actualizacion = ahora

            session.commit()

    def registrar_paso_compensacion(
        self,
        saga_id: UUID,
        paso_numero: int,
        nombre_paso: str,
        servicio_participante: str,
        estado: str,  # EN_PROCESO | COMPENSADO | ERROR
        comando_compensacion: dict[str, Any] | None = None,
        evento_compensacion: dict[str, Any] | None = None,
        error: str | None = None,
    ) -> None:
        ahora = datetime.now(timezone.utc)
        with self._session_factory() as session:
            paso = SagaPasoModel(
                id=uuid4(),
                saga_id=saga_id,
                paso_numero=paso_numero,
                nombre_paso=nombre_paso,
                servicio_participante=servicio_participante,
                estado_paso=estado,
                comando_enviado=comando_compensacion,
                evento_recibido=evento_compensacion,
                error=error,
                fecha_inicio=ahora,
                fecha_fin=ahora if estado in {"COMPENSADO", "ERROR"} else None,
            )
            session.add(paso)
            session.commit()

    def finalizar_saga(
        self,
        saga_id: UUID,
        estado_final: str,  # COMPLETADA_EXITOSA | COMPENSADA | FALLIDA
        error: str | None = None,
    ) -> None:
        ahora = datetime.now(timezone.utc)
        with self._session_factory() as session:
            stmt = select(SagaInstanciaModel).where(SagaInstanciaModel.saga_id == saga_id)
            instancia = session.execute(stmt).scalar_one_or_none()
            if instancia:
                instancia.estado_global = estado_final
                if error:
                    instancia.error = error
                instancia.fecha_actualizacion = ahora
                session.commit()

    def obtener_saga(self, saga_id: UUID) -> SagaInstanciaModel | None:
        with self._session_factory() as session:
            stmt = select(SagaInstanciaModel).where(SagaInstanciaModel.saga_id == saga_id)
            return session.execute(stmt).scalar_one_or_none()

    def listar_sagas(self, limite: int = 20) -> list[SagaInstanciaModel]:
        with self._session_factory() as session:
            stmt = select(SagaInstanciaModel).order_by(SagaInstanciaModel.fecha_creacion.desc()).limit(limite)
            return list(session.execute(stmt).scalars().all())
