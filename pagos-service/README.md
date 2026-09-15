# PagosBC — Cobros al cliente y pagos a proveedores

Microservicio de Hogar de los Alpes que resuelve dos flujos de dinero atados a un trabajo:

- **Checkout del marketplace:** un cliente paga un trabajo (`CobroCliente`), vía la API REST.
- **Liquidación a proveedores:** cuando **GestionDeTrabajosBC** cierra un trabajo, publica el
  evento `TrabajoCerradoV1` con la liquidación de cada proveedor. PagosBC lo consume por
  **Apache Pulsar** y crea un `PagoAProveedor` por cada uno, automáticamente.

Es el artefacto del escenario de **Interoperabilidad #7** ("Interoperar con múltiples
pasarelas de pago sin contaminar el dominio de Pago"): aísla cada PSP (Wompi, PayU,
MercadoPago) detrás de un adaptador con capa anti-corrupción y circuit breaker propio, de
modo que el agregado `Pago` nunca conoce el formato de una pasarela ni la caída de una
afecta a las demás.

GestionDeTrabajosBC y PagosBC **no se llaman entre sí de forma síncrona**: GestionDeTrabajosBC
publica sus eventos, y PagosBC los consume. PagosBC es *Conformist* con ese contrato (mapa de
contextos TO-BE): no lo traduce, lo consume tal cual porque GestionDeTrabajosBC es upstream
estable.

## Arquitectura

```
pagos-service/
├── Dockerfile
├── requirements.txt
├── .env.example
├── collections/                  # Colección Postman del checkout y las liquidaciones
└── app/
    ├── seedwork/
    │   ├── dominio/               # Entity, ValueObject, AggregateRoot, DomainEvent, DomainError
    │   ├── aplicacion/            # DomainEventHandler, IntegrationEvent, ApplicationError
    │   └── infraestructura/       # CircuitBreaker genérico (reutilizado por cada PSP)
    ├── dominio/
    │   ├── pago/                  # Agregado Pago, Dinero, TipoPago/EstadoPago, eventos
    │   └── errores/
    ├── aplicacion/
    │   ├── comandos/               # CrearPago, ProcesarCierreDeTrabajo
    │   ├── queries/                 # ObtenerPago, ListarPagos
    │   ├── puertos/                  # DomainEventDispatcher, MessageBroker, AdaptadorDePSP, CatalogoDePSP
    │   ├── manejadores/               # auditar, publicar en Pulsar, traductores
    │   └── eventos_integracion/        # contrato público versionado (V1)
    └── infraestructura/
        ├── configuracion.py
        ├── contenedor.py           # raíz de composición compartida por REST y Pulsar
        └── adaptadores/
            ├── entrada/
            │   ├── api/            # FastAPI: checkout y consultas de pagos
            │   └── mensajeria/      # consumidor de TrabajoCerradoV1 en Pulsar
            ├── acl_psp/             # un adaptador por PSP + catálogo + cliente simulado
            └── salida/              # persistencia/ eventos/ mensajeria/ (Pulsar, logs, memoria)
```

DDD, arquitectura hexagonal y CQS, igual que WalletBC, GestionDeTrabajosBC y OperacionesBC.

- `app/dominio/`: Python puro. No conoce PSPs, formatos, FastAPI, SQLAlchemy ni Pulsar.
- `app/aplicacion/`: un handler por comando o query, DTOs `dataclass` y puertos. No importa
  infraestructura.
- `app/infraestructura/contenedor.py`: decide qué adaptador hay detrás de cada puerto. La API
  REST y el consumidor de eventos de Pulsar ejecutan los mismos casos de uso.

## Modelo de dominio

| Concepto del negocio | En el código |
|---|---|
| Pago | Agregado raíz `Pago`: PENDIENTE → CONFIRMADO / RECHAZADO / PENDIENTE_CONCILIACION |
| Tipo de pago | Objeto valor `TipoPago`: `CobroCliente` (checkout) o `PagoAProveedor` (liquidación) |
| Monto | Objeto valor `Dinero`: monto positivo + moneda ISO de 3 letras |
| Resultado del PSP ya normalizado | `ResultadoPSP`: `exitoso`, `referencia_psp`, `motivo` — nunca el formato nativo del PSP |

