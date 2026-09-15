from enum import Enum


class TipoPago(str, Enum):
    """Distingue el cobro al cliente (checkout) del pago a un proveedor (liquidación)."""

    COBRO_CLIENTE = "CobroCliente"
    PAGO_A_PROVEEDOR = "PagoAProveedor"


class EstadoPago(str, Enum):
    PENDIENTE = "Pendiente"
    CONFIRMADO = "Confirmado"
    RECHAZADO = "Rechazado"
    PENDIENTE_CONCILIACION = "PendienteDeConciliacion"
