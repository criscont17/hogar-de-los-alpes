from app.seedwork.aplicacion import ApplicationError


class ConflictoDeConcurrenciaError(ApplicationError):
    """Otra operación modificó el pago entre su lectura y su guardado; se puede reintentar."""


class LiquidacionInvalidaError(ApplicationError):
    """El evento `TrabajoCerradoV1` trae una liquidación que no se pudo traducir
    a un comando de creación de pago (campo faltante o con un tipo inesperado)."""
