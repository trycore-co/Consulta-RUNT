from flask import Blueprint, jsonify, render_template, request
from app.services.workflows.proceso_consulta_wf import ProcesoConsultaWF
from app.infrastructure.nocodb_client import NocoDBClient
from app.infrastructure.web_client import WebClient
from config import settings
from datetime import datetime
from app.utils.horarios_utils import puede_ejecutar_en_fecha
from app.utils.logging_utils import get_logger

bp = Blueprint("gestion", __name__, template_folder="../templates")

logger = get_logger("gestion_bp")

# Inicializa cliente de NocoDB una sola vez
nocodb = NocoDBClient(base_url=settings.NOCODB_URL, api_key=settings.NOCO_XC_TOKEN)


@bp.route("/ejecutar", methods=["POST", "GET"])
def ejecutar():
    """
    Ejecuta el flujo completo: obtiene pendientes y procesa el lote.
    POST → ejecuta la automatización
    GET  → muestra una página con estado del proceso
    """
    if request.method == "GET":
        ahora = datetime.now()
        if not puede_ejecutar_en_fecha(ahora.date(), ahora):
            return render_template(
                "ejecutar.html",
                title="Consulta RUNT",
                message="No se puede ejecutar el proceso.",
                status="fuera_horario",
            )
        # Muestra página de “en ejecución”
        return render_template(
            "ejecutar.html",
            title="Consulta RUNT",
            message="Ejecutando proceso...",
            status="running",
        )
    try:
        web_client = WebClient(base_url=settings.RUNT_URL)
        wf = ProcesoConsultaWF(nocodb_client=nocodb, web_client=web_client)
        result = wf.ejecutar_lote()
        return render_template(
            "ejecutar.html",
            title="Consulta RUNT",
            message="Resultado del proceso:",
            status="ok",
            detail=result.get("mensaje"),
        )
    except Exception as e:
        logger.error(f"Error al ejecutar: {e}")
        return render_template(
            "ejecutar.html",
            title="Consulta RUNT",
            message="Ocurrió un error al ejecutar el proceso.",
            status="error",
            detail=str(e),
        ), 500


@bp.route("/pendientes", methods=["GET"])
def obtener_pendientes():
    """
    Devuelve la cantidad de registros 'Sin Procesar' en la tabla Insumo.
    Endpoint: GET /api/gestion/pendientes
    """
    try:
        tabla = settings.NOCO_INSUMO_TABLE
        filtro = "EstadoGestion,eq,Sin Procesar"
        registros = nocodb.list_records(tabla, where=filtro)
        cantidad = len(registros) if registros else 0

        if request.accept_mimetypes.accept_html:
            return render_template(
                "pendientes.html",
                title="Pendientes RUNT",
                message="Consulta de registros pendientes",
                status="ok",
                pendientes=cantidad,
                timestamp=datetime.now().strftime("%H:%M:%S"),
            )
        logger.info(f"Registros pendientes: {cantidad}")
        return jsonify({"pendientes": cantidad}), 200

    except Exception as e:
        logger.error(f"Error al consultar registros pendientes: {e}")
        return jsonify({"error": f"Error al consultar registros pendientes: {e}"}), 500