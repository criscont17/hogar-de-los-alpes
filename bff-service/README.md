# BFF — Backend For Frontend de Hogar de los Alpes

Fachada HTTP REST síncrona hacia las capacidades de negocio de HdA. Es la única puerta de
entrada pensada para clientes externos (Postman, futuras apps): expone rutas simples con
sentido de negocio y por dentro decide a qué microservicio llamar.

No tiene base de datos propia ni lógica de dominio: cada request se traduce 1 a 1 en una
llamada HTTP hacia **GestionDeTrabajosBC** (dueño del orquestador de la saga y del agregado
`Trabajo`) o hacia **WalletBC** (saldo del proveedor). El BFF nunca habla con Pulsar
directamente ni conoce el modelo interno de cada servicio, solo su contrato REST publicado.

## Arquitectura

```
bff-service/
├── Dockerfile
├── requirements.txt
├── .env.example
├── collections/            # Colección Postman: saga exitosa, saga compensada, consultas
└── app/
    ├── main.py              # App FastAPI, registro de routers, manejo de errores downstream
    ├── config.py             # URLs de los servicios internos (por variables de entorno)
    ├── clients.py              # Wrappers httpx hacia gestion-trabajos-service y wallet-service
    ├── schemas.py                # Payloads de entrada (Pydantic)
    └── routers/
        ├── trabajos.py            # POST /trabajos/completar-servicio, GET /trabajos/{id}/estado
        ├── sagas.py                 # GET /sagas/{saga_id}, GET /sagas
        └── wallet.py                 # POST /proveedores/{id}/wallet/retiros
```

## Endpoints

| Método y ruta | Descripción | Llama a |
| --- | --- | --- |
| `POST /trabajos/completar-servicio` | Inicia la saga distribuida: crea el trabajo, retiene el pago y asigna proveedor. | `gestion-trabajos-service POST /sagas/activar-servicio` |
| `GET /trabajos/{trabajo_id}/estado` | Estado del trabajo agregado con el de su saga. | `gestion-trabajos-service GET /trabajos/{id}` + `GET /sagas` |
| `GET /sagas/{saga_id}` | Línea de tiempo completa del Saga Log de una transacción. | `gestion-trabajos-service GET /sagas/{id}` |
| `GET /sagas` | Últimas transacciones distribuidas (para explorar en la demo). | `gestion-trabajos-service GET /sagas` |
| `POST /proveedores/{id}/wallet/retiros` | Solicita un retiro (débito) del saldo del proveedor. | `wallet-service POST /billeteras/{id}/debitar` |

**Nota / desviación consciente del contrato original de arquitectura:** el documento de
Entrega 5 proponía `POST /trabajos/{id}/completar`, asumiendo un trabajo ya existente. En la
implementación real el trabajo no existe todavía: lo crea el propio orquestador como Paso 1
de la saga. Por eso el BFF expone `POST /trabajos/completar-servicio` (sin id) y devuelve el
`trabajo_id` generado en la respuesta — ajuste explícitamente permitido por ese mismo
documento ("ajustar rutas... a las capacidades reales que ya existan en cada servicio").

Para forzar una compensación en la demo, `POST /trabajos/completar-servicio` acepta
`simular_fallo_en_paso: "PAGO"` o `"OPERACIONES"` en el body — se reenvía tal cual al
orquestador, que ya soporta ese modo de prueba.

## Ejecutar localmente

Como parte del stack completo (recomendado, así resuelve los nombres de host internos de
Docker):

```bash
docker compose up -d --build bff
```

Queda disponible en `http://127.0.0.1:8005` y, detrás del gateway, en `http://localhost/api`
(Swagger: `http://localhost/api/docs`).

Suelto, contra servicios ya corriendo en otra parte:

```bash
cd bff-service
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # ajustar URL_GESTION_TRABAJOS / URL_WALLET si no es Docker
uvicorn app.main:app --reload --port 8005
```

## Colección Postman

Ver [`collections/`](collections/): incluye una saga exitosa de punta a punta, una saga que
termina en compensación (`simular_fallo_en_paso`) y la consulta de su Saga Log.
