"""Observabilidad de la bandeja de salida.

Sin estas rutas el patrón es invisible: los eventos pendientes solo se verían
entrando a la base. Sirven para verificar en una demostración que, con el broker
caído, nada se pierde —se acumula—, y para reencolar a mano lo que agotó sus
intentos.
"""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.infraestructura.adaptadores.salida.persistencia.db import obtener_sesion
from app.infraestructura.adaptadores.salida.persistencia.sqlalchemy_bandeja_de_salida import (
    SqlAlchemyBandejaDeSalida,
)

router = APIRouter(prefix="/outbox", tags=["Bandeja de salida"])

ESTADOS = ("PENDIENTE", "PUBLICADO", "FALLIDO")


@router.get("/resumen", summary="Conteo de eventos por estado")
def resumen(sesion: Session = Depends(obtener_sesion)):
    conteos = SqlAlchemyBandejaDeSalida(sesion).resumen()
    return {
        "conteos": conteos,
        # Lo que un operador mira primero: si crece, el broker no está recibiendo.
        "por_publicar": conteos["PENDIENTE"],
        "requieren_atencion": conteos["FALLIDO"],
    }


@router.get("", summary="Listar eventos de la bandeja de salida")
def listar(
    estado: str | None = Query(None, description=f"Filtra por estado: {', '.join(ESTADOS)}"),
    limite: int = Query(50, ge=1, le=200),
    sesion: Session = Depends(obtener_sesion),
):
    if estado is not None and estado not in ESTADOS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"estado debe ser uno de {', '.join(ESTADOS)}",
        )
    eventos = SqlAlchemyBandejaDeSalida(sesion).listar(estado=estado, limite=limite)
    return [
        {
            "event_id": str(evento.event_id),
            "tipo": evento.tipo,
            "estado": evento.estado,
            "clave_particion": evento.clave_particion,
            "intentos": evento.intentos,
            "error": evento.error,
            "fecha_creacion": evento.fecha_creacion.isoformat(),
            "disponible_desde": evento.disponible_desde.isoformat(),
            "fecha_publicacion": (
                evento.fecha_publicacion.isoformat() if evento.fecha_publicacion else None
            ),
        }
        for evento in eventos
    ]


@router.post("/{event_id}/reencolar", summary="Devolver a la cola un evento abandonado")
def reencolar(event_id: UUID, sesion: Session = Depends(obtener_sesion)):
    bandeja = SqlAlchemyBandejaDeSalida(sesion)
    if not bandeja.reencolar(event_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="El evento no existe o ya fue publicado",
        )
    sesion.commit()
    return {"event_id": str(event_id), "estado": "PENDIENTE"}
