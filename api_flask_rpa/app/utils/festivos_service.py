"""
Servicio de Validación de Festivos en Colombia.

Verifica si una fecha es festivo o día hábil en Colombia,
considerando festivos nacionales y días no laborables.
"""

from datetime import datetime, date
from typing import Optional, Dict
from app.utils.logging_utils import get_logger
import holidays

logger = get_logger("festivos_service")


class FestivosService:
    """
    Servicio para manejo de festivos y días hábiles en Colombia.
    """

    # Días de la semana (0 = Lunes, 6 = Domingo)
    LUNES = 0
    MARTES = 1
    MIERCOLES = 2
    JUEVES = 3
    VIERNES = 4
    SABADO = 5
    DOMINGO = 6

    # Días laborables (Lunes a Viernes)
    DIAS_LABORABLES = [LUNES, MARTES, MIERCOLES, JUEVES, VIERNES]

    def __init__(self, country_code: str = "CO"):
        """
        Crea una instancia del servicio de festivos para el país indicado.
        """
        self.festivos_colombia = holidays.country_holidays(country_code)
        logger.info("FestivosService inicializado para %s", country_code)

    def es_festivo(self, fecha: Optional[date] = None) -> bool:
        """
        Verifica si una fecha es festivo en Colombia.
        Args:
            fecha: Fecha a verificar (usa hoy si es None)
        Returns:
            True si es festivo, False en caso contrario
        """
        if fecha is None:
            fecha = datetime.now().date()

        festivo = fecha in self.festivos_colombia
        logger.debug("es_festivo(%s) -> %s", fecha, festivo)
        return festivo

    def es_fin_de_semana(self, fecha: Optional[date] = None) -> bool:
        """
        Verifica si una fecha es fin de semana (sábado o domingo).

        Args:
            fecha: Fecha a verificar (usa hoy si es None)

        Returns:
            True si es fin de semana
        """
        if fecha is None:
            fecha = datetime.now().date()

        return fecha.weekday() in [self.SABADO, self.DOMINGO]

    def es_dia_habil(self, fecha: Optional[date] = None) -> bool:
        """
        Verifica si una fecha es día laborable (lunes a viernes).

        No considera festivos, solo el día de la semana.

        Args:
            fecha: Fecha a verificar (usa hoy si es None)

        Returns:
            True si es día laborable
        """
        if fecha is None:
            fecha = datetime.now().date()
        if self.es_fin_de_semana(fecha):
            logger.debug("%s es fin de semana", fecha)
            return False
        if self.es_festivo(fecha):
            logger.debug("%s es festivo", fecha)
            return False
        return True

    def obtener_nombre_festivo(self, fecha: date) -> Optional[str]:
        """
        Obtiene el nombre del festivo para una fecha.

        Args:
            fecha: Fecha a consultar

        Returns:
            Nombre del festivo o None si no es festivo
        """
        return self.festivos_colombia.get(fecha)

    def obtener_festivos_mes(
        self, mes: Optional[int] = None, anio: Optional[int] = None
    ) -> Dict[date, str]:
        """
        Obtiene todos los festivos de un mes específico.

        Args:
            mes: Mes a consultar (1-12, usa mes actual si es None)
            anio: Año a consultar (usa año actual si es None)

        Returns:
            Diccionario con fechas y nombres de festivos
        """
        if mes is None:
            mes = datetime.now().month
        if anio is None:
            anio = datetime.now().year

        resultado = {
            f: n
            for f, n in self.festivos_colombia.items()
            if isinstance(f, date) and f.year == anio and f.month == mes
        }
        logger.debug("Festivos mes %s/%s -> %d", mes, anio, len(resultado))
        return resultado


# Singleton helper
_instance: Optional[FestivosService] = None


def get_festivos_service() -> FestivosService:
    """
    Obtiene la instancia del servicio de festivos (Singleton).

    Returns:
        Instancia única del servicio
    """
    global _instance
    if _instance is None:
        _instance = FestivosService()
    return _instance
