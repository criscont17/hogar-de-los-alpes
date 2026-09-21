"""Traducción de eventos de dominio a eventos de integración.

Es el único punto donde el contrato interno se convierte en contrato público.
Los valores se normalizan a tipos primitivos aquí, de modo que ningún adaptador
de mensajería necesite saber serializar `Decimal` ni objetos valor.
"""

from collections.abc import Callable
from typing import Any

from app.aplicacion.eventos_integracion import (
    PagoConfirmadoV1,
    PagoPendienteDeConciliacionV1,
    PagoRechazadoV1,
    PagoRevertidoV1,
)
from app.dominio.pago.eventos import (
    PagoConfirmado,
    PagoPendienteDeConciliacion,
    PagoRechazado,
    PagoRevertido,
)
from app.seedwork.aplicacion import IntegrationEvent
from app.seedwork.dominio import DomainEvent


def _base(evento: Any) -> dict[str, Any]:
    return {
        "event_id": evento.event_id,
        "occurred_at": evento.occurred_at,
        "pago_id": evento.pago_id,
        "trabajo_id": evento.trabajo_id,
        "sub_trabajo_id": evento.sub_trabajo_id,
        "proveedor_id": evento.proveedor_id,
    }


def _a_pago_confirmado_v1(evento: PagoConfirmado) -> PagoConfirmadoV1:
    return PagoConfirmadoV1(
        **_base(evento),
        monto=str(evento.monto),
        moneda=evento.moneda,
        psp=evento.psp,
        referencia_psp=evento.referencia_psp,
    )


def _a_pago_rechazado_v1(evento: PagoRechazado) -> PagoRechazadoV1:
    return PagoRechazadoV1(
        **_base(evento),
        monto=str(evento.monto),
        moneda=evento.moneda,
        psp=evento.psp,
        motivo=evento.motivo,
    )


def _a_pago_pendiente_de_conciliacion_v1(
    evento: PagoPendienteDeConciliacion,
) -> PagoPendienteDeConciliacionV1:
    return PagoPendienteDeConciliacionV1(
        **_base(evento),
        monto=str(evento.monto),
        moneda=evento.moneda,
        psp=evento.psp,
        motivo=evento.motivo,
    )


def _a_pago_revertido_v1(evento: PagoRevertido) -> PagoRevertidoV1:
    return PagoRevertidoV1(
        **_base(evento),
        monto=str(evento.monto),
        moneda=evento.moneda,
        psp=evento.psp,
        motivo=evento.motivo,
    )


Traductor = Callable[[DomainEvent], IntegrationEvent]

TRADUCTORES: dict[type[DomainEvent], tuple[Traductor, ...]] = {
    PagoConfirmado: (_a_pago_confirmado_v1,),
    PagoRechazado: (_a_pago_rechazado_v1,),
    PagoPendienteDeConciliacion: (_a_pago_pendiente_de_conciliacion_v1,),
    PagoRevertido: (_a_pago_revertido_v1,),
}
