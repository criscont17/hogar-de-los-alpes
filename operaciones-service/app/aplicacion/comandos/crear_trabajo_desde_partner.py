from dataclasses import dataclass
from datetime import datetime, timezone

from app.aplicacion.carga import cargar_partner
from app.aplicacion.dtos import (
    EstadoTrabajoDePartner,
    ResultadoDeSolicitudDTO,
    SolicitudDeCreacionDeTrabajo,
    TrabajoDePartnerDTO,
)
from app.aplicacion.errores import SolicitudYaRegistradaError
from app.aplicacion.puertos import (
    CatalogoDeAdaptadores,
    GestionDeTrabajos,
    UnidadDeTrabajo,
)


@dataclass(frozen=True)
class CrearTrabajoDesdePartnerCommand:
    partner_id: str
    contenido: str


class CrearTrabajoDesdePartnerHandler:
    """Caso de uso generico para cualquier partner (`ICrearTrabajoDesdePartner`).

    1. El adaptador del partner traduce su formato al modelo canonico.
    2. El agregado `Partner` resuelve las condiciones de su acuerdo comercial.
    3. Se le pide a GestionDeTrabajosBC crear el trabajo; el agregado `Trabajo` vive alla.

    Depende de puertos, no de la API de ningun partner: integrar uno nuevo no lo modifica.
    El acuerdo y la vista del trabajo se leen y se escriben en la misma unidad de trabajo.
    """

    def __init__(
        self,
        uow: UnidadDeTrabajo,
        adaptadores: CatalogoDeAdaptadores,
        gestion_de_trabajos: GestionDeTrabajos,
    ) -> None:
        self._uow = uow
        self._adaptadores = adaptadores
        self._gestion_de_trabajos = gestion_de_trabajos

    def ejecutar(self, comando: CrearTrabajoDesdePartnerCommand) -> ResultadoDeSolicitudDTO:
        with self._uow as uow:
            partner = cargar_partner(uow.partners, comando.partner_id)
            partner_id = str(partner.id)
            adaptador = self._adaptadores.obtener(partner_id)
            solicitud = adaptador.traducir_solicitud(comando.contenido)

            existente = uow.trabajos.obtener(partner_id, solicitud.referencia_externa)
            if existente is not None and existente.estado is not EstadoTrabajoDePartner.RECHAZADO:
                # Un partner reintenta cuando no recibe respuesta: no se vuelve a solicitar.
                return ResultadoDeSolicitudDTO(
                    nueva=False, respuesta=adaptador.traducir_estado(existente)
                )

            condiciones = partner.resolver_condiciones(
                solicitud.clave_sla, solicitud.clave_tope, solicitud.tope_solicitado
            )
            # El comando sale antes de confirmar la vista. Si el envio falla, la unidad de
            # trabajo revierte y no queda una solicitud que nadie pidio; si falla el commit,
            # GestionDeTrabajosBC es idempotente por referencia y no duplica el trabajo.
            self._gestion_de_trabajos.solicitar_creacion(
                SolicitudDeCreacionDeTrabajo(
                    partner_id=partner_id,
                    referencia_externa=solicitud.referencia_externa,
                    descripcion=solicitud.descripcion,
                    urgencia=solicitud.urgencia,
                    pais=solicitud.pais,
                    ciudad=solicitud.ciudad,
                    direccion=solicitud.direccion,
                    moneda=solicitud.moneda,
                    sub_trabajos=solicitud.sub_trabajos,
                    sla_horas=condiciones.sla_horas,
                    monto_maximo=condiciones.monto_maximo,
                    proveedores_permitidos=condiciones.proveedores_permitidos,
                )
            )
            try:
                vigente = uow.trabajos.registrar_solicitud(
                    TrabajoDePartnerDTO(
                        partner_id=partner_id,
                        referencia_externa=solicitud.referencia_externa,
                        estado=EstadoTrabajoDePartner.SOLICITADO,
                        fecha_solicitud=datetime.now(timezone.utc),
                        moneda=solicitud.moneda,
                        monto_maximo=condiciones.monto_maximo,
                        sla_horas=condiciones.sla_horas,
                    )
                )
                uow.confirmar()
            except SolicitudYaRegistradaError:
                # El consumidor de eventos creo la vista con el primer evento del trabajo.
                uow.revertir()
                vigente = uow.trabajos.obtener(partner_id, solicitud.referencia_externa)
                if vigente is None:
                    raise
            return ResultadoDeSolicitudDTO(nueva=True, respuesta=adaptador.traducir_estado(vigente))
