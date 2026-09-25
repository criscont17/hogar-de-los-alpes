"""Traducción de eventos de dominio a eventos de integración.

Es el único punto donde el contrato interno se convierte en contrato público.
Los valores se normalizan a tipos primitivos aquí, de modo que ningún adaptador
de mensajería necesite saber serializar `Decimal`, `datetime` ni objetos valor.
"""

from collections.abc import Callable

from app.aplicacion.eventos_integracion import (
    AcreditacionRechazadaV1,
    BilleteraCreadaV1,
    BilleteraEliminadaV1,
    DebitoRechazadoV1,
    EstadoBilleteraCambiadoV1,
    SaldoAcreditadoV1,
    SaldoDebitadoV1,
)
from app.dominio.billetera.eventos import (
    AcreditacionRechazada,
    BilleteraCreada,
    BilleteraEliminada,
    DebitoRechazado,
    EstadoBilleteraCambiado,
    SaldoAcreditado,
    SaldoDebitado,
)
from app.seedwork.aplicacion import IntegrationEvent
from app.seedwork.dominio import DomainEvent


def _de_billetera_creada(evento: BilleteraCreada) -> BilleteraCreadaV1:
    return BilleteraCreadaV1(
        billetera_id=evento.billetera_id,
        proveedor_id=evento.proveedor_id,
        fecha=evento.fecha.isoformat(),
    )


def _de_saldo_acreditado(evento: SaldoAcreditado) -> SaldoAcreditadoV1:
    return SaldoAcreditadoV1(
        billetera_id=evento.billetera_id,
        monto=str(evento.monto),
        moneda=evento.moneda,
        motivo=evento.motivo,
        saldo_resultante=str(evento.saldo_resultante),
        fecha=evento.fecha.isoformat(),
        referencia_externa=evento.referencia_externa,
    )


def _de_saldo_debitado(evento: SaldoDebitado) -> SaldoDebitadoV1:
    return SaldoDebitadoV1(
        billetera_id=evento.billetera_id,
        monto=str(evento.monto),
        moneda=evento.moneda,
        motivo=evento.motivo,
        saldo_resultante=str(evento.saldo_resultante),
        fecha=evento.fecha.isoformat(),
        referencia_externa=evento.referencia_externa,
    )


def _de_debito_rechazado(evento: DebitoRechazado) -> DebitoRechazadoV1:
    return DebitoRechazadoV1(
        billetera_id=evento.billetera_id,
        monto_solicitado=str(evento.monto_solicitado),
        moneda=evento.moneda,
        motivo_rechazo=evento.motivo_rechazo,
        fecha=evento.fecha.isoformat(),
        referencia_externa=evento.referencia_externa,
    )


def _de_acreditacion_rechazada(evento: AcreditacionRechazada) -> AcreditacionRechazadaV1:
    return AcreditacionRechazadaV1(
        billetera_id=evento.billetera_id,
        proveedor_id=evento.proveedor_id,
        monto_solicitado=str(evento.monto_solicitado),
        moneda=evento.moneda,
        motivo_rechazo=evento.motivo_rechazo,
        fecha=evento.fecha.isoformat(),
        referencia_externa=evento.referencia_externa,
    )


def _de_estado_cambiado(evento: EstadoBilleteraCambiado) -> EstadoBilleteraCambiadoV1:
    return EstadoBilleteraCambiadoV1(
        billetera_id=evento.billetera_id,
        estado_anterior=evento.estado_anterior,
        estado_nuevo=evento.estado_nuevo,
        fecha=evento.fecha.isoformat(),
    )


def _de_billetera_eliminada(evento: BilleteraEliminada) -> BilleteraEliminadaV1:
    return BilleteraEliminadaV1(
        billetera_id=evento.billetera_id,
        proveedor_id=evento.proveedor_id,
        fecha=evento.fecha.isoformat(),
    )


Traductor = Callable[[DomainEvent], IntegrationEvent]

TRADUCTORES: dict[type[DomainEvent], Traductor] = {
    BilleteraCreada: _de_billetera_creada,
    SaldoAcreditado: _de_saldo_acreditado,
    SaldoDebitado: _de_saldo_debitado,
    DebitoRechazado: _de_debito_rechazado,
    AcreditacionRechazada: _de_acreditacion_rechazada,
    EstadoBilleteraCambiado: _de_estado_cambiado,
    BilleteraEliminada: _de_billetera_eliminada,
}
