import requests
import json
from typing import Any, Dict, List, Optional


class NocoDBClient:
    """
    Cliente para NocoDB API v2.
    Compatible con:
    GET  /api/v2/tables/{table_id}/records
    POST /api/v2/tables/{table_id}/records
    PATCH /api/v2/tables/{table_id}/records/{record_id}
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
            if isinstance(where, dict):
                params["where"] = json.dumps(where)
        params["limit"] = limit
        r = self.session.get(url, params=params, timeout=30)
        r.raise_for_status()
        return r.json().get("list", r.json())

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
