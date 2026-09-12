# Colección Postman — WalletBC

| Archivo | Qué es |
|---|---|
| `WalletBC.postman_collection.json` | Colección con los 6 endpoints y los casos de error |
| `WalletBC.local.postman_environment.json` | Environment con `base_url` apuntando a localhost |

## Uso

1. Levante el servicio:

   ```bash
   cd wallet-service
   env\Scripts\activate.bat
   uvicorn app.infraestructura.adaptadores.entrada.api.main:app --reload
   ```

2. En Postman, **Import** → arrastre los dos archivos de esta carpeta.
3. Seleccione el environment *WalletBC — local* en la esquina superior derecha.
4. Ejecute la colección completa con el **Collection Runner**, o los requests uno a uno
   en el orden en que aparecen.

El environment es opcional: la colección ya trae `base_url` como variable propia. Solo
hace falta si quiere apuntar a otro host sin editar la colección.

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

## Variables

`proveedor_id` y `trabajo_id` se generan en el primer request de cada corrida, y
`billetera_id` se captura de la respuesta. No hay que rellenar nada a mano, y como los
identificadores son nuevos cada vez, la colección se puede ejecutar tantas veces como
quiera sin limpiar la base ni ajustar los saldos esperados.

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
