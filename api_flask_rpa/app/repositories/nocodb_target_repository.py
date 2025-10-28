# app/repositories/nocodb_target_repository.py
from typing import Dict, List
from datetime import datetime
from config import settings
import json
from app.utils.logging_utils import get_logger
from app.infrastructure.nocodb_client import NocoDBClient

logger = get_logger("nocodb_target_repository")

class NocoDbTargetRepository:
    def __init__(self, client: NocoDBClient):
        self.client = client
        self.table = settings.NOCO_BASE_TRABAJO_TABLE
        self.date_format = "%Y-%m-%d %H:%M:%S%z"

    def upsert_vehicle_detail(
        self,
        source_record: Dict,
        vehicle_details: Dict,
        ruta_pdf: str | None = None,
        fecha_inicio: str | None = None,
        fecha_fin: str | None = None,
        num_unico_proceso: str | None = None,   # <-- ya lo traes desde main
    ) -> List[int]:
        """
        Inserta un registro por cada par NombreDetalle/ValorDetalle.
        Devuelve la lista de IDs creados en NocoDB.
        """
        record_id_insumo = (
            source_record.get("Id")
            or source_record.get("ID")
            or source_record.get("id")
        )
        num_identificacion = source_record.get("NumeroIdentificacion") or source_record.get("NumIdentificacion")
        nombre_propietario = source_record.get("NombrePropietario")

        if not record_id_insumo or not num_identificacion:
            logger.error("Faltan Id/NumIdentificacion en el registro fuente: %s", source_record)
            return []

        # No recalcular; usar el que recibimos del main
        if not num_unico_proceso:
            fecha_actual = datetime.now().strftime("%Y-%m-%d")
            num_unico_proceso = f"{num_identificacion}_{fecha_actual}"

        fecha_insercion = source_record.get("FechaIngreso") or datetime.now().isoformat()

        created_business_ids: List[int] = []

        for nombre_detalle, valor_detalle in vehicle_details.items():
            record = {
                "idBaseTrabajo": record_id_insumo,
                "NumUnicoProceso": num_unico_proceso,
                "NumIdentificacion": num_identificacion,
                "NombrePropietario": nombre_propietario,
                "Placa": vehicle_details.get("Placa", ""),
                "NombreDetalle": nombre_detalle,
                "ValorDetalle": str(valor_detalle),
                "FechaInsercion": fecha_insercion,
                "Estado": "Exitoso",
                "Observacion": "Detalle de vehículo insertado",
                "FechaHoraInicio": fecha_inicio,
                "FechaHoraFin": fecha_fin,
                "RutaPDF": ruta_pdf,  # puede ir None; luego lo actualizamos
            }
            try:
                resp = self.client.create_record(self.table, record)
                # ⚠️ Tu NocoDB devuelve solo 'Id' (PK de negocio)
                rid_business = resp.get("Id")
                if rid_business is not None:
                    created_business_ids.append(int(rid_business))
                    logger.info("[CREATE OK] Id=%s NombreDetalle=%s", rid_business, nombre_detalle)
                else:
                    logger.warning("[CREATE sin 'Id'] resp=%s", resp)
            except Exception as e:
                logger.error("[CREATE FAIL] %s | body=%s", e, record)


        return created_business_ids

    def update_ruta_pdf_by_ids(self, ids: List[int], ruta_pdf: str) -> Dict:
        """
        Actualiza RutaPDF en bulk usando el PK de negocio 'Id'.
        """
        if not ids:
            logger.warning("update_ruta_pdf_by_ids: lista vacía, nada que actualizar.")
            return {"msg": "Sin IDs"}

        ruta_web = (ruta_pdf or "").replace("\\", "/")

        # Construimos el cuerpo que NocoDB espera: records = [{Id: ..., RutaPDF: ...}, ...]
        records = [{"Id": rid, "RutaPDF": ruta_web} for rid in ids]

        try:
            resp = self.client.update_records_bulk(self.table, records)
            return {"msg": "OK (bulk by Id)", "count": len(ids), "RutaPDF": ruta_web, "resp": resp}
        except Exception as e:
            # Logs útiles si el servidor devuelve detalle
            body_txt = getattr(getattr(e, "response", None), "text", None)
            if body_txt:
                logger.error("Bulk PATCH falló: %s | body=%s", e, body_txt)
            else:
                logger.error("Bulk PATCH falló: %s", e)
            raise
