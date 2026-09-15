"""Adaptador de Muebles del Hogar: comercio que vende cocinas y closets e incluye la
instalación. Integra por webhooks JSON en inglés.

Solo traduce formato. El tope por país y el SLA de cada prioridad están en el acuerdo
comercial del partner (agregado `Partner`).

Particularidades del formato:
- Cada ítem vendido trae los servicios que necesita. Dentro de un ítem se respetan fases:
  desconexiones (plomería, electricidad), luego enchape, luego carpintería y al final
  retoques de pintura. Ítems distintos son independientes.
- El país de la dirección define la moneda y es la clave del tope en el acuerdo.
- `priority` (standard | express) es la clave del SLA.
- Recibe webhooks `installation.*`, incluido el avance de cada paso.

Ejemplo de solicitud:

    {
      "event": "installation.requested",
      "order_id": "MH-55012",
      "priority": "express",
      "customer_address": {"country": "CO", "city": "Medellin", "line1": "Calle 10 # 43-20"},
      "items": [
        {"sku": "COC-INT-01", "name": "Cocina integral",
         "services": ["plumbing_disconnect", "carpentry_install", "paint_touchup"]}
      ]
    }
"""

import json
from collections import defaultdict
from typing import Any

from app.aplicacion.dtos import (
    EstadoTrabajoDePartner,
    EventoDeTrabajoRecibido,
    RespuestaDePartner,
    SolicitudDePartner,
    SubTrabajoSolicitado,
    TrabajoDePartnerDTO,
)
from app.aplicacion.errores import SolicitudDePartnerInvalidaError

from .base import AdaptadorDePartnerBase, campo, leer_json, traducir_valor
from .mensaje import MensajeParaPartner

MEDIA_TYPE = "application/json"
EVENTO_DE_SOLICITUD = "installation.requested"

# servicio del comercio: (categoría en HdA, fase dentro del ítem)
SERVICIOS = {
    "plumbing_disconnect": ("Plomeria", 1),
    "electrical_disconnect": ("Electricidad", 1),
    "tiling": ("Baldoseria", 2),
    "carpentry_install": ("Carpinteria", 3),
    "paint_touchup": ("Pintura", 4),
}

URGENCIA_POR_PRIORIDAD = {"STANDARD": "Media", "EXPRESS": "Alta"}
MONEDA_POR_PAIS = {"CO": "COP", "MX": "MXN"}

STATUS_DEL_TRABAJO = {
    EstadoTrabajoDePartner.SOLICITADO: "received",
    EstadoTrabajoDePartner.CREADO: "scheduled",
    EstadoTrabajoDePartner.EN_EJECUCION: "in_progress",
    EstadoTrabajoDePartner.CERRADO: "completed",
    EstadoTrabajoDePartner.CANCELADO: "cancelled",
    EstadoTrabajoDePartner.RECHAZADO: "rejected",
}

STATUS_DEL_PASO = {
    "Bloqueado": "waiting",
    "Pendiente": "pending",
    "Asignado": "assigned",
    "EnEjecucion": "in_progress",
    "Completado": "done",
    "Cancelado": "cancelled",
}


