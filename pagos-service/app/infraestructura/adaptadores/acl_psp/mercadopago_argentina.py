"""Adaptador de MercadoPago Argentina: PSP para ARS.

MercadoPago trabaja en pesos con decimales (no en centavos, a diferencia de
PayU/Wompi) y responde con `status` en minúsculas (`approved`/`rejected`).
"""

from app.aplicacion.puertos import ResultadoPSP

from .base import AdaptadorDePSPBase


class MercadoPagoArgentinaAdapter(AdaptadorDePSPBase):
    PSP_ID = "mercadopago-argentina"
    MONEDA = "ARS"

    def _traducir(self, respuesta: dict) -> ResultadoPSP:
        status = "approved" if respuesta["aprobado"] else "rejected"
        if status == "approved":
            return ResultadoPSP(
                exitoso=True, referencia_psp=f"mp-payment-{respuesta['referencia']}"
            )
        return ResultadoPSP(exitoso=False, referencia_psp=None, motivo="MercadoPago: rejected")
