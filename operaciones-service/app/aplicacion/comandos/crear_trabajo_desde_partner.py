from dataclasses import dataclass
from datetime import datetime, timezone

from app.aplicacion.carga import cargar_partner
from app.aplicacion.dtos import (
    EstadoTrabajoDePartner,
    ResultadoDeSolicitudDTO,
    SolicitudDeCreacionDeTrabajo,
    TrabajoDePartnerDTO,
)
from app.aplicacion.puertos import (
    CatalogoDeAdaptadores,
    GestionDeTrabajos,
    TrabajosDePartnerRepository,
)
from app.dominio.partner.partner_repository import PartnerRepository


@dataclass(frozen=True)
class CrearTrabajoDesdePartnerCommand:
    partner_id: str
    contenido: str


class CrearTrabajoDesdePartnerHandler:
    """Caso de uso genérico para cualquier partner (`ICrearTrabajoDesdePartner`).

    1. El adaptador del partner traduce su formato al modelo canónico.
    2. El agregado `Partner` resuelve las condiciones de su acuerdo comercial.
    3. Se le pide a GestionDeTrabajosBC crear el trabajo; el agregado `Trabajo` vive allá.

    Depende de puertos, no de la API de ningún partner: integrar uno nuevo no lo modifica.
    """

    def __init__(
        self,
        partners: PartnerRepository,
        adaptadores: CatalogoDeAdaptadores,
        trabajos: TrabajosDePartnerRepository,
        gestion_de_trabajos: GestionDeTrabajos,
    ) -> None:
        self._partners = partners
        self._adaptadores = adaptadores
        self._trabajos = trabajos
        self._gestion_de_trabajos = gestion_de_trabajos

    def ejecutar(self, comando: CrearTrabajoDesdePartnerCommand) -> ResultadoDeSolicitudDTO:
        partner = cargar_partner(self._partners, comando.partner_id)
        partner_id = str(partner.id)
        adaptador = self._adaptadores.obtener(partner_id)
        solicitud = adaptador.traducir_solicitud(comando.contenido)

        existente = self._trabajos.obtener(partner_id, solicitud.referencia_externa)
        if existente is not None and existente.estado is not EstadoTrabajoDePartner.RECHAZADO:
            # Un partner reintenta cuando no recibe respuesta: no se vuelve a solicitar.
            return ResultadoDeSolicitudDTO(nueva=False, respuesta=adaptador.traducir_estado(existente))

        condiciones = partner.resolver_condiciones(
            solicitud.clave_sla, solicitud.clave_tope, solicitud.tope_solicitado
        )
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
        vigente = self._trabajos.registrar_solicitud(
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
        return ResultadoDeSolicitudDTO(nueva=True, respuesta=adaptador.traducir_estado(vigente))
