"""Contrato de los comandos que otros bounded contexts envían por Pulsar.

Cada mensaje lleva la propiedad `command_type` (por ejemplo `CerrarTrabajoV1`) y un
cuerpo JSON. Este módulo es a la mensajería lo que `mappers.py` es a la API: el único
lugar donde el mensaje se convierte en comando de aplicación. El sufijo de versión
permite aceptar un esquema nuevo sin dejar de atender el anterior.
"""

from collections.abc import Callable, Mapping
from decimal import Decimal
from typing import Any

from app.aplicacion.comandos import (
    AsignarProveedorCommand,
    CancelarTrabajoCommand,
    CerrarTrabajoCommand,
    CompletarSubTrabajoCommand,
    CrearTrabajoCommand,
    IniciarSubTrabajoCommand,
    RegistrarRediagnosticoCommand,
)
from app.aplicacion.dtos import CondicionesDelAcuerdo, SubTrabajoSolicitado


def _requerido(datos: Mapping[str, Any], campo: str) -> Any:
    valor = datos.get(campo)
    if valor is None or valor == "":
        raise ValueError(f"El comando no trae el campo obligatorio '{campo}'")
    return valor


def _condiciones(datos: Mapping[str, Any]) -> CondicionesDelAcuerdo:
    condiciones = datos.get("condiciones") or {}
    monto_maximo = condiciones.get("monto_maximo")
    red = condiciones.get("proveedores_permitidos")
    sla_horas = condiciones.get("sla_horas")
    return CondicionesDelAcuerdo(
        monto_maximo=Decimal(str(monto_maximo)) if monto_maximo is not None else None,
        proveedores_permitidos=frozenset(red) if red is not None else None,
        sla_horas=int(sla_horas) if sla_horas is not None else None,
    )


def _crear_trabajo_v1(datos: Mapping[str, Any]) -> CrearTrabajoCommand:
    """Lo envía Marketplace (sin partner) u OperacionesBC (con partner y condiciones resueltas)."""

    ubicacion = _requerido(datos, "ubicacion")
    partner_id = datos.get("partner_id")
    return CrearTrabajoCommand(
        descripcion=_requerido(datos, "descripcion"),
        urgencia=_requerido(datos, "urgencia"),
        pais=_requerido(ubicacion, "pais"),
        ciudad=_requerido(ubicacion, "ciudad"),
        direccion=_requerido(ubicacion, "direccion"),
        sub_trabajos=tuple(
            SubTrabajoSolicitado(
                clave=_requerido(sub, "clave"),
                categoria=_requerido(sub, "categoria"),
                descripcion=_requerido(sub, "descripcion"),
                depende_de=tuple(sub.get("depende_de", ())),
            )
            for sub in _requerido(datos, "sub_trabajos")
        ),
        moneda=datos.get("moneda", "COP"),
        canal=datos.get("canal") or ("Partner" if partner_id else "Marketplace"),
        partner_id=partner_id,
        referencia_externa=datos.get("referencia_externa"),
        condiciones=_condiciones(datos),
    )


def _asignar_proveedor_v1(datos: Mapping[str, Any]) -> AsignarProveedorCommand:
    return AsignarProveedorCommand(
        trabajo_id=_requerido(datos, "trabajo_id"),
        sub_trabajo_id=_requerido(datos, "sub_trabajo_id"),
        proveedor_id=_requerido(datos, "proveedor_id"),
        monto_cotizado=Decimal(str(_requerido(datos, "monto_cotizado"))),
    )


def _iniciar_sub_trabajo_v1(datos: Mapping[str, Any]) -> IniciarSubTrabajoCommand:
    return IniciarSubTrabajoCommand(
        trabajo_id=_requerido(datos, "trabajo_id"),
        sub_trabajo_id=_requerido(datos, "sub_trabajo_id"),
    )


def _completar_sub_trabajo_v1(datos: Mapping[str, Any]) -> CompletarSubTrabajoCommand:
    return CompletarSubTrabajoCommand(
        trabajo_id=_requerido(datos, "trabajo_id"),
        sub_trabajo_id=_requerido(datos, "sub_trabajo_id"),
        evidencias=tuple(datos.get("evidencias", ())),
    )


def _registrar_rediagnostico_v1(datos: Mapping[str, Any]) -> RegistrarRediagnosticoCommand:
    return RegistrarRediagnosticoCommand(
        trabajo_id=_requerido(datos, "trabajo_id"),
        hallazgo=_requerido(datos, "hallazgo"),
        categoria=_requerido(datos, "categoria"),
        descripcion=_requerido(datos, "descripcion"),
        bloquea_a=tuple(datos.get("bloquea_a", ())),
    )


def _cancelar_trabajo_v1(datos: Mapping[str, Any]) -> CancelarTrabajoCommand:
    return CancelarTrabajoCommand(
        trabajo_id=_requerido(datos, "trabajo_id"),
        motivo=_requerido(datos, "motivo"),
    )


def _cerrar_trabajo_v1(datos: Mapping[str, Any]) -> CerrarTrabajoCommand:
    return CerrarTrabajoCommand(trabajo_id=_requerido(datos, "trabajo_id"))


TRADUCTORES_DE_COMANDOS: dict[str, Callable[[Mapping[str, Any]], object]] = {
    "CrearTrabajoV1": _crear_trabajo_v1,
    "AsignarProveedorV1": _asignar_proveedor_v1,
    "IniciarSubTrabajoV1": _iniciar_sub_trabajo_v1,
    "CompletarSubTrabajoV1": _completar_sub_trabajo_v1,
    "RegistrarRediagnosticoV1": _registrar_rediagnostico_v1,
    "CancelarTrabajoV1": _cancelar_trabajo_v1,
    "CerrarTrabajoV1": _cerrar_trabajo_v1,
}
