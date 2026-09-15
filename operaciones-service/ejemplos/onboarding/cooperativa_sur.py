"""Adaptador de Cooperativa Sur: partner listo para demostrar el onboarding.

NO está registrado. Integrar este partner (escenario de Modificabilidad #3) tiene dos partes:

1. Onboarding contractual, sin código: registrar su acuerdo con
   `PUT /partners/cooperativa-sur` usando `acuerdo_cooperativa_sur.json`.
2. Integración técnica, solo en OperacionesBC:
   - copiar este archivo a `app/infraestructura/adaptadores/acl_partners/cooperativa_sur.py`;
   - en `registro.py`, agregar `from .cooperativa_sur import CooperativaSurAdapter` y
     `CooperativaSurAdapter` al final de `ADAPTADORES_REGISTRADOS`;
   - reconstruir y reiniciar solo OperacionesBC.

GestionDeTrabajosBC no se modifica ni se redespliega.

Particularidades que solo conoce este archivo:
- Cooperativa de vivienda argentina que envía cada orden como una línea de texto plano:
  `referencia|ciudad|dirección|urgencia|pasos`.
- En `pasos`, `>` separa etapas en secuencia y `+` agrupa oficios en paralelo.
- `urgencia` (URGENTE | NORMAL) es la clave del SLA en su acuerdo; el tope es único por
  orden (clave `ORDEN`).
- Responde y recibe novedades también en texto plano.

Ejemplo de solicitud:

    CS-2026-0042|Buenos Aires|Av. Corrientes 1234|URGENTE|PLOM>ELEC+PINT
"""

from app.aplicacion.dtos import (
    EstadoTrabajoDePartner,
    EventoDeTrabajoRecibido,
    RespuestaDePartner,
    SolicitudDePartner,
    SubTrabajoSolicitado,
    TrabajoDePartnerDTO,
)
from app.aplicacion.errores import SolicitudDePartnerInvalidaError

from .base import AdaptadorDePartnerBase, traducir_valor
from .mensaje import MensajeParaPartner

MEDIA_TYPE = "text/plain"

CATEGORIA_POR_OFICIO = {
    "PLOM": "Plomeria",
    "ELEC": "Electricidad",
    "CARP": "Carpinteria",
    "PINT": "Pintura",
    "BALD": "Baldoseria",
}

URGENCIA_POR_CLAVE = {"URGENTE": "Alta", "NORMAL": "Media"}

ESTADO_PARA_EL_PARTNER = {
    EstadoTrabajoDePartner.SOLICITADO: "RECIBIDA",
    EstadoTrabajoDePartner.CREADO: "REGISTRADA",
    EstadoTrabajoDePartner.EN_EJECUCION: "EN_OBRA",
    EstadoTrabajoDePartner.CERRADO: "TERMINADA",
    EstadoTrabajoDePartner.CANCELADO: "ANULADA",
    EstadoTrabajoDePartner.RECHAZADO: "RECHAZADA",
}


class CooperativaSurAdapter(AdaptadorDePartnerBase):
    PARTNER_ID = "cooperativa-sur"

    def traducir_solicitud(self, contenido: str) -> SolicitudDePartner:
        campos = [campo.strip() for campo in contenido.strip().split("|")]
        if len(campos) != 5 or not all(campos):
            raise SolicitudDePartnerInvalidaError(
                "Se esperaba 'referencia|ciudad|dirección|urgencia|pasos'"
            )
        referencia, ciudad, direccion, urgencia, pasos = campos
        urgencia = urgencia.upper()

        sub_trabajos: list[SubTrabajoSolicitado] = []
        etapa_anterior: tuple[str, ...] = ()
        for numero, etapa in enumerate(pasos.split(">"), start=1):
            claves: list[str] = []
            for oficio in etapa.split("+"):
                oficio = oficio.strip().upper()
                categoria = traducir_valor(CATEGORIA_POR_OFICIO, oficio, "Oficio")
                clave = f"{numero}-{oficio}"
                sub_trabajos.append(
                    SubTrabajoSolicitado(
                        clave=clave,
                        categoria=categoria,
                        descripcion=f"{categoria} en {direccion}",
                        depende_de=etapa_anterior,
                    )
                )
                claves.append(clave)
            etapa_anterior = tuple(claves)

        return SolicitudDePartner(
            referencia_externa=referencia,
            descripcion=f"Orden de la cooperativa {referencia}",
            urgencia=traducir_valor(URGENCIA_POR_CLAVE, urgencia, "Urgencia"),
            pais="AR",
            ciudad=ciudad,
            direccion=direccion,
            moneda="ARS",
            sub_trabajos=tuple(sub_trabajos),
            clave_sla=urgencia,
            clave_tope="ORDEN",
        )

    def traducir_estado(self, trabajo: TrabajoDePartnerDTO) -> RespuestaDePartner:
        terminados = sum(1 for sub in trabajo.sub_trabajos if sub.estado == "Completado")
        contenido = "|".join(
            [
                trabajo.referencia_externa,
                ESTADO_PARA_EL_PARTNER[trabajo.estado],
                f"{terminados}/{len(trabajo.sub_trabajos)}",
                f"{trabajo.costo_total} {trabajo.moneda or ''}".strip(),
                trabajo.trabajo_id or "-",
            ]
        )
        return RespuestaDePartner(contenido, MEDIA_TYPE)

    def traducir_evento(self, evento: EventoDeTrabajoRecibido) -> MensajeParaPartner | None:
        datos = evento.datos
        if evento.nombre == "TrabajoCerradoV1":
            tipo, detalle = "TERMINADA", f"{datos['costo_total']} {datos['moneda']}"
        elif evento.nombre == "TrabajoCanceladoV1":
            tipo, detalle = "ANULADA", datos["motivo"]
        elif evento.nombre == "TrabajoRediagnosticadoV1":
            tipo, detalle = "NOVEDAD", datos["hallazgo"]
        elif evento.nombre == "CreacionDeTrabajoRechazadaV1":
            tipo, detalle = "RECHAZADA", datos["motivo"]
        else:
            return None
        return MensajeParaPartner(tipo, f"{evento.referencia_externa}|{tipo}|{detalle}", MEDIA_TYPE)
