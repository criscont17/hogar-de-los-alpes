"""Piezas compartidas por los tres experimentos de calidad sobre la saga.

Los experimentos de elasticidad, disponibilidad y consistencia miden el sistema
desde afuera: hablan HTTP con las APIs, no con Pulsar. Esa es la vista que tiene
un cliente real, y es la única que sirve para afirmar algo sobre latencia
percibida o sobre dinero cuadrado.

La entrada preferida es el gateway (`http://127.0.0.1:80/trabajos`, `/pagos`,
`/wallet`), que es lo que está publicado en la VM de EC2. Si no responde —por
ejemplo cuando solo se levantaron algunos servicios— se cae a los puertos
directos. Se usa `127.0.0.1` y no `localhost` a propósito: los puertos internos
solo están ligados a IPv4 y un cliente que resuelva `localhost` pierde unos dos
segundos por petición intentando `::1` primero, lo que arruinaría cualquier
medición de latencia.
"""

from __future__ import annotations

import csv
import json
import math
import os
import time
import urllib.error
import urllib.request
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

RAIZ_REPOSITORIO = Path(__file__).resolve().parents[2]
ARCHIVO_COMPOSE = RAIZ_REPOSITORIO / "docker-compose.yml"

# OperacionesBC asigna siempre este proveedor en el paso 3 y WalletBC le siembra
# billetera al arrancar: es la contraparte de toda acreditación de la saga y, por
# lo tanto, la cuenta que audita el experimento de consistencia.
PROVEEDOR_DE_LA_SAGA = "prov-hda-expert-01"

ESTADOS_FINALES = frozenset({"COMPLETADA_EXITOSA", "COMPENSADA", "EN_DISPUTA", "FALLIDA"})

# Los pasos que `POST /sagas/activar-servicio` sabe hacer fallar a propósito.
FALLOS_SIMULABLES = ("PAGO", "OPERACIONES", "EJECUCION", "WALLET")

TIEMPO_ESPERA_HTTP = float(os.getenv("EXPERIMENTOS_TIMEOUT_HTTP", "20"))
PUERTO_GATEWAY = os.getenv("PUERTO_GATEWAY", "80")


# --- Cliente HTTP mínimo ---------------------------------------------------------
# Se usa la biblioteca estándar y no `requests` para que los experimentos corran
# en la VM recién aprovisionada sin instalar nada.


@dataclass(frozen=True)
class Respuesta:
    codigo: int
    """Código HTTP, o 0 si la petición no llegó a completarse."""

    cuerpo: dict | list
    latencia_ms: float

    @property
    def ok(self) -> bool:
        return 200 <= self.codigo < 300


def pedir(
    url: str,
    metodo: str = "GET",
    datos: dict | None = None,
    timeout: float = TIEMPO_ESPERA_HTTP,
) -> Respuesta:
    cuerpo = json.dumps(datos).encode("utf-8") if datos is not None else None
    cabeceras = {"Content-Type": "application/json"} if datos is not None else {}
    peticion = urllib.request.Request(url, data=cuerpo, headers=cabeceras, method=metodo)

    inicio = time.perf_counter()
    try:
        with urllib.request.urlopen(peticion, timeout=timeout) as respuesta:
            texto = respuesta.read().decode("utf-8")
            latencia = (time.perf_counter() - inicio) * 1000
            return Respuesta(respuesta.status, json.loads(texto) if texto else {}, latencia)
    except urllib.error.HTTPError as error:
        texto = error.read().decode("utf-8", errors="replace")
        latencia = (time.perf_counter() - inicio) * 1000
        try:
            detalle = json.loads(texto) if texto else {}
        except json.JSONDecodeError:
            detalle = {"detalle": texto}
        return Respuesta(error.code, detalle, latencia)
    except Exception as error:  # timeout, conexión rechazada, DNS…
        latencia = (time.perf_counter() - inicio) * 1000
        return Respuesta(0, {"error": f"{type(error).__name__}: {error}"}, latencia)


# --- Resolución de endpoints -----------------------------------------------------


@dataclass(frozen=True)
class Endpoints:
    trabajos: str
    pagos: str
    wallet: str
    via: str

    @property
    def sagas(self) -> str:
        return f"{self.trabajos}/sagas"


def _endpoints_por_gateway() -> Endpoints:
    base = f"http://127.0.0.1:{PUERTO_GATEWAY}"
    return Endpoints(f"{base}/trabajos", f"{base}/pagos", f"{base}/wallet", "gateway")


def _endpoints_directos() -> Endpoints:
    return Endpoints(
        "http://127.0.0.1:8001",
        "http://127.0.0.1:8003",
        "http://127.0.0.1:8000",
        "puertos directos",
    )


