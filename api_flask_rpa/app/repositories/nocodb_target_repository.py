from app.infrastructure.nocodb_client import NocoDBClient
from typing import Dict, List
from config import settings
from datetime import datetime
import json
from app.utils.logging_utils import get_logger

logger = get_logger("nocodb_target_repository")

class NocoDbTargetRepository:
    def __init__(self, client: NocoDBClient):
        self.client = client
        self.table = settings.NOCO_BASE_TRABAJO_TABLE
        self.date_format = "%Y-%m-%d %H:%M:%S%z"  # Formato ajustar si es necesario

    def upsert_vehicle_detail(
        self,
        source_record: Dict,
        vehicle_details: Dict,
        ruta_pdf: str | None = None,
        fecha_inicio: datetime = None,
        fecha_fin: datetime = None,
    ) -> List[Dict]:
        """
        Inserta un registro por cada par NombreDetalle/ValorDetalle extraído.

        :param source_record: El registro original de la tabla fuente (Insumo).
        :param vehicle_details: El diccionario con los datos extraídos del vehículo.
        :return: Una lista de las respuestas de creación de registros de NocoDB.
        """

        # 1. Obtener campos comunes de la fuente
        record_id_insumo = (
            source_record.get("Id")
            or source_record.get("ID")
            or source_record.get("id")
        )
        num_identificacion = source_record.get(
            "NumeroIdentificacion"
        ) or source_record.get("NumIdentificacion")
        nombre_propietario = source_record.get(
            "NombrePropietario"
        )
        if not record_id_insumo or not num_identificacion:
            logger.error(
                f"Faltan campos esenciales (Id/NumIdentificacion) en el registro fuente: {source_record}"
            )
            return []

        # 2. Generar NumUnicoProceso: NumIdentificacion + Fecha (YYYY-MM-DD)
        fecha_actual = datetime.now().strftime("%Y-%m-%d")
        num_unico_proceso = f"{num_identificacion}_{fecha_actual}"

        # 3. Usar FechaIngreso del insumo como FechaInsercion
        fecha_insercion = source_record.get("FechaIngreso") or datetime.now().isoformat()  # Si no hay FechaIngreso, usar fecha actual

        records_to_create = []

        # Iterar sobre cada detalle (par clave-valor) extraído
        for nombre_detalle, valor_detalle in vehicle_details.items():
            record = {
                # Campos de identificación y contexto
                "idBaseTrabajo": record_id_insumo,
                "NumUnicoProceso": num_unico_proceso,
                "NumIdentificacion": num_identificacion,
                "NombrePropietario": nombre_propietario,
                "Placa": vehicle_details.get("Placa", ""),
                # Campos del detalle extraído
                "NombreDetalle": nombre_detalle,
                "ValorDetalle": str(
                    valor_detalle
                ),  # Asegurar que es string si el campo NocoDB es 'T' (texto)
                # Metadatos del proceso
                "FechaInsercion": fecha_insercion,
                "Estado": "Exitoso",  # O el estado que corresponda a la inserción del detalle
                "Observacion": "Detalle de vehículo insertado",
                "FechaHoraInicio": fecha_inicio,
                "FechaHoraFin": fecha_fin,
                "RutaPDF": ruta_pdf,
            }
            records_to_create.append(record)

        # 4. Insertar los registros en NocoDB
        responses = []
        for record in records_to_create:
            response = self.client.create_record(self.table, record)
            responses.append(response)

        return responses

    def update_ruta_pdf_by_proceso(self, source_record: Dict, ruta_pdf: str) -> Dict:
        """
        Actualiza 'RutaPDF' en los registros de detalle cuyo NumUnicoProceso sea
        {NumIdentificacion}_{YYYY-MM-DD} usando la fecha actual.
        """
        # 1) Obtener identificación del registro fuente
        num_identificacion = (
            source_record.get("NumeroIdentificacion")
            or source_record.get("NumIdentificacion")
        )
        if not num_identificacion:
            logger.error(
                "No se pudo obtener NumIdentificacion del registro fuente para actualizar el PDF."
            )
            return {"msg": "Error: NumIdentificacion no encontrado"}

        # 2) Reconstruir NumUnicoProceso con fecha actual
        fecha_actual = datetime.now().strftime("%Y-%m-%d")
        num_unico_proceso = f"{num_identificacion}_{fecha_actual}"

        # 3) Normalizar ruta y armar filtro
        ruta_web = ruta_pdf.replace("\\", "/")
        payload = {"RutaPDF": ruta_web}
        where_filter = f"(NumUnicoProceso,eq,{json.dumps(num_unico_proceso)})"

        logger.info(
            "Actualizando RutaPDF: NumUnicoProceso=%s  RutaPDF=%s",
            num_unico_proceso, ruta_web
        )

        # Intento 1: update masivo con WHERE
        try:
            if hasattr(self.client, "update_records_with_where"):
                resp = self.client.update_records_with_where(
                    self.table,
                    payload=payload,
                    where=where_filter,
                )
                return {
                    "msg": "OK (where)",
                    "NumUnicoProceso": num_unico_proceso,
                    "RutaPDF": ruta_web,
                    "response": resp,
                }
        except Exception as e:
            # Log del cuerpo de error si viene de requests/httpx
            if hasattr(e, "response") and getattr(e.response, "text", None):
                logger.error(
                    "Fallo update_records_with_where: %s | body=%s",
                    e, e.response.text
                )
            else:
                logger.error("Fallo update_records_with_where: %s", e)
            # continuar al fallback

        # Fallback: listar IDs y hacer PATCH por Id
        try:
            # Quitar 'fields' porque tu cliente no lo soporta
            rows = self.client.list_records(
                self.table,
                where=where_filter,
                limit=1000,
            )

            # Dependiendo del cliente, puede devolver {"list": [...]} o una lista directa
            list_rows = rows.get("list") if isinstance(rows, dict) else rows
            ids = [r.get("Id") for r in list_rows if r.get("Id")]

            if not ids:
                logger.warning(
                    "Sin filas que actualizar (NumUnicoProceso=%s)", num_unico_proceso
                )
                return {
                    "msg": "Sin filas que actualizar",
                    "count": 0,
                    "NumUnicoProceso": num_unico_proceso,
                }

            updated = 0
            for row_id in ids:
                self.client.update_record_by_id(self.table, row_id, payload)
                updated += 1

            return {
                "msg": "OK (by-id)",
                "count": updated,
                "NumUnicoProceso": num_unico_proceso,
                "RutaPDF": ruta_web,
            }

        except Exception as e:
            if hasattr(e, "response") and getattr(e.response, "text", None):
                logger.error("Error al actualizar RutaPDF: %s | body=%s", e, e.response.text)
            else:
                logger.error("Error al actualizar RutaPDF: %s", e)
            raise