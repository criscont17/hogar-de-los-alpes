from datetime import datetime, timezone

from dominio.errores import (
    BilleteraSuspendidaError,
    FondosInsuficientesError,
    MontoInvalidoError,
)
from dominio.seedwork import AggregateRoot

from .dinero import Dinero
from .enums import EstadoBilletera, MotivoMovimiento, TipoMovimiento
from .eventos import DebitoRechazado, SaldoAcreditado, SaldoDebitado
from .identificadores import BilleteraId, MovimientoId
from .movimiento import Movimiento


class Billetera(AggregateRoot):
    def __init__(
        self,
        id: BilleteraId,
        proveedor_id: str,
        saldo: Dinero,
        estado: EstadoBilletera,
        movimientos: list[Movimiento] | None,
        fecha_creacion: datetime,
    ) -> None:
        super().__init__()
        if not proveedor_id or not proveedor_id.strip():
            raise ValueError("proveedor_id es obligatorio")
        self.id = id
        self.proveedor_id = proveedor_id.strip()
        self._saldo = saldo
        self._estado = estado
        self._movimientos = list(movimientos or [])
        self.fecha_creacion = fecha_creacion

    @classmethod
    def crear(cls, proveedor_id: str, moneda_inicial: str) -> "Billetera":
        from .billetera_factory import BilleteraFactory

        return BilleteraFactory.crear_nueva(proveedor_id, moneda_inicial)

    @property
    def saldo(self) -> Dinero:
        return self._saldo

    @property
    def estado(self) -> EstadoBilletera:
        return self._estado

    @property
    def movimientos(self) -> tuple[Movimiento, ...]:
        return tuple(self._movimientos)

    def acreditar(
        self,
        monto: Dinero,
        motivo: MotivoMovimiento,
        referencia_externa: str | None = None,
    ) -> None:
        self._validar_monto_positivo(monto)
        nuevo_saldo = self._saldo.sumar(monto)
        fecha = datetime.now(timezone.utc)
        self._saldo = nuevo_saldo
        self._movimientos.append(
            Movimiento(
                id=MovimientoId.nuevo(),
                tipo=TipoMovimiento.CREDITO,
                motivo=motivo,
                monto=monto,
                saldo_resultante=nuevo_saldo,
                fecha=fecha,
                referencia_externa=referencia_externa,
            )
        )
        self.add_domain_event(
            SaldoAcreditado(
                billetera_id=str(self.id),
                monto=monto.monto,
                moneda=monto.moneda,
                saldo_resultante=nuevo_saldo.monto,
                fecha=fecha,
                referencia_externa=referencia_externa,
            )
        )

    def debitar(
        self,
        monto: Dinero,
        motivo: MotivoMovimiento,
        referencia_externa: str | None = None,
    ) -> None:
        self._validar_monto_positivo(monto)
        monto._validar_moneda(self._saldo)
        if self._estado is EstadoBilletera.SUSPENDIDA:
            self._rechazar_debito(monto, "La billetera está suspendida", referencia_externa)
            raise BilleteraSuspendidaError("No se puede debitar una billetera suspendida")
        if monto.es_mayor_que(self._saldo):
            self._rechazar_debito(monto, "Fondos insuficientes", referencia_externa)
            raise FondosInsuficientesError("El débito excede el saldo disponible")

        nuevo_saldo = self._saldo.restar(monto)
        fecha = datetime.now(timezone.utc)
        self._saldo = nuevo_saldo
        self._movimientos.append(
            Movimiento(
                id=MovimientoId.nuevo(),
                tipo=TipoMovimiento.DEBITO,
                motivo=motivo,
                monto=monto,
                saldo_resultante=nuevo_saldo,
                fecha=fecha,
                referencia_externa=referencia_externa,
            )
        )
        self.add_domain_event(
            SaldoDebitado(
                billetera_id=str(self.id),
                monto=monto.monto,
                moneda=monto.moneda,
                saldo_resultante=nuevo_saldo.monto,
                fecha=fecha,
                referencia_externa=referencia_externa,
            )
        )

    def suspender(self) -> None:
        self._estado = EstadoBilletera.SUSPENDIDA

    def reactivar(self) -> None:
        self._estado = EstadoBilletera.ACTIVA

    @staticmethod
    def _validar_monto_positivo(monto: Dinero) -> None:
        if monto.monto <= 0:
            raise MontoInvalidoError("El monto de un movimiento debe ser mayor que cero")

    def _rechazar_debito(
        self, monto: Dinero, motivo: str, referencia_externa: str | None
    ) -> None:
        fecha = datetime.now(timezone.utc)
        self.add_domain_event(
            DebitoRechazado(
                billetera_id=str(self.id),
                monto_solicitado=monto.monto,
                moneda=monto.moneda,
                motivo_rechazo=motivo,
                fecha=fecha,
                referencia_externa=referencia_externa,
            )
        )
