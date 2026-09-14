"""Traducción de eventos de dominio a eventos de integración.

Es el único punto donde el contrato interno se convierte en contrato público.
Los valores se normalizan a tipos primitivos aquí, de modo que ningún adaptador
de mensajería necesite saber serializar `Decimal`, `datetime` ni objetos valor.

Un evento de dominio puede mapear a varias versiones del contrato. Todas conservan
el `event_id` y `occurred_at` del hecho original: representan el mismo hecho, y un
reintento de publicación no fabrica uno nuevo.
"""

from collections.abc import Callable, Iterable
from datetime import timedelta
from typing import Any

from app.aplicacion.eventos_integracion import (
    AsignacionRechazadaV1,
    ProveedorAsignadoV1,
    SubTrabajoCompletadoV1,
    SubTrabajoDesbloqueadoV1,
    SubTrabajoIniciadoV1,
    TrabajoCanceladoV1,
    TrabajoCerradoV1,
    TrabajoCreadoV1,
    TrabajoCreadoV2,
    TrabajoRediagnosticadoV1,
)
from app.dominio.trabajo.eventos import (
    AsignacionRechazada,
    DetalleSubTrabajo,
    EventoDeTrabajo,
    Liquidacion,
    ProveedorAsignado,
    SubTrabajoCompletado,
    SubTrabajoDesbloqueado,
    SubTrabajoIniciado,
    TrabajoCancelado,
    TrabajoCerrado,
    TrabajoCreado,
    TrabajoRediagnosticado,
)
from app.seedwork.aplicacion import IntegrationEvent
from app.seedwork.dominio import DomainEvent


def _base(evento: EventoDeTrabajo) -> dict[str, Any]:
    return {
        "event_id": evento.event_id,
        "occurred_at": evento.occurred_at,
        "trabajo_id": evento.trabajo_id,
        "partner_id": evento.partner_id,
        "referencia_externa": evento.referencia_externa,
    }


def _flujo(detalles: Iterable[DetalleSubTrabajo]) -> tuple[dict[str, Any], ...]:
    return tuple(
        {
            "sub_trabajo_id": detalle.sub_trabajo_id,
            "categoria": detalle.categoria,
            "estado": detalle.estado,
            "depende_de": list(detalle.depende_de),
        }
        for detalle in detalles
    )


def _liquidaciones(liquidaciones: Iterable[Liquidacion]) -> tuple[dict[str, str], ...]:
    return tuple(
        {
            "sub_trabajo_id": liquidacion.sub_trabajo_id,
            "proveedor_id": liquidacion.proveedor_id,
            "monto": str(liquidacion.monto),
        }
        for liquidacion in liquidaciones
    )


def _a_trabajo_creado_v1(evento: TrabajoCreado) -> TrabajoCreadoV1:
    return TrabajoCreadoV1(
        **_base(evento),
        canal=evento.canal,
        descripcion=evento.descripcion,
        urgencia=evento.urgencia,
        pais=evento.pais,
        ciudad=evento.ciudad,
        moneda=evento.moneda,
        sub_trabajos=_flujo(evento.sub_trabajos),
    )


def _a_trabajo_creado_v2(evento: TrabajoCreado) -> TrabajoCreadoV2:
    fecha_limite = (
        (evento.occurred_at + timedelta(hours=evento.sla_horas)).isoformat()
        if evento.sla_horas
        else None
    )
    return TrabajoCreadoV2(
        **_base(evento),
        canal=evento.canal,
        descripcion=evento.descripcion,
        urgencia=evento.urgencia,
        ubicacion={"pais": evento.pais, "ciudad": evento.ciudad},
        acuerdo={
            "moneda": evento.moneda,
            "monto_maximo": str(evento.monto_maximo) if evento.monto_maximo is not None else None,
            "sla_horas": evento.sla_horas,
            "fecha_limite_sla": fecha_limite,
        },
        flujo=_flujo(evento.sub_trabajos),
    )


