from app.infrastructure.nocodb_client import NocoDBClient
from typing import List, Dict, Any
from config import settings
from app.utils.logging_utils import get_logger

logger = get_logger("nocodb_source_repository")

class NocoDbSourceRepository:
    def __init__(self, client: NocoDBClient):
        self.client = client
        self.table_insumo = settings.NOCO_INSUMO_TABLE
        self.table_parametros = settings.NOCO_PARAMETROS_TABLE

    def _get_record_id(self, record: Dict[str, Any]) -> str:
        """Extrae el ID del registro de forma consistente."""
        record_id = record.get("Id") or record.get("ID") or record.get("id")
        if not record_id:
            raise ValueError(f"El registro no tiene campo Id: {record}")
        return str(record_id)

    def obtener_parametros(self) -> dict:
        """
        Retorna los parámetros del sistema como un diccionario clave:valor.
        """
        tabla = self.table_parametros
        registros = self.client.list_records(tabla)
        return {r["Nombre"]: r["Valor"] for r in registros if "Nombre" in r and "Valor" in r}

    def obtener_pendientes(self, limit: int = 100) -> List[Dict[str, Any]]:
        """
        Devuelve los registros pendientes en la tabla de insumo.
        Filtra por EstadoGestion = 'Sin Procesar'.
        """
        where = "EstadoGestion,eq,Sin Procesar"
        try:
            logger.debug("Intentando obtener registros pendientes con where=%s limit=%d", where, limit)
            result = self.client.list_records(self.table_insumo, where=where, limit=limit)
            logger.debug("Registros obtenidos: %d", len(result) if result else 0)
            return result
        except Exception as e:
            logger.error("Error aplicando filtro where='%s': %s", where, str(e))
            logger.warning("Intentando obtener registros sin filtro como fallback")
            return self.client.list_records(self.table_insumo, limit=limit)

    def marcar_en_proceso(self, record: Dict[str, Any]) -> None:
        record_id = self._get_record_id(record)
        payload = {
            "Id": record_id,  # o "ID" según como lo maneje NocoDB
            "EstadoGestion": "Procesando",
        }
        self.client.update_record(self.table_insumo, payload)

    def marcar_exitoso(self, record: Dict[str, Any]) -> None:
        record_id = self._get_record_id(record)
        payload = {"Id": record_id, "EstadoGestion": "Exitoso"}
        self.client.update_record(
            self.table_insumo, payload)

    def marcar_fallido(self, record: Dict[str, Any], motivo: str) -> None:
        record_id = self._get_record_id(record)
        payload = {
            "Id": record_id,
            "EstadoGestion": motivo,
        }
        self.client.update_record(
            self.table_insumo,
            payload)
