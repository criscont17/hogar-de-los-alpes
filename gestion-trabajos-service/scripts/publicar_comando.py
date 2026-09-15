"""Publica un comando en el tópico de comandos de GestionDeTrabajosBC.

Simula a otro bounded context (Marketplace, ServiciosRecurrentes...) que envía
comandos por Pulsar. Ejecutar desde `gestion-trabajos-service/`:

    python -m scripts.publicar_comando CrearTrabajoV1 scripts/ejemplos/crear_trabajo.json
    python -m scripts.publicar_comando CerrarTrabajoV1 "{\"trabajo_id\": \"<id>\"}"
"""

import argparse
import json
from pathlib import Path

import pulsar

from app.infraestructura.configuracion import PULSAR_TOPICO_COMANDOS, PULSAR_URL


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("comando", help="Nombre versionado del comando, p. ej. CrearTrabajoV1")
    parser.add_argument("datos", help="JSON en línea o ruta a un archivo .json")
    args = parser.parse_args()

    ruta = Path(args.datos)
    datos = json.loads(ruta.read_text(encoding="utf-8") if ruta.is_file() else args.datos)

    cliente = pulsar.Client(PULSAR_URL)
    try:
        productor = cliente.create_producer(PULSAR_TOPICO_COMANDOS)
        productor.send(
            json.dumps(datos, ensure_ascii=False).encode("utf-8"),
            properties={"command_type": args.comando},
        )
        print(f"{args.comando} publicado en {PULSAR_TOPICO_COMANDOS}")
    finally:
        cliente.close()


if __name__ == "__main__":
    main()
