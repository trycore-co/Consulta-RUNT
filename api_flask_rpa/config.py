from pydantic_settings import BaseSettings
from typing import Optional
from dotenv import load_dotenv
import os

load_dotenv()


class Settings(BaseSettings):
    # Flask settings
    FLASK_ENV: Optional[str] = os.getenv("FLASK_ENV")
    FLASK_APP: Optional[str] = os.getenv("FLASK_APP")
    FLASK_DEBUG: Optional[str] = os.getenv("FLASK_DEBUG")
    FLASK_BASE_URL: Optional[str] = os.getenv("FLASK_BASE_URL")

    # Poller settings
    POLLER_INTERVAL_SECONDS: Optional[str] = os.getenv("POLLER_INTERVAL_SECONDS")

    # NocoDB settings
    NOCODB_URL: Optional[str] = os.getenv("NOCODB_URL")
    NOCO_XC_TOKEN: Optional[str] = os.getenv("NOCO_XC_TOKEN")
    NOCO_PROJECT_ID: Optional[str] = os.getenv("NOCO_PROJECT_ID")
    NOCO_PARAMETROS_TABLE: Optional[str] = os.getenv("NOCO_PARAMETROS_TABLE")
    NOCO_INSUMO_TABLE: Optional[str] = os.getenv("NOCO_INSUMO_TABLE")
    NOCO_BASE_TRABAJO_TABLE: Optional[str] = os.getenv("NOCO_BASE_TRABAJO_TABLE")

    # RUNT settings
    RUNT_URL: Optional[str] = os.getenv("RUNT_URL")
    RUNT_USERNAME: Optional[str] = os.getenv("RUNT_USERNAME")
    RUNT_PASSWORD: Optional[str] = os.getenv("RUNT_PASSWORD")

    # Email settings
    CLIENT_ID: Optional[str] = os.getenv("CLIENT_ID")
    CLIENT_SECRET: Optional[str] = os.getenv("CLIENT_SECRET")
    TENANT_ID: Optional[str] = os.getenv("TENANT_ID")
    AUTHORITY: Optional[str] = os.getenv("AUTHORITY")
    SCOPE: Optional[str] = os.getenv("SCOPE")
    USER_EMAIL: Optional[str] = os.getenv("USER_EMAIL")
    RECEIVER_EMAIL: Optional[str] = os.getenv("RECEIVER_EMAIL")

    # Path settings
    FILESERVER_PATH: Optional[str] = os.getenv("FILESERVER_PATH")
    SCREENSHOT_PATH: Optional[str] = os.getenv("SCREENSHOT_PATH")
    PDF_DIR: Optional[str] = os.getenv("PDF_DIR")
    LOG_PATH: Optional[str] = os.getenv("LOG_PATH")

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = 'ignore'


settings = Settings()
