# Colección Postman — PagosBC

| Archivo | Qué es |
|---|---|
| `PagosBC.postman_collection.json` | Colección con el checkout, el PSP alterno, los casos de resiliencia y los de error |
| `PagosBC.local.postman_environment.json` | Environment con `base_url` apuntando a localhost |

## Uso

1. Levante el servicio:

   ```bash
   cd pagos-service
   source .venv/bin/activate
   uvicorn app.infraestructura.adaptadores.entrada.api.main:app --reload --port 8003
   ```

2. En Postman, **Import** → arrastre los dos archivos de esta carpeta.
3. Seleccione el environment *PagosBC — local* en la esquina superior derecha.
4. Ejecute la colección completa con el **Collection Runner**, o los requests uno a uno.

## Cómo está organizada

**01 Checkout principal** — cobra un trabajo en COP. Sin `psp` explícito, se resuelve por
moneda (Wompi Colombia por defecto). Incluye el reintento con la misma `referencia_externa`
para comprobar la idempotencia.

**02 PSP alterno** — el mismo checkout, pero forzando `psp: "payu-colombia"`: dos PSPs
activos para la misma moneda, cada uno con su propio formato de respuesta traducido por su
adaptador.

**03 Resiliencia (Interoperabilidad #7)** — usa las convenciones de `ClientePSPSimulado` para
forzar los otros dos desenlaces de un cobro sin apagar nada manualmente:

| Sufijo de la referencia | Resultado |
|---|---|
| `-RECHAZAR` | El PSP respondió y declinó → `Rechazado` |
| `-TIMEOUT` | El PSP no confirmó a tiempo → `PendienteDeConciliacion` |

**04 Casos de error** — una moneda sin PSP registrado (`MXN`, 400) y un pago inexistente (404).

## Simular la caída total de un PSP (circuit breaker)

La colección no lo automatiza porque requiere tocar el estado interno del proceso, pero se
puede reproducir con el servicio corriendo en un shell de Python:

```python
from app.infraestructura import contenedor
contenedor.obtener_catalogo_psp().cliente("wompi-colombia").disponible = False
```

Los primeros `PSP_CB_UMBRAL_FALLOS` checkouts en COP (sin forzar otro PSP) fallan con una
caída puntual del PSP y quedan `PendienteDeConciliacion`; a partir de ahí el circuito de
Wompi se abre y las siguientes solicitudes fallan de inmediato sin intentar la llamada.
Restaurarlo: `... .disponible = True`.

## Variables

`trabajo_id` y `referencia_externa` se generan en el pre-request de cada checkout, y
`pago_id` se captura de la respuesta. La colección se puede ejecutar tantas veces como se
quiera sin limpiar la base de datos.

## Qué mirar en los logs

```
pagos.psp             | psp=wompi-colombia referencia=checkout-... monto=150000.00 COP aprobado=True
pagos.domain_events    | domain_event=PagoConfirmado event_id=... occurred_at=...
pagos.integration_events | integration_event={"event_type": "PagoConfirmado", ...}
```

Con `docker compose up` (el sistema completo), cerrar un trabajo en GestionDeTrabajosBC
(`POST /trabajos/{id}/cerrar`) hace que PagosBC reciba `TrabajoCerradoV1` por Pulsar y cree
automáticamente un `PagoAProveedor` por cada liquidación — sin pasar por esta colección.
