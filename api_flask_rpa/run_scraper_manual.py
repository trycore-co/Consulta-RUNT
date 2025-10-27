"""
Ejecución manual del scraping incluyendo integración con NocoDB
para pruebas completas del flujo.
"""

from app.infrastructure.web_client import WebClient
from app.infrastructure.nocodb_client import NocoDBClient
from app.services.scraping_service import ScrapingService
from app.repositories.nocodb_source_repository import NocoDbSourceRepository
from app.repositories.nocodb_target_repository import NocoDbTargetRepository
from app.services.capture_service import CaptureService
from app.services.pdf_service import PDFService
from config import settings
import time
import uuid
from datetime import datetime


def test_nocodb_connection():
    """Prueba la conexión con NocoDB"""
    print("🔄 Probando conexión con NocoDB...")
    try:
        nocodb_client = NocoDBClient(
            base_url=settings.NOCODB_URL,
            api_key=settings.NOCO_XC_TOKEN
        )
        source_repo = NocoDbSourceRepository(nocodb_client)
        params = source_repo.obtener_parametros()
        print("✅ Conexión con NocoDB exitosa!")
        print(f"   Parámetros cargados: {len(params)}")
        return nocodb_client
    except Exception as e:
        print(f"❌ Error conectando con NocoDB: {e}")
        return None


def main():
    # 1️⃣ Probar conexión con NocoDB
    nocodb_client = test_nocodb_connection()
    if not nocodb_client:
        print("⛔ No se puede continuar sin conexión a NocoDB")
        return

    # 2️⃣ Inicializar repositorios
    source_repo = NocoDbSourceRepository(nocodb_client)
    target_repo = NocoDbTargetRepository(nocodb_client)

    # 3️⃣ Obtener un registro pendiente
    print("\n🔄 Obteniendo registro pendiente...")
    pendientes = source_repo.obtener_pendientes(limit=1)
    if not pendientes:
        print("❌ No hay registros pendientes para procesar")
        return

    registro = pendientes[0]
    print(f"Cantidad de registros detectados: {len(pendientes)}")
    print(f"✅ Registro obtenido - ID: {registro.get('Id')}")

    # 4️⃣ Inicializar servicios
    web_client = WebClient(base_url=settings.RUNT_URL, headless=False)
    scraper = ScrapingService(web_client)
    capture = CaptureService()
    pdf = PDFService()
    fecha_hora_inicio = datetime.now().isoformat()
    try:
        # 5️⃣ Login en el portal
        print("\n Iniciando sesión en RUNT...")
        if not scraper.login(settings.RUNT_USERNAME, settings.RUNT_PASSWORD):
            print("Error en el login")
            return

        print("Login exitoso")
        time.sleep(2)

        # 6️⃣ Marcar registro en proceso
        source_repo.marcar_en_proceso(registro)

        # 7️⃣ Consultar placas
        tipo_doc = registro.get('TipoIdentificacion')
        num_doc = registro.get('NumIdentificacion')

        print(f"\n🔄 Consultando placas para {tipo_doc}: {num_doc}")
        placas, screenshot = scraper.consultar_por_propietario(tipo_doc, num_doc)

        if not placas:
            print(" No se encontraron placas")
            source_repo.marcar_fallido(registro, "No se encontraron placas asociadas")
            return

        print(f"Placas encontradas: {placas}")

        # 8️⃣ Procesar cada placa
        correlation_id = str(uuid.uuid4())
        image_paths = []

        # Guardar screenshot de lista de placas
        screenshot_path = capture.save_screenshot_bytes(
            screenshot,
            correlation_id,
            f"lista_{num_doc}"
        )
        image_paths.append(screenshot_path)

        for placa in placas:
            print(f"\n Procesando placa: {placa}")
            # Extraer detalles
            detalle = scraper.abrir_ficha_y_extraer(placa)
            ruta_pdf = None
            fecha_hora_fin = datetime.now().isoformat()
            # Guardar en NocoDB
            target_repo.upsert_vehicle_detail(registro, detalle, ruta_pdf, fecha_hora_inicio, fecha_hora_fin)

            # Capturar pantalla
            screenshot = scraper.tomar_screenshot_bytes()
            screenshot_path = capture.save_screenshot_bytes(
                screenshot,
                correlation_id,
                placa
            )
            image_paths.append(screenshot_path)

            print(f"Placa {placa} procesada")

        # 9️⃣ Generar PDF
        pdf_path = pdf.consolidate_images_to_pdf(image_paths, num_doc)
        print(f"\n PDF generado: {pdf_path}")
        # 🔟 Marcar como exitoso
        source_repo.marcar_exitoso(registro)
        target_repo.update_ruta_pdf_by_proceso(registro, pdf_path)
        print("\n Proceso completado exitosamente!")

    except Exception as e:
        print(f"\n Error durante el proceso: {e}")
        source_repo.marcar_fallido(registro, str(e))
    finally:
        web_client.close()
        print("\n Sesión finalizada")


if __name__ == "__main__":
    main()
