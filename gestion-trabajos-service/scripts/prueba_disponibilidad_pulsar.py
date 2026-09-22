"""Escenario de calidad — Disponibilidad: caída del broker con sagas en tránsito.

Derriba Apache Pulsar mientras hay sagas a medio camino y mide qué pasa con ellas
cuando el broker vuelve: cuántas quedan retenidas, cuántas avanzan solas y cuánto
tarda esa recuperación.

Hay dos formas de derribarlo y dan resultados deliberadamente distintos:

- `--modo pausa` (por defecto): `docker pause`. Congela el proceso del broker sin
  perder sus datos, que es lo que se parece a una partición de red o a una pausa
  de GC larga. Los mensajes ya publicados siguen en los ledgers, así que al
  reanudar deberían entregarse y las sagas continuar.
- `--modo caida`: `docker compose kill` + `up -d`. El Pulsar de este despliegue
  arranca en modo standalone con `rm -rf /pulsar/data/*` (ver `docker-compose.yml`),
  porque un bookie que cambia de dirección no puede recuperar sus ledgers. Es una
  decisión consciente para la POC, y su consecuencia es medible: los mensajes en
  tránsito se pierden y las sagas afectadas no se recuperan solas.

Un segundo límite que el experimento deja a la vista: el consumidor de eventos de
saga hace *ack* incluso cuando el manejo del evento lanza excepción
(`consumidor_eventos_saga_pulsar.py:82-87`). Si el orquestador no logra publicar
el comando siguiente porque el broker está caído, ese evento se confirma y se
pierde: la saga queda detenida en ese paso aunque el broker vuelva.

Uso (con el stack arriba, desde `gestion-trabajos-service/`):

    python -m scripts.prueba_disponibilidad_pulsar                      # pausa, 12 sagas
    python -m scripts.prueba_disponibilidad_pulsar --modo caida --num 20
    python -m scripts.prueba_disponibilidad_pulsar --espera-caido 40 --csv

Requiere permisos de Docker en la máquina (en EC2, el usuario en el grupo
`docker`), porque derriba el contenedor con `docker`/`docker compose`.
"""

from __future__ import annotations

import argparse
import subprocess
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path

from scripts.comun_experimentos import (
    ARCHIVO_COMPOSE,
    RAIZ_REPOSITORIO,
    Endpoints,
    consultar_saga,
    es_final,
    escribir_csv,
    fila_metrica,
    iniciar_saga,
    marca_de_tiempo,
    paso_donde_quedo,
    pedir,
    percentil,
    resolver_endpoints_o_salir,
    titulo,
    veredicto,
)

SERVICIO_BROKER = "pulsar"


# --- Control del contenedor ------------------------------------------------------


def _docker(*argumentos: str, timeout: float = 120) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["docker", *argumentos], capture_output=True, text=True, timeout=timeout
    )


def _compose(*argumentos: str, timeout: float = 240) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["docker", "compose", "-f", str(ARCHIVO_COMPOSE), *argumentos],
        capture_output=True,
        text=True,
        timeout=timeout,
        cwd=str(RAIZ_REPOSITORIO),
    )


def _id_del_broker() -> str:
    try:
        resultado = _compose("ps", "-q", SERVICIO_BROKER, timeout=60)
    except (FileNotFoundError, subprocess.SubprocessError) as error:
        raise SystemExit(
            f"\n  No se pudo hablar con Docker ({error}). Este experimento derriba el\n"
            "  contenedor de Pulsar, así que necesita el cliente de Docker disponible y\n"
            "  permisos para usarlo (en EC2, el usuario en el grupo `docker`).\n"
        ) from None

    identificador = resultado.stdout.strip().splitlines()
    if not identificador:
        raise SystemExit(
            "\n  No hay un contenedor de Pulsar corriendo para este compose.\n"
            "  Levante el stack con `docker compose up -d --build --wait`.\n"
        )
    return identificador[0]


def _salud_del_broker(identificador: str) -> str:
    resultado = _docker(
        "inspect", "--format", "{{.State.Health.Status}}", identificador, timeout=30
    )
    return resultado.stdout.strip() or "desconocida"


