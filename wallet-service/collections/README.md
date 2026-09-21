# Colección Postman — WalletBC

| Archivo | Qué es |
|---|---|
| `WalletBC.postman_collection.json` | Colección con los 11 endpoints, los casos de error y la administración CRUD |
| `WalletBC.local.postman_environment.json` | Environment con `base_url` apuntando al gateway local |

## Uso

Las rutas van bajo el prefijo `/wallet` de la entrada pública (`{{base_url}}/wallet/billeteras`),
así que la colección se ejecuta contra el gateway, no contra el puerto del servicio.

1. Levante la plataforma desde la raíz del repositorio:

   ```bash
   docker compose up -d --build --wait
   ```

2. En Postman, **Import** → arrastre los dos archivos de esta carpeta.
3. Seleccione el environment *WalletBC — local* en la esquina superior derecha.
4. Ejecute la colección completa con el **Collection Runner**, o los requests uno a uno
   en el orden en que aparecen.

El environment es opcional: la colección ya trae `base_url` como variable propia. Solo
hace falta si quiere apuntar a otro host sin editar la colección.

`base_url` es `http://localhost`, el gateway en el puerto 80. Para el despliegue en AWS,
cámbielo por el host público; si levantó el gateway en otro puerto con `PUERTO_GATEWAY`,
agréguelo ahí (`http://localhost:8088`).

El gateway quita el prefijo antes de reenviar, de modo que `/wallet/billeteras` llega al
servicio como `/billeteras`. Si prefiere golpear el contenedor directo en `127.0.0.1:8000`
—o un `uvicorn` local sin Docker— tiene que quitar el segmento `/wallet` de las rutas: el
prefijo solo existe en la entrada pública.

## Cómo está organizada

**01 Flujo principal** — debe ejecutarse en orden, porque cada paso depende del anterior:

| # | Request | Saldo resultante |
|---|---|---|
| 1 | Crear billetera | 0 |
| 2 | Consultar saldo inicial | 0 |
| 3 | Acreditar 150.000 | 150.000 |
| 4 | Debitar 25.000 | 125.000 |
| 5 | Procesar trabajo liquidado 80.000 | 205.000 |
| 6 | Listar movimientos | 3 movimientos |
| 7 | Listar movimientos filtrando `Credito` | 2 movimientos |

**02 Casos de error** — reutilizan la billetera creada arriba: proveedor duplicado (409),
fondos insuficientes (409), billetera inexistente (404), monto negativo (400), moneda
distinta a la de la billetera (400) y motivo inválido (400).

**03 Administración CRUD** — gestión de datos sobre esa misma billetera, que a esta altura
tiene saldo 205.000 y 3 movimientos:

| # | Request | Qué comprueba |
|---|---|---|
| 1 | Listar billeteras (paginado) | La respuesta es una página: `items`, `total`, `limite`, `desplazamiento` |
| 2 | Listar filtrando por proveedor | Un proveedor tiene exactamente una billetera |
| 3 | Obtener billetera (detalle) | Agrega `fecha_creacion` y `total_movimientos` |
| 4 | Suspender billetera | Estado `Suspendida` y `EstadoBilleteraCambiadoV1` en el log |
| 5 | Debitar billetera suspendida | 400: suspender surte efecto |
| 6 | Reactivar billetera | Vuelve a `Activa` |
| 7 | Eliminar billetera con saldo | 409: el saldo la protege |
| 8 | Crear billetera temporal | Billetera desechable en cero |
| 9 | Eliminar billetera temporal | 204 sin cuerpo, y `BilleteraEliminadaV1` en el log |
| 10 | Consultar la eliminada | 404 |

## Variables

`proveedor_id` y `trabajo_id` se generan en el primer request de cada corrida, y
`billetera_id` se captura de la respuesta. `proveedor_temporal` y `billetera_temporal`
cumplen el mismo papel para la billetera desechable que se borra en la carpeta 03. No hay
que rellenar nada a mano, y como los identificadores son nuevos cada vez, la colección se
puede ejecutar tantas veces como quiera sin limpiar la base ni ajustar los saldos
esperados.

## Qué mirar en los logs

Cada operación que modifica la billetera deja dos líneas en la consola del servicio, una
por cada suscriptor del bus de eventos:

```
wallet.domain_events      | domain_event=SaldoAcreditado event_id=... occurred_at=...
wallet.integration_events | integration_event={"event_type": "SaldoAcreditadoV1", ...}
```

Dos comprobaciones interesantes que no se ven en la respuesta HTTP:

- Tras *Procesar trabajo liquidado*, el `SaldoAcreditadoV1` sale con
  `"motivo": "PagoDeTrabajo"` y el `trabajo_id` como `referencia_externa`.
- *Fondos insuficientes* responde 409, pero aun así publica `DebitoRechazadoV1`: el
  rechazo es un hecho de negocio que otros bounded contexts deben conocer.
