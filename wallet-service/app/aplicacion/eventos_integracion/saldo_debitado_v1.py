from dataclasses import dataclass

from app.seedwork.aplicacion import IntegrationEvent


@dataclass(frozen=True, kw_only=True)
class SaldoDebitadoV1(IntegrationEvent):
    billetera_id: str
    monto: str
    moneda: str
    motivo: str
    saldo_resultante: str
    fecha: str
    referencia_externa: str | None = None