def _esperar_salud(identificador: str, segundos: float) -> float | None:
    """Espera a que el healthcheck del broker vuelva a `healthy`.

    Devuelve los segundos que tardó, o `None` si se agotó el plazo. El instante en
    que el broker vuelve a estar sano es el origen del tiempo de recuperación: lo
    que se mide después es responsabilidad de la arquitectura, no del broker.
    """

    inicio = time.perf_counter()
    limite = inicio + segundos
    while time.perf_counter() < limite:
        if _salud_del_broker(identificador) == "healthy":
            return time.perf_counter() - inicio
        time.sleep(2)
    return None


def _derribar(modo: str, identificador: str) -> None:
    if modo == "pausa":
        resultado = _docker("pause", identificador, timeout=60)
    else:
        resultado = _compose("kill", SERVICIO_BROKER, timeout=120)
    if resultado.returncode != 0:
        raise RuntimeError(f"No se pudo derribar el broker: {resultado.stderr.strip()}")


def _restablecer(modo: str, identificador: str) -> None:
    if modo == "pausa":
        resultado = _docker("unpause", identificador, timeout=60)
    else:
        resultado = _compose("up", "-d", SERVICIO_BROKER, timeout=300)
    if resultado.returncode != 0:
        raise RuntimeError(f"No se pudo restablecer el broker: {resultado.stderr.strip()}")


# --- Seguimiento de sagas --------------------------------------------------------


@dataclass
class SagaSeguida:
    saga_id: str
    estado_al_caer: str = ""
    estado_con_broker_caido: str = ""
    estado_final: str = ""
    segundos_de_recuperacion: float | None = None
    paso_detenido: str = ""


@dataclass
class Conteo:
    aceptadas: list[str] = field(default_factory=list)
    rechazadas: list[tuple[int, str]] = field(default_factory=list)


def _lanzar_sagas(endpoints: Endpoints, num: int, monto: float, hilos: int) -> Conteo:
    def una(indice: int):
        return iniciar_saga(
            endpoints,
            monto=monto + indice,
            cliente_id=f"cli-disponibilidad-{indice}",
            referencia_externa=f"DISP-{indice}-{uuid.uuid4().hex[:8]}",
            descripcion="Servicio sintético del experimento de disponibilidad",
        )

    conteo = Conteo()
    with ThreadPoolExecutor(max_workers=min(hilos, num)) as pool:
        for respuesta in pool.map(una, range(num)):
            if respuesta.codigo == 202 and isinstance(respuesta.cuerpo, dict):
                conteo.aceptadas.append(respuesta.cuerpo["saga_id"])
            else:
                conteo.rechazadas.append((respuesta.codigo, str(respuesta.cuerpo)[:120]))
    return conteo


def _estados(endpoints: Endpoints, limite: int) -> dict[str, str]:
    respuesta = pedir(f"{endpoints.sagas}?limite={limite}", timeout=10)
    if not respuesta.ok or not isinstance(respuesta.cuerpo, list):
        return {}
    return {i["saga_id"]: i.get("estado_global", "") for i in respuesta.cuerpo}


