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
        self.api_key = api_key 
        self.session = requests.Session()
        self.session.headers.update(
            {"xc-token": api_key, "Content-Type": "application/json"}
        )

    def _auth_headers(self) -> dict:
        """Devuelve los encabezados comunes de autenticación para NocoDB."""
        return {
            "xc-token": self.api_key,
            "Content-Type": "application/json",
        }

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
        self, table_id: str, payload: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Actualiza un registro en la tabla indicada.
        """
        url = f"{self.base_url}/api/v2/tables/{table_id}/records"
        r = self.session.patch(url, json=payload, timeout=30)
        r.raise_for_status()
        return r.json()

    def update_records_bulk(self, table_id: str, records: list[dict]):
        """
        PATCH bulk a /records. Cada item de 'records' DEBE incluir el PK de negocio
        (en tu caso 'Id') y los campos a actualizar (p.ej. RutaPDF).
        """
        url = f"{self.base_url}/api/v2/tables/{table_id}/records"
        body = {"records": records}
        logger.info("PATCH (bulk %s) %s body=%s", len(records), url, body)
        r = self.session.patch(url, headers=self._auth_headers(), json=body, timeout=30)
        r.raise_for_status()
        return r.json()
    
    def get_internal_id_by_field(self, table: str, field: str, value) -> int | None:
        """
        Devuelve el id interno (minúsculas) de NocoDB para la fila que cumple field == value.
        """
        try:
            # usa tu list_records que ya arma el filtro "(field,eq,value)"
            rows = self.list_records(table, where=f"{field},eq,{value}", limit=1)
            # rows ya viene como lista (tu list_records lo estandariza)
            if rows and isinstance(rows, list):
                return rows[0].get("id")
            return None
        except Exception as e:
            logger.error("get_internal_id_by_field falló: field=%s value=%s err=%s", field, value, e)
            return None

    def update_record_by_id(self, table_id: str, row_id: int, payload: dict):

        """
        1) Intenta PUT /records/{row_id} (si tu instancia lo soporta).
        2) Fallback: PATCH bulk con 'id' (minúsculas) en 'records'.
        """
        url_put = f"{self.base_url}/api/v2/tables/{table_id}/records/{row_id}"
        try:
            logger.info(f"PUT {url_put}")
            r = self.session.put(url_put, headers=self._auth_headers(), json=payload, timeout=30)
            r.raise_for_status()
            return r.json()
        except Exception as e1:
            # Fallback: BULK PATCH usando 'id' minúsculas (ID interno de NocoDB)
            url_bulk = f"{self.base_url}/api/v2/tables/{table_id}/records"
            body = {"records": [{ "id": row_id, **payload }]}  # 👈 'id', NO 'Id'
            try:
                logger.info(f"PATCH (bulk 1) {url_bulk} body={body}")
                r2 = self.session.patch(url_bulk, headers=self._auth_headers(), json=body, timeout=30)
                r2.raise_for_status()
                return r2.json()
            except Exception as e2:
                msg1 = getattr(e1, "response", None).text if getattr(e1, "response", None) else str(e1)
                msg2 = getattr(e2, "response", None).text if getattr(e2, "response", None) else str(e2)
                logger.error(f"❌ update_record_by_id failed. PUT err={msg1} | BULK err={msg2}")
                raise