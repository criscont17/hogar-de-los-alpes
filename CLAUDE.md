# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Repository overview

Academic project (MISO · DANM course) migrating the Hogar de los Alpes monolith to an event-driven distributed architecture. Code, identifiers, comments, docs and API payloads are all in **Spanish** — keep new code consistent with that (e.g. `ejecutar`, `guardar`, `obtener_por_id`).

- `wallet-service/` — **WalletBC** (provider wallets). FastAPI + SQLAlchemy; events only go to logs.
- `gestion-trabajos-service/` — **GestionDeTrabajosBC**, the core domain (job lifecycle orchestration). Knows nothing about partners.
- `operaciones-service/` — **OperacionesBC**: B2B2C partners, their commercial agreements, and the anti-corruption layer (one adapter per partner format). Talks to GestionDeTrabajosBC **only through Apache Pulsar**.
- `docs/semana-2/` — strategic DDD deliverables in ContextMapper DSL (`.cml`) plus event-storming images in `lenguaje-ubicuo/`, which define the ubiquitous language for jobs. The TO-BE map says Kafka (implementation uses Pulsar) and places partner rules in SiniestrosBC (implementation follows quality scenario #3, which puts them in OperacionesBC).
- `docker-compose.yml` (repo root):
  - `postgres` (wallet, port 5432);
  - `postgres-trabajos` (5433) and `gestion-trabajos` (8001);
  - `postgres-operaciones` (5434) and `operaciones` (8002);
  - `pulsar` standalone (6650/8080). It wipes its data on every start, because a restarted standalone container cannot recover its ledgers.

Each service is self-contained (own `app/` package, seedwork copy and database); they share nothing at runtime. Branches: `main` stable, `develop` integration.

## Commands

Run service commands from inside the service directory (the `app` package must be importable). Python 3.11+.

```bash
# Everything in Docker (from repo root); rebuild a service after changing its code
docker compose up -d --build --wait gestion-trabajos operaciones
docker compose logs -f operaciones gestion-trabajos
docker compose stop

# A service locally without Docker (SQLite + log broker)
pip install -r requirements.txt
DATABASE_URL=sqlite+pysqlite:///./app/data/<name>.db MESSAGE_BROKER=logging \
  uvicorn app.infraestructura.adaptadores.entrada.api.main:app --reload --port 8001   # 8002 for operaciones, 8000 for wallet

# Pulsar helpers (gestion-trabajos-service)
python -m scripts.escuchar_eventos --evento TrabajoCerrado
python -m scripts.publicar_comando CrearTrabajoV1 scripts/ejemplos/crear_trabajo.json
```

Create `app/data/` before using SQLite. Schemas come from `Base.metadata.create_all` at startup; there are no migrations, so ORM model changes won't alter existing tables. `configuracion.py` reads env vars at import time, and `contenedor.reiniciar()` resets the cached singletons.

**There is no automated test suite.** The team removed it on purpose, so don't add pytest back unless asked. Verification is manual through the Postman collections:

- `gestion-trabajos-service/collections/`: core flow and error cases.
- `operaciones-service/collections/EscenariosDeCalidad…`: quality scenarios across both services.
  - Folders 01–04 run together.
  - Folder 05 (onboarding) runs in steps: 05.1 → 05.2 → copy `ejemplos/onboarding/cooperativa_sur.py` into `acl_partners/`, register it, rebuild **only** `operaciones` → 05.3.

## Shared architecture (all services)

DDD + hexagonal + CQS with the same layering:

- `app/seedwork/` — business-agnostic bases (`Entity`, `ValueObject`, `AggregateRoot`, `DomainEvent`, `DomainError`, `DomainEventHandler`, …).
- `app/dominio/` — pure Python; aggregate, entities, value objects, domain events, errors, repository `Protocol`.
- `app/aplicacion/` — must not import FastAPI, Pydantic, SQLAlchemy or Pulsar. Each use case is a frozen-dataclass `XxxCommand`/`XxxQuery` plus an `XxxHandler.ejecutar()` returning dataclass DTOs. Ports live in `aplicacion/puertos/`.
- `app/infraestructura/adaptadores/entrada/api/` — Pydantic schemas → `mappers.py` → commands. Error → HTTP mapping is centralized in `main.py`; validation errors return **400** (not 422).
- `app/infraestructura/contenedor.py` (trabajos and operaciones) is the composition root shared by the REST API and the Pulsar consumer: `handlers_de_comandos(session)` plus `lru_cache`d singletons. Wallet wires in `dependencias.py`.
- Packages re-export public names via `__init__.py` with `__all__`.

Event flow: the aggregate records events → the handler calls `repo.guardar()` (**the repository commits inside `guardar`**) → `despachar_eventos_pendientes()` → the in-memory dispatcher calls every subscriber on the base `DomainEvent`. Subscriber failures are logged, never propagated; there is no Outbox. Rejections are events too (`DebitoRechazado`, `AsignacionRechazada`): dispatched **without saving**, then re-raised.

## GestionDeTrabajosBC specifics

- **Domain.** `Trabajo` owns `SubTrabajo`s forming a dependency DAG (`flujo.ordenar_flujo`).
  - States: `Bloqueado → Pendiente → Asignado → EnEjecucion → Completado`.
  - Completing a sub-trabajo auto-unblocks dependents.
  - `registrar_rediagnostico` freezes dependents (keeping their provider) and validates before mutating.
  - `CondicionesDelTrabajo` (cap, allowed provider network, SLA) is the only partner-derived concept, and it arrives already resolved.
  - **Never add partner ids, formats or agreement concepts here.**
- **`CrearTrabajoHandler`:**
  - idempotent by `(partner_id, referencia_externa)`, returning the existing job;
  - on `DomainError`/`ValueError` it dispatches `CreacionDeTrabajoRechazada` (not from an aggregate) before re-raising, so senders over Pulsar learn about the rejection.
- **Integration events** (`aplicacion/eventos_integracion/`, mapped only in `manejadores/traductores.py`):
  - `TRADUCTORES` maps a domain event to a *tuple* of versions (`TrabajoCreado → V1, V2`) that reuse its `event_id`/`occurred_at`; deprecate with `deprecado: ClassVar[bool] = True`.
  - The Pulsar broker sends JSON with properties `event_type`, `event_version`, `event_name`, `deprecado`, `partner_id`.
  - Partition key: `trabajo_id`, falling back to `referencia_externa`.
- **Pulsar command consumer** (`entrada/mensajeria/`): contracts in `mapeo_comandos.py`. `CrearTrabajoV1` accepts `canal`, `partner_id`, `referencia_externa` and `condiciones`. It acks successes and business errors, and nacks `ConflictoDeConcurrenciaError` and technical failures (DLQ after 3).
- **Persistence.** Optimistic locking via `version_id_col`; `guardar` always bumps `fecha_actualizacion`. `StaleDataError` → 409. The unique `(partner_id, referencia_externa)` → `TrabajoDuplicadoError`.

## OperacionesBC specifics

- **Domain.** Aggregate `Partner` (slug `PartnerId`) owns `AcuerdoComercial`, a VO of `CondicionComercial(tipo TOPE|SLA, clave, valor)` plus an optional provider network. `AcuerdoComercial.resolver(clave_sla, clave_tope, tope_solicitado)` returns `CondicionesAplicables`:
  - a key that isn't agreed → `CondicionNoPactadaError` (400);
  - a requested cap above the agreed one → `TopeFueraDelAcuerdoError` (409).
  - Agreements are data: registered or renegotiated with `PUT /partners/{id}` (seeded at startup by `infraestructura/semilla.py`).
- **ACL** (`infraestructura/adaptadores/acl_partners/`).
  - Each partner is one `AdaptadorDePartnerBase` subclass that **only translates format**:
    - partner request → `SolicitudDePartner` (canonical data + `clave_sla`/`clave_tope`/`tope_solicitado`);
    - `TrabajoDePartnerDTO` → partner format;
    - `EventoDeTrabajoRecibido` (event name + primitive dict; never import GestionDeTrabajosBC classes) → `MensajeParaPartner` or `None`.
  - Translation is all-or-nothing (`SolicitudDePartnerInvalidaError` → 400).
  - **Onboarding** = `PUT /partners/{id}` + new adapter file + one entry in `registro.py` + rebuild operaciones only. Never touch `app/dominio`, `app/aplicacion` or gestion-trabajos-service.
  - `ejemplos/onboarding/cooperativa_sur.py` is a deliberately unregistered sample; keep it out of `registro.py`.
- **Flow.**
  - `CrearTrabajoDesdePartnerHandler`: loads the partner, translates, resolves conditions, and sends `CrearTrabajoV1` through the `GestionDeTrabajos` port (`PulsarGestionDeTrabajos` uses synchronous `send`; a failure → 503). It then records a `Solicitado` view and returns **202**. A repeated reference returns 200, unless it was rejected.
  - `ProcesarEventoDeTrabajoHandler`: consumed from `eventos-trabajo` (Key_Shared, subscription `operaciones-bc`). It updates the per-partner read model with pure functions in `aplicacion/proyeccion.py`, then calls `adaptador.notificar()`.
- **Partner resilience.** `SincronizadorDePartner` gives each partner its own thread, ordered pending queue and `CircuitBreaker`; `notificar()` never blocks. Partner cores are simulated by `ClientePartnerSimulado` (`PUT /partners/{id}/simulacion`); health is at `GET /partners/{id}/salud`.
