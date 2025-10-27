"""
Poller: revisa periódicamente la tabla Insumo en NocoDB y llama al endpoint
POST /api/gestion/ejecutar cuando haya registros pendientes.

Diseñado para ejecutarse como proceso separado (no dentro de Flask).
Configurable mediante variable de entorno POLLER_INTERVAL_SECONDS.
"""
import time
import requests
import sys
from config import settings
from app.infrastructure.nocodb_client import NocoDBClient
from app.repositories.nocodb_source_repository import NocoDbSourceRepository
from app.utils.logging_utils import get_logger

logger = get_logger("poller")

# Configuración
INTERVAL = int(getattr(settings, "POLLER_INTERVAL_SECONDS", 60))
FLASK_URL = getattr(settings, "FLASK_BASE_URL", "http://localhost:8080")
EXECUTE_ENDPOINT = f"{FLASK_URL}/api/gestion/ejecutar"


def check_nocodb_and_trigger(nocodb_client: NocoDBClient):
    source_repo = NocoDbSourceRepository(nocodb_client)
    try:
        pendientes = source_repo.obtener_pendientes(limit=1)
        count = len(pendientes) if pendientes else 0
        logger.info("Pendientes encontrados: %d", count)
        return count
    except Exception as e:
        logger.error("Error consultando NocoDB: %s", e)
        return None


def trigger_flask():
    try:
        logger.info("Llamando endpoint de ejecución: %s", EXECUTE_ENDPOINT)
        r = requests.post(EXECUTE_ENDPOINT, timeout=600)
        logger.info("Endpoint respondió: %s (status=%s)", r.text[:200], r.status_code)
        return True
    except Exception as e:
        logger.error("Error llamando endpoint: %s", e)
        return False


def main():
    logger.info("Iniciando poller (interval=%s seconds)", INTERVAL)

    # Inicializar cliente NocoDB
    try:
        nocodb_client = NocoDBClient(settings.NOCODB_URL, settings.NOCO_XC_TOKEN)
    except Exception as e:
        logger.error("No se pudo inicializar NocoDBClient: %s", e)
        sys.exit(1)

    backoff = 1
    while True:
        try:
            count = check_nocodb_and_trigger(nocodb_client)
            if count is None:
                # Error consultando NocoDB: aplicar backoff corto antes de reintentar
                logger.warning("Aplicando backoff: %s segundos", backoff)
                time.sleep(backoff)
                backoff = min(backoff * 2, 300)
                continue

            if count > 0:
                # Si hay pendientes, llamar al endpoint y esperar a que termine
                ok = trigger_flask()
                if not ok:
                    # si falla la llamada a flask, esperar y reintentar
                    logger.warning("Fallo al invocar endpoint, esperando antes de reintentar")
                    time.sleep(10)
                else:
                    # ejecución exitosa, reset backoff
                    backoff = 1
                    # tras ejecutar, esperar un poco para permitir que el proceso termine de actualizar registros
                    time.sleep(max(5, INTERVAL))
            else:
                # no hay pendientes: dormir el intervalo configurado
                time.sleep(INTERVAL)

        except KeyboardInterrupt:
            logger.info("Poller detenido por usuario (KeyboardInterrupt)")
            break
        except Exception as e:
            logger.exception("Error inesperado en poller: %s", e)
            time.sleep(10)


if __name__ == '__main__':
    main()
