"""Adaptador de Seguros de los Alpes: aseguradora con API REST propia en JSON.

Solo traduce formato. El tope de cada plan de póliza, el SLA de cada prioridad y la red
homologada están en el acuerdo comercial del partner (agregado `Partner`).

Particularidades del formato:
- Identifica el trabajo por `numeroSiniestro` y lo cubierto por `coberturas`, con códigos
  propios (COB-PLOM, COB-PINT...). Una cobertura puede exigir que otra termine antes
  (`requiereTerminar`).
- `poliza.plan` y `prioridad` son las claves que su acuerdo usa para el tope y el SLA.
- Recibe novedades como JSON con `tipoNovedad`.

Ejemplo de solicitud:

    {
      "numeroSiniestro": "SA-2026-000123",
      "poliza": {"numero": "H-88231", "plan": "PLUS"},
      "prioridad": "ALTA",
      "descripcionSiniestro": "Calentador estalló y humedeció el muro",
      "predio": {"pais": "CO", "ciudad": "Bogota", "direccion": "Cra 7 # 45-10"},
      "coberturas": [
        {"codigo": "COB-PLOM", "detalle": "Reparar tubería del calentador"},
        {"codigo": "COB-PINT", "detalle": "Resanar y pintar muro",
         "requiereTerminar": ["COB-PLOM"]}
      ]
    }
"""

import json
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

CATEGORIA_POR_COBERTURA = {
    "COB-PLOM": "Plomeria",
    "COB-ELEC": "Electricidad",
    "COB-CARP": "Carpinteria",
    "COB-PINT": "Pintura",
    "COB-BALD": "Baldoseria",
}
COBERTURA_POR_CATEGORIA = {categoria: codigo for codigo, categoria in CATEGORIA_POR_COBERTURA.items()}

URGENCIA_POR_PRIORIDAD = {
    "CRITICA": "Emergencia",
    "ALTA": "Alta",
    "MEDIA": "Media",
    "BAJA": "Baja",
}

ESTADO_PARA_EL_PARTNER = {
    EstadoTrabajoDePartner.SOLICITADO: "RECIBIDO",
    EstadoTrabajoDePartner.CREADO: "RECIBIDO",
    EstadoTrabajoDePartner.EN_EJECUCION: "EN_ATENCION",
    EstadoTrabajoDePartner.CERRADO: "FINALIZADO",
    EstadoTrabajoDePartner.CANCELADO: "ANULADO",
    EstadoTrabajoDePartner.RECHAZADO: "RECHAZADO",
}


class SegurosAlpesAdapter(AdaptadorDePartnerBase):
    PARTNER_ID = "seguros-alpes"

    def traducir_solicitud(self, contenido: str) -> SolicitudDePartner:
        datos = leer_json(contenido)
        poliza = campo(datos, "poliza", dict)
        predio = campo(datos, "predio", dict)
        coberturas = campo(datos, "coberturas", list)
        if not coberturas:
            raise SolicitudDePartnerInvalidaError("El siniestro no trae coberturas")
        prioridad = campo(datos, "prioridad").upper()
        return SolicitudDePartner(
            referencia_externa=campo(datos, "numeroSiniestro"),
            descripcion=campo(datos, "descripcionSiniestro"),
            urgencia=traducir_valor(URGENCIA_POR_PRIORIDAD, prioridad, "Prioridad"),
            pais=campo(predio, "pais"),
            ciudad=campo(predio, "ciudad"),
            direccion=campo(predio, "direccion"),
            moneda="COP",
            sub_trabajos=tuple(self._sub_trabajo(cobertura) for cobertura in coberturas),
            clave_sla=prioridad,
            clave_tope=campo(poliza, "plan").upper(),
        )

    def traducir_estado(self, trabajo: TrabajoDePartnerDTO) -> RespuestaDePartner:
        cuerpo: dict[str, Any] = {
            "numeroSiniestro": trabajo.referencia_externa,
            "idTrabajoHdA": trabajo.trabajo_id,
            "estado": ESTADO_PARA_EL_PARTNER[trabajo.estado],
            "coberturas": [
                {
                    "codigo": COBERTURA_POR_CATEGORIA.get(sub.categoria, "SIN-COBERTURA"),
                    "estado": sub.estado,
                    "proveedor": sub.proveedor_id,
                }
                for sub in trabajo.sub_trabajos
            ],
            "costoAcumulado": str(trabajo.costo_total),
            "topePoliza": str(trabajo.monto_maximo) if trabajo.monto_maximo is not None else None,
            "slaHoras": trabajo.sla_horas,
            "moneda": trabajo.moneda,
        }
        if trabajo.motivo_rechazo:
            cuerpo["motivoRechazo"] = trabajo.motivo_rechazo
        return RespuestaDePartner(json.dumps(cuerpo, ensure_ascii=False), MEDIA_TYPE)

    def traducir_evento(self, evento: EventoDeTrabajoRecibido) -> MensajeParaPartner | None:
        datos = evento.datos
        detalle: dict[str, Any]
        if evento.nombre == "ProveedorAsignadoV1":
            tipo = "PROVEEDOR_ASIGNADO"
            detalle = {"proveedor": datos["proveedor_id"], "valorCotizado": datos["monto_cotizado"]}
        elif evento.nombre == "TrabajoRediagnosticadoV1":
            tipo = "CAMBIO_DE_ALCANCE"
            detalle = {
                "hallazgo": datos["hallazgo"],
                "coberturaAdicional": COBERTURA_POR_CATEGORIA.get(datos["categoria"], "SIN-COBERTURA"),
            }
        elif evento.nombre == "TrabajoCanceladoV1":
            tipo, detalle = "ANULACION", {"motivo": datos["motivo"]}
        elif evento.nombre == "TrabajoCerradoV1":
            tipo, detalle = "CIERRE", {"valorTotal": datos["costo_total"], "moneda": datos["moneda"]}
        elif evento.nombre == "CreacionDeTrabajoRechazadaV1":
            tipo, detalle = "RECHAZO", {"motivo": datos["motivo"]}
        else:
            return None
        cuerpo = {
            "numeroSiniestro": evento.referencia_externa,
            "tipoNovedad": tipo,
            "fechaNovedad": evento.occurred_at,
            "idEventoHdA": evento.event_id,
            **detalle,
        }
        return MensajeParaPartner(tipo, json.dumps(cuerpo, ensure_ascii=False), MEDIA_TYPE)

    @staticmethod
    def _sub_trabajo(cobertura: object) -> SubTrabajoSolicitado:
        if not isinstance(cobertura, dict):
            raise SolicitudDePartnerInvalidaError("Cada cobertura debe ser un objeto")
        codigo = campo(cobertura, "codigo").upper()
        requiere = cobertura.get("requiereTerminar", [])
        if not isinstance(requiere, list) or not all(isinstance(c, str) for c in requiere):
            raise SolicitudDePartnerInvalidaError("'requiereTerminar' debe ser una lista de códigos")
        return SubTrabajoSolicitado(
            clave=codigo,
            categoria=traducir_valor(CATEGORIA_POR_COBERTURA, codigo, "Cobertura"),
            descripcion=campo(cobertura, "detalle"),
            depende_de=tuple(c.upper() for c in requiere),
        )