class MueblesHogarAdapter(AdaptadorDePartnerBase):
    PARTNER_ID = "muebles-hogar"

    def traducir_solicitud(self, contenido: str) -> SolicitudDePartner:
        datos = leer_json(contenido)
        evento = campo(datos, "event")
        if evento != EVENTO_DE_SOLICITUD:
            raise SolicitudDePartnerInvalidaError(f"Webhook no soportado: {evento}")
        direccion = campo(datos, "customer_address", dict)
        pais = campo(direccion, "country").upper()
        prioridad = campo(datos, "priority").upper()
        items = campo(datos, "items", list)
        if not items:
            raise SolicitudDePartnerInvalidaError("La orden no trae ítems para instalar")

        sub_trabajos: list[SubTrabajoSolicitado] = []
        nombres: list[str] = []
        for item in items:
            if not isinstance(item, dict):
                raise SolicitudDePartnerInvalidaError("Cada ítem debe ser un objeto")
            nombres.append(campo(item, "name"))
            sub_trabajos.extend(self._instalacion(item))

        return SolicitudDePartner(
            referencia_externa=campo(datos, "order_id"),
            descripcion="Instalación de " + ", ".join(nombres),
            urgencia=traducir_valor(URGENCIA_POR_PRIORIDAD, prioridad, "Prioridad"),
            pais=pais,
            ciudad=campo(direccion, "city"),
            direccion=campo(direccion, "line1"),
            moneda=traducir_valor(MONEDA_POR_PAIS, pais, "País"),
            sub_trabajos=tuple(sub_trabajos),
            clave_sla=prioridad,
            clave_tope=pais,
        )

    def traducir_estado(self, trabajo: TrabajoDePartnerDTO) -> RespuestaDePartner:
        cuerpo: dict[str, Any] = {
            "order_id": trabajo.referencia_externa,
            "hda_job_id": trabajo.trabajo_id,
            "status": STATUS_DEL_TRABAJO[trabajo.estado],
            "steps": [
                {
                    "step_id": sub.id,
                    "trade": sub.categoria,
                    "status": STATUS_DEL_PASO.get(sub.estado, sub.estado),
                }
                for sub in trabajo.sub_trabajos
            ],
        }
        if trabajo.motivo_rechazo:
            cuerpo["rejection_reason"] = trabajo.motivo_rechazo
        return RespuestaDePartner(json.dumps(cuerpo, ensure_ascii=False), MEDIA_TYPE)

    def traducir_evento(self, evento: EventoDeTrabajoRecibido) -> MensajeParaPartner | None:
        datos_evento = evento.datos
        datos: dict[str, Any]
        if evento.nombre == "SubTrabajoCompletadoV1":
            nombre = "installation.step_completed"
            datos = {"step_id": datos_evento["sub_trabajo_id"], "evidence": list(datos_evento["evidencias"])}
        elif evento.nombre == "TrabajoRediagnosticadoV1":
            nombre = "installation.rescheduled"
            datos = {"reason": datos_evento["hallazgo"], "new_step_id": datos_evento["sub_trabajo_agregado_id"]}
        elif evento.nombre == "TrabajoCanceladoV1":
            nombre, datos = "installation.cancelled", {"reason": datos_evento["motivo"]}
        elif evento.nombre == "TrabajoCerradoV1":
            nombre = "installation.completed"
            datos = {"total": datos_evento["costo_total"], "currency": datos_evento["moneda"]}
        elif evento.nombre == "CreacionDeTrabajoRechazadaV1":
            nombre, datos = "installation.rejected", {"reason": datos_evento["motivo"]}
        else:
            return None
        cuerpo = {
            "event": nombre,
            "order_id": evento.referencia_externa,
            "occurred_at": evento.occurred_at,
            "hda_event_id": evento.event_id,
            "data": datos,
        }
        return MensajeParaPartner(nombre, json.dumps(cuerpo, ensure_ascii=False), MEDIA_TYPE)

    @staticmethod
    def _instalacion(item: dict[str, Any]) -> list[SubTrabajoSolicitado]:
        sku = campo(item, "sku")
        nombre = campo(item, "name")
        servicios = campo(item, "services", list)
        if not servicios:
            raise SolicitudDePartnerInvalidaError(f"El ítem {sku} no trae servicios")

        por_fase: dict[int, list[tuple[str, str]]] = defaultdict(list)
        for servicio in servicios:
            if not isinstance(servicio, str):
                raise SolicitudDePartnerInvalidaError(f"Servicio inválido en el ítem {sku}")
            categoria, fase = traducir_valor(SERVICIOS, servicio, "Servicio")
            por_fase[fase].append((servicio, categoria))

        sub_trabajos: list[SubTrabajoSolicitado] = []
        fase_anterior: tuple[str, ...] = ()
        for fase in sorted(por_fase):
            claves: list[str] = []
            for servicio, categoria in por_fase[fase]:
                clave = f"{sku}:{servicio}"
                sub_trabajos.append(
                    SubTrabajoSolicitado(
                        clave=clave,
                        categoria=categoria,
                        descripcion=f"{nombre}: {servicio.replace('_', ' ')}",
                        depende_de=fase_anterior,
                    )
                )
                claves.append(clave)
            fase_anterior = tuple(claves)
        return sub_trabajos
