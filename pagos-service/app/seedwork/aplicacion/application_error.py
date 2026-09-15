class ApplicationError(Exception):
    """Error de un caso de uso que no proviene de una regla del dominio.

    Por ejemplo, un evento de cierre de trabajo con una liquidación que no se
    pudo traducir a un comando de creación de pago.
    """
