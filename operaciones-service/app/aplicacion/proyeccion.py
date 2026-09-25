"""Proyección de los eventos de GestionDeTrabajosBC sobre la vista de trabajos por partner.

Cada función recibe la vista actual y los datos primitivos de un evento publicado, y
devuelve la vista nueva. Aplicar dos veces el mismo evento da el mismo resultado, así que
una reentrega de Pulsar no corrompe la vista.
"""

from collections.abc import Callable, Mapping
from dataclasses import replace
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

from app.aplicacion.dtos import (
    EstadoTrabajoDePartner,
    SubTrabajoDePartnerDTO,
    TrabajoDePartnerDTO,
)

Datos = Mapping[str, Any]
Proyeccion = Callable[[TrabajoDePartnerDTO, Datos], TrabajoDePartnerDTO]


def proyectar(
    actual: TrabajoDePartnerDTO | None, nombre_evento: str, datos: Datos
) -> TrabajoDePartnerDTO | None:
    """Devuelve la vista tras aplicar el evento, o la actual si el evento no la afecta."""

    proyeccion = PROYECCIONES.get(nombre_evento)
    if proyeccion is None:
        return actual
    return proyeccion(_vista(actual, datos), datos)


def _vista(actual: TrabajoDePartnerDTO | None, datos: Datos) -> TrabajoDePartnerDTO:
    if actual is not None:
        return actual
    # El evento llegó antes de que se guardara la solicitud (o la vista se perdió):
    # se reconstruye desde el propio evento.
    return TrabajoDePartnerDTO(
        partner_id=datos["partner_id"],
        referencia_externa=datos["referencia_externa"],
        estado=EstadoTrabajoDePartner.SOLICITADO,
        fecha_solicitud=datetime.now(timezone.utc),
    )


def _costo(sub_trabajos: tuple[SubTrabajoDePartnerDTO, ...]) -> Decimal:
    return sum(
        (
            sub.monto_cotizado
            for sub in sub_trabajos
            if sub.monto_cotizado is not None and sub.estado != "Cancelado"
        ),
        Decimal("0"),
    )


def _con_sub_trabajo(vista: TrabajoDePartnerDTO, sub_trabajo_id: str, **cambios: Any) -> TrabajoDePartnerDTO:
    sub_trabajos = tuple(
        replace(sub, **cambios) if sub.id == sub_trabajo_id else sub for sub in vista.sub_trabajos
    )
    return replace(vista, sub_trabajos=sub_trabajos, costo_total=_costo(sub_trabajos))


def _trabajo_creado(vista: TrabajoDePartnerDTO, datos: Datos) -> TrabajoDePartnerDTO:
    acuerdo = datos.get("acuerdo") or {}
    monto_maximo = acuerdo.get("monto_maximo")
    estado = (
        EstadoTrabajoDePartner.CREADO
        if vista.estado in (EstadoTrabajoDePartner.SOLICITADO, EstadoTrabajoDePartner.RECHAZADO)
        else vista.estado
    )
    sub_trabajos = vista.sub_trabajos or tuple(
        SubTrabajoDePartnerDTO(
            id=paso["sub_trabajo_id"], categoria=paso["categoria"], estado=paso["estado"]
        )
        for paso in datos.get("flujo", ())
    )
    return replace(
        vista,
        estado=estado,
        trabajo_id=datos["trabajo_id"],
        moneda=acuerdo.get("moneda") or vista.moneda,
        monto_maximo=Decimal(monto_maximo) if monto_maximo is not None else vista.monto_maximo,
        sla_horas=acuerdo.get("sla_horas") or vista.sla_horas,
        motivo_rechazo=None,
        sub_trabajos=sub_trabajos,
    )


def _proveedor_asignado(vista: TrabajoDePartnerDTO, datos: Datos) -> TrabajoDePartnerDTO:
    return _con_sub_trabajo(
        vista,
        datos["sub_trabajo_id"],
        estado="Asignado",
        proveedor_id=datos["proveedor_id"],
        monto_cotizado=Decimal(datos["monto_cotizado"]),
    )


def _sub_trabajo_iniciado(vista: TrabajoDePartnerDTO, datos: Datos) -> TrabajoDePartnerDTO:
    vista = _con_sub_trabajo(vista, datos["sub_trabajo_id"], estado="EnEjecucion")
    if vista.estado is EstadoTrabajoDePartner.CREADO:
        vista = replace(vista, estado=EstadoTrabajoDePartner.EN_EJECUCION)
    return vista


def _sub_trabajo_completado(vista: TrabajoDePartnerDTO, datos: Datos) -> TrabajoDePartnerDTO:
    return _con_sub_trabajo(vista, datos["sub_trabajo_id"], estado="Completado")


def _sub_trabajo_desbloqueado(vista: TrabajoDePartnerDTO, datos: Datos) -> TrabajoDePartnerDTO:
    return _con_sub_trabajo(vista, datos["sub_trabajo_id"], estado=datos["estado"])


def _trabajo_rediagnosticado(vista: TrabajoDePartnerDTO, datos: Datos) -> TrabajoDePartnerDTO:
    congelados = set(datos.get("sub_trabajos_congelados", ()))
    sub_trabajos = tuple(
        replace(sub, estado="Bloqueado") if sub.id in congelados else sub
        for sub in vista.sub_trabajos
    )
    agregado = datos["sub_trabajo_agregado_id"]
    if not any(sub.id == agregado for sub in sub_trabajos):
        sub_trabajos += (
            SubTrabajoDePartnerDTO(id=agregado, categoria=datos["categoria"], estado="Pendiente"),
        )
    return replace(vista, sub_trabajos=sub_trabajos)


def _trabajo_cancelado(vista: TrabajoDePartnerDTO, datos: Datos) -> TrabajoDePartnerDTO:
    cancelados = set(datos.get("sub_trabajos_cancelados", ()))
    sub_trabajos = tuple(
        replace(sub, estado="Cancelado") if sub.id in cancelados else sub
        for sub in vista.sub_trabajos
    )
    return replace(
        vista,
        estado=EstadoTrabajoDePartner.CANCELADO,
        sub_trabajos=sub_trabajos,
        costo_total=_costo(sub_trabajos),
    )


def _trabajo_cerrado(vista: TrabajoDePartnerDTO, datos: Datos) -> TrabajoDePartnerDTO:
    return replace(
        vista, estado=EstadoTrabajoDePartner.CERRADO, costo_total=Decimal(datos["costo_total"])
    )


def _creacion_rechazada(vista: TrabajoDePartnerDTO, datos: Datos) -> TrabajoDePartnerDTO:
    if vista.trabajo_id is not None:
        return vista
    return replace(
        vista, estado=EstadoTrabajoDePartner.RECHAZADO, motivo_rechazo=datos.get("motivo")
    )


PROYECCIONES: dict[str, Proyeccion] = {
    "TrabajoCreadoV2": _trabajo_creado,
    "ProveedorAsignadoV1": _proveedor_asignado,
    "SubTrabajoIniciadoV1": _sub_trabajo_iniciado,
    "SubTrabajoCompletadoV1": _sub_trabajo_completado,
    "SubTrabajoDesbloqueadoV1": _sub_trabajo_desbloqueado,
    "TrabajoRediagnosticadoV1": _trabajo_rediagnosticado,
    "TrabajoCanceladoV1": _trabajo_cancelado,
    "TrabajoCerradoV1": _trabajo_cerrado,
    "CreacionDeTrabajoRechazadaV1": _creacion_rechazada,
}
