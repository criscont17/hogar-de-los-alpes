from app.seedwork.dominio import DomainError


class MontoInvalidoError(DomainError):
    """El monto de un pago no es un número decimal válido, no positivo o infinito."""