def _a_proveedor_asignado_v1(evento: ProveedorAsignado) -> ProveedorAsignadoV1:
    return ProveedorAsignadoV1(
        **_base(evento),
        sub_trabajo_id=evento.sub_trabajo_id,
        proveedor_id=evento.proveedor_id,
        monto_cotizado=str(evento.monto_cotizado),
        moneda=evento.moneda,
        reasignacion=evento.reasignacion,
    )


def _a_asignacion_rechazada_v1(evento: AsignacionRechazada) -> AsignacionRechazadaV1:
    return AsignacionRechazadaV1(
        **_base(evento),
        sub_trabajo_id=evento.sub_trabajo_id,
        proveedor_id=evento.proveedor_id,
        monto_cotizado=str(evento.monto_cotizado),
        moneda=evento.moneda,
        motivo_rechazo=evento.motivo_rechazo,
    )


def _a_sub_trabajo_iniciado_v1(evento: SubTrabajoIniciado) -> SubTrabajoIniciadoV1:
    return SubTrabajoIniciadoV1(
        **_base(evento),
        sub_trabajo_id=evento.sub_trabajo_id,
        proveedor_id=evento.proveedor_id,
    )


def _a_sub_trabajo_completado_v1(evento: SubTrabajoCompletado) -> SubTrabajoCompletadoV1:
    return SubTrabajoCompletadoV1(
        **_base(evento),
        sub_trabajo_id=evento.sub_trabajo_id,
        proveedor_id=evento.proveedor_id,
        evidencias=tuple(evento.evidencias),
    )


def _a_sub_trabajo_desbloqueado_v1(evento: SubTrabajoDesbloqueado) -> SubTrabajoDesbloqueadoV1:
    return SubTrabajoDesbloqueadoV1(
        **_base(evento),
        sub_trabajo_id=evento.sub_trabajo_id,
        categoria=evento.categoria,
        estado=evento.estado,
    )


def _a_trabajo_rediagnosticado_v1(evento: TrabajoRediagnosticado) -> TrabajoRediagnosticadoV1:
    return TrabajoRediagnosticadoV1(
        **_base(evento),
        hallazgo=evento.hallazgo,
        sub_trabajo_agregado_id=evento.sub_trabajo_agregado_id,
        categoria=evento.categoria,
        sub_trabajos_congelados=tuple(evento.sub_trabajos_congelados),
    )


def _a_trabajo_cancelado_v1(evento: TrabajoCancelado) -> TrabajoCanceladoV1:
    return TrabajoCanceladoV1(
        **_base(evento),
        motivo=evento.motivo,
        sub_trabajos_cancelados=tuple(evento.sub_trabajos_cancelados),
        liquidaciones=_liquidaciones(evento.liquidaciones),
        moneda=evento.moneda,
    )


def _a_trabajo_cerrado_v1(evento: TrabajoCerrado) -> TrabajoCerradoV1:
    return TrabajoCerradoV1(
        **_base(evento),
        costo_total=str(evento.costo_total),
        moneda=evento.moneda,
        liquidaciones=_liquidaciones(evento.liquidaciones),
    )


Traductor = Callable[[DomainEvent], IntegrationEvent]

TRADUCTORES: dict[type[DomainEvent], tuple[Traductor, ...]] = {
    TrabajoCreado: (_a_trabajo_creado_v1, _a_trabajo_creado_v2),
    ProveedorAsignado: (_a_proveedor_asignado_v1,),
    AsignacionRechazada: (_a_asignacion_rechazada_v1,),
    SubTrabajoIniciado: (_a_sub_trabajo_iniciado_v1,),
    SubTrabajoCompletado: (_a_sub_trabajo_completado_v1,),
    SubTrabajoDesbloqueado: (_a_sub_trabajo_desbloqueado_v1,),
    TrabajoRediagnosticado: (_a_trabajo_rediagnosticado_v1,),
    TrabajoCancelado: (_a_trabajo_cancelado_v1,),
    TrabajoCerrado: (_a_trabajo_cerrado_v1,),
}
