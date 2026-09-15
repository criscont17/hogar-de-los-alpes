from dataclasses import dataclass

from .evento_de_integracion_de_pago import EventoDeIntegracionDePago


@dataclass(frozen=True, kw_only=True)
class PagoConfirmadoV1(EventoDeIntegracionDePago):
    """Contrato que consumiría WalletBC (Conformist) para acreditar saldo al proveedor."""

    monto: str
    moneda: str
    psp: str
    referencia_psp: str
