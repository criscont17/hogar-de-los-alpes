"""Experimento del Escenario de calidad #4 (Escalabilidad): llegada masiva de
solicitudes de creación de trabajo desde partners.

Publica `N` comandos `CrearTrabajoV1` en `comandos-trabajo` tan rápido como el
cliente de Pulsar lo permite (simulando varios partners enviando solicitudes al
mismo tiempo, como en una granizada) y mide cuánto tarda GestionDeTrabajosBC en
*aceptar* cada uno: como la arquitectura es asíncrona, no hay una respuesta HTTP
que cronometrar, así que "aceptado" se mide como el tiempo entre publicar el
comando y recibir el evento de integración `TrabajoCreadoV2` correspondiente en
`eventos-trabajo`. Esa latencia es justamente lo que un partner percibiría si
estuviera escuchando esos eventos para confirmar su solicitud.

Uso (con Pulsar corriendo, vía `docker compose up -d pulsar` o el stack completo):

    python -m scripts.carga_escalabilidad --num 200

Para comparar 1 instancia vs. varias, levante una segunda réplica de
GestionDeTrabajosBC (ver `docker-compose.yml`, servicio `gestion-trabajos-2`,
perfil `escalabilidad`) y vuelva a correr el mismo comando: ambas comparten la
suscripción `Shared` sobre `comandos-trabajo`, así que Pulsar reparte la carga
entre las dos sin cambiar nada en el script ni en el código del servicio.
"""

import argparse
import json
import statistics
import threading
import time
import uuid
from dataclasses import dataclass, field

import pulsar

from app.infraestructura.configuracion import PULSAR_TOPICO_COMANDOS, PULSAR_TOPICO_EVENTOS, PULSAR_URL

PARTNER_DE_PRUEBA = "carga-escalabilidad"


def _payload(referencia: str) -> dict:
    return {
        "canal": "Partner",
        "partner_id": PARTNER_DE_PRUEBA,
        "referencia_externa": referencia,
        "descripcion": "Trabajo sintético del experimento de escalabilidad",
        "urgencia": "Alta",
        "ubicacion": {"pais": "CO", "ciudad": "Bogota", "direccion": "Carga sintetica"},
        "moneda": "COP",
        "sub_trabajos": [
            {"clave": "plomeria", "categoria": "Plomeria", "descripcion": "Sub-trabajo de carga"}
        ],
    }


@dataclass
class Resultados:
    enviados: dict[str, float] = field(default_factory=dict)
    confirmados: dict[str, float] = field(default_factory=dict)
    lock: threading.Lock = field(default_factory=threading.Lock)

    def marcar_enviado(self, referencia: str) -> None:
        with self.lock:
            self.enviados[referencia] = time.perf_counter()

    def marcar_confirmado(self, referencia: str) -> bool:
        """Registra la confirmación; devuelve False si ya estaba (duplicado)."""

        with self.lock:
            if referencia not in self.enviados or referencia in self.confirmados:
                return False
            self.confirmados[referencia] = time.perf_counter() - self.enviados[referencia]
            return True

    def total_confirmados(self) -> int:
        with self.lock:
            return len(self.confirmados)


def _publicar(cliente: pulsar.Client, num: int, resultados: Resultados) -> list[str]:
    productor = cliente.create_producer(
        PULSAR_TOPICO_COMANDOS, batching_enabled=True, batching_max_publish_delay_ms=5
    )
    referencias = [f"{PARTNER_DE_PRUEBA}-{uuid.uuid4()}" for _ in range(num)]

    inicio = time.perf_counter()
    for referencia in referencias:
        resultados.marcar_enviado(referencia)
        productor.send_async(
            json.dumps(_payload(referencia), ensure_ascii=False).encode("utf-8"),
            lambda res, msg_id: None,
            properties={"command_type": "CrearTrabajoV1", "partner_id": PARTNER_DE_PRUEBA},
            partition_key=f"{PARTNER_DE_PRUEBA}:{referencia}",
        )
    productor.flush()
    duracion_envio = time.perf_counter() - inicio
    productor.close()
    print(f"Enviados {num} comandos en {duracion_envio:.2f}s "
          f"({num / duracion_envio:.1f} comandos/s de throughput de publicación)")
    return referencias