def _sondear_api_caida(endpoints: Endpoints, monto: float) -> tuple[int, int, str]:
    """Con el broker caído, ¿la API sigue en pie y sigue aceptando solicitudes?

    Son dos preguntas distintas: leer el Saga Log solo toca Postgres, mientras que
    iniciar una saga necesita publicar en Pulsar. La diferencia entre ambas
    respuestas es el radio de impacto real de la caída del broker.
    """

    lectura = pedir(f"{endpoints.sagas}?limite=1", timeout=10)
    escritura = iniciar_saga(
        endpoints,
        monto=monto,
        cliente_id="cli-disponibilidad-sonda",
        referencia_externa=f"DISP-SONDA-{uuid.uuid4().hex[:8]}",
        descripcion="Sonda con el broker caído",
        timeout=10,
    )
    detalle = str(escritura.cuerpo)[:140] if escritura.codigo != 202 else "aceptada"
    return lectura.codigo, escritura.codigo, detalle


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--num", type=int, default=12, help="Sagas a poner en tránsito")
    parser.add_argument("--modo", choices=["pausa", "caida"], default="pausa")
    parser.add_argument(
        "--retraso-ms",
        type=float,
        default=400.0,
        help="Milisegundos entre lanzar las sagas y derribar el broker",
    )
    parser.add_argument("--espera-caido", type=float, default=25.0, help="Segundos con el broker abajo")
    parser.add_argument("--timeout-salud", type=float, default=240.0)
    parser.add_argument("--timeout-recuperacion", type=float, default=150.0)
    parser.add_argument("--monto-base", type=float, default=200000.0)
    parser.add_argument("--hilos", type=int, default=8)
    parser.add_argument("--via", choices=["auto", "gateway", "directo"], default="auto")
    parser.add_argument("--sin-sonda", action="store_true", help="No sondear la API durante la caída")
    parser.add_argument("--csv", action="store_true")
    args = parser.parse_args()

    endpoints = resolver_endpoints_o_salir(args.via)
    identificador = _id_del_broker()
    limite_consulta = args.num + 60

    titulo("Escenario de calidad — Disponibilidad ante caída de Apache Pulsar")
    fila_metrica("Entrada usada", f"{endpoints.trabajos} ({endpoints.via})")
    fila_metrica("Contenedor del broker", f"{identificador[:12]} ({_salud_del_broker(identificador)})")
    fila_metrica(
        "Modo de caída",
        "pausa (conserva los ledgers)" if args.modo == "pausa" else "kill + up (borra los ledgers)",
    )
    fila_metrica("Sagas en tránsito", args.num)
    print()

    print(f"  1. Lanzando {args.num} sagas…")
    conteo = _lanzar_sagas(endpoints, args.num, args.monto_base, args.hilos)
    print(f"     aceptadas {len(conteo.aceptadas)}/{args.num}")
    if conteo.rechazadas:
        print(f"     rechazadas {len(conteo.rechazadas)} (ej. HTTP {conteo.rechazadas[0][0]})")
    if not conteo.aceptadas:
        print("\n  Ninguna saga arrancó; no hay nada que medir.")
        raise SystemExit(1)

    seguidas = {s: SagaSeguida(s) for s in conteo.aceptadas}

    time.sleep(args.retraso_ms / 1000)
    print(f"  2. Derribando el broker ({args.modo})…")
    _derribar(args.modo, identificador)
    momento_caida = time.perf_counter()

    for saga_id, estado in _estados(endpoints, limite_consulta).items():
        if saga_id in seguidas:
            seguidas[saga_id].estado_al_caer = estado
    cerradas_antes = sum(1 for s in seguidas.values() if es_final(s.estado_al_caer))
    print(f"     {cerradas_antes} sagas ya habían cerrado antes de la caída")

    sonda = None
    if not args.sin_sonda:
        print("  3. Sondeando la API con el broker caído…")
        sonda = _sondear_api_caida(endpoints, args.monto_base)
        print(f"     lectura del Saga Log HTTP {sonda[0]} · inicio de saga HTTP {sonda[1]}")

    restante = args.espera_caido - (time.perf_counter() - momento_caida)
    if restante > 0:
        print(f"  4. Manteniendo el broker caído {restante:.0f}s más…")
        time.sleep(restante)

    for saga_id, estado in _estados(endpoints, limite_consulta).items():
        if saga_id in seguidas:
            seguidas[saga_id].estado_con_broker_caido = estado

    retenidas = [s for s in seguidas.values() if not es_final(s.estado_con_broker_caido)]
    print(f"     sagas retenidas con el broker caído: {len(retenidas)}")

    print("  5. Restableciendo el broker…")
    _restablecer(args.modo, identificador)
    tardanza_broker = _esperar_salud(identificador, args.timeout_salud)
    if tardanza_broker is None:
        print(f"     [aviso] el broker no volvió a `healthy` en {args.timeout_salud:.0f}s")
        tardanza_broker = args.timeout_salud
    else:
        print(f"     broker sano de nuevo en {tardanza_broker:.1f}s")
    momento_restablecido = time.perf_counter()

    print(f"  6. Observando la recuperación hasta {args.timeout_recuperacion:.0f}s…")
    pendientes = {s.saga_id for s in retenidas}
    limite = momento_restablecido + args.timeout_recuperacion
    while pendientes and time.perf_counter() < limite:
        time.sleep(2)
        estados = _estados(endpoints, limite_consulta)
        for saga_id in list(pendientes):
            if es_final(estados.get(saga_id)):
                seguida = seguidas[saga_id]
                seguida.estado_final = estados[saga_id]
                seguida.segundos_de_recuperacion = time.perf_counter() - momento_restablecido
                pendientes.discard(saga_id)
                print(
                    f"     recuperada {saga_id[:8]}… → {seguida.estado_final} "
                    f"en {seguida.segundos_de_recuperacion:.1f}s"
                )

    # Detalle de las que no volvieron: interesa en qué paso quedaron detenidas.
    for saga_id in pendientes:
        saga = consultar_saga(endpoints, saga_id)
        seguidas[saga_id].estado_final = saga.get("estado_global", "?")
        seguidas[saga_id].paso_detenido = paso_donde_quedo(saga)

    recuperadas = [s for s in retenidas if s.segundos_de_recuperacion is not None]
    no_recuperadas = [s for s in retenidas if s.segundos_de_recuperacion is None]
    tiempos = [s.segundos_de_recuperacion for s in recuperadas if s.segundos_de_recuperacion]

    titulo("Resultados del escenario de disponibilidad")
    fila_metrica("Sagas iniciadas", len(conteo.aceptadas))
    fila_metrica("Cerradas antes de la caída", cerradas_antes)
    fila_metrica("Retenidas por la caída", len(retenidas))
    fila_metrica(
        "Recuperadas automáticamente",
        f"{len(recuperadas)}/{len(retenidas)}"
        + (f" ({len(recuperadas) / len(retenidas):.0%})" if retenidas else ""),
    )
    fila_metrica("No recuperadas", len(no_recuperadas))
    fila_metrica("Broker sano de nuevo en", f"{tardanza_broker:.1f} s")
    if tiempos:
        fila_metrica("Recuperación de sagas — p50", f"{percentil(tiempos, 50):.1f} s")
        fila_metrica("Recuperación de sagas — p95", f"{percentil(tiempos, 95):.1f} s")
        fila_metrica("Recuperación de sagas — máx", f"{max(tiempos):.1f} s")
        fila_metrica(
            "Recuperación total (caída → última saga)",
            f"{tardanza_broker + max(tiempos):.1f} s",
        )
    if sonda is not None:
        fila_metrica("Con el broker caído — leer Saga Log", f"HTTP {sonda[0]}")
        fila_metrica("Con el broker caído — iniciar saga", f"HTTP {sonda[1]}")
        if sonda[1] != 202:
            print(f"      └─ {sonda[2]}")

    if no_recuperadas:
        print()
        print("  Sagas que quedaron detenidas (paso donde se cortó la cadena):")
        for seguida in no_recuperadas[:10]:
            print(
                f"   [·] {seguida.saga_id[:8]}… estado={seguida.estado_final:<18} "
                f"paso={seguida.paso_detenido}"
            )
        if len(no_recuperadas) > 10:
            print(f"   … y {len(no_recuperadas) - 10} más")
        print()
        if args.modo == "caida":
            print(
                "  Causa esperada en modo `caida`: el standalone borra sus datos al arrancar\n"
                "  (`rm -rf /pulsar/data/*`), así que los mensajes en tránsito no existen al\n"
                "  volver. Sin Outbox ni reintento del orquestador, nadie los vuelve a emitir."
            )
        else:
            print(
                "  Causa esperada en modo `pausa`: el orquestador intentó publicar el comando\n"
                "  siguiente mientras el broker estaba congelado; el consumidor de eventos de\n"
                "  saga confirma el mensaje aun cuando el manejo falla, así que el evento se\n"
                "  perdió y nadie reintenta ese paso."
            )

    print()
    veredicto(
        "El Saga Log siguió consultable durante la caída",
        sonda is None or sonda[0] == 200,
    )
    veredicto(
        "Toda saga retenida se recuperó sola",
        bool(retenidas) and not no_recuperadas,
    )
    veredicto(
        "Ninguna saga retenida quedó en un estado inconsistente de dinero",
        all(s.estado_final != "FALLIDA" for s in retenidas),
    )
    print()
    print(
        "  Nota: la auditoría de dinero de estas sagas se hace con\n"
        "  `python -m scripts.auditoria_consistencia_sagas --solo-auditar`."
    )

    if args.csv:
        ruta = Path.cwd() / f"disponibilidad-{args.modo}-{marca_de_tiempo()}.csv"
        escribir_csv(
            ruta,
            [
                "saga_id",
                "estado_al_caer",
                "estado_con_broker_caido",
                "estado_final",
                "segundos_de_recuperacion",
                "paso_detenido",
            ],
            [
                [
                    s.saga_id,
                    s.estado_al_caer,
                    s.estado_con_broker_caido,
                    s.estado_final,
                    f"{s.segundos_de_recuperacion:.2f}" if s.segundos_de_recuperacion else "",
                    s.paso_detenido,
                ]
                for s in seguidas.values()
            ],
        )
        print()
        fila_metrica("Detalle por saga", ruta)


if __name__ == "__main__":
    main()
