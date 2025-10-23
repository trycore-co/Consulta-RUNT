from pathlib import Path
from typing import Optional
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
        self.email_client = EmailClient()
        templates_path = Path(__file__).parent.parent / "resources" / "email_templates"
        self.env = Environment(
            loader=FileSystemLoader(templates_path),
            autoescape=select_autoescape(["html", "j2"]),
        )
        self.env.globals["now"] = (
            datetime.now
        )  # para usar {{ now().year }} en templates

    def _render_template(self, template_name: str, context: dict) -> str:
        template = self.env.get_template(template_name)
        context["now"] = datetime.now
        return template.render(**context)

    def send_start_notification(self, total_pendientes: int):
        """Envía correo de inicio del proceso."""
        html = self._render_template(
            "summary_batch.html.j2",
            {
                "titulo": "IMPORTANTE - RPA_RUNT - Inicio de ejecución del Bot",
                "total": total_pendientes,
                "estado": "Iniciado",
                "mensaje": f"Se ha iniciado la ejecución del lote. Pendientes a procesar: {total_pendientes}",
            },
        )
        self.email_client.send_email(
            "IMPORTANTE - RPA_RUNT - Inicio de ejecución del Bot", html
        )

    def send_end_notification(self, exitosos: int, errores: int, pdf_path: Optional[str]=None):
        """Envía correo de finalización del proceso."""
        html = self._render_template(
            "summary_batch.html.j2",
            {
                "titulo": "IMPORTANTE - RPA_RUNT - Fin de ejecución del Bot",
                "exitosos": exitosos,
                "errores": errores,
                "pdf_path": pdf_path,
                "estado": "Finalizado",
            },
        )
        attachments = [pdf_path] if pdf_path else []
        self.email_client.send_email(
            "IMPORTANTE - RPA_RUNT - Fin de ejecución del Bot", html, attachments=attachments
        )

    def send_failure_controlled(self, record_id: str,  motivo: str, input_masked: str):
        """Envía notificación de error controlado (casos esperados)."""
        html = self._render_template(
            "failure_controlled.html.j2", {
                "record_id": record_id,
                "motivo": motivo,
                "input_masked": input_masked
            },)
        self.email_client.send_email("IMPORTANTE - RPA_RUNT - Error controlado", html)

    def send_failure_unexpected(self, record_id: str, error: str, last_screenshot: str):
        """Envía correo de error inesperado (excepciones, fallos graves)"""
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
