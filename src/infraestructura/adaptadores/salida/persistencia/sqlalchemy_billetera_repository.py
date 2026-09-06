from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from dominio.billetera import (
    Billetera,
    BilleteraId,
    Dinero,
    EstadoBilletera,
    MotivoMovimiento,
    Movimiento,
    MovimientoId,
    TipoMovimiento,
)
from dominio.billetera.billetera_repository import BilleteraRepository

from .modelos_orm import BilleteraModel, MovimientoModel


def _con_zona_horaria(fecha: datetime) -> datetime:
    return fecha if fecha.tzinfo is not None else fecha.replace(tzinfo=timezone.utc)


class SqlAlchemyBilleteraRepository(BilleteraRepository):
    def __init__(self, session: Session) -> None:
        self._session = session

    def guardar(self, billetera: Billetera) -> None:
        try:
            model = self._session.get(BilleteraModel, billetera.id.valor)
            if model is None:
                model = BilleteraModel(
                    id=billetera.id.valor,
                    proveedor_id=billetera.proveedor_id,
                    saldo_monto=billetera.saldo.monto,
                    saldo_moneda=billetera.saldo.moneda,
                    estado=billetera.estado.value,
                    fecha_creacion=billetera.fecha_creacion,
                    movimientos=[],
                )
                self._session.add(model)
            else:
                model.saldo_monto = billetera.saldo.monto
                model.saldo_moneda = billetera.saldo.moneda
                model.estado = billetera.estado.value

            ids_persistidos = {movimiento.id for movimiento in model.movimientos}
            for movimiento in billetera.movimientos:
                if movimiento.id.valor not in ids_persistidos:
                    model.movimientos.append(
                        MovimientoModel(
                            id=movimiento.id.valor,
                            billetera_id=billetera.id.valor,
                            tipo=movimiento.tipo.value,
                            motivo=movimiento.motivo.value,
                            monto=movimiento.monto.monto,
                            saldo_resultante=movimiento.saldo_resultante.monto,
                            referencia_externa=movimiento.referencia_externa,
                            fecha=movimiento.fecha,
                        )
                    )
            self._session.commit()
        except Exception:
            self._session.rollback()
            raise

    def obtener_por_id(self, id: BilleteraId) -> Billetera | None:
        statement = (
            select(BilleteraModel)
            .where(BilleteraModel.id == id.valor)
            .options(selectinload(BilleteraModel.movimientos))
        )
        return self._a_dominio(self._session.scalar(statement))

    def obtener_por_proveedor_id(self, proveedor_id: str) -> Billetera | None:
        statement = (
            select(BilleteraModel)
            .where(BilleteraModel.proveedor_id == proveedor_id)
            .options(selectinload(BilleteraModel.movimientos))
        )
        return self._a_dominio(self._session.scalar(statement))

    @staticmethod
    def _a_dominio(model: BilleteraModel | None) -> Billetera | None:
        if model is None:
            return None
        moneda = model.saldo_moneda
        movimientos = [
            Movimiento(
                id=MovimientoId(item.id),
                tipo=TipoMovimiento(item.tipo),
                motivo=MotivoMovimiento(item.motivo),
                monto=Dinero(item.monto, moneda),
                saldo_resultante=Dinero(item.saldo_resultante, moneda),
                fecha=_con_zona_horaria(item.fecha),
                referencia_externa=item.referencia_externa,
            )
            for item in model.movimientos
        ]
        return Billetera(
            id=BilleteraId(model.id),
            proveedor_id=model.proveedor_id,
            saldo=Dinero(model.saldo_monto, moneda),
            estado=EstadoBilletera(model.estado),
            movimientos=movimientos,
            fecha_creacion=_con_zona_horaria(model.fecha_creacion),
        )