Transiciones que protege el agregado (todas parten de `Pendiente`, y solo de ahí):

- **Confirmar:** el PSP aprobó la operación. Guarda su referencia externa.
- **Rechazar:** el PSP respondió pero declinó (fondos, fraude). Es un rechazo de negocio.
- **Marcar pendiente de conciliación:** el circuito de ese PSP está abierto, o no respondió a
  tiempo, o hubo una caída puntual de conexión. No es un rechazo: espera un reintento
  diferido o resolución manual.

## Interoperabilidad con múltiples PSPs (capa anti-corrupción)

```
CrearPagoCommand
  └─ resolver PSP por moneda (o explícito si el llamador lo pide)
       └─ AdaptadorDePSP.cobrar(monto, moneda, referencia)
            └─ CircuitBreaker propio del PSP
                 └─ ClientePSPSimulado.cobrar(...)   ← simula la pasarela real
                      └─ traduce la respuesta nativa a ResultadoPSP (ACL)
```

| PSP | Moneda | Particularidad de formato que traduce el adaptador |
|---|---|---|
| `wompi-colombia` (por defecto en COP) | COP | Responde `data.status` (`APPROVED`/`DECLINED`), referencia con prefijo `wompi-txn-` |
| `payu-colombia` (alterno en COP) | COP | Responde con código propio (`APPROVED`/`DECLINED`), referencia `payu-order-` |
| `mercadopago-argentina` | ARS | Responde `status` en minúsculas (`approved`/`rejected`), referencia `mp-payment-` |

Incorporar un PSP nuevo (por ejemplo, para México) es agregar su adaptador a
`acl_psp/registro.py`: el agregado `Pago` y `CrearPagoHandler` no cambian — es la medida del
escenario de calidad. Pedir el pago en una moneda sin PSP registrado (`MXN` hoy) responde
`400` con `PSPNoSoportadoError` en vez de fallar silenciosamente.

### Simular los tres desenlaces de un cobro

`ClientePSPSimulado` (adaptador de infraestructura, nunca el dominio) reconoce convenciones en
la referencia para poder probar el escenario sin depender de una pasarela real:

- referencia terminada en `-RECHAZAR` → el PSP responde pero declina (`Pago.rechazar`).
- referencia terminada en `-TIMEOUT` → el PSP no confirma a tiempo (`Pago.marcar_pendiente_de_conciliacion`).
- cualquier otra referencia → aprobado (`Pago.confirmar`).
- `cliente.disponible = False` simula una caída total del PSP: los primeros fallos devuelven
  `ConnectionError` (igual se resuelve a conciliación diferida) y, tras el umbral configurado,
  el circuito se abre y las siguientes llamadas fallan de inmediato sin tocar la red.

## Eventos y comandos con Apache Pulsar

| Tópico | Dirección | Contenido |
|---|---|---|
| `persistent://public/default/eventos-pago` | Publica | Eventos de integración en JSON: `PagoConfirmadoV1`, `PagoRechazadoV1`, `PagoPendienteDeConciliacionV1` |
| `persistent://public/default/eventos-trabajo` | Consume (suscripción `pagos-bc`, `Key_Shared`) | Solo procesa `TrabajoCerradoV1`; el resto se confirma (ack) sin abrir el cuerpo |

`PagoConfirmadoV1` es el contrato que WalletBC consumiría (Conformist, igual que PagosBC lo es
de GestionDeTrabajosBC) para acreditar saldo al proveedor — la integración entre ambos queda
como trabajo futuro explícito de esta POC. `PagoCreado` es un hecho puramente interno: no se
traduce a evento de integración porque a nadie más le interesa que un pago exista antes de
resolverse.

