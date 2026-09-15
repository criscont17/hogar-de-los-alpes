from app.seedwork.aplicacion import ApplicationError


class ConflictoDeConcurrenciaError(ApplicationError):
    """Otra operación modificó el trabajo entre su lectura y su guardado; se puede reintentar."""
