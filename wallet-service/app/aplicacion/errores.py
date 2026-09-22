"""Errores propios de la capa de aplicación de WalletBC."""


class FalloSimuladoDeAcreditacionError(Exception):
    """Fallo forzado desde el comando de la saga para demostrar la política EN_DISPUTA.

    Se comporta como un fallo recuperable (equivale a una billetera bloqueada o a
    una caída de la pasarela interna), de modo que la acreditación agota sus
    reintentos antes de rendirse.
    """
