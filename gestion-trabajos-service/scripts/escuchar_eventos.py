"""Escucha los eventos de integración publicados por GestionDeTrabajosBC.

Simula a un consumidor downstream como PagosBC u OperacionesBC. Ejecutar desde
`gestion-trabajos-service/`:

    python -m scripts.escuchar_eventos
    python -m scripts.escuchar_eventos --suscripcion pagos-bc --evento TrabajoCerrado
"""

import argparse
import json

import pulsar

from app.infraestructura.configuracion import PULSAR_TOPICO_EVENTOS, PULSAR_URL


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--suscripcion", default="consola", help="Nombre de la suscripción")
    parser.add_argument("--evento", help="Filtra por tipo sin versión, p. ej. TrabajoCerrado")
    args = parser.parse_args()

    cliente = pulsar.Client(PULSAR_URL)
    # Key_Shared: varios consumidores reparten carga y los hechos de un mismo
    # trabajo (misma clave) siguen llegando en orden.
    consumidor = cliente.subscribe(
        PULSAR_TOPICO_EVENTOS,
        args.suscripcion,
        consumer_type=pulsar.ConsumerType.KeyShared,
        initial_position=pulsar.InitialPosition.Earliest,
    )
    print(f"Escuchando {PULSAR_TOPICO_EVENTOS} como '{args.suscripcion}' (Ctrl+C para salir)")
    try:
        while True:
            mensaje = consumidor.receive()
            propiedades = mensaje.properties()
            if args.evento is None or propiedades.get("event_type") == args.evento:
                marca = " [deprecado]" if propiedades.get("deprecado") == "true" else ""
                print(f"\n{propiedades.get('event_name')}{marca} key={mensaje.partition_key()}")
                print(json.dumps(json.loads(mensaje.data()), indent=2, ensure_ascii=False))
            consumidor.acknowledge(mensaje)
    except KeyboardInterrupt:
        pass
    finally:
        consumidor.close()
        cliente.close()


if __name__ == "__main__":
    main()
