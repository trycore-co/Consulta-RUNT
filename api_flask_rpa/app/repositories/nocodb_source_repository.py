from app.infrastructure.nocodb_client import NocoDBClient
from typing import List, Dict, Any
from config import settings


class NocoDbSourceRepository:
    def __init__(self, client: NocoDBClient):
        self.client = client
        self.table_insumo = settings.NOCO_INSUMO_TABLE
        self.table_parametros = settings.NOCO_PARAMETROS_TABLE

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
            return self.client.list_records(self.table_insumo, where=where, limit=limit)
        except Exception:
            return self.client.list_records(self.table_insumo, limit=limit)

    def marcar_en_proceso(self, record: Dict[str, Any]) -> None:
        record_id = record.get("Id") or record.get("ID")
        if not record_id:
            raise ValueError(f"El registro sin campo Id: {record}")
        self.client.update_record(self.table_insumo, record_id, {"EstadoGestion": "Procesando"})

    def marcar_exitoso(self, record: Dict[str, Any], url_pdf: str) -> None:
        record_id = record.get("Id") or record.get("id")
        if not record_id:
            raise ValueError(f"El registro sin campo Id: {record}")
        self.client.update_record(
            self.table_insumo, record_id, {"EstadoGestion": "Exitoso", "RutaPDF": url_pdf}
        )

    def marcar_fallido(self, record: Dict[str, Any], motivo: str) -> None:
        record_id = record.get("Id") or record.get("id")
        if not record_id:
            raise ValueError(f"El registro sin campo Id: {record}")
        self.client.update_record(
            self.table_insumo,
            record_id,
            {"EstadoGestion": "No Exitoso error controlado", "Observacion": motivo},
        )
