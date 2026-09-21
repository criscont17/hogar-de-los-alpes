from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from sqlalchemy.orm.exc import StaleDataError

from app.aplicacion.errores import ConflictoDeConcurrenciaError
from app.dominio.errores import PagoDuplicadoError
from app.dominio.pago import Dinero, EstadoPago, Pago, PagoId, TipoPago
from app.dominio.pago.pago_repository import PagoRepository

from .modelos_orm import PagoModel


def _con_zona_horaria(fecha: datetime) -> datetime:
    return fecha if fecha.tzinfo is not None else fecha.replace(tzinfo=timezone.utc)


class SqlAlchemyPagoRepository(PagoRepository):
    def __init__(self, session: Session) -> None:
        self._session = session

    def guardar(self, pago: Pago) -> None:
        """Escribe el agregado dentro de la transacción abierta por la unidad de trabajo.

        Hace `flush` para que los errores de integridad y de versión aparezcan aquí y se
        traduzcan a errores de negocio, pero no confirma: el `commit` es de la unidad de
        trabajo.
        """
        try:
            model = self._session.get(PagoModel, pago.id.valor)
            if model is None:
                model = PagoModel(
                    id=pago.id.valor,
                    trabajo_id=pago.trabajo_id,
                    sub_trabajo_id=pago.sub_trabajo_id,
                    proveedor_id=pago.proveedor_id,
                    tipo=pago.tipo.value,
                    monto=pago.monto.monto,
                    moneda=pago.monto.moneda,
                    psp=pago.psp,
                    referencia_externa=pago.referencia_externa,
                    fecha_creacion=pago.fecha_creacion,
                    estado=pago.estado.value,
                )
                self._session.add(model)
            model.estado = pago.estado.value
            model.referencia_psp = pago.referencia_psp
            model.motivo = pago.motivo
            self._session.flush()
        except IntegrityError as exc:
            raise PagoDuplicadoError(
                "Ya existe un pago con esa referencia externa"
            ) from exc
        except StaleDataError as exc:
            raise ConflictoDeConcurrenciaError(
                "El pago fue modificado por otra operación; vuelva a intentarlo"
            ) from exc


    def obtener_por_id(self, id: PagoId) -> Pago | None:
        return self._a_dominio(self._session.get(PagoModel, id.valor))

    def obtener_por_referencia_externa(self, referencia_externa: str) -> Pago | None:
        statement = select(PagoModel).where(PagoModel.referencia_externa == referencia_externa)
        return self._a_dominio(self._session.scalar(statement))

    def listar(self, trabajo_id: str | None = None, limite: int = 50) -> list[Pago]:
        statement = select(PagoModel).order_by(PagoModel.fecha_creacion.desc()).limit(limite)
        if trabajo_id is not None:
            statement = statement.where(PagoModel.trabajo_id == trabajo_id)
        return [self._a_dominio(model) for model in self._session.scalars(statement)]

    @staticmethod
    def _a_dominio(model: PagoModel | None) -> Pago | None:
        if model is None:
            return None
        return Pago(
            id=PagoId(model.id),
            trabajo_id=model.trabajo_id,
            tipo=TipoPago(model.tipo),
            monto=Dinero(model.monto, model.moneda),
            psp=model.psp,
            referencia_externa=model.referencia_externa,
            estado=EstadoPago(model.estado),
            sub_trabajo_id=model.sub_trabajo_id,
            proveedor_id=model.proveedor_id,
            referencia_psp=model.referencia_psp,
            motivo=model.motivo,
            fecha_creacion=_con_zona_horaria(model.fecha_creacion),
        )
