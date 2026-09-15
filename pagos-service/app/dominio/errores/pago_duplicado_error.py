from app.seedwork.dominio import DomainError


class PagoDuplicadoError(DomainError):
    """Ya existe un pago con esa referencia externa (idempotencia)."""
