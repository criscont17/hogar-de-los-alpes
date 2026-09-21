from app.seedwork.aplicacion import ApplicationError


class AdaptadorNoDisponibleError(ApplicationError):
    """El partner tiene acuerdo, pero HdA aún no tiene un adaptador para su formato."""


class SolicitudDePartnerInvalidaError(ApplicationError):
    """La capa anti-corrupción no pudo traducir la solicitud completa al modelo canónico."""


class TrabajoDePartnerNoEncontradoError(ApplicationError):
    pass


class GestionDeTrabajosNoDisponibleError(ApplicationError):
    """No se pudo entregar la solicitud a GestionDeTrabajosBC; el partner puede reintentar."""


class SolicitudYaRegistradaError(ApplicationError):
    """Otro proceso registró la vista del trabajo mientras se escribía esta."""
