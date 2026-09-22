from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.dominio.billetera import (
    Billetera,
    BilleteraId,
    Dinero,
    EstadoBilletera,
    MotivoMovimiento,
    Movimiento,
    MovimientoId,
    TipoMovimiento,
)
from app.dominio.billetera.billetera_repository import BilleteraRepository

from .modelos_orm import BilleteraModel, MovimientoModel


def _con_zona_horaria(fecha: datetime) -> datetime:
    return fecha if fecha.tzinfo is not None else fecha.replace(tzinfo=timezone.utc)


class SqlAlchemyBilleteraRepository(BilleteraRepository):
    def __init__(self, session: Session) -> None:
        self._session = session

    def guardar(self, billetera: Billetera) -> None:
        """Deja la escritura lista en la sesión; confirmarla es de la unidad de trabajo."""

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
        self._session.flush()

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

    def eliminar(self, billetera: Billetera) -> None:
        model = self._session.get(BilleteraModel, billetera.id.valor)
        if model is not None:
            # Los movimientos se van con ella por el cascade delete-orphan.
            self._session.delete(model)
            self._session.flush()

    def listar(
        self,
        estado: EstadoBilletera | None = None,
        proveedor_id: str | None = None,
        limite: int = 50,
        desplazamiento: int = 0,
    ) -> list[Billetera]:
        statement = (
            self._filtrar(select(BilleteraModel), estado, proveedor_id)
            .options(selectinload(BilleteraModel.movimientos))
            .order_by(BilleteraModel.fecha_creacion.desc(), BilleteraModel.id)
            .limit(limite)
            .offset(desplazamiento)
        )
        return [self._reconstruir(model) for model in self._session.scalars(statement)]

    def contar(
        self,
        estado: EstadoBilletera | None = None,
        proveedor_id: str | None = None,
    ) -> int:
        statement = self._filtrar(
            select(func.count()).select_from(BilleteraModel), estado, proveedor_id
        )
        return self._session.scalar(statement) or 0

    @staticmethod
    def _filtrar(statement, estado: EstadoBilletera | None, proveedor_id: str | None):
        if estado is not None:
            statement = statement.where(BilleteraModel.estado == estado.value)
        if proveedor_id:
            statement = statement.where(BilleteraModel.proveedor_id == proveedor_id)
        return statement

    @classmethod
    def _a_dominio(cls, model: BilleteraModel | None) -> Billetera | None:
        return None if model is None else cls._reconstruir(model)

    @staticmethod
    def _reconstruir(model: BilleteraModel) -> Billetera:
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
