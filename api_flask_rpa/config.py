import os
import logging
from logging.handlers import TimedRotatingFileHandler
import socket
from app.api_handler.parameters_client import get_parameters_client
from typing import Dict, Type

hostname = socket.gethostname()


def get_logger(name):
    return logging.getLogger(name)


def get_business_logger():
    return logging.getLogger("business")


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY") or "you-will-never-guess"
    API_URL = os.environ.get("API_URL")
    XC_AUTH_TOKEN = os.environ.get("XC_AUTH_TOKEN")
    XC_TOKEN = os.environ.get("XC_TOKEN")
    LOG_DIR = os.environ.get("LOG_PATH")
    BUSINESS_LOG_FILE = f"{LOG_DIR}/business-{hostname}.log"
    LOG_FILE = f"{LOG_DIR}/app-{hostname}.log"
    MAX_LOG_SIZE = 5 * 1024 * 1024  # 5 MB
    BACKUP_COUNT = 3

    def get_parameter(key):
        parameters = get_parameters_client(key)
        for parameter in parameters:
            if parameter["KEY"] == key:
                if parameter["DATATYPE"] == "INTEGER":
                    return int(parameter["VALUE"])
                elif parameter["DATATYPE"] == "BOOLEAN":
                    return bool(parameter["VALUE"])
                else:
                    return parameter["VALUE"]

    @staticmethod
    def init_app(app):
        configure_logging(app.config.get("LOG_LEVEL", logging.INFO))
        configure_business_logging(app.config.get("LOG_LEVEL", logging.INFO))


def configure_logging(log_level=logging.INFO):
    log_dir = Config.LOG_DIR
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)

    # File handler
    file_handler = TimedRotatingFileHandler(
        Config.LOG_FILE,
        when="midnight",
        interval=1,
        backupCount=Config.BACKUP_COUNT,
        encoding="utf-8",
        delay=False,
        utc=False,
    )
    file_handler.setLevel(log_level)
    file_handler.setFormatter(
        logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    )

    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(log_level)
    console_handler.setFormatter(
        logging.Formatter("%(name)s - %(levelname)s - %(message)s")
    )

    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)

    # Clear existing handlers to avoid duplicate logging
    root_logger.handlers = []
    root_logger.addHandler(file_handler)
    root_logger.addHandler(console_handler)


class InfoFilter(logging.Filter):
    def filter(self, record):
        return record.levelno == logging.INFO


def configure_business_logging(log_level=logging.INFO):
    # File handler for business log
    business_file_handler = TimedRotatingFileHandler(
        Config.BUSINESS_LOG_FILE,
        when="midnight",
        interval=1,
        backupCount=Config.BACKUP_COUNT,
        encoding="utf-8",
        delay=False,
        utc=False,
    )
    business_file_handler.setLevel(log_level)
    # business_file_handler.addFilter(InfoFilter())
    business_file_handler.setFormatter(
        logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
    )

    # Console handler for business log
    business_console_handler = logging.StreamHandler()
    business_console_handler.setLevel(log_level)
    # business_console_handler.addFilter(InfoFilter())
    business_console_handler.setFormatter(
        logging.Formatter("%(levelname)s - %(message)s")
    )

    business_logger = logging.getLogger("business")
    business_logger.setLevel(log_level)

    # Clear existing handlers to avoid duplicate logging
    business_logger.handlers = []
    business_logger.addHandler(business_file_handler)
    business_logger.addHandler(business_console_handler)
    business_logger.propagate = False


class DevelopmentConfig(Config):
    DEBUG = True
    LOG_LEVEL = logging.DEBUG


class TestingConfig(Config):
    TESTING = True
    LOG_LEVEL = logging.DEBUG


class ProductionConfig(Config):
    LOG_LEVEL = logging.INFO


config: Dict[str, Type[Config]] = {
    "development": DevelopmentConfig,
    "testing": TestingConfig,
    "production": ProductionConfig,
    "default": DevelopmentConfig,
}
