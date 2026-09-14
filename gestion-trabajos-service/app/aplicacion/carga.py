from app.dominio.errores import TrabajoNoEncontradoError
from app.dominio.trabajo import Trabajo, TrabajoId
from app.dominio.trabajo.trabajo_repository import TrabajoRepository


def cargar_trabajo(repo: TrabajoRepository, trabajo_id: str) -> Trabajo:
    trabajo = repo.obtener_por_id(TrabajoId(trabajo_id))
    if trabajo is None:
        raise TrabajoNoEncontradoError("El trabajo no existe")
    return trabajo
