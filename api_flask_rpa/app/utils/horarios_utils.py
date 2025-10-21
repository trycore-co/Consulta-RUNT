from datetime import datetime, time, date
from app.utils.festivos_service import get_festivos_service
from app.utils.logging_utils import get_logger

logger = get_logger("horarios_utils")

HORARIO_INICIO = time(7, 0)
HORARIO_FIN = time(18, 0)


def es_hora_laboral(hora: datetime | None) -> bool:
    """
    Retorna True si la hora actual está dentro del horario laboral: 7:00–18:00.
    """
    ahora = hora.time() if hora else datetime.now().time()
    return HORARIO_INICIO <= ahora <= HORARIO_FIN


def puede_ejecutar_en_fecha(fecha: date | None, hora: datetime | None) -> bool:
    """
    True si:
    - fecha es día hábil (no fin de semana, no festivo)
    - hora está entre 7:00 y 18:00
    """
    if fecha is None:
        fecha = datetime.now().date()
    festivos = get_festivos_service()
    dia_habil = festivos.es_dia_habil(fecha)
    horario_ok = es_hora_laboral(hora or datetime.now())
    logger.info(
        "Validación ejecución: fecha=%s dia_habil=%s horario_ok=%s",
        fecha,
        dia_habil,
        horario_ok,
    )
    return dia_habil and horario_ok
