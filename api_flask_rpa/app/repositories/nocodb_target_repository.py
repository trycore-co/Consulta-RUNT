from app.infrastructure.nocodb_client import NocoDBClient
from typing import Dict
from config import settings


class NocoDbTargetRepository:
    def __init__(self, client: NocoDBClient):
        self.client = client
        self.table = settings.NOCO_BASE_TRABAJO_TABLE

    def upsert_vehicle_detail(self, payload: Dict) -> Dict:
        # For simplicity, create new record. In production, implement upsert by unique key.
        return self.client.create_record(self.table, payload)
