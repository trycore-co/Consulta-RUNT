from app.infrastructure.web_client import WebClient
from app.infrastructure.nocodb_client import NocoDBClient
from app.services.scraping_service import ScrapingService
from app.services.capture_service import CaptureService
from app.services.pdf_service import PDFService
from app.repositories.nocodb_target_repository import NocoDbTargetRepository
from app.repositories.nocodb_source_repository import NocoDbSourceRepository
from app.utils.logging_utils import get_logger
# from app.infrastructure.email_client import EmailClient
from app.services.notification_service import NotificationService
from pathlib import Path
import time

logger = get_logger("proceso_unitario_wf")


class ProcesoUnitarioWF:
    def __init__(
        self,
        record: dict,
        nocodb_client: NocoDBClient,
        web_client: WebClient,
        correlation_id: str,
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

        # repos/services
        self.source_repo = NocoDbSourceRepository(self.nocodb_client)
        self.target_repo = NocoDbTargetRepository(self.nocodb_client)

        # selectors: carga desde archivo YAML si lo necesitas;
        selectors_path = Path(__file__).parent.parent / "resources" / "html_selectors.yaml"
        self.scraper = ScrapingService(web_client=self.web_client, selectors_path=selectors_path)
        self.capture = CaptureService()
        self.pdf = PDFService()
        # self.email_client = EmailClient()
        self.notifier = NotificationService()

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
        record_id = self.record.get("ID")
        tipo = self.record.get("TipoIdentificacion")
        numero = self.record.get("NumeroIdentificacion")
        input_masked = f"{tipo}:{numero}"

        self.notifier.send_start_notification(1)  # Notificación de inicio unitario

        try:
            from config import settings

            user = self.record.get("UserRunt") or settings.RUNT_USERNAME
            pwd = self.record.get("PassRunt") or settings.RUNT_PASSWORD

            # Intentos de login con reintentos
            if not self._attempt_login(user, pwd):
                motivo = "Login fallido tras múltiples intentos"
                self.source_repo.marcar_fallido(record_id, motivo)
                self.notifier.send_failure_controlled(
                    record_id=str(record_id),
                    motivo=motivo,
                    input_masked=input_masked,
                )
                return {"id": record_id, "status": "login_failed"}

            # Proceso principal (reintentos por registro)
            intento = 0
            while intento < self.reintentos_proceso:
                intento += 1
                try:
                    logger.info(f"Iniciando intento {intento}/{self.reintentos_proceso} para registro {record_id}")
                    placas = self.scraper.consultar_por_propietario(tipo, numero)
                    if not placas:
                        self.source_repo.marcar_fallido(record_id, "No Encontrado")
                        motivo = "No se encontraron placas asociadas"
                        self.notifier.send_failure_controlled(
                            record_id=str(record_id),
                            motivo=motivo,
                            input_masked=input_masked,
                        )
                        return {"id": record_id, "status": "no_encontrado"}

                    image_paths = []
                    for placa in placas:
                        detalle = self.scraper.abrir_ficha_y_extraer(placa)
                        self.target_repo.upsert_vehicle_detail(detalle)
                        png = self.scraper.tomar_screenshot_bytes()
                        saved = self.capture.save_screenshot_bytes(
                            png, self.correlation_id, placa
                        )
                        image_paths.append(saved)

                    pdf_path = self.pdf.consolidate_images_to_pdf(image_paths, self.correlation_id)
                    self.source_repo.marcar_exitoso(record_id, pdf_path)

                    self.notifier.send_end_notification(
                        exitosos=1, errores=0, pdf_path=pdf_path
                    )  # Notificación final
                    return {"id": record_id, "status": "exitoso", "pdf": pdf_path}

                except Exception as e:
                    logger.exception(f"Error en intento {intento}/{self.reintentos_proceso} para ID={record_id}")
                    last_screens = self.capture.list_images_for_correlation(self.correlation_id)
                    last_scr = last_screens[-1] if last_screens else None

                    if intento >= self.reintentos_proceso:
                        self.source_repo.marcar_fallido(record_id, str(e))
                        self.notifier.send_failure_unexpected(
                            record_id=str(record_id),
                            error=str(e),
                            last_screenshot=last_scr,
                        )
                        self.notifier.send_end_notification(exitosos=0, errores=1)
                        return {"id": record_id, "status": "error", "error": str(e)}
                    time.sleep(2 * intento)  # backoff exponencial

        except Exception as exc:
            logger.exception(f"Error inesperado en workflow unitario para id={record_id}")
            try:
                self.source_repo.marcar_fallido(record_id, str(exc))
            except Exception:
                pass
            last_screens = self.capture.list_images_for_correlation(self.correlation_id)
            last_scr = last_screens[-1] if last_screens else None
            self.notifier.send_failure_unexpected(
                record_id=str(record_id),
                error=str(exc),
                last_screenshot=last_scr,
            )
            self.notifier.send_end_notification(exitosos=0, errores=1)
            return {"id": record_id, "status": "error", "error": str(exc)}
