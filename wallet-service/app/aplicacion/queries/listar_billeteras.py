from dataclasses import dataclass

from app.aplicacion.dtos import PaginaBilleterasDTO
from app.aplicacion.mapeo import billetera_a_detalle_dto
from app.dominio.billetera import EstadoBilletera
from app.dominio.billetera.billetera_repository import BilleteraRepository

LIMITE_MAXIMO = 200


@dataclass(frozen=True)
class ListarBilleterasQuery:
    estado: str | None = None
    proveedor_id: str | None = None
    limite: int = 50
    desplazamiento: int = 0


class ListarBilleterasHandler:
    def __init__(self, repo: BilleteraRepository) -> None:
        self._repo = repo

    def ejecutar(self, query: ListarBilleterasQuery) -> PaginaBilleterasDTO:
        estado = EstadoBilletera(query.estado) if query.estado else None
        limite = self._validar_limite(query.limite)
        desplazamiento = self._validar_desplazamiento(query.desplazamiento)
        proveedor_id = query.proveedor_id.strip() if query.proveedor_id else None
        billeteras = self._repo.listar(
            estado=estado,
            proveedor_id=proveedor_id,
            limite=limite,
            desplazamiento=desplazamiento,
        )
        return PaginaBilleterasDTO(
            items=[billetera_a_detalle_dto(item) for item in billeteras],
            total=self._repo.contar(estado=estado, proveedor_id=proveedor_id),
            limite=limite,
            desplazamiento=desplazamiento,
        )

    @staticmethod
    def _validar_limite(limite: int) -> int:
        if limite < 1 or limite > LIMITE_MAXIMO:
            raise ValueError(f"limite debe estar entre 1 y {LIMITE_MAXIMO}")
        return limite

    @staticmethod
    def _validar_desplazamiento(desplazamiento: int) -> int:
        if desplazamiento < 0:
            raise ValueError("desplazamiento no puede ser negativo")
        return desplazamiento
