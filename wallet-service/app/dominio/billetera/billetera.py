from datetime import datetime, timezone

from app.dominio.errores import (
    BilleteraNoEliminableError,
    BilleteraSuspendidaError,
    FondosInsuficientesError,
    MontoInvalidoError,
)
from app.seedwork.dominio import AggregateRoot

from .dinero import Dinero
from .enums import EstadoBilletera, MotivoMovimiento, TipoMovimiento
from .eventos import (
    AcreditacionRechazada,
    BilleteraEliminada,
    DebitoRechazado,
    EstadoBilleteraCambiado,
    SaldoAcreditado,
    SaldoDebitado,
)
from .identificadores import BilleteraId, MovimientoId
from .movimiento import Movimiento


class Billetera(AggregateRoot[BilleteraId]):
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
                motivo=motivo.value,
                saldo_resultante=nuevo_saldo.monto,
                fecha=fecha,
                referencia_externa=referencia_externa,
            )
        )

    def acreditar_liquidacion(
        self,
        monto: Dinero,
        referencia_externa: str,
    ) -> None:
        """Acredita la liquidación de un trabajo ya ejecutado.

        A diferencia de `acreditar`, exige la billetera activa: una billetera
        bloqueada no puede recibir el dinero de una liquidación mientras Operaciones
        no resuelva por qué lo está. El rechazo no toca el saldo, pero sí se anuncia
        para que quien coordina la transacción decida entre reintentar y abrir una
        disputa.
        """

        if self._estado is EstadoBilletera.SUSPENDIDA:
            self.add_domain_event(
                AcreditacionRechazada(
                    billetera_id=str(self.id),
                    proveedor_id=self.proveedor_id,
                    monto_solicitado=monto.monto,
                    moneda=monto.moneda,
                    motivo_rechazo="La billetera está suspendida",
                    fecha=datetime.now(timezone.utc),
                    referencia_externa=referencia_externa,
                )
            )
            raise BilleteraSuspendidaError(
                "No se puede acreditar una liquidación en una billetera suspendida"
            )
        self.acreditar(monto, MotivoMovimiento.PAGO_DE_TRABAJO, referencia_externa)

    def tiene_movimiento_con_referencia(self, referencia_externa: str) -> bool:
        """Permite que un mismo hecho reentregado no se acredite dos veces."""

        return any(
            movimiento.referencia_externa == referencia_externa
            for movimiento in self._movimientos
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
                motivo=motivo.value,
                saldo_resultante=nuevo_saldo.monto,
                fecha=fecha,
                referencia_externa=referencia_externa,
            )
        )

    def suspender(self) -> None:
        self._cambiar_estado(EstadoBilletera.SUSPENDIDA)

    def reactivar(self) -> None:
        self._cambiar_estado(EstadoBilletera.ACTIVA)

    def confirmar_eliminacion(self) -> None:
        """Valida que la billetera pueda retirarse y anuncia el hecho.

        Una billetera con saldo representa dinero adeudado al proveedor: borrarla
        haría desaparecer ese pasivo sin contrapartida contable.
        """

        if self._saldo.monto > 0:
            raise BilleteraNoEliminableError(
                "No se puede eliminar una billetera con saldo disponible"
            )
        self.add_domain_event(
            BilleteraEliminada(
                billetera_id=str(self.id),
                proveedor_id=self.proveedor_id,
                fecha=datetime.now(timezone.utc),
            )
        )

    def _cambiar_estado(self, estado: EstadoBilletera) -> None:
        """Aplica el nuevo estado. Repetir el estado actual no es un hecho nuevo."""

        if self._estado is estado:
            return
        anterior = self._estado
        self._estado = estado
        self.add_domain_event(
            EstadoBilleteraCambiado(
                billetera_id=str(self.id),
                estado_anterior=anterior.value,
                estado_nuevo=estado.value,
                fecha=datetime.now(timezone.utc),
            )
        )

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
