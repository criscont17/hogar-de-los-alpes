"""Rutas orientadas al proveedor: identifican la billetera por el proveedor dueño.

El identificador de la billetera es un detalle contable interno de WalletBC; quien
solicita un retiro (el BFF, una app del proveedor) conoce al proveedor y nada más.
"""

from fastapi import APIRouter, Depends

from app.aplicacion.comandos import RetirarSaldoProveedorHandler

from .dependencias import obtener_retiro_proveedor_handler
from .mappers import a_comando_retiro_proveedor, a_schema_billetera
from .schemas import BilleteraResponseSchema, RetiroProveedorRequestSchema

router = APIRouter(prefix="/proveedores", tags=["Retiros del proveedor"])


@router.post(
    "/{proveedor_id}/wallet/retiros",
    response_model=BilleteraResponseSchema,
    summary="Solicitar un retiro del saldo del proveedor",
)
def solicitar_retiro(
    proveedor_id: str,
    schema: RetiroProveedorRequestSchema,
    handler: RetirarSaldoProveedorHandler = Depends(obtener_retiro_proveedor_handler),
) -> BilleteraResponseSchema:
    return a_schema_billetera(
        handler.ejecutar(a_comando_retiro_proveedor(proveedor_id, schema))
    )
