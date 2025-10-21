from app.infrastructure.email_client import EmailClient
from typing import Optional


class NotificationService:
    def __init__(self, email_client: EmailClient):
        self.email_client = email_client

    def send_failure_controlled(
        self,
        id_origen,
        corr_id,
        motivo,
        input_masked,
        pdf_path=None,
        last_screenshot=None,
    ):
        subject = f"[RPA][CONTROLADO] Fallo en id={id_origen}"
        body = f"Correlation: {corr_id}\nMotivo: {motivo}\nInput: {input_masked}"
        self.email_client.send_email(
            subject=subject,
            body=body,
            to=self.email_client.to_addrs,
            attachments=[pdf_path] if pdf_path else None,
        )

    def send_failure_unexpected(
        self, id_origen, corr_id, error_summary, last_screenshot=None
    ):
        subject = f"[RPA][CRÍTICO] Excepción id={id_origen}"
        body = f"Correlation: {corr_id}\nError: {error_summary}"
        self.email_client.send_email(
            subject=subject,
            body=body,
            to=self.email_client.to_addrs,
            attachments=[last_screenshot] if last_screenshot else None,
        )
