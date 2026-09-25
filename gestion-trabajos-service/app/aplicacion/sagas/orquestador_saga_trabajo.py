import logging
from typing import Any
from uuid import UUID, uuid4

from app.aplicacion.sagas.contratos_saga import (
    COMANDO_ACREDITAR_PROVEEDOR,
    COMANDO_ASIGNAR_PROVEEDOR,
    COMANDO_AUTORIZAR_PAGO,
    COMANDO_LIBERAR_ASIGNACION,
    COMANDO_REVERTIR_PAGO,
    FALLO_EN_EJECUCION,
    FALLO_EN_OPERACIONES,
    FALLO_EN_PAGO,
    FALLO_EN_WALLET,
    PASO_ACREDITAR_PROVEEDOR,
    PASO_ASIGNAR_PROVEEDOR,
    PASO_AUTORIZAR_PAGO,
    PASO_CREAR_TRABAJO,
    PASO_EJECUTAR_TRABAJO,
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
    4. OperacionesBC (reporta la ejecución del trabajo en campo)
    5. WalletBC (acredita la liquidación al proveedor)

    Los cuatro primeros pasos son reversibles: si alguno falla, el orquestador
    ejecuta las compensaciones en orden estrictamente inverso. El quinto no lo es,
    porque para cuando se acredita el trabajo físico ya se prestó: si la acreditación
    falla de forma definitiva el trabajo pasa a `EN_DISPUTA` para revisión manual de
    Operaciones, en lugar de deshacer un servicio que el cliente ya recibió.
    """

    def __init__(
        self,
        saga_log_repo,
        trabajo_repo=None,
        command_publisher=None,
        topico_comandos_pago: str = "",
        topico_comandos_operaciones: str = "",
        topico_comandos_wallet: str = "",
        fabrica_uow=None,
        dispatcher=None,
    ) -> None:
        self._saga_log = saga_log_repo
        self._trabajos = trabajo_repo
        self._fabrica_uow = fabrica_uow
        self._publisher = command_publisher
        self._topico_pago = topico_comandos_pago
        self._topico_ops = topico_comandos_operaciones
        self._topico_wallet = topico_comandos_wallet
        self._dispatcher = dispatcher

    def _guardar_trabajo(self, trabajo: Trabajo) -> None:
        if self._fabrica_uow is not None:
            with self._fabrica_uow() as uow:
                uow.trabajos.guardar(trabajo)
                uow.confirmar()
        elif self._trabajos is not None:
            self._trabajos.guardar(trabajo)
        self._anunciar_hechos(trabajo)

    def _anunciar_hechos(self, trabajo: Trabajo) -> None:
        """Publica los eventos del agregado una vez que el cambio es definitivo."""

        if self._dispatcher is None:
            return
        for evento in trabajo.pull_domain_events():
            self._dispatcher.despachar(evento)

    def _obtener_trabajo(self, trabajo_id: TrabajoId) -> Trabajo | None:
        if self._fabrica_uow is not None:
            with self._fabrica_uow() as uow:
                return uow.trabajos.obtener_por_id(trabajo_id)
        elif self._trabajos is not None:
            return self._trabajos.obtener_por_id(trabajo_id)
        return None

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
            paso_numero=PASO_CREAR_TRABAJO,
            nombre_paso="CREAR_TRABAJO_PRELIMINAR",
            servicio_participante="gestion-trabajos-service",
            comando_enviado={"trabajo_id": str(trabajo_id)},
        )

        self._guardar_trabajo(trabajo)

        self._saga_log.registrar_paso_completado(
            saga_id=saga_id,
            paso_numero=PASO_CREAR_TRABAJO,
            evento_recibido={"estado_trabajo": trabajo.estado.value},
        )

        # 3. Paso 2: Emitir comando de autorización de pago a PagosBC
        self._saga_log.registrar_paso_iniciado(
            saga_id=saga_id,
            paso_numero=PASO_AUTORIZAR_PAGO,
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
            "simular_fallo": solicitud.simular_fallo_en_paso == FALLO_EN_PAGO,
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
            paso_numero=PASO_AUTORIZAR_PAGO,
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
            paso_numero=PASO_ASIGNAR_PROVEEDOR,
            nombre_paso="ASIGNAR_PROVEEDOR",
            servicio_participante="operaciones-service",
            comando_enviado={"partner_id": payload_inicial.get("partner_id")},
        )

        fallo_simulado = payload_inicial.get("simular_fallo_en_paso")
        comando_ops = {
            "trabajo_id": str(instancia.trabajo_id),
            "partner_id": payload_inicial.get("partner_id"),
            "pais": payload_inicial.get("pais"),
            "ciudad": payload_inicial.get("ciudad"),
            "simular_fallo": fallo_simulado == FALLO_EN_OPERACIONES,
            # OperacionesBC reporta la ejecución en campo justo después de asignar;
            # esta bandera le pide simular que el proveedor no pudo ejecutarla.
            "simular_fallo_ejecucion": fallo_simulado == FALLO_EN_EJECUCION,
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
            paso_numero=PASO_ASIGNAR_PROVEEDOR,
            evento_recibido=payload,
        )

        instancia = self._saga_log.obtener_saga(saga_id)
        if not instancia:
            return

        # Paso 4: la ejecución en campo. No lleva comando: el trabajo ya está asignado
        # y es OperacionesBC quien reporta cómo terminó.
        self._saga_log.registrar_paso_iniciado(
            saga_id=saga_id,
            paso_numero=PASO_EJECUTAR_TRABAJO,
            nombre_paso="EJECUTAR_TRABAJO",
            servicio_participante="operaciones-service",
            comando_enviado={"proveedor_id": self._proveedor_de(instancia, payload)},
        )

    def procesar_ejecucion_completada(self, saga_id: UUID, payload: dict[str, Any]) -> None:
        """El proveedor ejecutó el trabajo: solo queda pagarle su liquidación."""

        logger.info("Saga %s: Ejecución completada reportada por OperacionesBC", saga_id)
        self._saga_log.registrar_paso_completado(
            saga_id=saga_id,
            paso_numero=PASO_EJECUTAR_TRABAJO,
            evento_recibido=payload,
        )

        instancia = self._saga_log.obtener_saga(saga_id)
        if not instancia:
            return

        payload_inicial = instancia.payload_inicial
        proveedor_id = self._proveedor_de(instancia, payload)

        # Paso 5: Acreditar al proveedor en WalletBC. Es el último paso y el único
        # que no se compensa: si falla, el trabajo entra en disputa.
        self._saga_log.registrar_paso_iniciado(
            saga_id=saga_id,
            paso_numero=PASO_ACREDITAR_PROVEEDOR,
            nombre_paso="ACREDITAR_PROVEEDOR",
            servicio_participante="wallet-service",
            comando_enviado={
                "proveedor_id": proveedor_id,
                "monto": payload_inicial.get("monto_estimado"),
                "moneda": payload_inicial.get("moneda"),
            },
        )

        comando_wallet = {
            "trabajo_id": str(instancia.trabajo_id),
            "proveedor_id": proveedor_id,
            "monto": payload_inicial.get("monto_estimado"),
            "moneda": payload_inicial.get("moneda"),
            "simular_fallo": payload_inicial.get("simular_fallo_en_paso") == FALLO_EN_WALLET,
        }
        self._publisher.enviar_comando(
            topico=self._topico_wallet,
            tipo_comando=COMANDO_ACREDITAR_PROVEEDOR,
            saga_id=saga_id,
            payload=comando_wallet,
            partition_key=str(instancia.trabajo_id),
        )

    @staticmethod
    def _proveedor_de(instancia, payload: dict[str, Any]) -> str | None:
        """Resuelve el proveedor asignado: del evento recibido o del Saga Log.

        Quien reporta la ejecución no siempre repite el `proveedor_id`, pero el
        paso de asignación ya lo dejó registrado en su evento.
        """

        if payload.get("proveedor_id"):
            return payload["proveedor_id"]
        for paso in instancia.pasos:
            if paso.paso_numero == PASO_ASIGNAR_PROVEEDOR and paso.evento_recibido:
                proveedor_id = paso.evento_recibido.get("proveedor_id")
                if proveedor_id:
                    return proveedor_id
        return instancia.payload_inicial.get("proveedor_id")

    def procesar_wallet_acreditada(self, saga_id: UUID, payload: dict[str, Any]) -> None:
        """Último paso confirmado: la saga alcanzó consistencia eventual completa."""

        logger.info("Saga %s: WalletBC acreditó al proveedor", saga_id)
        self._saga_log.registrar_paso_completado(
            saga_id=saga_id,
            paso_numero=PASO_ACREDITAR_PROVEEDOR,
            evento_recibido=payload,
        )

        instancia = self._saga_log.obtener_saga(saga_id)
        if not instancia:
            return

        self._saga_log.finalizar_saga(saga_id=saga_id, estado_final="COMPLETADA_EXITOSA")
        logger.info("Saga %s COMPLETADA EXITOSAMENTE", saga_id)

    def procesar_acreditacion_fallida(self, saga_id: UUID, payload: dict[str, Any]) -> None:
        """Acreditación agotada: se abre la disputa, no se compensa nada.

        WalletBC ya reintentó con backoff antes de emitir este evento. Revertir el
        pago o cancelar el trabajo dejaría al proveedor sin respaldo de un servicio
        que efectivamente prestó, así que el trabajo queda `EN_DISPUTA` y Operaciones
        lo resuelve a mano.
        """

        motivo = payload.get("motivo", "No fue posible acreditar al proveedor")
        intentos = payload.get("intentos")
        logger.error(
            "Saga %s: acreditación fallida tras %s intento(s): %s. El trabajo pasa a EN_DISPUTA.",
            saga_id,
            intentos,
            motivo,
        )
        self._saga_log.registrar_paso_fallido(
            saga_id=saga_id,
            paso_numero=PASO_ACREDITAR_PROVEEDOR,
            error=motivo,
            evento_recibido=payload,
        )

        instancia = self._saga_log.obtener_saga(saga_id)
        if not instancia:
            return

        trabajo = self._obtener_trabajo(TrabajoId(instancia.trabajo_id))
        if trabajo:
            trabajo.marcar_en_disputa(motivo=f"Acreditación al proveedor fallida: {motivo}")
            self._guardar_trabajo(trabajo)

        self._saga_log.registrar_paso_compensacion(
            saga_id=saga_id,
            paso_numero=PASO_ACREDITAR_PROVEEDOR,
            nombre_paso="ABRIR_DISPUTA_REVISION_MANUAL",
            servicio_participante="operaciones-service",
            estado="COMPENSADO",
            evento_compensacion={
                "trabajo_en_disputa": True,
                "requiere_revision_manual": True,
                "intentos_de_acreditacion": intentos,
            },
        )

        self._saga_log.finalizar_saga(saga_id=saga_id, estado_final="EN_DISPUTA", error=motivo)
        logger.warning("Saga %s finalizada EN_DISPUTA a la espera de revisión manual", saga_id)

    def procesar_pago_rechazado(self, saga_id: UUID, payload: dict[str, Any]) -> None:
        motivo = payload.get("motivo", "Fondos insuficientes o fallo en pago")
        logger.warning("Saga %s: Pago rechazado: %s. Iniciando compensación.", saga_id, motivo)
        self._saga_log.registrar_paso_fallido(
            saga_id=saga_id,
            paso_numero=PASO_AUTORIZAR_PAGO,
            error=motivo,
            evento_recibido=payload,
        )

        instancia = self._saga_log.obtener_saga(saga_id)
        if not instancia:
            return

        # Compensar Paso 1: Cancelar trabajo en GestionDeTrabajosBC. Todavía no hay
        # proveedor asignado, así que no hay asignación que liberar.
        trabajo = self._obtener_trabajo(TrabajoId(instancia.trabajo_id))
        if trabajo:
            trabajo.cancelar(motivo=f"Saga fallida por pago: {motivo}")
            self._guardar_trabajo(trabajo)

        self._saga_log.registrar_paso_compensacion(
            saga_id=saga_id,
            paso_numero=PASO_CREAR_TRABAJO,
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
            paso_numero=PASO_ASIGNAR_PROVEEDOR,
            error=motivo,
            evento_recibido=payload,
        )

        instancia = self._saga_log.obtener_saga(saga_id)
        if not instancia:
            return

        # La asignación nunca llegó a ocurrir: la compensación arranca en el paso 2.
        self._compensar_pago(saga_id, str(instancia.trabajo_id), motivo)

    def procesar_ejecucion_fallida(self, saga_id: UUID, payload: dict[str, Any]) -> None:
        """El proveedor asignado no pudo ejecutar el trabajo.

        A diferencia de la acreditación, aquí el servicio no se prestó: se compensa
        en orden inverso, empezando por liberar la asignación que sí llegó a hacerse.
        """

        motivo = payload.get("motivo", "El proveedor no pudo ejecutar el trabajo")
        logger.warning(
            "Saga %s: Ejecución fallida: %s. Liberando asignación y revirtiendo el pago.",
            saga_id,
            motivo,
        )
        self._saga_log.registrar_paso_fallido(
            saga_id=saga_id,
            paso_numero=PASO_EJECUTAR_TRABAJO,
            error=motivo,
            evento_recibido=payload,
        )

        instancia = self._saga_log.obtener_saga(saga_id)
        if not instancia:
            return

        # Compensar Paso 3: liberar al proveedor antes de tocar el dinero.
        self._saga_log.registrar_paso_compensacion(
            saga_id=saga_id,
            paso_numero=PASO_ASIGNAR_PROVEEDOR,
            nombre_paso="COMPENSAR_LIBERAR_ASIGNACION",
            servicio_participante="operaciones-service",
            estado="EN_PROCESO",
            comando_compensacion={"trabajo_id": str(instancia.trabajo_id)},
        )
        self._publisher.enviar_comando(
            topico=self._topico_ops,
            tipo_comando=COMANDO_LIBERAR_ASIGNACION,
            saga_id=saga_id,
            payload={"trabajo_id": str(instancia.trabajo_id), "motivo": motivo},
            partition_key=str(instancia.trabajo_id),
        )

    def procesar_asignacion_liberada(self, saga_id: UUID, payload: dict[str, Any]) -> None:
        """Confirmada la liberación, sigue el reverso del pago (orden inverso estricto)."""

        instancia = self._saga_log.obtener_saga(saga_id)
        if not instancia:
            logger.error("Saga %s no encontrada al confirmar la liberación de la asignación", saga_id)
            return

        if not payload.get("liberado"):
            motivo = payload.get("motivo", "OperacionesBC no pudo liberar la asignación")
            self._saga_log.completar_paso_compensacion(
                saga_id, PASO_ASIGNAR_PROVEEDOR, "COMPENSAR_LIBERAR_ASIGNACION", "ERROR", payload, motivo
            )
            self._saga_log.finalizar_saga(saga_id, "FALLIDA", motivo)
            return

        self._saga_log.completar_paso_compensacion(
            saga_id, PASO_ASIGNAR_PROVEEDOR, "COMPENSAR_LIBERAR_ASIGNACION", "COMPENSADO", payload
        )
        self._compensar_pago(
            saga_id,
            str(instancia.trabajo_id),
            instancia.error or "Compensación de Saga",
        )

    def _compensar_pago(self, saga_id: UUID, trabajo_id: str, motivo: str) -> None:
        """Pide a PagosBC revertir la autorización. El paso 1 espera su confirmación."""

        self._saga_log.registrar_paso_compensacion(
            saga_id=saga_id,
            paso_numero=PASO_AUTORIZAR_PAGO,
            nombre_paso="COMPENSAR_REVERTIR_PAGO",
            servicio_participante="pagos-service",
            estado="EN_PROCESO",
            comando_compensacion={"trabajo_id": trabajo_id},
        )
        self._publisher.enviar_comando(
            topico=self._topico_pago,
            tipo_comando=COMANDO_REVERTIR_PAGO,
            saga_id=saga_id,
            payload={"trabajo_id": trabajo_id, "motivo": motivo},
            partition_key=trabajo_id,
        )
        logger.info("Saga %s espera la confirmación de reverso de PagosBC", saga_id)

    def procesar_pago_revertido(self, saga_id: UUID, payload: dict[str, Any]) -> None:
        """Completa la compensación solo después de la confirmación de PagosBC."""

        instancia = self._saga_log.obtener_saga(saga_id)
        if not instancia:
            logger.error("Saga %s no encontrada al confirmar reverso de pago", saga_id)
            return
        if not payload.get("revertido"):
            motivo = payload.get("motivo", "PagosBC no pudo revertir la autorización")
            self._saga_log.completar_paso_compensacion(
                saga_id, PASO_AUTORIZAR_PAGO, "COMPENSAR_REVERTIR_PAGO", "ERROR", payload, motivo
            )
            self._saga_log.finalizar_saga(saga_id, "FALLIDA", motivo)
            return

        self._saga_log.completar_paso_compensacion(
            saga_id, PASO_AUTORIZAR_PAGO, "COMPENSAR_REVERTIR_PAGO", "COMPENSADO", payload
        )

        # Compensar paso 1 después de confirmar el paso 2, en orden inverso.
        trabajo = self._obtener_trabajo(TrabajoId(instancia.trabajo_id))
        if trabajo:
            trabajo.cancelar(motivo=f"Saga compensada: {instancia.error or 'sin cobertura'}")
            self._guardar_trabajo(trabajo)

        self._saga_log.registrar_paso_compensacion(
            saga_id=saga_id,
            paso_numero=PASO_CREAR_TRABAJO,
            nombre_paso="COMPENSAR_CREAR_TRABAJO",
            servicio_participante="gestion-trabajos-service",
            estado="COMPENSADO",
            evento_compensacion={"trabajo_cancelado": True},
        )

        self._saga_log.finalizar_saga(
            saga_id=saga_id, estado_final="COMPENSADA", error=instancia.error
        )
        logger.info("Saga %s COMPENSADA tras confirmación de reverso de PagosBC", saga_id)
