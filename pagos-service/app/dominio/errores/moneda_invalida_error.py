from app.seedwork.dominio import DomainError


class MonedaInvalidaError(DomainError):
    """La moneda no es un código ISO de tres letras válido."""
