from app.infrastructure.nocodb_client import NocoDBClient
from typing import Dict


class NocoDbTargetRepository:
    def __init__(
        self, client: NocoDBClient, table_name: str = "R_ConsultaRUNT.BaseTrabajo"
    ):
        self.client = client
        self.table = table_name

    def upsert_vehicle_detail(self, payload: Dict) -> Dict:
        # For simplicity, create new record. In production, implement upsert by unique key.
        return self.client.create_record(self.table, payload)
