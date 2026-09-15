"""Carga de configuración del servicio.

Importar este módulo lee el `.env` del microservicio antes de que cualquier
adaptador consulte el entorno. La ruta se resuelve desde este archivo y no desde
el directorio de trabajo, así que el servicio arranca igual desde
`gestion-trabajos-service/` o desde cualquier otro sitio.

Las variables ya presentes en el entorno tienen prioridad: `load_dotenv` no
sobrescribe, de modo que en despliegue basta exportarlas.
"""

import os
from pathlib import Path

from dotenv import load_dotenv

RAIZ_SERVICIO = Path(__file__).resolve().parents[2]

load_dotenv(RAIZ_SERVICIO / ".env")


def _texto(nombre: str, por_defecto: str) -> str:
    return os.getenv(nombre, por_defecto).strip()


def _booleano(nombre: str, por_defecto: bool) -> bool:
    valor = os.getenv(nombre)
    if valor is None:
        return por_defecto
    return valor.strip().lower() in {"1", "true", "si", "sí", "yes"}


DATABASE_URL = _texto(
    "DATABASE_URL",
    "postgresql+psycopg://trabajos:trabajos@localhost:5433/trabajos_db",
)

# Adaptador del puerto MessageBroker: logging | pulsar | memoria
MESSAGE_BROKER = _texto("MESSAGE_BROKER", "logging").lower()
PULSAR_URL = _texto("PULSAR_URL", "pulsar://localhost:6650")
PULSAR_TOPICO_EVENTOS = _texto(
    "PULSAR_TOPICO_EVENTOS", "persistent://public/default/eventos-trabajo"
)
PULSAR_TOPICO_COMANDOS = _texto(
    "PULSAR_TOPICO_COMANDOS", "persistent://public/default/comandos-trabajo"
)
PULSAR_SUSCRIPCION_COMANDOS = _texto("PULSAR_SUSCRIPCION_COMANDOS", "gestion-trabajos")
PULSAR_CONSUMIR_COMANDOS = _booleano("PULSAR_CONSUMIR_COMANDOS", False)
