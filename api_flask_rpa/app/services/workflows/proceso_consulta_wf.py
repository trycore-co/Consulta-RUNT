import uuid
import os
from app.repositories.nocodb_source_repository import NocoDbSourceRepository
from app.infrastructure.nocodb_client import NocoDBClient
from app.infrastructure.web_client import WebClient
from app.services.workflows.proceso_unitario_wf import ProcesoUnitarioWF
from app.services.notification_service import NotificationService
from app.utils.horarios_utils import puede_ejecutar_en_fecha
from datetime import datetime
from app.utils.logging_utils import get_logger

logger = get_logger("proceso_consulta_wf")


class ProcesoConsultaWF:
    def __init__(self, nocodb_client: NocoDBClient, web_client: WebClient):
        self.nocodb_client = nocodb_client
        self.web_client = web_client
        self.notifier = NotificationService()
        self.source_repo = NocoDbSourceRepository(self.nocodb_client)

    def ejecutar_lote(self):
        """
        Ejecuta un lote de consultas pendientes según las HU definidas.
        Controla horario laboral y estados de gestión.
        """
        # 1) leer parámetros
        parametros = self.source_repo.obtener_parametros()
        # Buscar el registro de destinatarios.
        recipients_str = parametros.get("EmailRecipients", "")

        # Parsear la cadena (asumiendo formato "correo1,correo2,correo3")
        recipients_list = [
            email.strip()
            for email in recipients_str.split(",")
            if email.strip()  # Filtra cadenas vacías
        ]
        # Asignar los destinatarios al NotificationService
        self.notifier.set_recipients(recipients_list)
        ahora = datetime.now()
        hora_inicio_str = parametros.get("HoraInicio", "07:00")
        hora_fin_str = parametros.get("HoraFin", "18:00")
        if not puede_ejecutar_en_fecha(
            ahora.date(), ahora, hora_inicio=hora_inicio_str, hora_fin=hora_fin_str
        ):
            motivo = "Ejecución omitida: fuera de horario o día no hábil."
            logger.info(motivo)
            self.notifier.send_failure_controlled(None, motivo, None)
            return {
                "processed": 0,
                "message": "Fuera de horario laboral o día no hábil.",
            }

        # obtener pendientes
        limit = int(parametros.get("LimitePendientes", 50) or 50)
        pendientes = self.source_repo.obtener_pendientes(limit=limit)
        logger.info("Pendientes encontrados: %d", len(pendientes))
        self.notifier.send_start_notification(total_pendientes=len(pendientes))

        # parámetros comunes que pasaremos downstream
        reintentos_login = int(parametros.get("ReintentosLogin", 2) or 2)
        reintentos_proceso = int(parametros.get("ReintentosProceso", 2) or 2)
        timeout_bajo = int(parametros.get("DelayBajo", 5) or 5)
        timeout_medio = int(parametros.get("DelayMedio", 10) or 10)
        timeout_largo = int(parametros.get("DelayAlto", 15) or 15)
        url_runt = parametros.get("URLRUNT", "")
        usuario_runt = parametros.get("UsuarioRUNT", "")
        password_runt = parametros.get("PasswordRUNT", "")

        # Contadores y resultados
        ok_count, error_count = 0, 0
        results = []
        all_pdfs = []

        is_logged_in = False

        for record in pendientes:
            corr_id = str(uuid.uuid4())
            record_id = record.get("Id")

            if not record_id:
                logger.warning(f"Registro sin 'Id' válido: {record}")
                continue

            try:
                # Ejecutar flujo unitario
                wf_unit = ProcesoUnitarioWF(
                    record=record,
                    nocodb_client=self.nocodb_client,
                    web_client=self.web_client,
                    correlation_id=corr_id,
                    notifier=self.notifier,
                    session_active=is_logged_in,
                    reintentos_login=reintentos_login,
                    reintentos_proceso=reintentos_proceso,
                    timeout_bajo=timeout_bajo,
                    timeout_medio=timeout_medio,
                    timeout_largo=timeout_largo,
                    url_runt=url_runt,
                    usuario_runt=usuario_runt,
                    password_runt=password_runt,
                )
                resultado = wf_unit.ejecutar()

                # ACTUALIZAR EL ESTADO DE LA SESIÓN:
                # Si el primer registro fue exitoso, el login fue exitoso.
                if not is_logged_in and resultado.get("status") == "exitoso":
                    is_logged_in = True
                    logger.info(
                        "Login exitoso en el primer registro, se activó la bandera para el resto del lote."
                    )
                # Si el primer registro falló el login, el estado 'is_logged_in' seguirá siendo False,
                # forzando el login en el siguiente registro.
                if resultado.get("status") == "login_failed":
                    is_logged_in = False
                    logger.warning(
                        "Fallo de login. La bandera de sesión activa se restableció."
                    )

                # Solo marcar como exitoso si el status es "exitoso"
                if resultado.get("status") == "exitoso":
                    ok_count += 1
                    if resultado.get("pdf"):
                        all_pdfs.append(resultado["pdf"])
                else:
                    # El workflow unitario ya marcó el estado apropiado (login_failed, no_encontrado, error)
                    error_count += 1

                results.append(resultado)
            except Exception as e:
                logger.exception(f"Error procesando registro {record_id}: {e}")
                error_count += 1
                screenshot = self.web_client.screenshot_save(f"./data/capturas/error_{record_id}.png")
                self.notifier.send_failure_unexpected(
                    record_id=str(record_id), error=str(e), last_screenshot=screenshot
                )
                try:
                    self.source_repo.marcar_fallido(record, str(e))
                except Exception as e2:
                    logger.warning(f"No se pudo actualizar estado de error en NocoDB: {e2}")
                results.append({"id": record_id, "error": str(e)})

        logger.info(f"Lote completado. OK={ok_count}, ERROR={error_count}")

        # Determinar la ruta base de los PDFs
        pdf_base_path = None
        if all_pdfs:
            # Extrae la ruta del directorio del primer PDF generado.
            pdf_base_path = os.path.dirname(all_pdfs[0])

        self.notifier.send_end_notification(
            exitosos=ok_count,
            errores=error_count,
            adjuntos=all_pdfs,  # Enviamos la lista de PDFs generados
            pdf_base_path=pdf_base_path,
        )
        return {
            "procesados": ok_count,
            "errores": error_count,
            "mensaje": "Ejecución completada correctamente",
            "detalles": results,
            "pdfs_generados": all_pdfs,
        }