def resolver_endpoints(via: str = "auto") -> Endpoints:
    """Devuelve por dónde hablarle al stack, comprobando que responda.

    `via` acepta `auto` (gateway y, si no, puertos directos), `gateway` o
    `directo`. Falla con un mensaje accionable en vez de dejar que cada petición
    del experimento se caiga por separado.
    """

    candidatos: list[Endpoints]
    if via == "gateway":
        candidatos = [_endpoints_por_gateway()]
    elif via == "directo":
        candidatos = [_endpoints_directos()]
    elif via == "auto":
        candidatos = [_endpoints_por_gateway(), _endpoints_directos()]
    else:
        raise ValueError(f"via debe ser auto, gateway o directo; llegó {via!r}")

    for endpoints in candidatos:
        # Listar sagas prueba justo lo que el experimento necesita: que la API del
        # orquestador responda y que su base esté disponible.
        if pedir(f"{endpoints.sagas}?limite=1", timeout=5).ok:
            return endpoints

    raise RuntimeError(
        "No respondió ni el gateway ni los puertos directos. Levante el stack con "
        "`docker compose up -d --build --wait` desde la raíz del repositorio. "
        f"Si el gateway no está en el puerto {PUERTO_GATEWAY}, exporte PUERTO_GATEWAY."
    )


def resolver_endpoints_o_salir(via: str = "auto") -> Endpoints:
    """Igual que `resolver_endpoints`, pero sin volcarle una traza al usuario."""

    try:
        return resolver_endpoints(via)
    except RuntimeError as error:
        raise SystemExit(f"\n  {error}\n") from None


# --- Operaciones de saga ---------------------------------------------------------


def iniciar_saga(
    endpoints: Endpoints,
    *,
    monto: float,
    cliente_id: str,
    referencia_externa: str,
    descripcion: str = "Servicio sintético del experimento de calidad",
    partner_id: str = "seguros-bolivar",
    simular_fallo_en_paso: str | None = None,
    timeout: float = TIEMPO_ESPERA_HTTP,
) -> Respuesta:
    return pedir(
        f"{endpoints.sagas}/activar-servicio",
        "POST",
        {
            "cliente_id": cliente_id,
            "descripcion": descripcion,
            "pais": "CO",
            "ciudad": "Bogotá",
            "direccion": "Carrera 7 # 72-10",
            "moneda": "COP",
            "monto_estimado": monto,
            "partner_id": partner_id,
            "referencia_externa": referencia_externa,
            "simular_fallo_en_paso": simular_fallo_en_paso,
        },
        timeout=timeout,
    )


def consultar_saga(endpoints: Endpoints, saga_id: str, timeout: float = TIEMPO_ESPERA_HTTP) -> dict:
    respuesta = pedir(f"{endpoints.sagas}/{saga_id}", timeout=timeout)
    return respuesta.cuerpo if respuesta.ok and isinstance(respuesta.cuerpo, dict) else {}


def es_final(estado: str | None) -> bool:
    return estado in ESTADOS_FINALES


def paso_donde_quedo(saga: dict) -> str:
    """Último paso del Saga Log que quedó sin cerrar. Ubica dónde se detuvo."""

    for paso in saga.get("pasos", []):
        if paso.get("estado_paso") in {"EN_PROCESO", "INICIADO", "PENDIENTE"}:
            return f"{paso.get('paso_numero')}:{paso.get('nombre_paso')}"
    return saga.get("paso_actual", "?")


# --- Estadística y salida --------------------------------------------------------


def percentil(valores: Sequence[float], p: float) -> float:
    """Percentil por rango más cercano (el mismo criterio que usa k6)."""

    if not valores:
        return 0.0
    ordenados = sorted(valores)
    posicion = max(math.ceil(p / 100 * len(ordenados)) - 1, 0)
    return ordenados[min(posicion, len(ordenados) - 1)]


def parsear_fecha(texto: str | None) -> datetime | None:
    if not texto:
        return None
    try:
        fecha = datetime.fromisoformat(texto)
    except ValueError:
        return None
    # Postgres devuelve timestamptz y SQLite fechas ingenuas: se normaliza a UTC
    # para poder restarlas sin excepciones.
    return fecha if fecha.tzinfo else fecha.replace(tzinfo=timezone.utc)


def duracion_segundos(saga: dict) -> float | None:
    """Cuánto tardó la saga según sus propias marcas de tiempo.

    Se miden en el servidor, así que no incluyen el ida y vuelta HTTP ni el
    intervalo del sondeo del experimento: es la latencia real de la transacción
    distribuida.
    """

    inicio = parsear_fecha(saga.get("fecha_creacion"))
    fin = parsear_fecha(saga.get("fecha_actualizacion"))
    if inicio is None or fin is None:
        return None
    return max((fin - inicio).total_seconds(), 0.0)


def marca_de_tiempo() -> str:
    return datetime.now().strftime("%Y%m%d-%H%M%S")


def escribir_csv(ruta: Path, encabezados: Sequence[str], filas: Iterable[Sequence]) -> Path:
    ruta.parent.mkdir(parents=True, exist_ok=True)
    with ruta.open("w", newline="", encoding="utf-8") as archivo:
        escritor = csv.writer(archivo)
        escritor.writerow(encabezados)
        escritor.writerows(filas)
    return ruta


def titulo(texto: str) -> None:
    print()
    print("=" * 78)
    print(f"  {texto}")
    print("=" * 78)


def fila_metrica(etiqueta: str, valor: object, meta: str = "") -> None:
    sufijo = f"   (meta: {meta})" if meta else ""
    print(f"  {etiqueta:<42} {valor}{sufijo}")


def veredicto(etiqueta: str, cumple: bool) -> None:
    print(f"  {etiqueta:<42} {'CUMPLE' if cumple else 'NO CUMPLE'}")
