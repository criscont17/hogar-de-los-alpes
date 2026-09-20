# Hogar de los Alpes — Arquitectura Distribuida

> **Maestría en Ingeniería de Software (MISO) · 2026-14**  
> Curso: Diseño y Arquitectura de Aplicaciones No Monolíticas (DANM)  
> Proyecto: Migración del sistema monolítico de Hogar de los Alpes (HdA) a una arquitectura reactiva distribuida basada en eventos.

## Implementación WalletBC

La implementación ejecutable del bounded context de billetera se encuentra en
`wallet-service/`. Incluye DDD, arquitectura hexagonal, CQS, PostgreSQL con SQLAlchemy,
API FastAPI y eventos de dominio e integración simulada. Consulte
[`wallet-service/README.md`](wallet-service/README.md) para instalarla, ejecutarla y
probar sus endpoints.

## Implementación GestionDeTrabajosBC

El núcleo del sistema, el motor del ciclo de vida de los trabajos, se encuentra en
`gestion-trabajos-service/`. Usa la misma arquitectura que WalletBC (DDD, hexagonal y CQS),
publica eventos de integración versionados y recibe comandos por Apache Pulsar. No conoce a
ningún partner. Demuestra el escenario de calidad de Escalabilidad (#4): la suscripción
`Shared` sobre `comandos-trabajo` reparte la carga entre réplicas sin cambios de código —
ver el experimento de carga en
[`gestion-trabajos-service/scripts/carga_escalabilidad.py`](gestion-trabajos-service/scripts/carga_escalabilidad.py).
Consulte [`gestion-trabajos-service/README.md`](gestion-trabajos-service/README.md).

## Implementación OperacionesBC

La relación con los partners B2B2C se encuentra en `operaciones-service/`:

- los acuerdos comerciales (agregado `Partner`);
- la capa anti-corrupción, con un adaptador por formato (REST propio, SOAP, webhooks);
- el circuit breaker por partner.

Se comunica con GestionDeTrabajosBC solo por Pulsar. Juntos demuestran los escenarios de
calidad de Interoperabilidad (#9) y Modificabilidad (#3). Consulte
[`operaciones-service/README.md`](operaciones-service/README.md) y su colección Postman.

## Implementación PagosBC

El cuarto microservicio, en `pagos-service/`: cobros al cliente (checkout) y pagos a
proveedores. Consume `TrabajoCerradoV1` de GestionDeTrabajosBC por Pulsar (Conformist) y
libera un pago por cada liquidación automáticamente. Aísla cada PSP (Wompi, PayU,
MercadoPago) detrás de un adaptador con capa anti-corrupción y circuit breaker propio —
demuestra el escenario de calidad de Interoperabilidad (#7). Consulte
[`pagos-service/README.md`](pagos-service/README.md) y su colección Postman.

---

## 📋 Tabla de Contenido

- [Contexto del Proyecto](#contexto-del-proyecto)
- [Estructura del Proyecto](#estructura-del-proyecto)
- [Despliegue con Docker y entrada pública](#despliegue-con-docker-y-entrada-pública)
- [Dependencias e Instalación](#dependencias-e-instalación)
- [Guía de Evaluación — Dónde encontrar cada entregable](#guía-de-evaluación--dónde-encontrar-cada-entregable)
- [Ramas del Repositorio](#ramas-del-repositorio)

---

## Contexto del Proyecto

Hogar de los Alpes (HdA) es una plataforma colombiana de servicios para el hogar (plomería, electricidad, carpintería, pintura, etc.) que conecta propietarios con proveedores verificados. Tras su adquisición por Seguros de los Alpes, el equipo de ingeniería fue contratado para diseñar e implementar la migración del monolito actual (en producción desde 2016) a un sistema reactivo distribuido capaz de soportar la expansión a México, Brasil y Argentina.

---

## Estructura del Proyecto

```
hogar-de-los-alpes/
├── README.md                          # Este archivo
├── .gitignore
│
├── wallet-service/                    # Microservicio WalletBC (billetera de proveedores)
│   ├── README.md                      # Arquitectura, ejecución y API del servicio
│   ├── Dockerfile                     # Imagen del servicio (se despliega con docker compose)
│   ├── requirements.txt               # Dependencias Python del servicio
│   ├── .env.example                   # Variables de entorno del servicio
│   └── app/                           # Código fuente
│       ├── seedwork/                  # Bloques genéricos compartidos por las capas
│       ├── dominio/                   # Agregado, entidades, VO, eventos y errores
│       ├── aplicacion/                # Comandos, queries, handlers, DTOs y puertos
│       └── infraestructura/           # API, SQLAlchemy y adaptadores de eventos
│
├── gestion-trabajos-service/          # Microservicio GestionDeTrabajosBC (core domain)
│   ├── README.md                      # Arquitectura, escenarios de calidad, Pulsar y API
│   ├── Dockerfile                     # Imagen del servicio (se despliega con docker compose)
│   ├── requirements.txt               # Dependencias Python del servicio
│   ├── collections/                   # Colección Postman del motor de trabajos
│   ├── scripts/                       # Publicar comandos y escuchar eventos en Pulsar
│   └── app/                           # seedwork/ dominio/ aplicacion/ infraestructura/
│
├── operaciones-service/               # Microservicio OperacionesBC (partners B2B2C)
│   ├── README.md                      # Acuerdos, capa anti-corrupción y decisiones
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── collections/                   # Colección Postman de los escenarios de calidad
│   ├── ejemplos/onboarding/           # Partner de ejemplo para demostrar el onboarding
│   └── app/                           # seedwork/ dominio/ aplicacion/ infraestructura/
│                                      # (incluye acl_partners/: capa anti-corrupción)
│
├── pagos-service/                     # Microservicio PagosBC (checkout y pagos a proveedores)
│   ├── README.md                      # PSPs, capa anti-corrupción, circuit breaker y Pulsar
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── collections/                   # Colección Postman del checkout y la resiliencia por PSP
│   └── app/                           # seedwork/ dominio/ aplicacion/ infraestructura/
│                                      # (incluye acl_psp/: capa anti-corrupción por pasarela)
│
├── gateway/                           # Entrada pública única (Nginx, puerto 80)
│   ├── Dockerfile
│   └── nginx.conf                     # Rutas /wallet, /trabajos, /operaciones y /pagos
│
├── docker-compose.yml                 # Gateway, los cuatro servicios, sus bases y Apache Pulsar
│
└── docs/                              # Documentación de arquitectura y diseño
    └── semana-2/                      # Entregables Semana 2: Diseño Estratégico DDD
        ├── dominios-subdominios/      # Dominios, sub-dominios y vision statements (.cml)
        ├── lenguaje-ubicuo/           # Diagramas e imágenes del lenguaje ubicuo
        └── contextos-acotados/        # Mapa de contextos acotados (.cml)
```

---

## Despliegue con Docker y entrada pública

`docker-compose.yml` levanta el sistema completo en una sola máquina:

- los cuatro microservicios;
- una base PostgreSQL por servicio;
- Apache Pulsar;
- un **gateway Nginx**, que es la única entrada pública.

```
                    Internet / red
                          │  :80
                    ┌─────▼─────┐
                    │  gateway  │  (Nginx)
                    └─────┬─────┘
   /wallet/…  /trabajos/…  /operaciones/…  /pagos/…
      │            │              │            │
   wallet   gestion-trabajos  operaciones    pagos        ← solo red interna de Docker
      │            │              │            │
   postgres   postgres-trabajos  postgres-   postgres-
                   └──── Apache Pulsar ─────┘ pagos
```

### Levantar el sistema

Desde la raíz del repositorio:

```bash
docker compose up -d --build --wait
```

- La primera construcción tarda unos minutos.
- `--wait` termina cuando todos los contenedores quedan `healthy`.
- Verifique con `curl http://localhost/`: responde el índice de contextos.

Si el puerto 80 está ocupado en su máquina, cambie el puerto del gateway. En Bash:

```bash
PUERTO_GATEWAY=8088 docker compose up -d --build --wait
```

En PowerShell:

```powershell
$env:PUERTO_GATEWAY="8088"; docker compose up -d --build --wait
```

### Rutas publicadas

El gateway quita el prefijo antes de reenviar. La URL pública es el prefijo seguido de la
ruta del servicio: por ejemplo, `GET /trabajos/trabajos/{id}` llega a GestionDeTrabajosBC
como `GET /trabajos/{id}`.

| Contexto | Entrada pública | Swagger | Ejemplo | Puerto directo (solo en la máquina) |
|---|---|---|---|---|
| WalletBC | `/wallet/…` | `/wallet/docs` | `POST /wallet/billeteras` | `127.0.0.1:8000` |
| GestionDeTrabajosBC | `/trabajos/…` | `/trabajos/docs` | `GET /trabajos/trabajos?limite=5` | `127.0.0.1:8001` |
| OperacionesBC | `/operaciones/…` | `/operaciones/docs` | `GET /operaciones/partners` | `127.0.0.1:8002` |
| PagosBC | `/pagos/…` | `/pagos/docs` | `GET /pagos/pagos` | `127.0.0.1:8003` |

El gateway también publica:

- `GET /`: índice de contextos;
- `GET /salud`: salud del propio gateway.

Una ruta que no existe responde `404` en JSON. Si un servicio está caído, sus rutas responden
`503` en JSON y los demás contextos siguen funcionando.

### Decisiones de la entrada pública

- **Una sola puerta.** Solo el gateway escucha en todas las interfaces (`0.0.0.0:80`). Las
  APIs directas, las bases y Pulsar quedan ligadas a `127.0.0.1`. Se pueden usar desde la
  propia máquina (Postman, scripts, clientes de base de datos), pero no quedan expuestas en
  la VM aunque el security group se abra de más. Para exponerlas a propósito, levante con
  `IP_PUERTOS_INTERNOS=0.0.0.0`.
- **Swagger detrás del prefijo.** Cada API arranca con `UVICORN_ROOT_PATH` igual a su
  prefijo. Así `/wallet/docs` carga su esquema, y "Try it out" llama a través del gateway.
  El precio es que, en Docker, Swagger no carga en el puerto directo (`localhost:8000/docs`),
  aunque las llamadas a la API por ese puerto siguen funcionando.
- **Resolución DNS por petición.** Nginx consulta el DNS interno de Docker en cada petición
  (con una caché de 10 s). Por eso reconstruir un solo servicio, como en el onboarding del
  escenario 3, no obliga a reiniciar el gateway, y el gateway arranca aunque falte un servicio.
- **Sin TLS por ahora.** Si se pone un balanceador de AWS con certificado delante de la VM,
  el gateway conserva `X-Forwarded-Proto`.
- **Use `127.0.0.1`, no `localhost`, para los puertos directos.** Al estar ligados solo a la
  interfaz IPv4, un cliente que resuelva `localhost` intenta primero `::1` y pierde unos 2
  segundos por petición antes de caer a IPv4. El gateway no tiene ese problema: escucha en
  ambas familias.

### Postman a través del gateway

Las colecciones apuntan por defecto a los puertos directos (`127.0.0.1:800x`), que funcionan
desde la misma máquina. Para usarlas contra la VM, cambie las variables base del environment
a la entrada pública:

| Colección | Variables | Valor |
|---|---|---|
| WalletBC | `base_url` | `http://<IP-pública>/wallet` |
| GestionDeTrabajosBC | `base_url` | `http://<IP-pública>/trabajos` |
| Escenarios de calidad (OperacionesBC) | `base_operaciones` / `base_trabajos` | `http://<IP-pública>/operaciones` / `http://<IP-pública>/trabajos` |
| PagosBC | `base_url` | `http://<IP-pública>/pagos` |

La carpeta 05 (onboarding) reconstruye OperacionesBC. Ese paso se ejecuta por SSH en la VM.

### En una máquina virtual de AWS (EC2)

Consumo medido del stack completo en reposo:

- **Memoria:** unos 2,9 GiB. Apache Pulsar usa 2,4 GiB, y cada API y cada base menos de 70 MiB.
- **CPU:** Pulsar tiene ráfagas de varios núcleos, sobre todo al arrancar.
- **Disco:** las imágenes ocupan unos 2,6 GB.

1. **Instancia:**
   - **Sistema:** Ubuntu 24.04 LTS, x86_64.
   - **Tamaño:** mínimo `t3.large` (2 vCPU, 8 GiB). Para el experimento de escalabilidad,
     `t3.xlarge` (4 vCPU, 16 GiB).
   - **Disco:** 30 GB gp3.
   - **IP:** asigne una *Elastic IP* para que no cambie al reiniciar.
2. **Security group (entrada):**
   - `80/tcp` desde las IPs que necesiten acceso, o `0.0.0.0/0` para una demo abierta;
   - `22/tcp` solo desde su IP.
   - No abra 5432–5435, 6650, 8000–8003 ni 8080.
3. **Docker:**

   ```bash
   curl -fsSL https://get.docker.com | sudo sh
   sudo usermod -aG docker $USER && sudo systemctl enable --now docker
   # cierre la sesión SSH y vuelva a entrar
   ```

4. **Despliegue:**

   ```bash
   git clone -b develop https://github.com/criscont17/hogar-de-los-alpes.git
   cd hogar-de-los-alpes
   docker compose up -d --build --wait
   curl http://localhost/salud
   ```

5. **Verificación desde su equipo:** abra `http://<IP-pública>/` y
   `http://<IP-pública>/trabajos/docs`.
6. **Actualizar tras un cambio:** `git pull && docker compose up -d --build --wait`.
7. **Acceso a una base desde su equipo, sin abrir puertos:**
   `ssh -L 5433:localhost:5433 ubuntu@<IP-pública>`, y conecte a `localhost:5433`.

Tenga en cuenta:

- Los contenedores tienen `restart: unless-stopped` y vuelven solos tras un reinicio de la VM.
- Los datos de PostgreSQL persisten en volúmenes.
- Pulsar arranca siempre limpio: los mensajes en tránsito al reiniciar se pierden, pero lo
  ya guardado en cada base se conserva.

---

## Dependencias e Instalación

### ContextMapper (Semana 2)

ContextMapper es la herramienta usada para modelar dominios, sub-dominios y contextos acotados mediante su DSL (Domain-Specific Language).

**Opción A — Plugin para VS Code**

1. Abrir VS Code.
2. Ir a la pestaña de Extensiones (`Ctrl+Shift+X` / `Cmd+Shift+X`).
3. Buscar **"ContextMapper"** e instalar la extensión oficial.
4. Abrir cualquier archivo `.cml` del proyecto — el plugin lo reconoce automáticamente.

> Documentación oficial: https://contextmapper.org/docs/vs-code-extension/

**Opción B — Plugin para IntelliJ / Eclipse**

> Documentación oficial: https://contextmapper.org/docs/ide-plugins/

**Requisitos previos (ambas opciones)**

- **Java 11 o superior** instalado y en el `PATH`.
- **Graphviz** instalado — ContextMapper lo necesita para generar los diagramas PNG.

> ⚠️ Después de instalar Graphviz, **reinicia VS Code** para que el plugin lo detecte en el PATH.

---

## Guía de Evaluación — Dónde encontrar cada entregable

### Semana 2 — Modelado Estratégico con DDD

| Descripción | Artefacto | Ubicación |
|---|---|---|
| Dominios y sub-dominios identificados y documentados con DSL de ContextMapper | `hda-dominios.cml` | [`docs/semana-2/dominios-subdominios/`](docs/semana-2/dominios-subdominios/) |
| Lenguaje ubicuo documentado | Imágenes / diagramas | [`docs/semana-2/lenguaje-ubicuo/`](docs/semana-2/lenguaje-ubicuo/) |
| Mapas de contextos acotados (AS-IS y TO-BE) en DSL de ContextMapper | `hda-context-map-*.cml` | [`docs/semana-2/contextos-acotados/`](docs/semana-2/contextos-acotados/) |

---

## Ramas del Repositorio

| Rama | Propósito |
|---|---|
| `main` | Versión estable — entregables revisados y aprobados. |
| `develop` | Rama de integración — trabajo en progreso antes de pasar a `main`. |
