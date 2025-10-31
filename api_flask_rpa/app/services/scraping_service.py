"""
ScrapingService: controla todo el flujo Selenium del portal RUNT PRO
usando WebClient y los selectores centralizados en resources/html_selectors.yaml
"""

from app.utils.logging_utils import get_logger
from selenium.webdriver.common.by import By
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from app.utils.homologacion_utils import homologar_tipo_documento
from app.utils.string_utils import normalizar_nombre
import time
import yaml
from pathlib import Path

logger = get_logger("scraping_service")
BACKDROP_SEL = ".cdk-overlay-backdrop.cdk-overlay-backdrop-showing"
PANEL_OPEN_SEL = ".cdk-overlay-pane .mat-select-panel"


class ScrapingService:
    """
    Service que usa WebClient para realizar:
    - login (delegado a WebClient)
    - consultar por propietario -> devuelve lista de placas
    - abrir ficha y extraer detalle -> devuelve dict con campos
    """

    def __init__(
        self,
        web_client,
        selectors_path: str = None,
        timeout_bajo: int = 5,
        timeout_medio: int = 10,
        timeout_largo: int = 15,
        url_runt: str = "",
        usuario_runt: str = "", 
        password_runt: str = "",
    ):
        """
        Inicializa el servicio de scraping con el cliente web (Selenium)
        y carga los selectores desde el archivo YAML.
        """
        self.web_client = web_client
        default_path = (
            Path(__file__).parent.parent / "resources" / "html_selectors.yaml"
        )
        selectors_path = selectors_path or default_path
        self.timeout_bajo = timeout_bajo
        self.timeout_medio = timeout_medio
        self.timeout_largo = timeout_largo
        self.url_runt = url_runt
        self.usuario_runt = usuario_runt
        self.password_runt = password_runt

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

    def login(self) -> bool:
        """
        Realiza el proceso de login en RUNT PRO.
        Retorna True si el inicio de sesión es exitoso.
        """
        if not self.usuario_runt or not self.password_runt:
            logger.error("Credenciales del RUNT no disponibles para el login.")
            return False

        s = self.selectors["login"]
        s_home = self.selectors["home"]
        try:
            logger.info("Abriendo página principal de RUNT PRO...")
            self.web_client.open("/")
            # Si el indicador de bienvenida ya está presente, se asume sesión activa.
            try:
                welcome_indicator = self.web_client.find_by_selector(
                    s_home["mensaje_bienvenida"], timeout=self.timeout_bajo
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
                logger.warning(
                    f"Error al verificar estado de sesión (no fatal): {e}. Se procede con login."
                )

            self.web_client.click_selector(s["boton_continuar"])
            logger.info("Ingresando credenciales...")
            self.web_client.send_keys_selector(s["input_usuario"], self.usuario_runt)
            self.web_client.send_keys_selector(s["input_contrasena"], self.password_runt)
            self.web_client.click_selector(s["boton_iniciar_sesion"])
            logger.info("Iniciando sesión...")
            time.sleep(self.timeout_bajo)

            try:
                if self._handle_session_limit_popup():
                    logger.info("Popup de sesiones manejado correctamente")
                    time.sleep(self.timeout_bajo)
            except Exception as e:
                logger.error(f"Error manejando popup de sesiones: {e}")
                return False

            # Verificar que el login fue exitoso
            try:
                s_home = self.selectors["home"]
                ok = self.web_client.wait_until_is_visible(
                    s_home["mensaje_bienvenida"], timeout=self.timeout_bajo
                )
                if ok:
                    cerrar_guia = self.web_client.wait_until_is_visible(
                        s_home["cerrar_navegacion_guiada"], timeout=self.timeout_bajo
                    )
                    if cerrar_guia:
                        self.web_client.click_selector(
                            s_home["cerrar_navegacion_guiada"]
                        )
                        # Asegura limpiar overlays del tour
                        try:
                            self._wait_backdrops_clear(timeout=self.timeout_bajo)
                        except Exception:
                            pass
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
        """
        try:
            s_popup = self.selectors["popup_sesiones"]
            try:
                mensaje_sel = s_popup["mensaje"]
                popup_visible = self.web_client.wait_until_is_visible(
                    mensaje_sel, timeout=self.timeout_bajo
                )
                if popup_visible:
                    popup = self.web_client.find_by_selector(
                        mensaje_sel, timeout=self.timeout_bajo
                    )
                    if popup is not None and popup.is_displayed():
                        logger.warning("Detectado popup de sesiones excedidas")
                        try:
                            btn_cerrar_sel = s_popup["boton_cerrar_sesiones"]
                            self.web_client.click_selector(
                                btn_cerrar_sel, timeout=self.timeout_bajo
                            )
                            logger.info("Clic en 'Cerrar sesiones'")
                            time.sleep(self.timeout_bajo)
                            return True
                        except Exception as e:
                            logger.error(f"No se pudo hacer clic en 'Cerrar sesiones': {e}")
                            # Alternativa: Aceptar
                            try:
                                btn_aceptar_sel = s_popup["boton_aceptar"]
                                self.web_client.click_selector(
                                    btn_aceptar_sel, timeout=self.timeout_bajo
                                )
                                logger.info("Clic en 'Aceptar' como alternativa")
                                time.sleep(self.timeout_bajo)
                                return True
                            except Exception as e2:
                                logger.error(f"No se pudo cerrar el popup: {e2}")
                                return False
            except TimeoutException:
                logger.debug("No se detectó popup de sesiones")
                return False
            except Exception as e:
                logger.debug(f"No se detectó popup de sesiones: {e}")
                return False
        except Exception as e:
            logger.error(f"Error manejando popup de sesiones: {e}")
            return False

    def _handle_error_ruta_popup(self) -> bool:
        """
        Detecta y maneja el popup de error de ruta/permisos.
        """
        try:
            s_popup = self.selectors["popup_error_ruta"]
            try:
                mensaje_error_sel = s_popup["mensaje"]
                mensaje_sel = s_popup["mensaje_permisos"]
                popup = self.web_client.find_by_selector(
                    mensaje_error_sel, timeout=self.timeout_bajo
                ) or self.web_client.find_by_selector(
                    mensaje_sel, timeout=self.timeout_bajo
                )

                if popup and popup.is_displayed():
                    logger.warning("Detectado popup de error de ruta/permisos")
                    try:
                        btn_aceptar_sel = s_popup["boton_aceptar"]
                        self.web_client.click_selector(
                            btn_aceptar_sel, timeout=self.timeout_bajo
                        )
                        logger.info("Popup de error de ruta cerrado")
                        time.sleep(self.timeout_bajo)
                        return True
                    except Exception as e:
                        logger.error(f"No se pudo cerrar popup de error de ruta: {e}")
                        return False
            except TimeoutException:
                logger.debug("No se detectó popup de error de ruta")
                return False
            except Exception as e:
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
        time.sleep(self.timeout_bajo)
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
                return ([], b"")
            except Exception:
                return ([], b"")
        return placas

    def consultar_por_propietario(self, tipo_doc: str, numero_doc: str, nombre: str):
        """
        Consulta las placas asociadas a un propietario en RUNT PRO.
        Primero intenta navegar por el menú.
        Si no está el menú visible, navega a la url directamente.
        Retorna (placas, screenshot_bytes).
        """
        s = self.selectors["consulta_propietario"]
        navegacion_exitosa = False

        # 1. Intentar navegar por el menú (Prioridad)
        if self._navegar_a_consulta_por_menu():
            navegacion_exitosa = True
        else:
            # 2. Acceso directo a URL si falla el menú
            logger.warning("Fallo al navegar por el menú. Intentando acceso directo a la URL...")
            self.web_client.open(s["url_consulta"])
            time.sleep(self.timeout_bajo)

            # 2.1. Manejo de error de ruta/permisos
            if self._handle_error_ruta_popup():
                logger.error("Popup de error de ruta detectado incluso con acceso directo. Abortando consulta.")
                raise Exception("No se pudo acceder a la consulta por propietario ni por menú ni por URL")
                logger.error(
                    "Popup de error de ruta detectado incluso con acceso directo. Abortando consulta."
                )
                raise Exception(
                    "No se pudo acceder a la consulta por propietario ni por menú ni por URL"
                )
            else:
                logger.info("Acceso directo por URL exitoso.")
                navegacion_exitosa = True

        if not navegacion_exitosa:
            raise Exception("No se pudo acceder a la consulta por propietario: Fallo en navegación por menú y URL.")
            raise Exception(
                "No se pudo acceder a la consulta por propietario: Fallo en navegación por menú y URL."
            )

        # 3. Ingresar tipo y número de documento (con manejo de overlay)
        try:
            # Homologar valor visible
            tipo_doc = homologar_tipo_documento(tipo_doc)
            logger.info(f"Tipo de documento homologado: {tipo_doc}")

            # Asegura que no haya overlays activos previos
            try:
                self._wait_backdrops_clear(timeout=self.timeout_medio)
            except Exception:
                pass

            # Abrir el mat-select
            tipo_elem = self.web_client.find_by_selector(s["select_tipo_documento"], timeout=self.timeout_medio)
            try:
                tipo_elem.click()
            except Exception as e:
                logger.warning(f"Click normal en mat-select falló ({e}), usando JS click.")
                self._safe_js_click(tipo_elem)

            # Esperar panel abierto
            self._wait_panel_open(timeout=self.timeout_medio)

            # Seleccionar opción por texto
            opt_xpath = f"//mat-option//span[contains(normalize-space(.), '{tipo_doc}')]"
            logger.info(f"Buscando opción de tipo_doc con XPATH: {opt_xpath}")
            opcion = WebDriverWait(self.web_client.driver, self.timeout_medio).until(
                EC.element_to_be_clickable((By.XPATH, opt_xpath))
            )
            try:
                opcion.click()
            except Exception as e:
                logger.warning(f"Click normal en opción falló ({e}), usando JS click.")
                self._safe_js_click(opcion)

            # Esperar cierre de panel y desaparición de backdrop
            self._wait_panel_closed(timeout=self.timeout_medio)
            try:
                self._wait_backdrops_clear(timeout=self.timeout_bajo)
            except Exception:
                pass

            # Número de documento + Consultar
            self.web_client.send_keys_selector(s["input_numero_documento"], numero_doc)
            self.web_client.click_selector(s["boton_consultar"])
            logger.info("Se dio clic en consultar")
        except Exception as e:
            logger.error("Error ingresando datos de propietario: %s", e)
            raise

        # 4. Validar nombre mostrado (si corresponde)
        selector_placa = s["selector_placa"]
        nombre_encontrado = False
        # 4. Esperar respuesta del servidor antes de verificar elementos
        time.sleep(self.timeout_medio)  # Dar más tiempo para la respuesta
        
        # 5. PRIMERO verificar si aparece el popup de "no tiene placas"
        popup_detectado = False
        try:
            alerta_visible = self.web_client.wait_until_is_visible(
                s["alerta_modal"], timeout=self.timeout_bajo
            )
            if alerta_visible:
                popup_detectado = True
                logger.warning(f"ID {numero_doc} - Popup de alerta detectado (sin placas asociadas)")
                png_bytes = self.tomar_screenshot_bytes()
                
                try:
                    self.web_client.click_selector(
                        s["alerta_boton_aceptar"], timeout=self.timeout_bajo
                    )
                    time.sleep(self.timeout_bajo)
                    logger.info("Popup cerrado exitosamente")
                except Exception as e:
                    logger.error(f"Error al cerrar popup: {e}")
                
                return ([], png_bytes)
        except TimeoutException:
            # No hay popup de alerta, continuar con el flujo normal
            logger.info("No se detectó popup de alerta, continuando con validación de nombre")
        except Exception as e:
            logger.warning(f"Error al verificar popup de alerta: {e}")
        
        # Si se detectó y cerró el popup, no continuar
        if popup_detectado:
            return ([], b"")

        # 6. Validar que el nombre del propietario coincida
        try:
            # Intentar encontrar el input de nombre con múltiples estrategias
            nombre_plataforma_element = None
            nombre_encontrado = False
            
            # Estrategia 1: Wait until visible
            try:
                self.web_client.wait_until_is_visible(
                    s["input_nombre_propietario"], timeout=self.timeout_bajo
                )
                nombre_plataforma_element = self.web_client.find_by_selector(
                    s["input_nombre_propietario"], timeout=self.timeout_bajo
                )
                nombre_encontrado = True
            except TimeoutException:
                logger.warning("Timeout esperando visibilidad del input de nombre")
            except Exception as e:
                logger.warning(f"Error en wait_until_is_visible: {e}")
            
            # Estrategia 2: Búsqueda directa si la primera falló
            if not nombre_encontrado:
                try:
                    self.web_client.find_by_selector(
                        s["input_nombre_propietario"], timeout=self.timeout_bajo
                    )
                    nombre_encontrado = True
                except Exception:
                    pass

            if nombre_encontrado:
                nombre_plataforma_element = self.web_client.find_by_selector(
                    s["input_nombre_propietario"], timeout=self.timeout_bajo
                )
                nombre_plataforma = (
                    nombre_plataforma_element.text.strip()
                    or nombre_plataforma_element.get_attribute("value")
                    or ""
                ).strip()

                nombre_plataforma_normalizado = normalizar_nombre(nombre_plataforma)
                nombre_noco_normalizado = normalizar_nombre(nombre)

                logger.info(
                    f"Comparando nombres: Plataforma='{nombre_plataforma_normalizado}' vs NocoDB='{nombre_noco_normalizado}'"
                )
                if nombre_plataforma_normalizado != nombre_noco_normalizado:
                    motivo = f"Nombre no coincide. Plataforma: '{nombre_plataforma}'. NocoDB: '{nombre}'."
                    screenshot_fallo = self.tomar_screenshot_bytes()
                    time.sleep(self.timeout_bajo)
                    logger.warning(f"ID {numero_doc} - {motivo}")
                    return ([], screenshot_fallo)
                else:
                    logger.info("Nombre coincide")
        except TimeoutException:
            logger.error("No se encontró el input de nombre.")
            screenshot_fallo = self.tomar_screenshot_bytes()
            time.sleep(self.timeout_bajo)
            return ([], screenshot_fallo)

        # 5. Esperar selector de placa o alerta modal
        elemento_encontrado = False
        try:
            try:
                self.web_client.wait_until_is_visible(selector_placa, timeout=self.timeout_bajo)
                except Exception as e:
                    logger.warning(f"Error en find_by_selector: {e}")
            
            if not nombre_encontrado or nombre_plataforma_element is None:
                logger.error(f"ID {numero_doc} - No se encontró el input de nombre del propietario después de múltiples intentos")
                screenshot_fallo = self.tomar_screenshot_bytes()
                time.sleep(self.timeout_bajo)
                return ([], screenshot_fallo)

            # Extraer el nombre con manejo seguro de atributos
            nombre_plataforma = ""
            try:
                # Intentar obtener el texto del elemento
                texto = nombre_plataforma_element.text
                if texto:
                    nombre_plataforma = texto.strip()
            except Exception as e:
                logger.warning(f"Error obteniendo .text: {e}")
            
            # Si no hay texto, intentar con el atributo value
            if not nombre_plataforma:
                try:
                    value = nombre_plataforma_element.get_attribute("value")
                    if value:
                        nombre_plataforma = value.strip()
                except Exception as e:
                    logger.warning(f"Error obteniendo attribute 'value': {e}")
            
            # Si aún no hay nombre, intentar con innerText
            if not nombre_plataforma:
                try:
                    inner = nombre_plataforma_element.get_attribute("innerText")
                    if inner:
                        nombre_plataforma = inner.strip()
                except Exception as e:
                    logger.warning(f"Error obteniendo attribute 'innerText': {e}")
            
            if not nombre_plataforma:
                logger.error(f"ID {numero_doc} - No se pudo extraer el nombre del elemento")
                screenshot_fallo = self.tomar_screenshot_bytes()
                return ([], screenshot_fallo)
            
            logger.info(f"Nombre extraído de la plataforma: '{nombre_plataforma}'")

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
                time.sleep(self.timeout_bajo)
                logger.warning(f"ID {numero_doc} - {motivo}")
                return ([], screenshot_fallo)
            else:
                logger.info("Nombre coincide correctamente")
                
        except Exception as e:
            logger.error(f"Error crítico al validar nombre del propietario: {type(e).__name__} - {str(e)}")
            try:
                screenshot_fallo = self.tomar_screenshot_bytes()
            except:
                screenshot_fallo = b""
            time.sleep(self.timeout_bajo)
            return ([], screenshot_fallo)

        # 7. Verificar y hacer clic en el selector de placas
        selector_placa = s["selector_placa"]
        elemento_encontrado = False
        
        try:
            try:
                self.web_client.wait_until_is_visible(
                    selector_placa, timeout=self.timeout_bajo
                )
                elemento_encontrado = True
            except TimeoutException:
                try:
                    self.web_client.find_by_selector(selector_placa, timeout=self.timeout_bajo)
                    elemento_encontrado = True
                except Exception:
                    pass

            logger.info(f"Selector de placas visible, {elemento_encontrado}")
            if not elemento_encontrado:
                s_consulta = self.selectors["consulta_propietario"]
                ok = self.web_client.wait_until_is_visible(
                    s_consulta["alerta_modal"], timeout=self.timeout_bajo
                )
                if ok:
                    png_bytes = self.tomar_screenshot_bytes()
                    self.web_client.click_selector(
                        s_consulta["alerta_boton_aceptar"], timeout=self.timeout_bajo
                    )
                    time.sleep(self.timeout_bajo)
                    return ([], png_bytes)
                else:
                    logger.error("No se encontró alerta modal tras consulta fallida.")
            else:
                # Clic en el selector de placa (proteger con anti-overlay)
                try:
                    self._wait_backdrops_clear(timeout=self.timeout_medio)
                except Exception:
                    pass
                try:
                    self.web_client.click_selector(s["selector_placa"], timeout=self.timeout_bajo)
                except Exception:
                    el = self.web_client.find_by_selector(s["selector_placa"], timeout=self.timeout_bajo)
                    self._safe_js_click(el)

        except TimeoutException:
            logger.error("No se encontró el selector de placas.")
            return ([], b"")

        # 6. Screenshot y listado de placas
        png_bytes = self.tomar_screenshot_bytes()
        time.sleep(self.timeout_bajo)

            logger.info(f"Selector de placas visible: {elemento_encontrado}")
            
            if not elemento_encontrado:
                logger.error(f"ID {numero_doc} - No se encontró el selector de placas")
                png_bytes = self.tomar_screenshot_bytes()
                time.sleep(self.timeout_bajo)
                return ([], png_bytes)
            
            # Hacer clic en el selector para desplegar las placas
            self.web_client.click_selector(
                s["selector_placa"], timeout=self.timeout_bajo
            )
            time.sleep(self.timeout_bajo)
            
        except Exception as e:
            logger.error(f"Error al interactuar con selector de placas: {e}")
            png_bytes = self.tomar_screenshot_bytes()
            return ([], png_bytes)

        # 8. Tomar captura de la lista de placas
        png_bytes = self.tomar_screenshot_bytes()
        time.sleep(self.timeout_bajo)

        # 9. Obtener lista de placas
        try:
            elementos = self.web_client.find_all_by_selector(s["lista_placas"])
            placas = [
                el.text.strip()
                for el in elementos
                if el.text.strip() and el.text.upper() != "SELECCIONE"
            ]
            logger.info("Placas encontradas: %s", placas)

            logger.info(f"ID {numero_doc} - Placas encontradas: {placas}")
            return (placas, png_bytes)
            
        except Exception as e:
            logger.error(f"Error al extraer lista de placas: {e}")
            return ([], png_bytes)

    def _navegar_a_consulta_por_menu(self) -> bool:
        """
        Navega a la página de consulta de automotores por propietario usando el menú.
        """
        s_home = self.selectors["home"]
        try:
            logger.info("Intentando navegación por el menú...")

            # Abrir menú lateral
            try:
                self._wait_backdrops_clear(timeout=self.timeout_medio)
            except Exception:
                pass
            el = self.web_client.find_by_selector(s_home["menu_consultas"], timeout=self.timeout_bajo)
            try:
                el.click()
            except Exception:
                self._safe_js_click(el)
            time.sleep(self.timeout_bajo)

            # Click en "Consulta información"
            try:
                self._wait_backdrops_clear(timeout=self.timeout_medio)
            except Exception:
                pass
            el = self.web_client.find_by_selector(s_home["consultar_informacion"], timeout=self.timeout_bajo)
            try:
                el.click()
            except Exception:
                self._safe_js_click(el)
            time.sleep(self.timeout_bajo)

            # Click en "Consulta de automotores por propietario"
            try:
                self._wait_backdrops_clear(timeout=self.timeout_medio)
            except Exception:
                pass
            el = self.web_client.find_by_selector(s_home["opcion_automotores_propietario"], timeout=self.timeout_bajo)
            try:
                el.click()
            except Exception:
                self._safe_js_click(el)
            time.sleep(self.timeout_bajo)

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
            xpath_placa = f"{s_panel['value']}//mat-option[./span[contains(text(), '{placa}')]]"
            el = self.web_client.find_element("xpath", xpath_placa)
            try:
                el.click()
            except Exception:
                self._safe_js_click(el)
            time.sleep(self.timeout_bajo)

            # Esperar contenedor de detalle
            contenedor = self.web_client.find_by_selector(
                s_det["contenedor_detalle"], timeout=self.timeout_bajo
            )
            bloques = self.web_client.find_all_by_selector(s_det["bloque_detalle"])

            formulario_consulta = self.web_client.find_by_selector(
                s["formulario_consulta"], timeout=self.timeout_bajo
            )
            self.web_client.driver.execute_script("arguments[0].style.zoom = '20%';", formulario_consulta)
            time.sleep(self.timeout_bajo)

            datos_generales = self.web_client.find_by_selector(
                s["datos_generales"], timeout=self.timeout_bajo
            )
            self.web_client.driver.execute_script("arguments[0].style.zoom = '20%';", datos_generales)
            time.sleep(1.0)

            footer = self.web_client.find_by_selector(s["footer"], timeout=self.timeout_bajo)
            self.web_client.driver.execute_script("arguments[0].style.zoom = '20%';", footer)
            time.sleep(1.0)

            self.web_client.driver.execute_script("arguments[0].style.zoom = '60%';", contenedor)
            time.sleep(1.0)
            self.web_client.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", contenedor)
            time.sleep(1.0)

            # Extraer pares clave-valor
            png_bytes = self.tomar_screenshot_bytes()
            logger.info(f"Extrayendo datos de placa: {placa}")
            for block in bloques:
                labels = block.find_elements(By.TAG_NAME, s_det["etiquetas_datos"]["value"])
                if len(labels) >= 2:
                    key = labels[0].text.replace(":", "").strip()
                    val = labels[1].text.strip()
                    if key and val:
                        detalle[key] = val

            logger.info("Campos extraídos: %d", len(detalle))

            # Restaurar zoom al 100%
            logger.info("Restaurando zoom al 100% para el resto del flujo.")
            self.web_client.driver.execute_script("arguments[0].style.zoom = '100%';", formulario_consulta)
            self.web_client.driver.execute_script("arguments[0].style.zoom = '100%';", datos_generales)
            self.web_client.driver.execute_script("arguments[0].style.zoom = '100%';", footer)
            self.web_client.driver.execute_script("arguments[0].style.zoom = '100%';", contenedor)

            # Reabrir selector de placa (si procede)
            try:
                self._wait_backdrops_clear(timeout=self.timeout_medio)
            except Exception:
                pass
            try:
                self.web_client.click_selector(s["selector_placa"], timeout=self.timeout_bajo)
            except Exception:
                el = self.web_client.find_by_selector(s["selector_placa"], timeout=self.timeout_bajo)
                self._safe_js_click(el)

            return (detalle, png_bytes)

        except Exception as e:
            logger.error("Error al abrir ficha o extraer datos de placa %s: %s", placa, e)
            try:
                self.web_client.driver.execute_script("document.body.style.zoom = '100%';")
            except Exception:
                pass
            raise

    def volver_a_inicio(self):
        """
        Navega de vuelta a la página principal haciendo clic en el logo.
        Usa el índice [2] del XPath para asegurar el elemento correcto.
        """
        try:
            s_panel = self.selectors["consulta_propietario"]["panel_lista_placas"]
            visible = self.web_client.wait_until_is_visible(s_panel, timeout=self.timeout_bajo)
            if visible:
                try:
                    self.web_client.click_selector(s_panel, timeout=self.timeout_bajo)
                except Exception:
                    el = self.web_client.find_by_selector(s_panel, timeout=self.timeout_bajo)
                    self._safe_js_click(el)
                time.sleep(self.timeout_bajo)

            s_home = self.selectors["home"]
            logo_xpath = f"({s_home['logo']['value']})[2]"  # Selecciona el segundo elemento
            logger.info(f"Volviendo a inicio con XPath indexado: {logo_xpath}")

            self.web_client.find_element(By.XPATH, logo_xpath).click()
            time.sleep(self.timeout_bajo)
            return True
        except Exception as e:
            logger.warning(f"No se pudo hacer clic en el logo para volver a inicio: {e}")
            return False

    def tomar_screenshot_bytes(self) -> bytes:
        """Devuelve una captura de pantalla actual en bytes PNG."""
        return self.web_client.screenshot_bytes()

    # ===== Helpers anti-overlay =====
    def _wait_backdrops_clear(self, timeout=None):
        """Espera a que no haya backdrops activos (overlays de Angular Material)."""
        t = timeout or self.timeout_medio
        WebDriverWait(self.web_client.driver, t).until(
            EC.invisibility_of_element_located((By.CSS_SELECTOR, BACKDROP_SEL))
        )

    def _wait_panel_open(self, timeout=None):
        """Espera a que el panel del mat-select esté visible (abierto)."""
        t = timeout or self.timeout_medio
        WebDriverWait(self.web_client.driver, t).until(
            EC.visibility_of_element_located((By.CSS_SELECTOR, PANEL_OPEN_SEL))
        )

    def _wait_panel_closed(self, timeout=None):
        """Espera a que el panel del mat-select se cierre (desaparezca)."""
        t = timeout or self.timeout_medio
        WebDriverWait(self.web_client.driver, t).until(
            EC.invisibility_of_element_located((By.CSS_SELECTOR, PANEL_OPEN_SEL))
        )

    def _safe_js_click(self, element):
        """Click via JS, útil si hay micro-animaciones o layouts inestables."""
        self.web_client.driver.execute_script(
            "arguments[0].scrollIntoView({block:'center'});", element
        )
        time.sleep(0.15)
        self.web_client.driver.execute_script("arguments[0].click();", element)
