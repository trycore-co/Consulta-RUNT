import logging
from pythonjsonlogger.json import JsonFormatter


def get_logger(name: str):
    logger = logging.getLogger(name)
    if not logger.handlers:
        handler = logging.StreamHandler()
        fmt = JsonFormatter("%(asctime)s %(name)s %(levelname)s %(message)s")
        handler.setFormatter(fmt)
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
    return logger
