"""
ScrapingService: controla todo el flujo Selenium del portal RUNT PRO
usando WebClient y los selectores centralizados en resources/html_selectors.yaml
"""

from typing import List, Dict
from app.utils.logging_utils import get_logger
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
from app.utils.homologacion_utils import homologar_tipo_documento
from app.utils.string_utils import normalizar_nombre
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
        default_path = (
            Path(__file__).parent.parent / "resources" / "html_selectors.yaml"
        )
        selectors_path = selectors_path or default_path

        try:
            with open(selectors_path, "r", encoding="utf-8") as f:
                self.selectors = yaml.safe_load(f)
            logger.info(f"Selectores cargados correctamente desde {selectors_path}")
        except FileNotFoundError:
            logger.error(f"No se encontró el archivo YAML en {selectors_path}")
            self.selectors = {}
        except Exception as e:
            logger.error(f"Error cargando YAML de selectores: {e}")
            self.selectors = {}

    def login(self, username: str, password: str) -> bool:
        """
        Realiza el proceso de login en RUNT PRO.
        Retorna True si el inicio de sesión es exitoso.
        """
        s = self.selectors["login"]
        s_home = self.selectors["home"]
        try:
            logger.info("Abriendo página principal de RUNT PRO...")
            self.web_client.open("/")
            # Si el indicador de bienvenida ya está presente, se asume sesión activa.
            try:
                # Usamos el selector de bienvenida como indicador de sesión activa/bienvenida.
                welcome_indicator = self.web_client.find_by_selector(
                    s_home["mensaje_bienvenida"], timeout=5
                )
                if welcome_indicator and welcome_indicator.is_displayed():
                    logger.info(
                        "Sesión ya activa. Se encontró el indicador de página principal, saltando login."
                    )
                    return True
            except TimeoutException:
                logger.info(
                    "Indicador de página principal no encontrado, se procede con el flujo de login normal."
                )
            except Exception as e:
                # Manejar cualquier otra excepción y proceder con el login
                logger.warning(
                    f"Error al verificar estado de sesión (no fatal): {e}. Se procede con login."
                )

            self.web_client.click_selector(s["boton_continuar"])
            logger.info("Ingresando credenciales...")
            self.web_client.send_keys_selector(s["input_usuario"], username)
            self.web_client.send_keys_selector(s["input_contrasena"], password)
            self.web_client.click_selector(s["boton_iniciar_sesion"])
            logger.info("Iniciando sesión...")
            time.sleep(5)

            try:
                # Verificar y manejar popup de sesiones
                if self._handle_session_limit_popup():
                    logger.info("Popup de sesiones manejado correctamente")
                    time.sleep(3)  # Esperar a que cierre las sesiones anteriores
            except Exception as e:
                logger.error(f"Error manejando popup de sesiones: {e}")
                return False

            # Verificar que el login fue exitoso
            try:
                # selector tu página principal después del login
                s_home = self.selectors["home"]
                ok = self.web_client.wait_until_is_visible(
                    s_home["mensaje_bienvenida"], timeout=5
                )
                if ok:
                    cerrar_guia = self.web_client.wait_until_is_visible(
                        s_home["cerrar_navegacion_guiada"], timeout=5
                    )
                    if cerrar_guia:
                        self.web_client.click_selector(
                            s_home["cerrar_navegacion_guiada"]
                        )
                    logger.info("Inicio de sesión exitoso.")
                    return True
            except TimeoutException:
                logger.error("No se encontró el indicador de sesión exitosa")
                return False

        except Exception as e:
            logger.error("Error durante el login: %s", e)
            return False

    def _handle_session_limit_popup(self) -> bool:
        """
        Detecta y maneja el popup de sesiones excedidas.
        Hace clic en 'Cerrar sesiones' para cerrar las sesiones anteriores.
        Retorna True si se detectó y manejó el popup, False si no apareció.
        """
        try:
            s_popup = self.selectors["popup_sesiones"]

            # Intentar detectar el popup (timeout corto porque puede no aparecer)
            try:
                # Buscar el mensaje característico del popup
                mensaje_sel = s_popup["mensaje"]
                popup_visible = self.web_client.wait_until_is_visible(mensaje_sel, timeout=5)
                if popup_visible:
                    popup = self.web_client.find_by_selector(mensaje_sel, timeout=5)

                    if popup is not None and popup.is_displayed():
                        logger.warning("Detectado popup de sesiones excedidas")
                        # Hacer clic en "Cerrar sesiones" para cerrar las sesiones anteriores
                        try:
                            btn_cerrar_sel = s_popup["boton_cerrar_sesiones"]
                            self.web_client.click_selector(btn_cerrar_sel, timeout=5)
                            logger.info(
                                "Clic en 'Cerrar sesiones' - cerrando sesiones anteriores"
                            )
                            time.sleep(5)  # Esperar a que se cierren las sesiones
                            return True

                        except Exception as e:
                            logger.error(f"No se pudo hacer clic en 'Cerrar sesiones': {e}")

                            # Intentar con "Aceptar" como alternativa
                            try:
                                btn_aceptar_sel = s_popup["boton_aceptar"]
                                self.web_client.click_selector(btn_aceptar_sel, timeout=5)
                                logger.info("Clic en 'Aceptar' como alternativa")
                                time.sleep(5)
                                return True
                            except Exception as e2:
                                logger.error(f"No se pudo cerrar el popup: {e2}")
                                return False

            except TimeoutException:
                # No apareció el popup, continuar normal
                logger.debug("No se detectó popup de sesiones")
                return False
            except Exception as e:
                # Cualquier otro error (elemento no encontrado, etc.)
                logger.debug(f"No se detectó popup de sesiones: {e}")
                return False

        except Exception as e:
            logger.error(f"Error manejando popup de sesiones: {e}")
            return False

    def _handle_error_ruta_popup(self) -> bool:
        """
        Detecta y maneja el popup de error de ruta/permisos.
        Retorna True si se detectó y manejó el popup, False si no apareció.
        """
        try:
            s_popup = self.selectors["popup_error_ruta"]

            # Intentar detectar el popup (timeout corto porque puede no aparecer)
            try:
                # Buscar el mensaje característico del popup
                mensaje_error_sel = s_popup["mensaje"]
                mensaje_sel = s_popup["mensaje_permisos"]
                popup = self.web_client.find_by_selector(
                    mensaje_error_sel, timeout=5
                ) or self.web_client.find_by_selector(mensaje_sel, timeout=5)

                if popup.is_displayed():
                    logger.warning("Detectado popup de error de ruta/permisos")

                    # Hacer clic en "Aceptar" para cerrar el popup
                    try:
                        btn_aceptar_sel = s_popup["boton_aceptar"]
                        self.web_client.click_selector(btn_aceptar_sel, timeout=5)
                        logger.info("Popup de error de ruta cerrado")
                        time.sleep(5)  # Esperar a que se cierre el popup
                        return True

                    except Exception as e:
                        logger.error(f"No se pudo cerrar popup de error de ruta: {e}")
                        return False

            except TimeoutException:
                # No apareció el popup, continuar normal
                logger.debug("No se detectó popup de error de ruta")
                return False
            except Exception as e:
                # Cualquier otro error (elemento no encontrado, etc.)
                logger.debug(f"No se detectó popup de error de ruta: {e}")
                return False

        except Exception as e:
            logger.error(f"Error manejando popup de error de ruta: {e}")
            return False

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

    def consultar_por_propietario(
        self, tipo_doc: str, numero_doc: str, nombre: str
    ):
        """
        Consulta las placas asociadas a un propietario en RUNT PRO.
        Primero intenta navegar por el menú.
        Si no esta el menú visible, navega a la url directamente.
        Retorna lista de placas encontradas.
        """
        s = self.selectors["consulta_propietario"]
        navegacion_exitosa = False

        # 1. Intentar navegar por el menú (Prioridad)
        if self._navegar_a_consulta_por_menu():
            navegacion_exitosa = True
        else:
            # 2. Si falla el menú, intentar navegar directo a la URL como alternativa
            logger.warning(
                "Fallo al navegar por el menú. Intentando acceso directo a la URL..."
            )
            self.web_client.open(s["url_consulta"])
            time.sleep(2)

            # 2.1. Verificar si apareció popup de error de ruta/permisos
            if self._handle_error_ruta_popup():
                logger.error(
                    "Popup de error de ruta detectado incluso con acceso directo. Abortando consulta."
                )
                """
                # Verificar que el login fue exitoso
                    try:
                        # selector tu página principal después del pop up
                        s_home = self.selectors["home"]
                        ok = self.web_client.find_by_selector(
                            s_home["menu_consultas"], timeout=5
                        )
                        if ok:
                            logger.info("Menú de consultas visible.")
                            return True
                    except TimeoutException:
                        logger.error("No se esta visible el menú de consultas")
                        return False
                """
                raise Exception(
                    "No se pudo acceder a la consulta por propietario ni por menú ni por URL"
                )
            else:
                logger.info("Acceso directo por URL exitoso.")
                navegacion_exitosa = True

        if not navegacion_exitosa:
            # Esto solo debería ocurrir si el menú falla y el acceso directo falla sin levantar pop-up
            raise Exception(
                "No se pudo acceder a la consulta por propietario: Fallo en navegación por menú y URL."
            )

        # 3. Ingresar tipo y número de documento
        try:
            tipo_doc = homologar_tipo_documento(tipo_doc)
            logger.info(f"Tipo de documento homologado: {tipo_doc}")
            tipo_elem = self.web_client.find_by_selector(s["select_tipo_documento"])
            tipo_elem.click()
            time.sleep(1)

            panel_selector = s["panel_opciones_tipo_doc"]
            if panel_selector:
                self.web_client.find_by_selector(panel_selector, timeout=10)

            opt_xpath = (
                f"//mat-option//span[contains(normalize-space(.), '{tipo_doc}')]"
            )
            logger.info(f"Buscando opción de tipo_doc con XPATH: {opt_xpath}")
            opcion = self.web_client.find_element(By.XPATH, opt_xpath)
            opcion.click()
            time.sleep(1.0)

            self.web_client.send_keys_selector(s["input_numero_documento"], numero_doc)
            self.web_client.click_selector(s["boton_consultar"])
            logger.info("Se dio clic en consultar")
        except Exception as e:
            logger.error("Error ingresando datos de propietario: %s", e)
            raise

        # Esperar el selector de placa
        selector_placa = s["selector_placa"]
        elemento_encontrado = False
        try:
            try:
                # 1. Intento de espera (timeout corto es más rápido si está visible de inmediato)
                self.web_client.wait_until_is_visible(selector_placa, timeout=5)
                elemento_encontrado = True
            except TimeoutException:
                # Si la espera falla, intentamos una búsqueda directa por más tiempo (opcional)
                try:
                    self.web_client.find_by_selector(selector_placa, timeout=3)
                    elemento_encontrado = True
                except Exception:
                    # El elemento realmente no está
                    pass

            logger.info(f"Selector de placas visible,{elemento_encontrado}")
            nombre_plataforma_element = self.web_client.find_by_selector(
                s["input_nombre_propietario"], timeout=3
            )
            # Extraer el nombre de la plataforma
            nombre_plataforma = (
                nombre_plataforma_element.text.strip()
                or nombre_plataforma_element.get_attribute("value")
                or ""
            ).strip()
            logger.info(
                f"Texto bruto: '{nombre_plataforma_element.text}' | value='{nombre_plataforma_element.get_attribute('value')}'"
            )

            # Normalizar AMBOS nombres para la comparación
            nombre_plataforma_normalizado = normalizar_nombre(nombre_plataforma)
            nombre_noco_normalizado = normalizar_nombre(nombre)

            logger.info(
                f"Comparando nombres: Plataforma='{nombre_plataforma_normalizado}' vs NocoDB='{nombre_noco_normalizado}'"
            )
            # VALIDACIÓN DE COINCIDENCIA
            if nombre_plataforma_normalizado != nombre_noco_normalizado:
                motivo = f"Nombre no coincide. Plataforma: '{nombre_plataforma}'. NocoDB: '{nombre}'."
                screenshot_fallo = self.tomar_screenshot_bytes()
                logger.warning(f"ID {numero_doc} - {motivo}")
                return (
                    [],
                    screenshot_fallo,
                )

            if not elemento_encontrado:
                s_consulta = self.selectors["consulta_propietario"]
                ok = self.web_client.wait_until_is_visible(
                    s_consulta["alerta_modal"], timeout=5
                )
                if ok:
                    png_bytes = self.tomar_screenshot_bytes()
                    self.web_client.click_selector(
                        s_consulta["alerta_boton_aceptar"], timeout=5
                    )
                    time.sleep(1)
                    return ([], png_bytes)
                else:
                    logger.error("No se encontró alerta modal tras consulta fallida.")
                    return []
            else:
                self.web_client.click_selector(s["selector_placa"], timeout=5)

        except TimeoutException:
            logger.error("No se encontró el selector de placas.")
            return []

        #  Se toma la captura de la lista de placas
        png_bytes = self.tomar_screenshot_bytes()

        # Obtener lista de placas
        try:
            elementos = self.web_client.find_all_by_selector(s["lista_placas"])
            placas = [
                el.text.strip()
                for el in elementos
                if el.text.strip() and el.text.upper() != "SELECCIONE"
            ]

            logger.info("Placas encontradas: %s", placas)
            return (placas, png_bytes)
        except Exception as e:
            logger.error("Error al extraer lista de placas: %s", e)
            return ([], png_bytes)

    def _navegar_a_consulta_por_menu(self) -> bool:
        """
        Navega a la página de consulta de automotores por propietario usando el menú.
        Retorna True si la navegación es exitosa, False si falla.
        """
        s_home = self.selectors["home"]
        try:
            logger.info("Intentando navegación por el menú...")
            # Abrir menú lateral
            self.web_client.click_selector(s_home["menu_consultas"], timeout=3)
            time.sleep(3)

            # Click en "Consulta información"
            self.web_client.click_selector(s_home["consultar_informacion"], timeout=3)
            time.sleep(3)

            # Click en "Consulta de automotores por propietario"
            self.web_client.click_selector(
                s_home["opcion_automotores_propietario"], timeout=3
            )
            time.sleep(3)

            logger.info("Navegación por menú exitosa.")
            return True

        except Exception as e:
            logger.warning(f"Error navegando por el menú: {e}")
            return False

    def abrir_ficha_y_extraer(self, placa: str):
        """
        Abre la ficha de detalle del vehículo y extrae todos los campos visibles.
        Retorna un diccionario con la información del vehículo.
        """
        s = self.selectors["consulta_propietario"]
        s_det = self.selectors["detalle_vehiculo"]
        s_panel = self.selectors["consulta_propietario"]["panel_lista_placas"]
        detalle = {"Placa": placa}

        try:
            logger.info(f"Abriendo ficha de placa: {placa}")
            # Clic en la placa dentro del panel de resultados
            xpath_placa = (
                f"{s_panel['value']}//mat-option[./span[contains(text(), '{placa}')]]"
            )
            el = self.web_client.find_element("xpath", xpath_placa)
            el.click()
            time.sleep(2)

            # Esperar contenedor de detalle
            contenedor = self.web_client.find_by_selector(
                s_det["contenedor_detalle"], timeout=5
            )
            bloques = self.web_client.find_all_by_selector(s_det["bloque_detalle"])

            formulario_consulta = self.web_client.find_by_selector(
                s["formulario_consulta"], timeout=5
            )
            self.web_client.driver.execute_script(
                "arguments[0].style.zoom = '20%';", formulario_consulta
            )
            time.sleep(1.0)

            datos_generales = self.web_client.find_by_selector(
                s["datos_generales"], timeout=5
            )
            self.web_client.driver.execute_script(
                "arguments[0].style.zoom = '20%';", datos_generales
            )
            time.sleep(1.0)

            footer = self.web_client.find_by_selector(s["footer"], timeout=5)
            self.web_client.driver.execute_script(
                "arguments[0].style.zoom = '20%';", footer
            )
            time.sleep(1.0)

            self.web_client.driver.execute_script(
                "arguments[0].style.zoom = '60%';", contenedor
            )
            time.sleep(1.0)
            # Asegura bajar hasta el final
            self.web_client.driver.execute_script(
                "arguments[0].scrollIntoView({block: 'center'});", contenedor
            )
            time.sleep(1.0)

            # Extraer pares clave-valor de los bloques de detalle
            png_bytes = self.tomar_screenshot_bytes()
            logger.info(f"Extrayendo datos de placa: {placa}")
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

            # PASO 2: RESTAURAR EL ZOOM AL 100% ANTES DE CONTINUAR
            logger.info("Restaurando zoom al 100% para el resto del flujo.")
            self.web_client.driver.execute_script(
                "arguments[0].style.zoom = '100%';", formulario_consulta
            )
            self.web_client.driver.execute_script(
                "arguments[0].style.zoom = '100%';", datos_generales
            )
            self.web_client.driver.execute_script(
                "arguments[0].style.zoom = '100%';", footer
            )
            self.web_client.driver.execute_script(
                "arguments[0].style.zoom = '100%';", contenedor
            )

            self.web_client.click_selector(s["selector_placa"], timeout=5)
            return (detalle, png_bytes)

        except Exception as e:
            logger.error(
                "Error al abrir ficha o extraer datos de placa %s: %s", placa, e
            )
            try:
                self.web_client.driver.execute_script("document.body.style.zoom = '100%';")
            except Exception:
                pass  # No pasa nada si el driver ya está roto o cerrado
            raise

    def volver_a_inicio(self):
        """
        Navega de vuelta a la página principal haciendo clic en el logo.
        Usa el índice [2] del XPath para asegurar el elemento correcto.
        """
        try:
            s_panel = self.selectors["consulta_propietario"]["panel_lista_placas"]
            visible = self.web_client.wait_until_is_visible(
                s_panel, timeout=5
            )
            if visible:
                self.web_client.click_selector(s_panel, timeout=5)
                time.sleep(1)

            s_home = self.selectors["home"]
            logo_xpath = (
                f"({s_home['logo']['value']})[2]"  # Selecciona el segundo elemento)
            )
            logger.info(f"Volviendo a inicio con XPath indexado: {logo_xpath}")

            # Usar find_element en lugar de click_selector para el XPath indexado
            self.web_client.find_element(By.XPATH, logo_xpath).click()
            time.sleep(1)
            return True
        except Exception as e:
            logger.warning(
                f"No se pudo hacer clic en el logo para volver a inicio: {e}"
            )
            return False

    def tomar_screenshot_bytes(self) -> bytes:
        """
        Devuelve una captura de pantalla actual en bytes PNG.
        """
        return self.web_client.screenshot_bytes()
