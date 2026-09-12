# WalletBC — Billetera de proveedores

Microservicio backend de **Hogar de los Alpes** para crear billeteras, acreditar y debitar
saldo, consultar movimientos y reaccionar al evento externo simulado `TrabajoLiquidado`.
Esta implementación es independiente de los demás bounded contexts.

## Arquitectura

El código del servicio vive bajo el paquete `app/`, y junto a él quedan los archivos
propios del microservicio:

```
wallet-service/
├── README.md
├── requirements.txt
├── .env.example
└── app/
    ├── seedwork/
    │   ├── dominio/              # Entity, ValueObject, AggregateRoot, DomainEvent
    │   └── aplicacion/           # DomainEventHandler, IntegrationEvent
    ├── dominio/
    ├── aplicacion/
    │   ├── comandos/  queries/  dtos/
    │   ├── puertos/              # DomainEventDispatcher, MessageBroker
    │   ├── manejadores/          # suscriptores del bus + traductores
    │   └── eventos_integracion/  # contrato público versionado
    └── infraestructura/
        └── adaptadores/
            ├── entrada/api/      # main.py: crear_app() y la instancia ASGI
            └── salida/           # persistencia/  eventos/  mensajeria/
```

La implementación sigue DDD, arquitectura hexagonal y CQS:

- `app/seedwork/`: bloques de construcción genéricos, sin conocimiento del negocio. No
  pertenece a ninguna capa porque las tres lo consumen; `seedwork/dominio/` aporta
  `Entity`, `ValueObject`, `AggregateRoot`, `DomainEvent` y `DomainError`, y
  `seedwork/aplicacion/` las bases `DomainEventHandler` e `IntegrationEvent`.
- `app/dominio/`: Python puro. Contiene `Billetera` como agregado raíz, `Movimiento` como
  entidad, objetos valor, fábrica, errores, eventos y el puerto del repositorio.
- `app/aplicacion/`: comandos y queries con un handler dedicado, DTOs `dataclass`, los
  puertos `DomainEventDispatcher` y `MessageBroker`, los handlers suscritos al bus y el
  contrato de eventos de integración. No importa FastAPI, Pydantic ni SQLAlchemy.
- `app/infraestructura/adaptadores/entrada/api/`: rutas FastAPI, schemas Pydantic y mappers.
- `app/infraestructura/adaptadores/salida/`: repositorio SQLAlchemy/PostgreSQL, bus interno
  de eventos y adaptadores de mensajería.

## Eventos de dominio y de integración

El caso de uso no decide qué ocurre tras un hecho: persiste el agregado y entrega sus
eventos al bus. Todo lo demás son suscriptores.

```
Handler de comando
  └─ repo.guardar(billetera)                     commit
  └─ despachar_eventos_pendientes(billetera, dispatcher)
       └─ dispatcher.despachar(SaldoDebitado)
            ├─ AuditarEventoDeDominioHandler      lógica interna
            └─ PublicarEventoDeIntegracionHandler
                 └─ traduce a SaldoDebitadoV1
                      └─ MessageBroker.publicar()   ← puerto abstracto
                           └─ LoggingMessageBroker | RabbitMQ | SQS
```

Tres decisiones importantes:

- **Los eventos de integración son clases aparte** (`aplicacion/eventos_integracion/`),
  con sufijo de versión y campos primitivos. El contrato público no es un volcado del
  evento de dominio, así que renombrar un campo interno no rompe a otros bounded contexts.
  La conversión vive en un solo sitio: `aplicacion/manejadores/traductores.py`.
- **Al handler de publicación se le inyecta el puerto `MessageBroker`**, nunca un
  adaptador concreto. Migrar a RabbitMQ o SQS es implementar esa interfaz en
  `infraestructura/adaptadores/salida/mensajeria/` y cambiar la instancia que devuelve
  `obtener_broker()` en `dependencias.py`.
- **Un suscriptor que falla no arrastra a los demás.** El dispatcher aísla cada handler y
  registra la excepción: cuando se despacha, el agregado ya está confirmado en base, y
  propagar el error produciría una respuesta que contradice el estado persistido. El
  precio es que un evento puede perderse si el broker está caído; resolverlo requiere el
  patrón Outbox, pendiente para cuando entre mensajería real.

La suscripción se hace sobre `DomainEvent`, de modo que un evento nuevo queda cubierto sin
registrarlo a mano. Si aun así llega un evento sin suscriptores, o sin traductor de
integración, el bus lo advierte en el log en lugar de ignorarlo en silencio.

