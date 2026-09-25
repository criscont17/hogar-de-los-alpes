"""Servicio de dominio que construye el flujo de un trabajo.

Un trabajo complejo es un grafo: lo que no depende de nada puede ejecutarse en
paralelo y lo que depende de otro sub-trabajo queda bloqueado hasta que este
termine ("no se instalan muebles si la tubería no está lista").
"""

from collections.abc import Sequence

from app.dominio.errores import FlujoInvalidoError

from .plan import SubTrabajoPlaneado


def ordenar_flujo(planeados: Sequence[SubTrabajoPlaneado]) -> list[SubTrabajoPlaneado]:
    """Valida el grafo de dependencias y lo devuelve en orden topológico.

    Rechaza claves repetidas, dependencias inexistentes, auto-dependencias y
    ciclos: un flujo con ciclo nunca terminaría. Entre sub-trabajos
    independientes se conserva el orden en que fueron solicitados.
    """

    if not planeados:
        raise FlujoInvalidoError("Un trabajo requiere al menos un sub-trabajo")

    por_clave: dict[str, SubTrabajoPlaneado] = {}
    for planeado in planeados:
        if planeado.clave in por_clave:
            raise FlujoInvalidoError(f"Clave de sub-trabajo repetida: {planeado.clave}")
        por_clave[planeado.clave] = planeado

    for planeado in planeados:
        for dependencia in planeado.depende_de:
            if dependencia == planeado.clave:
                raise FlujoInvalidoError(
                    f"El sub-trabajo '{planeado.clave}' no puede depender de sí mismo"
                )
            if dependencia not in por_clave:
                raise FlujoInvalidoError(
                    f"El sub-trabajo '{planeado.clave}' depende de '{dependencia}', "
                    "que no existe en la solicitud"
                )

    faltantes = {clave: set(planeado.depende_de) for clave, planeado in por_clave.items()}
    listos = [clave for clave, dependencias in faltantes.items() if not dependencias]
    ordenados: list[SubTrabajoPlaneado] = []
    while listos:
        clave = listos.pop(0)
        ordenados.append(por_clave[clave])
        for otra, dependencias in faltantes.items():
            if clave in dependencias:
                dependencias.discard(clave)
                if not dependencias:
                    listos.append(otra)

    if len(ordenados) != len(por_clave):
        raise FlujoInvalidoError("Las dependencias entre sub-trabajos forman un ciclo")
    return ordenados
