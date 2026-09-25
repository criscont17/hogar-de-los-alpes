"""Contrato del comando `CrearTrabajoV1` que acepta GestionDeTrabajosBC.

OperacionesBC es cliente de ese contrato público. Si GestionDeTrabajosBC publica una
versión nueva del comando, se agrega aquí sin tocar los casos de uso.
"""

from typing import Any

from app.aplicacion.dtos import SolicitudDeCreacionDeTrabajo

COMANDO_CREAR_TRABAJO = "CrearTrabajoV1"


def crear_trabajo_v1(solicitud: SolicitudDeCreacionDeTrabajo) -> dict[str, Any]:
    return {
        "canal": "Partner",
        "partner_id": solicitud.partner_id,
        "referencia_externa": solicitud.referencia_externa,
        "descripcion": solicitud.descripcion,
        "urgencia": solicitud.urgencia,
        "ubicacion": {
            "pais": solicitud.pais,
            "ciudad": solicitud.ciudad,
            "direccion": solicitud.direccion,
        },
        "moneda": solicitud.moneda,
        "sub_trabajos": [
            {
                "clave": sub.clave,
                "categoria": sub.categoria,
                "descripcion": sub.descripcion,
                "depende_de": list(sub.depende_de),
            }
            for sub in solicitud.sub_trabajos
        ],
        "condiciones": {
            "monto_maximo": str(solicitud.monto_maximo) if solicitud.monto_maximo is not None else None,
            "proveedores_permitidos": (
                sorted(solicitud.proveedores_permitidos)
                if solicitud.proveedores_permitidos is not None
                else None
            ),
            "sla_horas": solicitud.sla_horas,
        },
    }
