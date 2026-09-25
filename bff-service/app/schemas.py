from decimal import Decimal

from pydantic import BaseModel, Field


class IniciarTrabajoRequest(BaseModel):
    """Payload para arrancar la saga 'Completar y liquidar un Trabajo'.

    El trabajo todavía no existe: lo crea el propio orquestador como parte del
    Paso 1 de la saga, por eso no se recibe un trabajo_id (a diferencia del
    contrato original propuesto en el documento de arquitectura).
    """

    cliente_id: str
    descripcion: str
    pais: str = "CO"
    ciudad: str = "Bogotá"
    direccion: str = "Calle 100 # 15-20"
    moneda: str = "COP"
    monto_estimado: Decimal = Field(..., gt=0)
    partner_id: str | None = None
    referencia_externa: str | None = None
    simular_fallo_en_paso: str | None = Field(
        default=None,
        description=(
            "Solo para demos. 'PAGO', 'OPERACIONES' y 'EJECUCION' fuerzan el fallo de "
            "ese paso y disparan la compensación en orden inverso; 'WALLET' agota los "
            "reintentos de la acreditación y deja el trabajo EN_DISPUTA, sin revertir nada."
        ),
    )


class RetiroWalletRequest(BaseModel):
    monto: Decimal = Field(..., gt=0)
    motivo: str = Field(
        ...,
        description=(
            "Debe ser uno de los valores de MotivoMovimiento en WalletBC: "
            "'PagoDeTrabajo', 'RetiroAProveedor', 'AjusteManual' o 'Reverso'. "
            "El BFF no valida este enum (pertenece al dominio de WalletBC); "
            "un valor inválido se propaga tal cual como error 400."
        ),
    )
    referencia_externa: str | None = None
