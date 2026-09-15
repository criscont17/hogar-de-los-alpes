from app.seedwork.dominio import DomainError


class PagoNoEncontradoError(DomainError):
    """No existe un pago con el identificador solicitado."""
