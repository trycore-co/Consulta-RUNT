"""
ScrapingService: controla todo el flujo Selenium del portal RUNT PRO
usando WebClient y los selectores centralizados en resources/html_selectors.yaml
"""
from typing import List, Dict
from app.utils.logging_utils import get_logger
from selenium.webdriver.common.by import By
from selenium.common.exceptions import TimeoutException
from app.utils.homologacion_utils import homologar_tipo_documento
import time
import yaml
from pathlib import Path

logger = get_logger("scraping_service")


class ScrapingService:
    """
    Service que usa WebClient para realizar:
    - login (delegado a WebClient)
    - consultar por propietario -> devuelve lista de placas
    - abrir ficha y extraer detalle -> devuelve dict con campos
    """

    def __init__(self, web_client, selectors_path: str = None):
        """
        Inicializa el servicio de scraping con el cliente web (Selenium)
        y carga los selectores desde el archivo YAML.
        """
        self.web_client = web_client
        selectors_path = (
            selectors_path
            or Path(__file__).parent.parent / "resources" / "html_selectors.yaml"
        )
        with open(selectors_path, "r", encoding="utf-8") as f:
            self.selectors = yaml.safe_load(f)
            logger.info("Selectores cargados correctamente desde %s", selectors_path)

    def login(self, username: str, password: str) -> bool:
        """
        Realiza el proceso de login en RUNT PRO.
        Retorna True si el inicio de sesión es exitoso.
        """
        s = self.selectors["login"]
        try:
            logger.info("Abriendo página principal de RUNT PRO...")
            self.web_client.open("/")
            self.web_client.click_selector(s["boton_continuar"])
            logger.info("Ingresando credenciales...")
            self.web_client.send_keys_selector(s["input_usuario"], username)
            self.web_client.send_keys_selector(s["input_contrasena"], password)
            self.web_client.click_selector(s["boton_iniciar_sesion"])

            # Espera que el botón desaparezca como indicador de login correcto
            try:
                self.web_client.wait_until_invisible(
                    s["boton_iniciar_sesion"]["by"],
                    s["boton_iniciar_sesion"]["value"],
                    timeout=20,
                )
                logger.info("Inicio de sesión exitoso.")
                return True
            except TimeoutException:
                logger.warning("No se detectó finalización del login.")
                return False
        except Exception as e:
            logger.error("Error durante el login: %s", e)
            return False

    def consultar_por_propietario2(self, tipo_documento: str, numero: str) -> List[str]:
        """
        1) Click en menú
        2) Seleccionar consulta de automotores por propietario
        3) Llenar tipo de documento y número
        4) Click buscar
        5) Leer lista de placas (retorna lista de strings)
        """
        # 1. ir al menu (si selector de menu existe)
        try:
            menu_sel = self.selectors["consulta"]["menu"]
            self.web_client.find_element(By.CSS_SELECTOR, menu_sel).click()
        except Exception:
            # puede que ya estés en la página; no fatal
            pass

        # 2. diligenciar tipo y número (los selectores dependen del html)
        input_sel = self.selectors["consulta"]["input_doc"]
        input_el = self.web_client.find_element(By.CSS_SELECTOR, input_sel)
        input_el.clear()
        input_el.send_keys(numero)

        # si hay un selector tipo_documento (select), manejarlo:
        tipo_sel = self.selectors["consulta"].get("tipo_documento")
        if tipo_sel:
            try:
                self.web_client.find_element(By.CSS_SELECTOR, tipo_sel).click()
                # seleccionar la opción adecuada (por texto igual al tipo_documento)
                opt_xpath = f"//mat-option//span[contains(., '{tipo_documento}')]"
                self.web_client.find_element(By.XPATH, opt_xpath).click()
            except Exception:
                # continuar si no existe selector de tipo
                pass

        # 3. click buscar
        boton_buscar = self.selectors["consulta"]["boton_buscar"]
        self.web_client.find_element(By.CSS_SELECTOR, boton_buscar).click()

        # 4. esperar resultados y parsear lista de placas
        time.sleep(1.0)
        placas = []
        try:
            placas_sel = self.selectors["consulta"]["lista_placas"]
            elems = self.web_client.find_elements(By.CSS_SELECTOR, placas_sel)
            for e in elems:
                txt = e.text.strip()
                if txt:
                    placas.append(txt)
        except Exception:
            # posible caso "no encontrado"
            # intentamos detectar modal SweetAlert2 con texto de "No hay resultados"
            try:
                # ejemplo SweetAlert2 class .swal2-popup
                swal_sel = self.selectors.get("sweetalert_selector", ".swal2-popup")
                el = self.web_client.find_element(By.CSS_SELECTOR, swal_sel, wait=False)
                # si hay modal, no hay placas
                return []
            except Exception:
                return []
        return placas

    def consultar_por_propietario(self, tipo_doc: str, numero_doc: str):
        """
        Consulta las placas asociadas a un propietario en RUNT PRO.
        Retorna lista de placas encontradas.
        """
        s = self.selectors["consulta_propietario"]
        logger.info("Navegando a la página de consulta por propietario...")
        self.web_client.open(s["url_consulta"])

        # Ingresar tipo y número de documento
        try:
            tipo_doc = homologar_tipo_documento(tipo_doc)
            logger.info(f"Tipo de documento homologado: {tipo_doc}")
            tipo_elem = self.web_client.find_by_selector(s["select_tipo_documento"])
            tipo_elem.click()
            time.sleep(1)
            
            self.web_client.send_keys_selector(s["input_numero_documento"], numero_doc)
            self.web_client.click_selector(s["boton_consultar"])
        except Exception as e:
            logger.error("Error ingresando datos de propietario: %s", e)
            raise

        # Esperar el selector de placa
        try:
            self.web_client.find_by_selector(s["selector_placa"], timeout=30).click()
        except TimeoutException:
            logger.error("No se encontró el selector de placas.")
            return []

        # Obtener lista de placas
        try:
            elementos = self.web_client.find_all_by_selector(s["lista_placas"])
            placas = [
                el.text.strip()
                for el in elementos
                if el.text.strip() and el.text.upper() != "SELECCIONE"
            ]
            logger.info("Placas encontradas: %s", placas)
            return placas
        except Exception as e:
            logger.error("Error al extraer lista de placas: %s", e)
            return []

    def abrir_ficha_y_extraer2(self, placa: str) -> Dict[str, str]:
        """
        Abre el detalle de la placa y extrae los campos clave (27 campos).
        Debes hacer click sobre la placa en la lista y extraer por selectores.
        """
        # localizar elemento de la placa en la lista (puede necesitar un xpath con el texto)
        try:
            placa_xpath = f"//td[contains(normalize-space(.), '{placa}')]"
            self.web_client.find_element(By.XPATH, placa_xpath).click()
        except Exception:
            # fallback: intentar abrir primer resultado
            try:
                first = self.web_client.find_elements(
                    By.CSS_SELECTOR, self.selectors["consulta"]["lista_placas"]
                )[0]
                first.click()
            except Exception:
                pass

        time.sleep(0.8)  # esperar carga detalle

        # Ahora extraer campos (ejemplo con selectors mapeados en selectors['detalle'])
        detalle = {}
        detalle_selectors = self.selectors.get("detalle", {})
        for key, sel in detalle_selectors.items():
            try:
                el = self.web_client.find_element(By.CSS_SELECTOR, sel)
                detalle[key] = el.text.strip()
            except Exception:
                detalle[key] = None

        # Asegurar que placa esté en el dict
        detalle.setdefault("Placa", placa)
        return detalle

    def abrir_ficha_y_extraer(self, placa: str) -> dict:
        """
        Abre la ficha de detalle del vehículo y extrae todos los campos visibles.
        Retorna un diccionario con la información del vehículo.
        """
        s_det = self.selectors["detalle_vehiculo"]
        s_panel = self.selectors["consulta_propietario"]["panel_lista_placas"]
        detalle = {"Placa": placa}

        try:
            # Clic en la placa dentro del panel de resultados
            xpath_placa = (
                f"{s_panel['value']}//mat-option[./span[contains(text(), '{placa}')]]"
            )
            el = self.web_client.find("xpath", xpath_placa)
            el.click()
            time.sleep(2)

            # Esperar contenedor de detalle
            self.web_client.find_by_selector(s_det["contenedor_detalle"], timeout=30)
            bloques = self.web_client.find_all_by_selector(s_det["bloque_detalle"])

            for block in bloques:
                labels = block.find_elements(
                    By.TAG_NAME, s_det["etiquetas_datos"]["value"]
                )
                if len(labels) >= 2:
                    key = labels[0].text.replace(":", "").strip()
                    val = labels[1].text.strip()
                    if key and val:
                        detalle[key] = val

            logger.info("Campos extraídos: %d", len(detalle))
            return detalle

        except Exception as e:
            logger.error(
                "Error al abrir ficha o extraer datos de placa %s: %s", placa, e
            )
            raise

    def tomar_screenshot_bytes(self) -> bytes:
        """
        Devuelve una captura de pantalla actual en bytes PNG.
        """
        return self.web_client.screenshot_bytes()
