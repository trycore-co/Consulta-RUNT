from pathlib import Path
from typing import Optional, List
from datetime import datetime
from jinja2 import Environment, FileSystemLoader, select_autoescape
from app.infrastructure.email_client import EmailClient
from app.utils.logging_utils import get_logger

logger = get_logger("notification_service")


class NotificationService:
    """
    Servicio que gestiona el envío de correos automáticos
    (inicio, errores y resumen de ejecución).
    """

    def __init__(self):
        # Inicializar EmailClient de forma segura: si faltan variables de configuración
        # evitamos lanzar una excepción y deshabilitamos el envío de correos.
        try:
            self.email_client = EmailClient()
            self._email_enabled = True
        except Exception as e:
            logger.warning(
                "EmailClient no pudo inicializarse, las notificaciones por correo estarán deshabilitadas: %s",
                e,
            )
            self.email_client = None
            self._email_enabled = False
        templates_path = Path(__file__).parent.parent / "resources" / "email_templates"
        self.env = Environment(
            loader=FileSystemLoader(templates_path),
            autoescape=select_autoescape(["html", "j2"]),
        )
        self.env.globals["now"] = (
            datetime.now
        )  # para usar {{ now().year }} en templates

    def set_recipients(self, recipients: List[str]):
        """Establece la lista de correos destinatarios en el cliente de correo."""
        if self._email_enabled:
            # Llama al nuevo método de EmailClient
            self.email_client.set_recipients(recipients)

    def _render_template(self, template_name: str, context: dict) -> str:
        template = self.env.get_template(template_name)
        context["now"] = datetime.now
        return template.render(**context)

    def send_start_notification(self, total_pendientes: int):
        """Envía correo de inicio del proceso."""
        if not self._email_enabled:
            logger.info("Notificación de inicio omitida: EmailClient no configurado")
            return

        html = self._render_template(
            "summary_batch.html.j2",
            {
                "titulo": "IMPORTANTE - RPA_RUNT - Inicio de ejecución del Bot",
                "total": total_pendientes,
                "estado": "Iniciado",
                "mensaje": f"Se ha iniciado la ejecución del lote. Pendientes a procesar: {total_pendientes}",
            },
        )
        subject = "IMPORTANTE - RPA_RUNT - Inicio de ejecución del Bot"
        self.email_client.send_email(subject, html)

    def send_end_notification(
        self,
        exitosos: int,
        errores: int,
        pdf_path: Optional[str] = None,
        adjuntos: Optional[List[str]] = None,
        pdf_base_path: Optional[str] = None,
    ):
        """Envía correo de finalización del proceso."""
        if not self._email_enabled:
            logger.info("Notificación de fin omitida: EmailClient no configurado")
            return

        total_procesados = exitosos + errores

        html = self._render_template(
            "summary_batch.html.j2",
            {
                "titulo": "IMPORTANTE - RPA_RUNT - Fin de ejecución del Bot",
                "exitosos": exitosos,
                "errores": errores,
                "total": total_procesados,
                "pdf_path": pdf_path,
                "pdf_storage_path": pdf_base_path,
                "pdfs_adjuntos": len(adjuntos) if adjuntos else 0,
                "estado": "Finalizado",
            },
        )
        attachments = [pdf_path] if pdf_path else [] or adjuntos if adjuntos else []
        subject = f"IMPORTANTE - RPA_RUNT - Fin de ejecución del Bot: Exitosos: {exitosos} / Error: {errores}"

        self.email_client.send_email(subject, html, attachments=attachments)

    def send_failure_controlled(
        self,
        record_id: str,
        motivo: str,
        input_masked: str,
        screenshot_path: Optional[str] = None,
    ):
        """Envía notificación de error controlado (casos esperados)."""
        if not self._email_enabled:
            logger.info("Notificación de error controlado omitida: EmailClient no configurado")
            return

        html = self._render_template(
            "failure_controlled.html.j2", {
                "record_id": record_id,
                "motivo": motivo,
                "input_masked": input_masked
            },)
        attachments = [screenshot_path] if screenshot_path else []
        self.email_client.send_email("IMPORTANTE - RPA_RUNT - Error controlado", html, attachments=attachments)

    def send_failure_unexpected(self, record_id: str, error: str, last_screenshot: str):
        """Envía correo de error inesperado (excepciones, fallos graves)"""
        if not self._email_enabled:
            logger.info("Notificación de error inesperado omitida: EmailClient no configurado")
            return

        html = self._render_template(
            "failure_unexpected.html.j2",
            {
                "record_id": record_id,
                "error": error,
                "last_screenshot": last_screenshot,
            },
        )
        attachments = [last_screenshot] if last_screenshot else []
        self.email_client.send_email(
            "IMPORTANTE - RPA_RUNT - Error inesperado",
            html,
            attachments=attachments
        )