`DebitoRechazado` también se despacha cuando el agregado rechaza una operación; no requiere
guardar porque el saldo y los movimientos permanecen intactos.

## Requisitos y ejecución

Se necesita Python 3.11 o posterior. Docker es opcional: la aplicación puede ejecutarse
con PostgreSQL en Docker, con una instalación local de PostgreSQL o con SQLite.

Todos los comandos se ejecutan desde el directorio del microservicio. Primero instale
las dependencias:

```bash
cd hogar-de-los-alpes/wallet-service
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### Configuración

La conexión se toma de `DATABASE_URL`. Copie la plantilla y ajuste sus credenciales:

```bash
cp .env.example .env
```

`app/infraestructura/configuracion.py` carga ese `.env` al arrancar, resolviendo la ruta
desde el propio archivo y no desde el directorio de trabajo, así que no hacen falta
banderas ni exportar nada. Una variable ya presente en el entorno tiene prioridad sobre
el `.env`, de modo que en despliegue basta exportarla. Los `export` de los ejemplos
siguientes solo son necesarios si prefiere no usar el archivo.

### Opción A — PostgreSQL con Docker

Esta es la forma recomendada para levantar rápidamente la base exigida por la entrega.
El `docker-compose.yml` vive en la raíz del repositorio:

```bash
docker compose -f ../docker-compose.yml up -d postgres
export DATABASE_URL=postgresql+psycopg://wallet:wallet@localhost:5432/wallet_db
uvicorn app.infraestructura.adaptadores.entrada.api.main:app --reload
```

### Opción B — PostgreSQL instalado localmente

No se necesita Docker si ya existe una instancia local. Cree previamente la base y el
usuario, y sustituya los valores de conexión según su instalación:

```bash
export DATABASE_URL=postgresql+psycopg://usuario:clave@localhost:5432/wallet_db
uvicorn app.infraestructura.adaptadores.entrada.api.main:app --reload
```

### Opción C — SQLite sin Docker ni servidor de base de datos

Para una demostración o desarrollo rápido puede utilizarse un archivo SQLite local:

```bash
mkdir -p app/data
export DATABASE_URL=sqlite+pysqlite:///./app/data/wallet.db
uvicorn app.infraestructura.adaptadores.entrada.api.main:app --reload
```

SQLite permite ejecutar todos los endpoints sin infraestructura adicional. Sin embargo,
la especificación académica establece PostgreSQL como tecnología de persistencia; por
eso las opciones A o B son las apropiadas para validar formalmente la entrega.

La documentación interactiva queda en <http://localhost:8000/docs>. Las tablas se crean
al iniciar el servicio. Para producción se recomienda sustituir esta inicialización por
migraciones versionadas.

## API REST

Use UUID diferentes para el proveedor y los trabajos. Primero cree una billetera:

```bash
curl -X POST http://localhost:8000/billeteras \
  -H 'Content-Type: application/json' \
  -d '{"proveedor_id":"11111111-1111-4111-8111-111111111111","moneda":"COP"}'
```

Copie el campo `id` de la respuesta en `BILLETERA_ID`:

```bash
export BILLETERA_ID=<id-de-la-billetera>

curl http://localhost:8000/billeteras/$BILLETERA_ID/saldo

curl -X POST http://localhost:8000/billeteras/$BILLETERA_ID/acreditar \
  -H 'Content-Type: application/json' \
  -d '{"monto":"150000.00","motivo":"AjusteManual","referencia_externa":"ajuste-1"}'

curl -X POST http://localhost:8000/billeteras/$BILLETERA_ID/debitar \
  -H 'Content-Type: application/json' \
  -d '{"monto":"25000.00","motivo":"RetiroAProveedor"}'

curl "http://localhost:8000/billeteras/$BILLETERA_ID/movimientos?tipo=Credito"

curl -X POST http://localhost:8000/eventos-externos/trabajo-liquidado \
  -H 'Content-Type: application/json' \
  -d '{"trabajo_id":"22222222-2222-4222-8222-222222222222","proveedor_id":"11111111-1111-4111-8111-111111111111","monto":"80000.00","moneda":"COP"}'
```

Los valores permitidos son:

- `motivo`: `PagoDeTrabajo`, `RetiroAProveedor`, `AjusteManual` o `Reverso`.
- filtro `tipo`: `Credito` o `Debito`.
- filtros de fecha: `fecha_desde` y `fecha_hasta` en formato ISO 8601.

La API responde `201` al crear, `200` en operaciones exitosas, `400` ante datos o reglas
inválidas, `404` si no existe la billetera y `409` ante fondos insuficientes o una billetera
duplicada.
