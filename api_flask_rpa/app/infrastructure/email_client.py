import smtplib
from email.message import EmailMessage
from config import settings
from typing import List, Optional


class EmailClient:
    def __init__(self):
        self.host = settings.SMTP_HOST
        self.port = settings.SMTP_PORT
        self.user = settings.SMTP_USER
        self.password = settings.SMTP_PASSWORD
        self.from_addr = settings.NOTIFY_FROM
        self.to_addrs = [
            a.strip() for a in (settings.NOTIFY_TO or "").split(",") if a.strip()
        ]

    def send_email(
        self,
        subject: str,
        body: str,
        to: Optional[List[str]] = None,
        attachments: Optional[List[str]] = None,
    ):
        if not self.host or not self.to_addrs:
            return False
        to = to or self.to_addrs
        msg = EmailMessage()
        msg["Subject"] = subject
        msg["From"] = self.from_addr
        msg["To"] = ", ".join(to)
        msg.set_content(body)

        # attach files
        if attachments:
            for path in attachments:
                if not path:
                    continue
                try:
                    with open(path, "rb") as f:
                        data = f.read()
                    # infer maintype/subtype by extension - basic approach
                    msg.add_attachment(
                        data,
                        maintype="application",
                        subtype="octet-stream",
                        filename=path.split("/")[-1],
                    )
                except Exception:
                    continue

        with smtplib.SMTP(self.host, self.port, timeout=30) as s:
            s.starttls()
            if self.user and self.password:
                s.login(self.user, self.password)
            s.send_message(msg)
        return True
