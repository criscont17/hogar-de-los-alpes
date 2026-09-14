from app.seedwork.aplicacion import ApplicationError


class PartnerNoRegistradoError(ApplicationError):
    pass


class SolicitudDePartnerInvalidaError(ApplicationError):
    """La capa anti-corrupción no pudo traducir la solicitud completa al modelo canónico."""


class ConflictoDeConcurrenciaError(ApplicationError):
    """Otra operación modificó el trabajo entre su lectura y su guardado; se puede reintentar."""
