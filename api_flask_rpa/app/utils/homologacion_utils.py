"""
Define las homologaciones de valores que provienen de fuentes externas
(como NocoDB) para alinearlos con los valores que espera el portal RUNT PRO.
"""

from typing import Optional
from app.utils.logging_utils import get_logger

logger = get_logger("homologacion_utils")


# Diccionario de homologación de tipos de documento
TIPO_DOCUMENTO_MAP = {
    "CC": "Cédula Ciudadanía",
    "CÉDULA DE CIUDADANÍA": "Cédula Ciudadanía",
    "CEDULA DE CIUDADANIA": "Cédula Ciudadanía",
    "CE": "Cédula de Extranjería",
    "CÉDULA DE EXTRANJERÍA": "Cédula de Extranjería",
    "CEDULA DE EXTRANJERIA": "Cédula de Extranjería",
    "RC": "Registro Civil",
    "TI": "Tarjeta de Identidad",
    "TI2": "TI2",
    "NIT": "NIT",
    "PA": "Pasaporte",
    "PPT": "Permiso por Protección Temporal",
    "CD": "Carnet Diplomático",
}


def homologar_tipo_documento(tipo_doc: Optional[str]) -> str:
    """
    Retorna el tipo de documento homologado según las opciones
    que reconoce el portal RUNT PRO.

    Si no se encuentra en el mapa, retorna el valor original.
    """
    if not tipo_doc:
        return ""
    tipo_doc_norm = tipo_doc.strip().upper()
    homologado = TIPO_DOCUMENTO_MAP.get(tipo_doc_norm, tipo_doc)
    if homologado != tipo_doc:
        logger.debug(f"Homologado tipo_doc '{tipo_doc}' -> '{homologado}'")
    else:
        logger.warning(f"No se encontró homologación para tipo_doc '{tipo_doc}'")
    return homologado
