class ApplicationError(Exception):
    """Error de un caso de uso que no proviene de una regla del dominio.

    Por ejemplo, un partner que no está registrado o una solicitud que la capa
    anti-corrupción no pudo traducir al modelo canónico.
    """
