"""Traducción de eventos de dominio a eventos de integración.

Es el único punto donde el contrato interno se convierte en contrato público.
Los valores se normalizan a tipos primitivos aquí, de modo que ningún adaptador
de mensajería necesite saber serializar `Decimal`, `datetime` ni objetos valor.
"""

from collections.abc import Callable

from app.aplicacion.eventos_integracion import (
    BilleteraCreadaV1,
    DebitoRechazadoV1,
    SaldoAcreditadoV1,
    SaldoDebitadoV1,
)
from app.dominio.billetera.eventos import (
    BilleteraCreada,
    DebitoRechazado,
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


Traductor = Callable[[DomainEvent], IntegrationEvent]

TRADUCTORES: dict[type[DomainEvent], Traductor] = {
    BilleteraCreada: _de_billetera_creada,
    SaldoAcreditado: _de_saldo_acreditado,
    SaldoDebitado: _de_saldo_debitado,
    DebitoRechazado: _de_debito_rechazado,
}