Cada evento viaja con las propiedades `event_type`, `event_version`, `event_name` y
`deprecado` en el mensaje de Pulsar, igual que en los demás servicios: un consumidor puede
filtrar sin deserializar el cuerpo, y el esquema evoluciona agregando una clase `V2` sin
romper a quien sigue leyendo `V1`.

## Escenario de calidad

| Escenario | Aporte de este servicio |
|---|---|
| Interoperabilidad #7 | Adapter + ACL por PSP (`acl_psp/`), objeto valor `Dinero` con validación de moneda, circuit breaker por PSP. Incorporar un PSP nuevo no toca el agregado `Pago`. Ante timeout o caída de un PSP, el pago pasa a `PendienteDeConciliacion` en vez de bloquear el resto de transacciones. |

## Requisitos y ejecución

Se necesita Python 3.11 o posterior. Docker es opcional: la aplicación puede ejecutarse con
PostgreSQL en Docker o con SQLite (archivo, no `:memory:` — SQLite abre una base nueva por
conexión y las tablas se perderían entre requests).

```bash
cd hogar-de-los-alpes/pagos-service
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

### Opción A — PostgreSQL con Docker (recomendada)

```bash
docker compose -f ../docker-compose.yml up -d postgres-pagos pulsar
export DATABASE_URL=postgresql+psycopg://pagos:pagos@localhost:5435/pagos_db
uvicorn app.infraestructura.adaptadores.entrada.api.main:app --reload --port 8003
```

### Opción B — SQLite local (sin Docker)

```bash
mkdir -p app/data
export DATABASE_URL=sqlite+pysqlite:///./app/data/pagos.db
uvicorn app.infraestructura.adaptadores.entrada.api.main:app --reload --port 8003
```

La documentación interactiva queda en <http://localhost:8003/docs> cuando el servicio corre
local. Con Docker Compose completo queda detrás de la entrada pública, en
<http://localhost/pagos/docs>; ver el [README raíz](../README.md#despliegue-con-docker-y-entrada-pública).

### Con el resto del sistema (Docker Compose completo)

```bash
docker compose up -d --build
```

Levanta Postgres de cada servicio, Apache Pulsar, y los tres microservicios conectados por
Pulsar: crear un trabajo en GestionDeTrabajosBC, asignarle proveedor(es), completar sus
sub-trabajos y cerrarlo (`POST /trabajos/{id}/cerrar`) dispara automáticamente un
`PagoAProveedor` por cada liquidación en PagosBC.

## API REST

```bash
# Checkout: cobra un trabajo al cliente (COP → Wompi por defecto)
curl -X POST http://localhost:8003/pagos \
  -H 'Content-Type: application/json' \
  -d '{"trabajo_id":"trabajo-1","monto":"150000.00","moneda":"COP","referencia_externa":"checkout-1"}'

# Forzar un PSP específico
curl -X POST http://localhost:8003/pagos \
  -H 'Content-Type: application/json' \
  -d '{"trabajo_id":"trabajo-1","monto":"150000.00","moneda":"COP","referencia_externa":"checkout-2","psp":"payu-colombia"}'

# Simular que el PSP rechaza la operación
curl -X POST http://localhost:8003/pagos \
  -H 'Content-Type: application/json' \
  -d '{"trabajo_id":"trabajo-2","monto":"50000.00","moneda":"COP","referencia_externa":"checkout-3-RECHAZAR"}'

# Simular que el PSP no responde a tiempo (pasa a conciliación diferida)
curl -X POST http://localhost:8003/pagos \
  -H 'Content-Type: application/json' \
  -d '{"trabajo_id":"trabajo-2","monto":"50000.00","moneda":"COP","referencia_externa":"checkout-4-TIMEOUT"}'

curl http://localhost:8003/pagos
curl "http://localhost:8003/pagos?trabajo_id=trabajo-1"
curl http://localhost:8003/pagos/<id>
```

La API responde `201` al crear (o al reintentar la misma `referencia_externa`, de forma
idempotente), `200` en consultas, `400` ante datos inválidos o un PSP no soportado para la
moneda pedida, `404` si el pago no existe y `409` ante una transición de estado inválida o un
conflicto de concurrencia.
