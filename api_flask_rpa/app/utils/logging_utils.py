import os
import logging
from datetime import datetime
from pathlib import Path
import socket
import getpass
from config import settings

# === Datos base del asistente ===
CODIGO_ASISTENTE = "R_Consulta_RUNT"  # Código interno del bot
NOMBRE_BOT_TASK = "ConsultaRUNT"  # Nombre general del proceso

# === Encabezado del archivo ===
HEADER = (
    "Código asistente;Usuario de red;Máquina;Hostname;Nombre Bot Task;"
    "Fecha ejecución;Hora Ejecución;Número único de proceso (Si aplica);"
    "Aplicación intervenida;Nombre Archivo imagen Proceso;Descripción del evento"
)


def get_logger(name: str):
    """
    Devuelve un logger configurado para escritura de logs diarios con formato RPA corporativo.
    Crea dos archivos por día: auditoría y errores.
    """
    base_path = Path(settings.LOG_PATH)
    hoy_str = datetime.now().strftime("%Y-%m-%d")
    carpeta_dia = base_path / hoy_str
    carpeta_dia.mkdir(parents=True, exist_ok=True)

    fecha_actual = datetime.now().strftime("%Y%m%d")
    audit_file = (
        carpeta_dia
        / f"{CODIGO_ASISTENTE}{NOMBRE_BOT_TASK}_LOG_DE_AUDITORIA_{fecha_actual}.log"
    )
    error_file = (
        carpeta_dia
        / f"{CODIGO_ASISTENTE}{NOMBRE_BOT_TASK}_LOG_DE_ERRORES_{fecha_actual}.log"
    )

    # === Crear encabezados si no existen ===
    for file in (audit_file, error_file):
        if not file.exists():
            with open(file, "w", encoding="utf-8") as f:
                f.write(HEADER + "\n")

    # === Configuración base ===
    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)

    if logger.handlers:
        return logger

    # === Formato personalizado ===
    class RPALogFormatter(logging.Formatter):
        def format(self, record):
            now = datetime.now()
            fecha = now.strftime("%Y-%m-%d")
            hora = now.strftime("%H:%M:%S")

            usuario = getpass.getuser()
            maquina = socket.gethostname()
            hostname = socket.getfqdn()

            # Datos personalizados
            num_proceso = getattr(record, "process_id", "NO APLICA")
            archivo_img = getattr(record, "image_name", "NO APLICA")
            aplicacion_intervenida = record.name  # se usa el nombre del logger

            linea = (
                f"{CODIGO_ASISTENTE};{usuario};{maquina};{hostname};{NOMBRE_BOT_TASK};"
                f"{fecha};{hora};{num_proceso};{aplicacion_intervenida};"
                f"{archivo_img};{record.getMessage()}"
            )
            return linea

    formatter = RPALogFormatter()

    # === Handlers ===
    fh_audit = logging.FileHandler(audit_file, encoding="utf-8")
    fh_audit.setLevel(logging.INFO)
    fh_audit.setFormatter(formatter)

    fh_error = logging.FileHandler(error_file, encoding="utf-8")
    fh_error.setLevel(logging.ERROR)
    fh_error.setFormatter(formatter)

    # (Opcional) Consola en modo debug
    if getattr(settings, "DEBUG", False):
        ch = logging.StreamHandler()
        ch.setLevel(logging.DEBUG)
        ch.setFormatter(formatter)
        logger.addHandler(ch)

    logger.addHandler(fh_audit)
    logger.addHandler(fh_error)

    return logger
