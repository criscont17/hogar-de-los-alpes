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
├── docker-compose.yml                 # PostgreSQL de cada servicio, Apache Pulsar y los servicios
│
└── docs/                              # Documentación de arquitectura y diseño
    └── semana-2/                      # Entregables Semana 2: Diseño Estratégico DDD
        ├── dominios-subdominios/      # Dominios, sub-dominios y vision statements (.cml)
        ├── lenguaje-ubicuo/           # Diagramas e imágenes del lenguaje ubicuo
        └── contextos-acotados/        # Mapa de contextos acotados (.cml)
```

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
