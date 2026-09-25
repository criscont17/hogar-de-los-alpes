"""Carga de configuración del servicio.

Importar este módulo lee el `.env` del microservicio antes de que cualquier
adaptador consulte el entorno. La ruta se resuelve desde este archivo y no desde
el directorio de trabajo, así que el servicio arranca igual desde `wallet-service/`
o desde cualquier otro sitio.

Las variables ya presentes en el entorno tienen prioridad: `load_dotenv` no
sobrescribe, de modo que en despliegue basta exportarlas y el `.env` local se
ignora sin cambiar nada.
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
    "postgresql+psycopg://wallet:wallet@localhost:5432/wallet_db",
)

# Comandos y eventos de la Saga de Activación de Servicio. WalletBC es el último
# participante: recibe AcreditarProveedorV1 y responde con el resultado.
PULSAR_URL = _texto("PULSAR_URL", "pulsar://localhost:6650")
PULSAR_TOPICO_COMANDOS_WALLET = _texto(
    "PULSAR_TOPICO_COMANDOS_WALLET", "persistent://public/default/comandos-wallet"
)
PULSAR_TOPICO_EVENTOS_WALLET = _texto(
    "PULSAR_TOPICO_EVENTOS_WALLET", "persistent://public/default/eventos-wallet"
)
PULSAR_SUSCRIPCION_COMANDOS_WALLET = _texto(
    "PULSAR_SUSCRIPCION_COMANDOS_WALLET", "wallet-saga-comandos"
)
PULSAR_CONSUMIR_COMANDOS_WALLET = _booleano("PULSAR_CONSUMIR_COMANDOS_WALLET", False)

# Billeteras de demostración creadas al arrancar (ver `semilla.py`).
SEMBRAR_BILLETERAS = _booleano("SEMBRAR_BILLETERAS", True)

# Reintentos con backoff de la acreditación antes de declarar la disputa.
ACREDITACION_INTENTOS = int(_numero("ACREDITACION_INTENTOS", 3))
ACREDITACION_ESPERA_INICIAL_SEGUNDOS = _numero("ACREDITACION_ESPERA_INICIAL_SEGUNDOS", 0.5)
ACREDITACION_FACTOR_BACKOFF = _numero("ACREDITACION_FACTOR_BACKOFF", 2.0)
