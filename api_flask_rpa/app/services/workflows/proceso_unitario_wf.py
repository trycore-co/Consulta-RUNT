from app.infrastructure.web_client import WebClient
from app.infrastructure.nocodb_client import NocoDBClient
from app.services.scraping_service import ScrapingService
from app.services.capture_service import CaptureService
from app.services.pdf_service import PDFService
from app.repositories.nocodb_target_repository import NocoDbTargetRepository
from app.repositories.nocodb_source_repository import NocoDbSourceRepository
from app.utils.logging_utils import get_logger
from app.utils.limpiar_nit import limpiar_nit_sin_dv
from app.services.notification_service import NotificationService
import time
from datetime import datetime

logger = get_logger("proceso_unitario_wf")


class ProcesoUnitarioWF:
    def __init__(
        self,
        record: dict,
        nocodb_client: NocoDBClient,
        web_client: WebClient,
        correlation_id: str,
        notifier: NotificationService,
        session_active: bool = False,
        reintentos_login: int = 3,
        reintentos_proceso: int = 2,
        timeout_bajo: int = 3,
        timeout_medio: int = 8,
        timeout_largo: int = 20,
    ):
        self.record = record
        self.nocodb_client = nocodb_client
        self.web_client = web_client
        self.correlation_id = correlation_id
        self.session_active = session_active

        # repos/services
        self.source_repo = NocoDbSourceRepository(self.nocodb_client)
        self.target_repo = NocoDbTargetRepository(self.nocodb_client)

        # selectors: carga desde archivo YAML si lo necesitas;
        self.scraper = ScrapingService(web_client=self.web_client)
        self.capture = CaptureService()
        self.pdf = PDFService()
        # self.email_client = EmailClient()
        self.notifier = notifier

        # parámetros dinámicos
        self.reintentos_login = max(1, int(reintentos_login))
        self.reintentos_proceso = max(1, int(reintentos_proceso))
        self.timeout_bajo = timeout_bajo
        self.timeout_medio = timeout_medio
        self.timeout_largo = timeout_largo

    def _attempt_login(self, user, password) -> bool:
        ultimo_error = None
        for i in range(self.reintentos_login):
            try:
                ok = self.scraper.login(user, password)
                if ok:
                    logger.info("Login exitoso en intento %d/%d", i+1, self.reintentos_login)
                    return True
                else:
                    logger.warning("Login fallido en intento %d/%d", i+1, self.reintentos_login)
                    ultimo_error = "Credenciales o flujo de login incorrecto"
            except Exception as e:
                ultimo_error = str(e)
                logger.exception("Excepción en intento de login %d/%d", i+1, self.reintentos_login)
            time.sleep(1)  # pequeño backoff
        logger.error("Login falló tras %d intentos: %s", self.reintentos_login, ultimo_error)
        return False

    def ejecutar(self):
        record_id = (
            self.record.get("Id") or self.record.get("ID") or self.record.get("id")
        )
        tipo = self.record.get("TipoIdentificacion")
        num_identificacion_original = self.record.get(
            "NumeroIdentificacion"
        ) or self.record.get("NumIdentificacion")
        # Aplicar la función para obtener el número listo para la consulta
        num_identificacion_str = (
            str(num_identificacion_original)
            if num_identificacion_original is not None
            else None
        )
        numero = limpiar_nit_sin_dv(num_identificacion_str, tipo)

        logger.info(
            f"ID {record_id} - Documento original: {num_identificacion_original}, "
            f"Documento limpio para consulta: {numero}"
        )
        # Validar que tenemos los datos necesarios
        if not record_id:
            logger.error(f"No se pudo extraer el ID del registro: {self.record}")
            return {"status": "error", "error": "ID de registro no encontrado"}

        if not numero:
            logger.error(
                f"No se pudo extraer el número de identificación del registro: {self.record}"
            )
            return {
                "id": record_id,
                "status": "error",
                "error": "Número de identificación no encontrado",
            }

        input_masked = f"{tipo}:{numero}"
        fecha_hora_inicio = datetime.now().isoformat()
        logger.info(f"Procesando registro ID={record_id}, Tipo={tipo}, Numero={numero}")
        # Marcar como “Procesando” en Noco
        self.source_repo.marcar_en_proceso(self.record)

        try:
            from config import settings
            if not self.session_active:
                user = self.record.get("UserRunt") or settings.RUNT_USERNAME
                pwd = self.record.get("PassRunt") or settings.RUNT_PASSWORD

                # Intentos de login con reintentos
                if not self._attempt_login(user, pwd):
                    motivo = "Login fallido tras múltiples intentos"
                    self.source_repo.marcar_fallido(self.record, motivo)
                    self.notifier.send_failure_controlled(
                        record_id=str(record_id),
                        motivo=motivo,
                        input_masked=input_masked,
                    )
                    return {"id": record_id, "status": "login_failed"}
            else:
                logger.info(
                    f"Saltando login para registro {record_id}. La sesión se considera activa."
                )

            # Proceso principal (reintentos por registro)
            intento = 0
            while intento < self.reintentos_proceso:
                intento += 1
                try:
                    logger.info(f"Iniciando intento {intento}/{self.reintentos_proceso} para registro {record_id}")
                    placas, captura_lista_placas = (
                        self.scraper.consultar_por_propietario(tipo, numero)
                    )  # type: ignore
                    screenshot_list_path = self.capture.save_screenshot_bytes(
                        captura_lista_placas,
                        self.correlation_id,
                        numero,  # Identificador único para esta captura: [correlation_id]_[NumeroIdentificacion].png
                    )
                    image_paths = []
                    image_paths.append(screenshot_list_path)

                    logger.info(
                        f"Captura de lista de placas guardada en: {screenshot_list_path}"
                    )
                    if not placas:
                        self.scraper.volver_a_inicio()
                        self.source_repo.marcar_fallido(self.record, "Error Controlado: No Encontrado")
                        pdf_path = self.pdf.consolidate_images_to_pdf(
                            image_paths, numero
                        )

                        return {
                            "id": record_id,
                            "status": "exitoso",
                            "pdf": pdf_path,
                        }

                    for placa in placas:
                        detalle, png = self.scraper.abrir_ficha_y_extraer(placa)
                        fecha_hora_fin = datetime.now().isoformat()
                        self.target_repo.upsert_vehicle_detail(self.record, vehicle_details=detalle, ruta_pdf=None, fecha_inicio=fecha_hora_inicio, fecha_fin=fecha_hora_fin)
                        saved = self.capture.save_screenshot_bytes(
                            png, self.correlation_id, placa
                        )
                        image_paths.append(saved)

                    self.scraper.volver_a_inicio()
                    pdf_path = self.pdf.consolidate_images_to_pdf(image_paths, numero)
                    self.source_repo.marcar_exitoso(self.record)
                    self.target_repo.update_ruta_pdf_by_proceso(self.record, pdf_path)

                    return {"id": record_id, "status": "exitoso", "pdf": pdf_path}

                except Exception as e:
                    logger.exception(f"Error en intento {intento}/{self.reintentos_proceso} para ID={record_id}")
                    last_screens = self.capture.list_images_for_correlation(self.correlation_id)
                    last_scr = last_screens[-1] if last_screens else None

                    if intento >= self.reintentos_proceso:
                        self.source_repo.marcar_fallido(self.record, f"Error inesperado: {str(e)}")  # type: ignore ("str(e))
                        self.notifier.send_failure_unexpected(
                            record_id=str(record_id),
                            error=str(e),
                            last_screenshot=last_scr,
                        )

                        return {"id": record_id, "status": "error", "error": str(e)}
                    time.sleep(2 * intento)  # backoff exponencial

        except Exception as exc:
            logger.exception(f"Error inesperado en workflow unitario para id={record_id}")
            try:
                self.source_repo.marcar_fallido(self.record, f"Error inesperado: {str(exc)}")
            except Exception:
                pass
            last_screens = self.capture.list_images_for_correlation(self.correlation_id)
            last_scr = last_screens[-1] if last_screens else None
            self.notifier.send_failure_unexpected(
                record_id=str(record_id),
                error=str(exc),
                last_screenshot=last_scr,
            )
            return {"id": record_id, "status": "error", "error": str(exc)}
