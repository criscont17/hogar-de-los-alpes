from enum import Enum


class CanalDeOrigen(str, Enum):
    MARKETPLACE = "Marketplace"
    PARTNER = "Partner"
    SUSCRIPCION = "Suscripcion"


class Urgencia(str, Enum):
    BAJA = "Baja"
    MEDIA = "Media"
    ALTA = "Alta"
    EMERGENCIA = "Emergencia"


class Categoria(str, Enum):
    PLOMERIA = "Plomeria"
    ELECTRICIDAD = "Electricidad"
    CARPINTERIA = "Carpinteria"
    PINTURA = "Pintura"
    BALDOSERIA = "Baldoseria"


class EstadoTrabajo(str, Enum):
    CREADO = "Creado"
    EN_EJECUCION = "EnEjecucion"
    CERRADO = "Cerrado"
    CANCELADO = "Cancelado"


class EstadoSubTrabajo(str, Enum):
    BLOQUEADO = "Bloqueado"
    PENDIENTE = "Pendiente"
    ASIGNADO = "Asignado"
    EN_EJECUCION = "EnEjecucion"
    COMPLETADO = "Completado"
    CANCELADO = "Cancelado"
