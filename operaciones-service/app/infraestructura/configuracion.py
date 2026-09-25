"""Carga de configuración del servicio.

Importar este módulo lee el `.env` del microservicio antes de que cualquier adaptador
consulte el entorno. Las variables ya presentes en el entorno tienen prioridad.
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
    "postgresql+psycopg://operaciones:operaciones@localhost:5434/operaciones_db",
)

# Adaptador hacia GestionDeTrabajosBC: pulsar | logging (sin Pulsar, solo registra el comando)
MESSAGE_BROKER = _texto("MESSAGE_BROKER", "logging").lower()
PULSAR_URL = _texto("PULSAR_URL", "pulsar://localhost:6650")
PULSAR_TOPICO_COMANDOS_TRABAJO = _texto(
    "PULSAR_TOPICO_COMANDOS_TRABAJO", "persistent://public/default/comandos-trabajo"
)
PULSAR_TOPICO_EVENTOS_TRABAJO = _texto(
    "PULSAR_TOPICO_EVENTOS_TRABAJO", "persistent://public/default/eventos-trabajo"
)
PULSAR_SUSCRIPCION_EVENTOS = _texto("PULSAR_SUSCRIPCION_EVENTOS", "operaciones-bc")
PULSAR_CONSUMIR_EVENTOS = _booleano("PULSAR_CONSUMIR_EVENTOS", False)

# Comandos y Eventos de Saga para OperacionesBC
PULSAR_TOPICO_COMANDOS_OPERACIONES = _texto(
    "PULSAR_TOPICO_COMANDOS_OPERACIONES", "persistent://public/default/comandos-operaciones"
)
PULSAR_TOPICO_EVENTOS_OPERACIONES = _texto(
    "PULSAR_TOPICO_EVENTOS_OPERACIONES", "persistent://public/default/eventos-operaciones"
)
PULSAR_SUSCRIPCION_COMANDOS_OPERACIONES = _texto(
    "PULSAR_SUSCRIPCION_COMANDOS_OPERACIONES", "operaciones-saga-comandos"
)
PULSAR_CONSUMIR_COMANDOS_OPERACIONES = _booleano("PULSAR_CONSUMIR_COMANDOS_OPERACIONES", True)

# Partners con acuerdo vigente que se registran al arrancar si no existen
SEMBRAR_PARTNERS = _booleano("SEMBRAR_PARTNERS", True)

# Resiliencia de la sincronización con cada partner B2B2C
PARTNER_CB_UMBRAL_FALLOS = int(_numero("PARTNER_CB_UMBRAL_FALLOS", 3))
PARTNER_CB_RECUPERACION_SEGUNDOS = _numero("PARTNER_CB_RECUPERACION_SEGUNDOS", 10.0)
PARTNER_SINCRONIZACION_ASINCRONA = _booleano("PARTNER_SINCRONIZACION_ASINCRONA", True)

