"""
WebClient: wrapper Selenium para RUNT PRO.
"""

from selenium import webdriver
from selenium.webdriver.chrome.service import Service as ChromeService
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
from typing import Optional
import time


class WebClient:
    def __init__(
        self, base_url: str, headless: bool = True,
        browser=None, timeout: int = 20
    ):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.driver = browser or self._create_driver(headless=headless)
        self.wait = WebDriverWait(self.driver, self.timeout)

    def _create_driver(self, headless=True):
        options = webdriver.ChromeOptions()
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_argument("--start-maximized")
        options.add_argument("--disable-gpu")
        options.add_argument("--no-zygote")
        options.add_argument("--ignore-certificate-errors")
        if headless:
            options.add_argument("--headless=new")
        driver = webdriver.Chrome(
            service=ChromeService(ChromeDriverManager().install()), options=options
        )
        return driver

    def open(self, path: str = "/"):
        url = self.base_url + (path if path.startswith("/") else f"/{path}")
        self.driver.get(url)

    def click_continue_if_present(self, timeout: float = 3.0):
        """
        se hace 'clic' en un botón 'Continuar' si aparece.
        """
        try:
            btn = WebDriverWait(self.driver, timeout).until(
                EC.element_to_be_clickable(
                    (
                        By.ID,
                        "continue"
                    )
                )
            )
            # Hacer scroll hasta el botón
            self.driver.execute_script(
                "arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});",
                btn,
            )
            time.sleep(1)  # pequeña pausa para asegurar visibilidad
            btn.click()
            time.sleep(0.5)
            return True
        except TimeoutException:
            return False
        except Exception:
            return False

    def login_runt(
        self,
        user_selector: str,
        pass_selector: str,
        submit_selector: str,
        user: str,
        password: str,
        wait_after: float = 2.0,
    ):
        """
        Secuencia de login:
        - open homepage
        - click continuar (si existe)
        - set user/pass
        - click submit
        - detectar alerta de error (div.role=alert) o confirmar éxito
        Devuelve True = login OK (no error alert detected) - False = detected error / exception
        """
        try:
            self.open("/")
            # Intentar cerrar posible modal "Continuar"
            self.click_continue_if_present()

            # esperar campos
            self.wait.until(
                EC.visibility_of_element_located((By.CSS_SELECTOR, user_selector))
            )
            el_user = self.driver.find_element(By.CSS_SELECTOR, user_selector)
            el_pass = self.driver.find_element(By.CSS_SELECTOR, pass_selector)

            el_user.clear()
            el_user.send_keys(user)
            el_pass.clear()
            el_pass.send_keys(password)

            # submit
            submit_el = self.driver.find_element(By.CSS_SELECTOR, submit_selector)
            submit_el.click()
            time.sleep(wait_after)

            # detectar si aparece mensaje de error
            try:
                error_div = WebDriverWait(self.driver, 3).until(
                    EC.visibility_of_element_located(
                        (
                            By.CSS_SELECTOR,
                            "div.error.pageLevel[role='alert'], div[role='alert'].error",
                        )
                    )
                )
                # si existe, retorno False
                return False
            except TimeoutException:
                # no se detectó error -> asumimos login OK (caller puede verificar con URL o elemento de landing)
                return True
        except Exception as exc:
            # Dejar excepción para que el caller haga logging/handling
            raise

    def find_elements(self, by, selector, wait=True, timeout=None):
        if wait:
            WebDriverWait(self.driver, timeout or self.timeout).until(
                EC.presence_of_all_elements_located((by, selector))
            )
        return self.driver.find_elements(by, selector)

    def find_element(self, by, selector, wait=True, timeout=None):
        if wait:
            WebDriverWait(self.driver, timeout or self.timeout).until(
                EC.presence_of_element_located((by, selector))
            )
        return self.driver.find_element(by, selector)

    def screenshot_bytes(self) -> bytes:
        """Devuelve PNG en bytes (útil para guardar con CaptureService)."""
        return self.driver.get_screenshot_as_png()

    def screenshot_save(self, path: str):
        self.driver.save_screenshot(path)

    def wait_for_css(self, css_selector: str, timeout: Optional[int] = None):
        WebDriverWait(self.driver, timeout or self.timeout).until(
            EC.visibility_of_element_located((By.CSS_SELECTOR, css_selector))
        )

    def close(self):
        try:
            self.driver.quit()
        except Exception:
            pass

    def find_by_selector(self, selector: dict, timeout: Optional[int] = None):
        """
        Recibe un diccionario de selector del YAML, por ejemplo:
        {"by": "xpath", "value": "//*[@id='signInName']"}
        """
        by = selector.get("by", "xpath").lower()
        value = selector.get("value")
        return self.find_element(By.XPATH if by == "xpath" else By.CSS_SELECTOR, value, timeout=timeout)

    def click_selector(self, selector: dict, timeout: Optional[int] = None):
        el = self.find_by_selector(selector, timeout)
        self.driver.execute_script("arguments[0].scrollIntoView({block:'center'});", el)
        el.click()
        return el

    def send_keys_selector(self, selector: dict, text: str, clear: bool = True, timeout: Optional[int] = None):
        el = self.find_by_selector(selector, timeout)
        if clear:
            el.clear()
        el.send_keys(text)
        return el

    def find_all_by_selector(self, selector: dict, timeout: Optional[int] = None):
        by = selector.get("by", "xpath").lower()
        value = selector.get("value")
        return self.find_elements(By.XPATH if by == "xpath" else By.CSS_SELECTOR, value, timeout=timeout)

    def wait_until_invisible(self, by, value, timeout=15):
        """
        Espera hasta que un elemento deje de ser visible en el DOM.
        Retorna True si desaparece, False si no.
        """
        try:
            WebDriverWait(self.driver, timeout).until(
                EC.invisibility_of_element_located((by, value))
            )
            return True
        except TimeoutException:
            return False
