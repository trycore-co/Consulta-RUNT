import os
import base64
import requests
from app.utils.logging_utils import get_logger
from typing import List, Optional
from config import settings

logger = get_logger("email_client")


class EmailClient:
    """
    Cliente para envío de correos mediante Microsoft Graph API
    usando autenticación con OAuth2 (client credentials flow).
    """

    def __init__(self):
        self.client_id = settings.CLIENT_ID
        self.client_secret = settings.CLIENT_SECRET
        self.tenant_id = settings.TENANT_ID
        self.authority = settings.AUTHORITY
        self.scope = settings.SCOPE
        self.sender = settings.USER_EMAIL
        self.receiver = settings.RECEIVER_EMAIL
        self.token_url = (
            f"{self.authority.rstrip('/')}/{self.tenant_id}/oauth2/v2.0/token"
        )
        logger.info(f"EmailClient inicializado para remitente: {self.sender}, destinatario: {self.receiver}")

    def _get_access_token(self) -> str:

        headers = {"Content-Type": "application/x-www-form-urlencoded"}
        data = {
            "grant_type": "client_credentials",
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "scope": self.scope,
        }

        logger.info("Obteniendo token de acceso para Microsoft Graph API: %s", self.token_url)
        response = requests.post(self.token_url, data=data, headers=headers)

        if response.status_code == 200:
            self.token = response.json().get("access_token")
            return self.token
        else:
            print(f"Error al obtener el token: {response.text}")
            response.raise_for_status()
            return None

    def send_email(
        self,
        subject: str,
        html_body: str,
        *,
        to: Optional[List[str]] = None,
        attachments: Optional[List[str]] = None,
    ):
        token = self._get_access_token()
        url = f'https://graph.microsoft.com/v1.0/users/{self.sender}/sendMail'

        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }

        # Preparar cuerpo del mensaje
        message = {
            "message": {
                "subject": subject,
                "body": {"contentType": "HTML", "content": html_body},
                "toRecipients": [
                    {"emailAddress": {"address": addr}}
                    for addr in (to or [self.receiver])
                ],
            },
            "saveToSentItems": "true",
        }

        # Adjuntar archivos (opcional)
        if attachments:
            attachments_list = []
            for path in attachments:
                try:
                    if not os.path.exists(path):
                        logger.warning(f"No se encontró el archivo para adjuntar: {path}")
                        continue

                    with open(path, "rb") as f:
                        content_bytes = f.read()
                        encoded = base64.b64encode(content_bytes).decode("utf-8")

                    # Detectar tipo MIME (para Outlook/Gmail)
                    import mimetypes

                    mime_type, _ = mimetypes.guess_type(path)
                    mime_type = mime_type or "application/octet-stream"

                    attachments_list.append(
                        {
                            "@odata.type": "#microsoft.graph.fileAttachment",
                            "name": os.path.basename(path),
                            "contentType": mime_type,
                            "contentBytes": encoded,
                        }
                    )
                except Exception as e:
                    logger.warning(f"No se pudo adjuntar archivo {path}: {e}")

            if attachments_list:
                message["message"]["attachments"] = attachments_list

        response = requests.post(url, headers=headers, json=message)

        if response.status_code not in (200, 202):
            logger.error(f"Error enviando correo: {response.text}")
            response.raise_for_status()

        logger.info(f"Correo enviado correctamente a: {to or [self.receiver]}")
