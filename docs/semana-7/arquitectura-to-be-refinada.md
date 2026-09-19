# Refinamiento de Arquitectura TO-BE y Vistas Dinámicas
## Entrega Semana 7 — Hogar de los Alpes

---

## 1. Refinamiento del Mapa de Contextos TO-BE
### 1.1 Justificación de Cambios Arquitecturales
<!-- Explicar qué cambió respecto a la versión inicial TO-BE (incorporación de BFF, Orquestador de Sagas, tópicos de compensación y adaptación de contratos). -->

### 1.2 Definición Formal en ContextMapper
<!-- Referencia y diagrama conceptual actualizado de contextos acotados. -->

---

## 2. Vistas Dinámicas y de Proceso (Diagramas Mermaid)
### 2.1 Flujo Exitoso de la Saga (Happy Path)
<!-- Diagrama de secuencia Mermaid detallando la interacción entre cliente, BFF, Orquestador y microservicios. -->

```mermaid
sequenceDiagram
    autonumber
    %% Definir secuencia del camino exitoso
```

### 2.2 Flujo Compensatorio ante Fallos
<!-- Diagrama de secuencia Mermaid mostrando la detección de error y la ejecución de compensaciones en orden inverso. -->

```mermaid
sequenceDiagram
    autonumber
    %% Definir secuencia del flujo compensatorio
```

---

## 3. Topología de Despliegue Consolidada
<!-- Vista de distribución física de contenedores, redes internas aisladas y punto de entrada Gateway/BFF. -->
