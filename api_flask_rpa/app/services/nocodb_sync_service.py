from app.repositories.nocodb_source_repository import NocoDbSourceRepository
from app.repositories.nocodb_target_repository import NocoDbTargetRepository


class NocoDbSyncService:
    def __init__(
        self, source_repo: NocoDbSourceRepository, target_repo: NocoDbTargetRepository
    ):
        self.source = source_repo
        self.target = target_repo

    def obtener_pendientes(self, limit: int = 100):
        return self.source.obtener_pendientes(limit=limit)

    def marcar_en_proceso(self, record_id: int):
        self.source.marcar_en_proceso(record_id)

    def marcar_exitoso(self, record_id: int, url_pdf: str):
        self.source.marcar_exitoso(record_id, url_pdf)

    def marcar_fallido(self, record_id: int, motivo: str):
        self.source.marcar_fallido(record_id, motivo)

    def insertar_detalle(self, detalle_payload):
        return self.target.upsert_vehicle_detail(detalle_payload)
