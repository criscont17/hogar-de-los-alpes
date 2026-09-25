# Backend For Frontend (BFF)
## Entrega Semana 7 — Hogar de los Alpes

---

## 1. Propósito y Alcance del BFF

El BFF (`bff-service/`) es la única puerta de entrada HTTP REST síncrona pensada para
clientes externos (Postman, apps móviles/web futuras, el tutor evaluando la entrega). Expone
rutas simples con sentido de negocio (`/trabajos/completar-servicio`, `/sagas/{id}`) en lugar
de obligar al cliente a conocer los 4 microservicios internos, sus puertos o sus contratos de
mensajería.

No tiene base de datos propia ni modelo de dominio propio: cada endpoint se traduce 1 a 1 en
una llamada HTTP hacia el servicio dueño de esa capacidad —hoy, **GestionDeTrabajosBC**
(orquestador de la saga y dueño del agregado `Trabajo`) y **WalletBC** (saldo del proveedor).
Es la única excepción síncrona autorizada en el ecosistema: los microservicios entre sí siguen
comunicándose exclusivamente por comandos/eventos sobre Apache Pulsar.

---

## 2. Aislamiento y Desacoplamiento de Clientes

El cliente del BFF nunca ve un tópico de Pulsar, un `saga_id` interno construido a mano ni la
topología de contenedores (`wallet:8000`, `gestion-trabajos:8001`, etc.). El BFF:

- Traduce el POST de arranque de la saga en la llamada REST que ya expone el orquestador
  (`gestion-trabajos-service POST /sagas/activar-servicio`), y devuelve `saga_id` +
  `trabajo_id` para que el cliente pueda hacer seguimiento.
- Agrega respuestas cuando la pregunta del cliente ("¿cómo va mi trabajo?") requiere más de
  una fuente: junta el agregado `Trabajo` con el estado de su saga en un solo JSON
  (`GET /trabajos/{id}/estado`).
- Traduce errores de forma uniforme: si un microservicio interno no responde, el BFF nunca
  deja la conexión colgada ni filtra una traza interna — responde `502` con un mensaje
  consistente (`ServicioNoDisponibleError`); si el microservicio responde un error de negocio
  (404, 409, 400), el BFF lo reenvía tal cual.

---

## 3. Especificación de Endpoints y Casos de Uso

### 3.1 Endpoint de Inicio de Transacciones / Sagas

`POST /trabajos/completar-servicio` → `202 Accepted`

```json
{
  "cliente_id": "cliente-demo-001",
  "descripcion": "Fuga de agua en cocina",
  "pais": "CO",
  "ciudad": "Bogotá",
  "direccion": "Calle 100 # 15-20",
  "moneda": "COP",
  "monto_estimado": 180000,
  "simular_fallo_en_paso": null
}
```

Respuesta:

```json
{
  "saga_id": "e5b2a6ca-076e-44cc-837c-29676d81eb39",
  "trabajo_id": "b7c1...",
  "estado_global": "INICIADA",
  "mensaje": "Saga distribuida iniciada exitosamente en GestionDeTrabajosBC"
}
```

**Desviación consciente frente al documento de arquitectura de Entrega 5:** ese documento
proponía `POST /trabajos/{id}/completar`, asumiendo un trabajo ya existente. En la
implementación real el `Trabajo` no existe todavía antes de la saga — lo crea el propio
orquestador como su Paso 1. Por eso no hay `{id}` en la ruta: el `trabajo_id` se genera dentro
de la saga y se devuelve en la respuesta. El mismo documento habilita explícitamente este tipo
de ajuste ("ajustar rutas y verbos... a las capacidades reales que ya existan en cada
servicio").

Para la demostración de compensación (Sección 3.2 de `patron-sagas-y-saga-log.md`), el campo
`simular_fallo_en_paso` acepta `"PAGO"` u `"OPERACIONES"` y se reenvía tal cual al
orquestador, que ya implementa ese modo de prueba.

### 3.2 Endpoints de Agregación de Consultas

| Endpoint | Agrega | Uso en la demo |
| --- | --- | --- |
| `GET /trabajos/{trabajo_id}/estado` | `GET /trabajos/{id}` (gestion-trabajos) + búsqueda de la saga asociada | Ver el estado de negocio del trabajo y de su transacción en una sola llamada |
| `GET /sagas/{saga_id}` | Proxy directo al Saga Log (`GET /sagas/{id}` en gestion-trabajos) | Mostrar la línea de tiempo completa (camino feliz o compensación) en el video |
| `GET /sagas` | Proxy directo (`GET /sagas`) | Explorar las últimas transacciones sin conocer un `saga_id` de antemano |
| `POST /proveedores/{id}/wallet/retiros` | Traduce a `POST /billeteras/{id}/debitar` en WalletBC | Ejemplo de capacidad de negocio fuera de la saga, servida por el mismo BFF |

Nota sobre `GET /trabajos/{id}/estado`: `gestion-trabajos-service` no expone hoy una búsqueda
de saga por `trabajo_id`, así que el BFF la resuelve filtrando entre las sagas recientes
(`GET /sagas?limite=100`). Es suficiente para el volumen de la demo; si el número de sagas
concurrentes creciera, ese filtro debería moverse al propio servicio (índice por
`trabajo_id`).

---

## 4. Despliegue y Enrutamiento en Infraestructura

El BFF se agregó a `docker-compose.yml` como un servicio más (`bff`), sin base de datos
propia, con `URL_GESTION_TRABAJOS` y `URL_WALLET` apuntando a los nombres de host internos de
Docker. Expone el puerto `8005` (ligado a `127.0.0.1` igual que el resto, salvo que se fuerce
`IP_PUERTOS_INTERNOS=0.0.0.0`).

El `gateway` (Nginx, única entrada pública en el puerto 80) lo publica bajo el prefijo `/api`,
igual que a los demás bounded contexts (`/wallet`, `/trabajos`, `/operaciones`, `/pagos`):

```
/api/trabajos/completar-servicio  → bff:8005/trabajos/completar-servicio
/api/docs                          → Swagger del BFF
```

`/api` es el contrato público de esta entrega: los demás prefijos (`/wallet`, `/trabajos`,
...) siguen publicados para depuración interna de cada bounded context, pero un cliente
externo solo debería necesitar `/api`.

Ejecución:

```bash
docker compose up -d --build bff
# directo:            http://127.0.0.1:8005/docs
# vía gateway:         http://localhost/api/docs
```

Ver [`bff-service/README.md`](../../bff-service/README.md) para el detalle de arquitectura
interna y [`bff-service/collections/`](../../bff-service/collections/) para la colección
Postman (saga exitosa, saga compensada, consulta de Saga Log, retiro de wallet).
