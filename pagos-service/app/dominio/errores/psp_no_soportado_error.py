from app.seedwork.dominio import DomainError


class PSPNoSoportadoError(DomainError):
    """No hay un adaptador de PSP registrado para la moneda o el identificador solicitado."""
