from enum import Enum


class TipoMovimiento(str, Enum):
    CREDITO = "Credito"
    DEBITO = "Debito"


class MotivoMovimiento(str, Enum):
    PAGO_DE_TRABAJO = "PagoDeTrabajo"
    RETIRO_A_PROVEEDOR = "RetiroAProveedor"
    AJUSTE_MANUAL = "AjusteManual"
    REVERSO = "Reverso"


class EstadoBilletera(str, Enum):
    ACTIVA = "Activa"
    SUSPENDIDA = "Suspendida"
