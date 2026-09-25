import httpx

from app.config import TIMEOUT_SEGUNDOS, URL_GESTION_TRABAJOS, URL_WALLET


class ServicioNoDisponibleError(Exception):
    """El microservicio interno no respondió (caído, timeout o red)."""

    def __init__(self, servicio: str):
        self.servicio = servicio
        super().__init__(f"{servicio} no respondió")


def detalle_error(respuesta: httpx.Response):
    try:
        return respuesta.json()
    except ValueError:
        return respuesta.text


async def _pedir(base_url: str, servicio: str, metodo: str, ruta: str, **kwargs) -> httpx.Response:
    try:
        async with httpx.AsyncClient(base_url=base_url, timeout=TIMEOUT_SEGUNDOS) as cliente:
            return await cliente.request(metodo, ruta, **kwargs)
    except httpx.HTTPError as exc:
        raise ServicioNoDisponibleError(servicio) from exc


# --- GestionDeTrabajosBC: orquestador de la saga y dueño del agregado Trabajo ------


async def iniciar_saga(payload: dict) -> httpx.Response:
    return await _pedir(
        URL_GESTION_TRABAJOS, "gestion-trabajos-service", "POST", "/sagas/activar-servicio", json=payload
    )


async def obtener_saga(saga_id: str) -> httpx.Response:
    return await _pedir(URL_GESTION_TRABAJOS, "gestion-trabajos-service", "GET", f"/sagas/{saga_id}")


async def listar_sagas(limite: int = 20) -> httpx.Response:
    return await _pedir(
        URL_GESTION_TRABAJOS, "gestion-trabajos-service", "GET", "/sagas", params={"limite": limite}
    )


async def obtener_trabajo(trabajo_id: str) -> httpx.Response:
    return await _pedir(URL_GESTION_TRABAJOS, "gestion-trabajos-service", "GET", f"/trabajos/{trabajo_id}")


# --- WalletBC: saldo y movimientos del proveedor ------------------------------------


async def retirar_de_proveedor(proveedor_id: str, payload: dict) -> httpx.Response:
    """WalletBC resuelve la billetera del proveedor; el BFF no conoce su id contable."""

    return await _pedir(
        URL_WALLET,
        "wallet-service",
        "POST",
        f"/proveedores/{proveedor_id}/wallet/retiros",
        json=payload,
    )
