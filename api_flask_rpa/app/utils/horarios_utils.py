from datetime import datetime, time, date
from app.utils.festivos_service import get_festivos_service
from app.utils.logging_utils import get_logger

logger = get_logger("horarios_utils")

HORARIO_INICIO = time(7, 0)
HORARIO_FIN = time(18, 0)


def es_hora_laboral(
    hora: datetime | None,
    hora_inicio_str: str = "07:00",
    hora_fin_str: str = "18:00",
) -> bool:
    """
    Retorna True si la hora actual está dentro del horario laboral: 7:00–18:00.
    """
    ahora = hora.time() if hora else datetime.now().time()
    # Conversión de strings a objetos time para comparación
    try:
        # Parsear HH:MM a objeto time
        inicio = datetime.strptime(hora_inicio_str, "%H:%M").time()
        fin = datetime.strptime(hora_fin_str, "%H:%M").time()
    except ValueError:
        logger.error(
            "Formato de hora inválido (%s o %s). Usando valores por defecto.",
            hora_inicio_str,
            hora_fin_str,
        )
        inicio = HORARIO_INICIO
        fin = HORARIO_FIN

    return inicio <= ahora <= fin


def puede_ejecutar_en_fecha(
    fecha: date | None,
    hora: datetime | None,
    hora_inicio: str = "07:00",
    hora_fin: str = "18:00",
) -> bool:
    """
    True si:
    - fecha es día hábil (no fin de semana, no festivo)
    - hora está entre HoraInico y HoraFin
    """
    if fecha is None:
        fecha = datetime.now().date()
    festivos = get_festivos_service()
    dia_habil = festivos.es_dia_habil(fecha)
    horario_ok = es_hora_laboral(
        hora or datetime.now(), hora_inicio_str=hora_inicio, hora_fin_str=hora_fin
    )
    logger.info(
        "Validación ejecución: fecha=%s dia_habil=%s horario_ok=%s",
        fecha,
        dia_habil,
        horario_ok,
        hora_inicio,
        hora_fin,
    )
    return dia_habil and horario_ok