def _consumir_confirmaciones(
    cliente: pulsar.Client, resultados: Resultados, num_esperado: int, timeout_seg: float
) -> None:
    suscripcion = f"carga-escalabilidad-{uuid.uuid4()}"
    consumidor = cliente.subscribe(
        PULSAR_TOPICO_EVENTOS,
        suscripcion,
        consumer_type=pulsar.ConsumerType.Shared,
        initial_position=pulsar.InitialPosition.Latest,
    )
    limite = time.perf_counter() + timeout_seg
    ultimo_progreso = time.perf_counter()
    try:
        while resultados.total_confirmados() < num_esperado:
            ahora = time.perf_counter()
            if ahora > limite:
                print(f"Timeout: se agotaron los {timeout_seg:.0f}s de espera")
                break
            try:
                mensaje = consumidor.receive(timeout_millis=1000)
            except pulsar.Timeout:
                if ahora - ultimo_progreso > 15:
                    print("15s sin eventos nuevos; deteniendo la espera")
                    break
                continue
            propiedades = mensaje.properties()
            if propiedades.get("event_name") in ("TrabajoCreadoV1", "TrabajoCreadoV2"):
                datos = json.loads(mensaje.data())
                referencia = datos.get("referencia_externa")
                if referencia and resultados.marcar_confirmado(referencia):
                    ultimo_progreso = time.perf_counter()
            consumidor.acknowledge(mensaje)
    finally:
        consumidor.close()


def _reportar(resultados: Resultados, num_enviados: int) -> None:
    latencias_ms = sorted(v * 1000 for v in resultados.confirmados.values())
    confirmados = len(latencias_ms)
    print()
    print("=== Resultado del experimento — Escenario de calidad #4 (Escalabilidad) ===")
    print(f"Comandos enviados:      {num_enviados}")
    print(f"Comandos confirmados:   {confirmados} ({confirmados / num_enviados:.1%})")
    if not latencias_ms:
        print("Ningún comando fue confirmado; revise que el servicio y Pulsar estén corriendo.")
        return
    p50 = statistics.median(latencias_ms)
    p95 = latencias_ms[min(int(len(latencias_ms) * 0.95), confirmados - 1)]
    p99 = latencias_ms[min(int(len(latencias_ms) * 0.99), confirmados - 1)]
    print(f"Latencia p50:           {p50:.1f} ms")
    print(f"Latencia p95:           {p95:.1f} ms   (meta del escenario: < 500 ms)")
    print(f"Latencia p99:           {p99:.1f} ms   (meta del escenario: < 1000 ms)")
    print(f"Latencia máxima:        {max(latencias_ms):.1f} ms")
    print()
    print(f"Cumple p95 < 500ms:  {'SI' if p95 < 500 else 'NO'}")
    print(f"Cumple p99 < 1000ms: {'SI' if p99 < 1000 else 'NO'}")
    print(f"Cumple >=99.95% persistido: {'SI' if confirmados / num_enviados >= 0.9995 else 'NO'}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--num", type=int, default=200, help="Comandos CrearTrabajoV1 a enviar")
    parser.add_argument(
        "--timeout", type=float, default=60.0, help="Segundos máximos a esperar confirmaciones"
    )
    args = parser.parse_args()

    resultados = Resultados()
    cliente_productor = pulsar.Client(PULSAR_URL)
    cliente_consumidor = pulsar.Client(PULSAR_URL)

    hilo_consumidor = threading.Thread(
        target=_consumir_confirmaciones,
        args=(cliente_consumidor, resultados, args.num, args.timeout),
    )
    hilo_consumidor.start()
    # Pequeña espera para que la suscripción quede activa antes de publicar.
    time.sleep(1.0)

    try:
        _publicar(cliente_productor, args.num, resultados)
        hilo_consumidor.join()
    finally:
        cliente_productor.close()
        cliente_consumidor.close()

    _reportar(resultados, args.num)


if __name__ == "__main__":
    main()
