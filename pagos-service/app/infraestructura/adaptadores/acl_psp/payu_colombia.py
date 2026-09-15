"""Adaptador de PayU Colombia: pasarela alterna para COP.

PayU liquida en centavos (`COP` sin decimales en su API real) y responde con un
código de estado propio (`APPROVED`/`DECLINED`) en vez de un booleano. La
traducción vive aquí para que el dominio de Pago jamás vea ese formato.
"""

from app.aplicacion.puertos import ResultadoPSP

from .base import AdaptadorDePSPBase


class PayUColombiaAdapter(AdaptadorDePSPBase):
    PSP_ID = "payu-colombia"
    MONEDA = "COP"

    def _traducir(self, respuesta: dict) -> ResultadoPSP:
        estado = "APPROVED" if respuesta["aprobado"] else "DECLINED"
        if estado == "APPROVED":
            return ResultadoPSP(
                exitoso=True, referencia_psp=f"payu-order-{respuesta['referencia']}"
            )
        return ResultadoPSP(exitoso=False, referencia_psp=None, motivo="PayU: DECLINED")
