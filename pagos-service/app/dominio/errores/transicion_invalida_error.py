from app.seedwork.dominio import DomainError


class TransicionInvalidaError(DomainError):
    """El pago no puede pasar a ese estado desde su estado actual."""
