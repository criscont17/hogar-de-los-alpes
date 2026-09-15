"""Carga de configuración del servicio.

Importar este módulo lee el `.env` del microservicio antes de que cualquier
adaptador consulte el entorno. Las variables ya presentes en el entorno tienen
prioridad: `load_dotenv` no sobrescribe, de modo que en despliegue basta
exportarlas.
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


def _numero(nombre: str, por_defecto: float) -> float:
    valor = os.getenv(nombre)
    return por_defecto if valor is None else float(valor)


DATABASE_URL = _texto(
    "DATABASE_URL",
    "postgresql+psycopg://pagos:pagos@localhost:5435/pagos_db",
)

# Adaptador del puerto MessageBroker: logging | pulsar | memoria
MESSAGE_BROKER = _texto("MESSAGE_BROKER", "logging").lower()
PULSAR_URL = _texto("PULSAR_URL", "pulsar://localhost:6650")
PULSAR_TOPICO_EVENTOS_PAGO = _texto(
    "PULSAR_TOPICO_EVENTOS_PAGO", "persistent://public/default/eventos-pago"
)
PULSAR_TOPICO_EVENTOS_TRABAJO = _texto(
    "PULSAR_TOPICO_EVENTOS_TRABAJO", "persistent://public/default/eventos-trabajo"
)
PULSAR_SUSCRIPCION_EVENTOS_TRABAJO = _texto("PULSAR_SUSCRIPCION_EVENTOS_TRABAJO", "pagos-bc")
PULSAR_CONSUMIR_EVENTOS_TRABAJO = _booleano("PULSAR_CONSUMIR_EVENTOS_TRABAJO", False)

# Resiliencia de la integración con cada PSP
PSP_CB_UMBRAL_FALLOS = int(_numero("PSP_CB_UMBRAL_FALLOS", 3))
PSP_CB_RECUPERACION_SEGUNDOS = _numero("PSP_CB_RECUPERACION_SEGUNDOS", 10.0)
