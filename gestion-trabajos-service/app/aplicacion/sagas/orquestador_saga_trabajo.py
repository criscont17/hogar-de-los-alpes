import logging
from typing import Any
from uuid import UUID, uuid4

from app.aplicacion.sagas.contratos_saga import (
    COMANDO_ASIGNAR_PROVEEDOR,
    COMANDO_AUTORIZAR_PAGO,
    COMANDO_REVERTIR_PAGO,
    SolicitudInicioSaga,
)
from app.dominio.trabajo import (
    CanalDeOrigen,
    Categoria,
    CondicionesDelTrabajo,
    Dinero,
    OrigenDelTrabajo,
    SubTrabajoPlaneado,
    Trabajo,
    TrabajoFactory,
    TrabajoId,
    Ubicacion,
    Urgencia,
)


logger = logging.getLogger("trabajos.orquestador_saga")


class OrquestadorSagaTrabajo:
    """Coordinador central de la Saga de Activación de Servicio (Orquestación).

    Coordina la secuencia distribuida entre:
    1. GestionDeTrabajosBC (crea el trabajo preliminar)
    2. PagosBC (autoriza/retiene el pago)
    3. OperacionesBC (asigna partner/proveedor)

    Si cualquier paso falla, ejecuta las transacciones de compensación en orden inverso.
    """

    def __init__(
        self,
        saga_log_repo,
        trabajo_repo,
        command_publisher,
        topico_comandos_pago: str,
        topico_comandos_operaciones: str,
    ) -> None:
        self._saga_log = saga_log_repo
        self._trabajos = trabajo_repo
        self._publisher = command_publisher
        self._topico_pago = topico_comandos_pago
        self._topico_ops = topico_comandos_operaciones

    def iniciar_saga(self, solicitud: SolicitudInicioSaga) -> UUID:
        saga_id = uuid4()

        origen = OrigenDelTrabajo(
            canal=CanalDeOrigen.PARTNER if solicitud.partner_id else CanalDeOrigen.MARKETPLACE,
            partner_id=solicitud.partner_id,
            referencia_externa=solicitud.referencia_externa,
        )
        ubicacion = Ubicacion(
            pais=solicitud.pais,
            ciudad=solicitud.ciudad,
            direccion=solicitud.direccion,
        )
        condiciones = CondicionesDelTrabajo(
            monto_maximo=Dinero(solicitud.monto_estimado, solicitud.moneda)
        )
        plan = [
            SubTrabajoPlaneado(
                clave="st-principal",
                categoria=Categoria.PLOMERIA,
                descripcion=solicitud.descripcion,
            )
        ]
        trabajo = TrabajoFactory.crear(
            origen=origen,
            descripcion=solicitud.descripcion,
            urgencia=Urgencia.MEDIA,
            ubicacion=ubicacion,
            moneda=solicitud.moneda,
            condiciones=condiciones,
            plan=plan,
        )
        trabajo_id = trabajo.id.valor


        payload_inicial = {
            "trabajo_id": str(trabajo_id),
            "cliente_id": solicitud.cliente_id,
            "descripcion": solicitud.descripcion,
            "pais": solicitud.pais,
            "ciudad": solicitud.ciudad,
            "direccion": solicitud.direccion,
            "moneda": solicitud.moneda,
            "monto_estimado": float(solicitud.monto_estimado),
            "partner_id": solicitud.partner_id,
            "referencia_externa": solicitud.referencia_externa,
            "simular_fallo_en_paso": solicitud.simular_fallo_en_paso,
        }

        # 1. Registrar inicio de la saga en el Saga Log
        self._saga_log.registrar_inicio_saga(
            saga_id=saga_id,
            tipo_saga="SagaActivacionServicio",
            trabajo_id=trabajo_id,
            payload_inicial=payload_inicial,
        )

        # 2. Paso 1: Crear trabajo preliminar en GestionDeTrabajosBC
        self._saga_log.registrar_paso_iniciado(
            saga_id=saga_id,
            paso_numero=1,
            nombre_paso="CREAR_TRABAJO_PRELIMINAR",
            servicio_participante="gestion-trabajos-service",
            comando_enviado={"trabajo_id": str(trabajo_id)},
        )

        self._trabajos.guardar(trabajo)

        self._saga_log.registrar_paso_completado(
            saga_id=saga_id,
            paso_numero=1,
            evento_recibido={"estado_trabajo": trabajo.estado.value},
        )

        # 3. Paso 2: Emitir comando de autorización de pago a PagosBC
        self._saga_log.registrar_paso_iniciado(
            saga_id=saga_id,
            paso_numero=2,
            nombre_paso="AUTORIZAR_PAGO",
            servicio_participante="pagos-service",
            comando_enviado={
                "monto": float(solicitud.monto_estimado),
                "moneda": solicitud.moneda,
            },
        )

        comando_pago = {
            "trabajo_id": str(trabajo_id),
            "cliente_id": solicitud.cliente_id,
            "monto": float(solicitud.monto_estimado),
            "moneda": solicitud.moneda,
            "simular_fallo": solicitud.simular_fallo_en_paso == "PAGO",
        }
        self._publisher.enviar_comando(
            topico=self._topico_pago,
            tipo_comando=COMANDO_AUTORIZAR_PAGO,
            saga_id=saga_id,
            payload=comando_pago,
            partition_key=str(trabajo_id),
        )

        logger.info("Saga %s iniciada para trabajo=%s. Paso 2 enviado a PagosBC.", saga_id, trabajo_id)
        return saga_id

    def procesar_pago_autorizado(self, saga_id: UUID, payload: dict[str, Any]) -> None:
        logger.info("Saga %s: Pago autorizado recibido de PagosBC", saga_id)
        self._saga_log.registrar_paso_completado(
            saga_id=saga_id,
            paso_numero=2,
            evento_recibido=payload,
        )

        instancia = self._saga_log.obtener_saga(saga_id)
        if not instancia:
            logger.error("Saga %s no encontrada", saga_id)
            return

        payload_inicial = instancia.payload_inicial

        # Paso 3: Emitir comando de asignación de proveedor a OperacionesBC
        self._saga_log.registrar_paso_iniciado(
            saga_id=saga_id,
            paso_numero=3,
            nombre_paso="ASIGNAR_PROVEEDOR",
            servicio_participante="operaciones-service",
            comando_enviado={"partner_id": payload_inicial.get("partner_id")},
        )

        comando_ops = {
            "trabajo_id": str(instancia.trabajo_id),
            "partner_id": payload_inicial.get("partner_id"),
            "pais": payload_inicial.get("pais"),
            "ciudad": payload_inicial.get("ciudad"),
            "simular_fallo": payload_inicial.get("simular_fallo_en_paso") == "OPERACIONES",
        }
        self._publisher.enviar_comando(
            topico=self._topico_ops,
            tipo_comando=COMANDO_ASIGNAR_PROVEEDOR,
            saga_id=saga_id,
            payload=comando_ops,
            partition_key=str(instancia.trabajo_id),
        )

    def procesar_proveedor_asignado(self, saga_id: UUID, payload: dict[str, Any]) -> None:
        logger.info("Saga %s: Proveedor asignado recibido de OperacionesBC", saga_id)
        self._saga_log.registrar_paso_completado(
            saga_id=saga_id,
            paso_numero=3,
            evento_recibido=payload,
        )

        instancia = self._saga_log.obtener_saga(saga_id)
        if not instancia:
            return

        # Paso 4: Finalizar exitosamente la transacción
        trabajo = self._trabajos.obtener_por_id(TrabajoId(instancia.trabajo_id))
        if trabajo:
            self._trabajos.guardar(trabajo)

        self._saga_log.finalizar_saga(saga_id=saga_id, estado_final="COMPLETADA_EXITOSA")
        logger.info("Saga %s COMPLETADA EXITOSAMENTE", saga_id)

    def procesar_pago_rechazado(self, saga_id: UUID, payload: dict[str, Any]) -> None:
        motivo = payload.get("motivo", "Fondos insuficientes o fallo en pago")
        logger.warning("Saga %s: Pago rechazado: %s. Iniciando compensación.", saga_id, motivo)
        self._saga_log.registrar_paso_fallido(
            saga_id=saga_id,
            paso_numero=2,
            error=motivo,
            evento_recibido=payload,
        )

        instancia = self._saga_log.obtener_saga(saga_id)
        if not instancia:
            return

        # Compensar Paso 1: Cancelar trabajo en GestionDeTrabajosBC
        trabajo = self._trabajos.obtener_por_id(TrabajoId(instancia.trabajo_id))
        if trabajo:
            trabajo.cancelar(motivo=f"Saga fallida por pago: {motivo}")
            self._trabajos.guardar(trabajo)

        self._saga_log.registrar_paso_compensacion(
            saga_id=saga_id,
            paso_numero=1,
            nombre_paso="COMPENSAR_CREAR_TRABAJO",
            servicio_participante="gestion-trabajos-service",
            estado="COMPENSADO",
            evento_compensacion={"trabajo_cancelado": True},
        )

        self._saga_log.finalizar_saga(saga_id=saga_id, estado_final="COMPENSADA", error=motivo)
        logger.info("Saga %s COMPENSADA exitosamente tras fallo de pago", saga_id)

    def procesar_proveedor_rechazado(self, saga_id: UUID, payload: dict[str, Any]) -> None:
        motivo = payload.get("motivo", "Sin proveedores disponibles o partner sin cobertura")
        logger.warning("Saga %s: Asignación rechazada: %s. Compensando Pagos y Trabajos.", saga_id, motivo)
        self._saga_log.registrar_paso_fallido(
            saga_id=saga_id,
            paso_numero=3,
            error=motivo,
            evento_recibido=payload,
        )

        instancia = self._saga_log.obtener_saga(saga_id)
        if not instancia:
            return

        # 1. Compensar Paso 2: Revertir reserva/pago en PagosBC
        self._saga_log.registrar_paso_compensacion(
            saga_id=saga_id,
            paso_numero=2,
            nombre_paso="COMPENSAR_REVERTIR_PAGO",
            servicio_participante="pagos-service",
            estado="EN_PROCESO",
            comando_compensacion={"trabajo_id": str(instancia.trabajo_id)},
        )

        comando_revertir = {
            "trabajo_id": str(instancia.trabajo_id),
            "motivo": motivo,
        }
        self._publisher.enviar_comando(
            topico=self._topico_pago,
            tipo_comando=COMANDO_REVERTIR_PAGO,
            saga_id=saga_id,
            payload=comando_revertir,
            partition_key=str(instancia.trabajo_id),
        )

        # 2. Compensar Paso 1: Cancelar trabajo en GestionDeTrabajosBC
        trabajo = self._trabajos.obtener_por_id(TrabajoId(instancia.trabajo_id))
        if trabajo:
            trabajo.cancelar(motivo=f"Saga fallida por asignación: {motivo}")
            self._trabajos.guardar(trabajo)

        self._saga_log.registrar_paso_compensacion(
            saga_id=saga_id,
            paso_numero=1,
            nombre_paso="COMPENSAR_CREAR_TRABAJO",
            servicio_participante="gestion-trabajos-service",
            estado="COMPENSADO",
            evento_compensacion={"trabajo_cancelado": True},
        )

        self._saga_log.finalizar_saga(saga_id=saga_id, estado_final="COMPENSADA", error=motivo)
        logger.info("Saga %s COMPENSADA exitosamente tras fallo de asignación", saga_id)
