from app.infrastructure.nocodb_client import NocoDBClient
from typing import Dict, List
from config import settings
from datetime import datetime
from app.utils.logging_utils import get_logger

logger = get_logger("nocodb_target_repository")

class NocoDbTargetRepository:
    def __init__(self, client: NocoDBClient):
        self.client = client
        self.table = settings.NOCO_BASE_TRABAJO_TABLE
        self.date_format = "%Y-%m-%d %H:%M:%S%z"  # Formato ajustar si es necesario

    def upsert_vehicle_detail(
        self, source_record: Dict, vehicle_details: Dict
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
                "FechaHoraInicio": datetime.now().isoformat(),
                "FechaHoraFin": datetime.now().isoformat(),
            }
            records_to_create.append(record)

        # 4. Insertar los registros en NocoDB
        responses = []
        for record in records_to_create:
            response = self.client.create_record(self.table, record)
            responses.append(response)

        return responses
