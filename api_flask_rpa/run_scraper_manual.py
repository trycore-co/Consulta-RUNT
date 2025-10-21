"""
Ejecución manual del scraping (login + consulta de placas + detalle)
sin depender del workflow ni NocoDB.
"""

from app.infrastructure.web_client import WebClient
from app.services.scraping_service import ScrapingService
from config import settings
import time


def main():
    # 1️⃣ Inicializa el cliente web (Chrome en modo visible)
    print("Iniciando WebClient (modo visible)...")
    web_client = WebClient(base_url=settings.RUNT_URL,headless=False)

    # 2️⃣ Inicializa el servicio de scraping
    scraper = ScrapingService(web_client)

    # 3️⃣ Login en el portal
    usuario = settings.RUNT_USERNAME
    contrasena = settings.RUNT_PASSWORD

    print(f"Iniciando sesión con el usuario: {usuario}")
    if not scraper.login(usuario, contrasena):
        print("Error en el login. Revisa credenciales o selectores.")
        return

    print("Login exitoso, continuando con consulta...")
    time.sleep(10)

    # 4️⃣ Consultar placas por documento
    tipo_doc = "Cedula de ciudadania"
    num_doc = "1032503041"

    print(f"Consultando placas del documento: {num_doc}")
    placas = scraper.consultar_por_propietario(tipo_doc, num_doc)

    if not placas:
        print("No se encontraron placas para el propietario.")
        return

    print(f"Placas encontradas: {placas}")
    """
    # 5️⃣ Extraer detalle del primer vehículo
    placa = placas[0]
    print(f"Extrayendo detalle de la placa: {placa}")
    detalle = scraper.abrir_ficha_y_extraer(placa)

    print("Detalle del vehículo obtenido:")
    for k, v in detalle.items():
        print(f"   {k}: {v}")
    """
    # 6️⃣ Toma un pantallazo final
    screenshot = scraper.tomar_screenshot_bytes()
    with open("captura_runt.png", "wb") as f:
        f.write(screenshot)
    print("Captura guardada como captura_runt.png")
    time.sleep(5)
    """
    # 7️⃣ Cerrar navegador
    time.sleep(2)
    web_client.close()
    print("Sesión finalizada correctamente.")
    """

if __name__ == "__main__":
    main()
