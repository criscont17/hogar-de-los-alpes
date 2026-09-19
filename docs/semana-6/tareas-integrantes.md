# Distribución de Tareas y Responsabilidades del Equipo
## Proyecto: Hogar de los Alpes

Este documento detalla a nivel general las responsabilidades, componentes y aportes arquitecturales desarrollados por cada integrante del equipo para la solución de microservicios orientada a eventos, los escenarios de calidad, la persistencia y la transaccionalidad distribuida del sistema.

> [!NOTE]
> **Alcance temporal del documento:**  
> Lo descrito a continuación consolida tanto las tareas ejecutadas y entregadas en la **Semana 6** (diseño e implementación de los 4 microservicios, broker Apache Pulsar, persistencia descentralizada y validación de escenarios de calidad) como las tareas que se encuentran en desarrollo y ejecución para la **Semana 7** (diseño e implementación de transacciones distribuidas mediante el Patrón Sagas Orquestado y persistencia de Saga Log).

---

## 1. Detalle de Contribuciones por Integrante

### Cristhian Contreras
* **Microservicio Billetera (`wallet-service`):**
  - Implementación integral bajo Arquitectura Hexagonal y separación CQS.
  - Modelado del dominio financiero puro (`Billetera`, libro mayor append-only de `Movimiento`) asegurando auditoría inmutable de saldos.
  - Persistencia relacional desacoplada con PostgreSQL y SQLAlchemy.
  - Despacho y publicación asíncrona de eventos de dominio e integración.
* **Transaccionalidad Distribuida - Patrón Sagas:**
  - Diseño e implementación del `OrquestadorSagaTrabajo` en `gestion-trabajos-service`.
  - Persistencia de trazabilidad con `SagaLog` relacional (`saga_instancias`, `saga_pasos`) para garantizar atomicidad y consistencia eventual.
  - Publicación de comandos y consumo asíncrono de eventos de compensación y éxito vía Apache Pulsar entre los servicios de trabajos, pagos y operaciones.

---

### Juan Pablo Delgado
* **Microservicio de Gestión de Trabajos (`gestion-trabajos-service`):**
  - Modelado del agregado central `Trabajo` y su máquina de estados (asignación, ejecución, novedades y cierre).
  - Control de concurrencia optimista y gestión de eventos de integración versionados (`TrabajoCreadoV1/V2`, `TrabajoCerradoV1`).
* **Microservicio de Operaciones (`operaciones-service`):**
  - Implementación de la capa de integración con aliados externos (ACL) soportando protocolos heterogéneos (REST, SOAP y Webhooks).
  - Implementación de patrones de resiliencia (Circuit Breaker) por aliado para aislar fallas de terceros (**Escenario de Calidad #9**).
* **Infraestructura, Integración y Despliegue:**
  - Configuración unificada de `docker-compose` (Reverse Proxy Nginx en puerto 80, broker Apache Pulsar con Zookeeper y 4 bases de datos PostgreSQL aisladas).
  - Configuración y parametrización de despliegue en AWS y colecciones de pruebas interoperables en Postman.

---

### Camilo Téllez
* **Microservicio de Pagos (`pagos-service`):**
  - Diseño e implementación completa de `PagosBC` (checkout de clientes y dispersión/liquidación de aliados).
  - Consumidor de eventos de integración (`TrabajoCerradoV1`) bajo relación Conformista.
  - Capa Anti-Corruption Layer (ACL) para pasarelas de pago múltiples (Wompi Colombia, PayU Colombia, MercadoPago Argentina).
  - Implementación de Circuit Breakers independientes por pasarela de pago (**Escenario de Calidad #7**).
* **Experimentación y Escalabilidad:**
  - Diseño y ejecución de la suite de pruebas de carga y escalabilidad (`carga_escalabilidad.py`).
  - Validación del auto-escalamiento horizontal y consumo concurrente usando suscripciones compartidas (`Shared`) de Apache Pulsar (**Escenario de Calidad #4**).

---

### Maycol Steven Avendaño Niño
* **Arquitectura Base y Seedwork Transversal:**
  - Definición e implementación de los bloques fundamentales de DDD (`AggregateRoot`, `Entity`, `ValueObject`, `DomainEvent`, `IntegrationEvent`), asegurando inversión de dependencias y desacoplamiento de capas en el ecosistema.
* **Capa de Traducción de Eventos (Anti-Corruption):**
  - Implementación del patrón de traductores de eventos (`traductores.py`), aislando el modelo interno de dominio de los contratos de integración que se publican hacia el bus de mensajería.
* **Verificación de Integración y Pruebas de API:**
  - Diseño y documentación de la suite de pruebas e interoperabilidad en Postman para la validación funcional de contratos (`WalletBC.postman_collection.json` y entornos asociados).
* **Estandarización y Refactorización Arquitectural:**
  - Reestructuración modular del servicio hacia arquitectura hexagonal limpia, saneamiento de dependencias y revisión y aprobación de Pull Requests (`code review`).

---

## 2. Mapeo con Escenarios de Calidad y Pilares Arquitecturales del Sistema

| Escenario / Pilar Arquitectural | Foco Técnico | Responsable(s) Principal(es) | Evidencia en Repositorio |
| :--- | :--- | :--- | :--- |
| **Escenario #3: Interoperabilidad / Modificabilidad** | Adaptación de protocolos heterogéneos y compatibilidad de eventos V1/V2 | **Juan Pablo Delgado** | Eventos versionados en `gestion-trabajos-service` y adaptadores en `operaciones-service`. |
| **Escenario #4: Escalabilidad** | Procesamiento concurrente y pruebas de carga masiva | **Camilo Téllez** | `gestion-trabajos-service/scripts/carga_escalabilidad.py`, suscripciones `Shared` en Apache Pulsar. |
| **Escenario #7: Resiliencia en Pagos** | Tolerancia a fallos e interoperabilidad con múltiples PSPs | **Camilo Téllez** | Circuit Breakers y clientes simulados en `pagos-service/app/infraestructura/adaptadores/acl_psp/`. |
| **Escenario #9: Resiliencia en Operaciones** | Interoperabilidad con partners heterogéneos y aislamiento de caídas | **Juan Pablo Delgado** | Circuit Breakers, colas dedicadas y adaptadores en `operaciones-service/app/infraestructura/adaptadores/acl_aliados/`. |
| **Transacciones Distribuidas** | Consistencia eventual mediante Sagas y persistencia de Saga Log | **Cristhian Contreras** | `OrquestadorSagaTrabajo` y modelos de persistencia `SagaLog` en `gestion-trabajos-service`. |
| **Seedwork y Pruebas de Integración** | Abstracciones base DDD, traductores de eventos y suite Postman | **Maycol Steven Avendaño** | Clases base de Seedwork, `traductores.py` y colecciones de prueba en `wallet-service`. |
