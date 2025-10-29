# Puedes añadir esto en un módulo de utilidades como homologacion_utils.py (si manejas ahí otros campos)
# o simplemente en el ProcesoUnitarioWF antes de la consulta.

import re
from typing import Optional


def limpiar_nit_sin_dv(
    numero_identificacion: Optional[str], tipo_documento: str
) -> str:
    """
    Limpia el número de identificación. Si el tipo es 'NIT', remueve el dígito de verificación.
    """
    if not numero_identificacion:
        return ""

    # 1. Quitar cualquier guion, punto o espacio
    nit_limpio = re.sub(r"[.\- ]", "", numero_identificacion).strip()

    if tipo_documento.upper() in ["NIT", "NÚMERO DE IDENTIFICACIÓN TRIBUTARIA"]:
        # 2. Si el NIT limpio tiene 10 dígitos (9 del NIT + 1 DV), asumimos que el último es el DV.
        # El NIT colombiano tiene 9 dígitos base, el DV es el décimo.
        if len(nit_limpio) == 10:
            return nit_limpio[:-1]  # Retorna los primeros 9 dígitos

    return nit_limpio


# --- USO EN EL WORKFLOW ---
# num_sin_dv = limpiar_nit_sin_dv(record["NumeroIdentificacion"], record["TipoDocumento"])
