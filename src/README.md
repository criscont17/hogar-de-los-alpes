# WalletBC — Billetera de proveedores

Microservicio backend de **Hogar de los Alpes** para crear billeteras, acreditar y debitar
saldo, consultar movimientos y reaccionar al evento externo simulado `TrabajoLiquidado`.
Esta implementación es independiente de los demás bounded contexts.

## Arquitectura

La implementación sigue DDD, arquitectura hexagonal y CQS:

- `dominio/`: Python puro. Contiene `Billetera` como agregado raíz, `Movimiento` como
  entidad, objetos valor, fábrica, errores, eventos y el puerto del repositorio.
- `aplicacion/`: comandos y queries con un handler dedicado, DTOs `dataclass` y puertos
  de eventos. No importa FastAPI, Pydantic ni SQLAlchemy.
- `infraestructura/adaptadores/entrada/api/`: rutas FastAPI, schemas Pydantic y mappers.
- `infraestructura/adaptadores/salida/`: repositorio SQLAlchemy/PostgreSQL, bus interno y
  publicador de integración simulado mediante logs.

Los eventos de dominio permanecen dentro del proceso y se entregan mediante
`DomainEventDispatcher`. Después de persistir el agregado, el mismo hecho se serializa
como evento de integración mediante el puerto `EventPublisher`. El adaptador actual lo
escribe en logs y puede reemplazarse por Kafka sin cambiar dominio o aplicación.
`DebitoRechazado` también se publica cuando el agregado rechaza una operación; no requiere
guardar porque el saldo y los movimientos permanecen intactos.

## Requisitos y ejecución

Se necesita Python 3.11 o posterior. Docker es opcional: la aplicación puede ejecutarse
con PostgreSQL en Docker, con una instalación local de PostgreSQL o con SQLite.

Primero instale las dependencias comunes:

```bash
cd hogar-de-los-alpes
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### Opción A — PostgreSQL con Docker

Esta es la forma recomendada para levantar rápidamente la base exigida por la entrega:

```bash
docker compose up -d postgres
export DATABASE_URL=postgresql+psycopg://wallet:wallet@localhost:5432/wallet_db
PYTHONPATH=src uvicorn main:app --reload
```

### Opción B — PostgreSQL instalado localmente

No se necesita Docker si ya existe una instancia local. Cree previamente la base y el
usuario, y sustituya los valores de conexión según su instalación:

```bash
export DATABASE_URL=postgresql+psycopg://usuario:clave@localhost:5432/wallet_db
PYTHONPATH=src uvicorn main:app --reload
```

### Opción C — SQLite sin Docker ni servidor de base de datos

Para una demostración o desarrollo rápido puede utilizarse un archivo SQLite local:

```bash
mkdir -p src/data
export DATABASE_URL=sqlite+pysqlite:///./src/data/wallet.db
PYTHONPATH=src uvicorn main:app --reload
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
