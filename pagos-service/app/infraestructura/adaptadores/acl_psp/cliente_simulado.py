import logging

logger = logging.getLogger("pagos.psp")


class ClientePSPSimulado:
    """Hace las veces de la pasarela de pago real.

    En producción sería un cliente HTTP con timeout hacia PayU, Wompi o
    MercadoPago. Aquí permite simular tres comportamientos para observar el
    circuit breaker y la conciliación diferida del escenario de
    Interoperabilidad #7:

    - `disponible=False`: el PSP no responde (`ConnectionError`), como una
      caída real del proveedor externo.
    - una referencia terminada en `-TIMEOUT`: el PSP tarda más de lo tolerado
      (`TimeoutError`), sin necesidad de apagar todo el adaptador.
    - una referencia terminada en `-RECHAZAR`: el PSP sí respondió, pero
      declina la operación (fondos, fraude); no es una falla técnica.
    """

    def __init__(self, psp_id: str) -> None:
        self.psp_id = psp_id
        self.disponible = True
        self._procesados: list[dict] = []

    @property
    def procesados(self) -> tuple[dict, ...]:
        return tuple(self._procesados)

    def cobrar(self, monto, moneda: str, referencia: str) -> dict:
        if not self.disponible:
            raise ConnectionError(f"El PSP {self.psp_id} no responde")
        if referencia.endswith("-TIMEOUT"):
            raise TimeoutError(f"El PSP {self.psp_id} no confirmó la operación a tiempo")
        aprobado = not referencia.endswith("-RECHAZAR")
        respuesta = {
            "referencia": referencia,
            "monto": str(monto),
            "moneda": moneda,
            "aprobado": aprobado,
        }
        self._procesados.append(respuesta)
        logger.info(
            "psp=%s referencia=%s monto=%s %s aprobado=%s",
            self.psp_id,
            referencia,
            monto,
            moneda,
            aprobado,
        )
        return respuesta
