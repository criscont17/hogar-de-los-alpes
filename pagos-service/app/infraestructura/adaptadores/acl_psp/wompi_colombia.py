"""Adaptador de Wompi Colombia: PSP por defecto para COP.

Wompi identifica la transacción con su propio prefijo y responde con
`data.status` (`APPROVED`/`DECLINED`/`ERROR`). La traducción vive aquí para
que el dominio de Pago no conozca ese esquema.
"""

from app.aplicacion.puertos import ResultadoPSP

from .base import AdaptadorDePSPBase


class WompiColombiaAdapter(AdaptadorDePSPBase):
    PSP_ID = "wompi-colombia"
    MONEDA = "COP"

    def _traducir(self, respuesta: dict) -> ResultadoPSP:
        status = "APPROVED" if respuesta["aprobado"] else "DECLINED"
        if status == "APPROVED":
            return ResultadoPSP(
                exitoso=True, referencia_psp=f"wompi-txn-{respuesta['referencia']}"
            )
        return ResultadoPSP(exitoso=False, referencia_psp=None, motivo="Wompi: DECLINED")
