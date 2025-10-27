import requests
import json
from typing import Any, Dict, List, Optional
from app.utils.logging_utils import get_logger

logger = get_logger("nocodb_client")

class NocoDBClient:
    """
    Cliente para NocoDB API v2.
    Compatible con:
    GET  /api/v2/tables/{table_id}/records
    POST /api/v2/tables/{table_id}/records
    PATCH /api/v2/tables/{table_id}/records
    """
    def __init__(self, base_url: str, api_key: str):
        self.base_url = base_url.rstrip("/")
        self.session = requests.Session()
        self.session.headers.update(
            {"xc-token": api_key, "Content-Type": "application/json"}
        )

    def list_records(
        self, table: str, where: Optional[str] = None, limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        Obtiene registros desde una tabla en NocoDB API v2.
        """
        url = f"{self.base_url}/api/v2/tables/{table}/records"
        params = {}
        if where:
            # Accept either a dict (to be JSON-encoded) or a pre-built
            # string filter. Some call sites pass a string like
            # "EstadoGestion,eq,Sin Procesar" — convert that into the
            # JSON array form that NocoDB expects (array of arrays)
            # e.g. [["EstadoGestion","eq","Sin Procesar"]]
            if isinstance(where, dict):
                params["where"] = json.dumps(where)
            else:
                s = str(where)
                # if filter looks like 'col,op,value' convert to JSON array
                parts = [p.strip() for p in s.split(",")]
                if len(parts) >= 3:
                    # join remaining parts as the value (in case value contains commas)
                    col = parts[0]
                    op = parts[1].lower()  # aseguramos que el operador esté en minúsculas
                    val = ",".join(parts[2:]).strip()

                    # Prueba con formato de filtro array usando corchetes
                    where_json = {
                        "fk_column_id": col,
                        "status": "enable",
                        "logical_op": "and",
                        "comparison_op": op,
                        "value": val
                    }

                    # Convertir a query string format que espera NocoDB
                    filter_str = f"({col},{op},{val})"
                    params["filter"] = filter_str
                    logger.debug("Usando filtro: %s", filter_str)
                else:
                    # fallback: send raw string
                    params["where"] = s
                    logger.warning("Filtro no tiene formato col,op,val: %s", s)

        params["limit"] = limit
        logger.debug("GET %s params=%s", url, params)
        try:
            # Construir y loggear la URL completa antes de la petición
            prepared_request = requests.Request('GET', url, params=params).prepare()
            logger.debug("URL completa: %s", prepared_request.url)
            r = self.session.get(url, params=params, timeout=30)
            logger.debug("Response status=%d headers=%s", r.status_code, dict(r.headers))
            if r.status_code >= 400:
                logger.error("Error response: %s", r.text[:1000])
            r.raise_for_status()
            data = r.json()
            result = data.get("list", data)
            logger.debug("Registros obtenidos: %d", len(result) if result else 0)
            if result:
                logger.debug("Ejemplo primer registro: %s", result[0])
            return result
        except requests.exceptions.RequestException as e:
            logger.error("Error en request: %s", str(e))
            raise

    def create_record(self, table: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Crea un nuevo registro en la tabla indicada.
        """
        url = f"{self.base_url}/api/v2/tables/{table}/records"
        r = self.session.post(url, json=payload, timeout=30)
        r.raise_for_status()
        return r.json()

    def update_record(
        self, table: str, payload: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Actualiza un registro en la tabla indicada.
        """
        url = f"{self.base_url}/api/v2/tables/{table}/records"
        r = self.session.patch(url, json=payload, timeout=30)
        r.raise_for_status()
        return r.json()

    def update_record_where(
        self, table: str, payload: Dict[str, Any], where: str = None
    ) -> Dict[str, Any]:
        """
        Actualiza un registro en la tabla indicada. Si se proporciona 'where', realiza una actualización masiva.
        """
        url = f"{self.base_url}/api/v2/tables/{table}/records"
        data = {
            "list": [payload],  # El 'payload' original son los campos a actualizar
            "where": where,  # El filtro para seleccionar los registros
        }
        r = self.session.patch(url, json=data, timeout=30)
        r.raise_for_status()
        return r.json()
