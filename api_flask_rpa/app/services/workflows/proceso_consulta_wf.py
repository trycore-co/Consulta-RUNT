import uuid
from app.repositories.nocodb_source_repository import NocoDbSourceRepository
from app.infrastructure.nocodb_client import NocoDBClient
from app.infrastructure.web_client import WebClient
from app.services.workflows.proceso_unitario_wf import ProcesoUnitarioWF
from app.utils.horarios_utils import puede_ejecutar_en_fecha
from datetime import datetime
from app.utils.logging_utils import get_logger

logger = get_logger("proceso_consulta_wf")


class ProcesoConsultaWF:
    def __init__(self, nocodb_client: NocoDBClient, web_client: WebClient):
        self.nocodb_client = nocodb_client
        self.web_client = web_client
        self.source_repo = NocoDbSourceRepository(self.nocodb_client)

    def ejecutar_lote(self):
        """
        Ejecuta un lote de consultas pendientes según las HU definidas.
        Controla horario laboral y estados de gestión.
        """
        # 1) leer parámetros
        parametros = self.source_repo.obtener_parametros()
        ahora = datetime.now()
        if not puede_ejecutar_en_fecha(ahora.date(), ahora):
            logger.info("Ejecución omitida: fuera de horario o día no hábil.")
            return {
                "processed": 0,
                "message": "Fuera de horario laboral o día no hábil.",
            }
        # obtener pendientes
        limit = int(parametros.get("LimitePendientes", 50) or 50)
        pendientes = self.source_repo.obtener_pendientes(limit=limit)
        logger.info("Pendientes encontrados: %d", len(pendientes))

        # parámetros comunes que pasaremos downstream
        reintentos_login = int(parametros.get("ReintentosLogin", 2) or 2)
        reintentos_proceso = int(parametros.get("ReintentosProceso", 2) or 2)
        timeout_bajo = int(parametros.get("DelayBajo", 5) or 5)
        timeout_medio = int(parametros.get("DelayMedio", 10) or 10)
        timeout_largo = int(parametros.get("DelayAlto", 15) or 15)

        # Contadores y resultados
        ok_count, error_count = 0, 0
        results = []

        for record in pendientes:
            corr_id = str(uuid.uuid4())
            record_id = record.get("Id")

            if not record_id:
                logger.warning(f"Registro sin 'Id' válido: {record}")
                continue

            try:
                # Marcar como “En Proceso” en Noco
                logger.info(f"registro {record}")
                self.source_repo.marcar_en_proceso(record)

                # Ejecutar flujo unitario
                wf_unit = ProcesoUnitarioWF(
                    record=record,
                    nocodb_client=self.nocodb_client,
                    web_client=self.web_client,
                    correlation_id=corr_id,
                    reintentos_login=reintentos_login,
                    reintentos_proceso=reintentos_proceso,
                    timeout_bajo=timeout_bajo,
                    timeout_medio=timeout_medio,
                    timeout_largo=timeout_largo,
                )
                resultado = wf_unit.ejecutar()

                # Marcar como “Procesado”
                self.source_repo.marcar_exitoso(record, resultado.get("url_pdf", ""))

                ok_count += 1
                results.append(resultado)

            except Exception as e:
                logger.exception(f"Error procesando registro {record_id}: {e}")
                error_count += 1
                try:
                    self.source_repo.marcar_fallido(record, str(e))
                except Exception as e2:
                    logger.warning(f"No se pudo actualizar estado de error en NocoDB: {e2}")
                results.append({"id": record_id, "error": str(e)})

        logger.info(f"Lote completado. OK={ok_count}, ERROR={error_count}")

        return {
            "procesados": ok_count,
            "errores": error_count,
            "mensaje": "Ejecución completada correctamente",
            "detalles": results,
        }
