# Hogar de los Alpes — Arquitectura Distribuida

> **Maestría en Ingeniería de Software (MISO) · 2026-14**  
> Curso: Diseño y Arquitectura de Aplicaciones No Monolíticas (DANM)  
> Proyecto: Migración del sistema monolítico de Hogar de los Alpes (HdA) a una arquitectura reactiva distribuida basada en eventos.

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
├── src/                               # Código fuente (POC e implementaciones por semana)
│   └── (vacío — se poblará en semanas posteriores)
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
