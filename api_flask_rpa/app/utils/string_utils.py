import re
from typing import Optional


def normalizar_nombre(nombre: Optional[str]) -> str:
    """
    Limpia y normaliza una cadena de nombre para comparación flexible.
    1. Convierte a mayúsculas.
    2. Elimina tildes (acentos).
    3. Remueve caracteres especiales (puntos, comas, guiones, etc.).
    4. Elimina espacios múltiples y espacios al inicio/fin.
    """
    if not nombre:
        return ""

    # 1. Convertir a mayúsculas
    nombre_normalizado = nombre.upper()

    # 2. Eliminar tildes (solo caracteres comunes en español)
    reemplazos = {
        "Á": "A",
        "É": "E",
        "Í": "I",
        "Ó": "O",
        "Ú": "U",
        "Ñ": "N",  # Opcional: mantener 'Ñ' si es crucial, o reemplazar por 'N'
    }
    for acentuado, sin_acento in reemplazos.items():
        nombre_normalizado = nombre_normalizado.replace(acentuado, sin_acento)

    # 3. Remover caracteres no alfanuméricos ni espacios (incluye puntos, comas, etc.)
    # Se mantienen letras (A-Z, Ñ), números (0-9) y espacios.
    nombre_normalizado = re.sub(r"[^\w\s]", "", nombre_normalizado)

    # 4. Eliminar espacios múltiples y espacios al inicio/fin
    nombre_normalizado = re.sub(r"\s+", " ", nombre_normalizado).strip()

    return nombre_normalizado
