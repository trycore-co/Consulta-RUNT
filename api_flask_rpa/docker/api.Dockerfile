# 1. Fija la imagen a la versión estable "Bookworm"
FROM python:3.11-slim-bookworm
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app

# 2. Instalar TODAS las dependencias del sistema (AÑADIENDO libgbm1)
RUN apt-get update && apt-get install -y --no-install-recommends \
    # Dependencias base
    curl \
    ca-certificates \
    gcc \
    wget \
    unzip \
    gnupg \
    python3-dev \
    python3-cffi \
    git \
    nano \
    sshfs \
    fuse3 \
    libpq-dev \
    libreoffice \
    fonts-liberation \
    xvfb \
    libasound2 \
    libatk-bridge2.0-0 \
    libatk1.0-0 \
    libatspi2.0-0 \
    libdrm2 \
    libgtk-3-0 \
    libnspr4 \
    libnss3 \
    libx11-xcb1 \
    libxcomposite1 \
    libxdamage1 \
    libxrandr2 \
    xdg-utils \
    libxss1 \
    libgconf-2-4 \
    libpango-1.0-0 \
    libpangocairo-1.0-0 \
    libpangoft2-1.0-0 \
    libharfbuzz0b \
    libfontconfig1 \
    libcairo2 \
    libgdk-pixbuf2.0-0 \
    libffi-dev \
    shared-mime-info \
    # Dependencia faltante para Chrome:
    libgbm1 \
    # Dependencias de WeasyPrint
    libxml2-dev \
    libxslt1-dev \
    zlib1g-dev \
    libjpeg-dev \
    && rm -rf /var/lib/apt/lists/* # Limpiar la caché

# 3. Instalar NAVEGADOR y DRIVER (v140) desde "Chrome for Testing"
RUN CHROMEDRIVER_VERSION="140.0.7339.80" \
    && echo "Installing Chrome & ChromeDriver CfT version: $CHROMEDRIVER_VERSION" \
    \
    # Instalar ChromeDriver (v140)
    && wget -O /tmp/chromedriver.zip "https://storage.googleapis.com/chrome-for-testing-public/$CHROMEDRIVER_VERSION/linux64/chromedriver-linux64.zip" \
    && unzip /tmp/chromedriver.zip -d /tmp/ \
    && mv /tmp/chromedriver-linux64/chromedriver /usr/local/bin/chromedriver \
    && chmod +x /usr/local/bin/chromedriver \
    \
    # Instalar Navegador Chrome (v140)
    && wget -O /tmp/chrome.zip "https://storage.googleapis.com/chrome-for-testing-public/$CHROMEDRIVER_VERSION/linux64/chrome-linux64.zip" \
    && unzip /tmp/chrome.zip -d /tmp/ \
    # Mover la carpeta 'chrome-linux64' a /opt/
    && mv /tmp/chrome-linux64 /opt/chrome-v140 \
    # Crear un enlace simbólico para que 'chrome' sea encontrado
    && ln -s /opt/chrome-v140/chrome /usr/local/bin/chrome \
    && chmod +x /usr/local/bin/chrome \
    \
    # Limpiar
    && rm -rf /tmp/chromedriver* /tmp/chrome* \
    && chromedriver --version \
    && chrome --version

# 4. Instalar dependencias de Python
COPY ./requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir --upgrade pip setuptools wheel
RUN pip install --no-cache-dir cffi cairocffi
RUN pip install --no-cache-dir weasyprint
RUN pip install --no-cache-dir -r /app/requirements.txt && pip install gunicorn

# 5. Configurar ENV para que web_client.py los encuentre
ENV PYTHONPATH=${PYTHONPATH}
ENV DISPLAY=:{DISPLAY}
# Apuntar a los binarios v140 que acabamos de instalar
ENV CHROME_BIN=/usr/local/bin/chrome
ENV CHROMEDRIVER_PATH=/usr/local/bin/chromedriver
ENV SELENIUM_HEADLESS=True
ENV CHROME_NO_SANDBOX=True 

COPY . /app

# 6. Configurar permisos
RUN useradd -u 1000 -m appuser
RUN chown -R 1000:1000 /app

USER 1000:1000

EXPOSE 8080
HEALTHCHECK --interval=30s --timeout=5s --retries=5 \
  CMD curl -f http://localhost:8080/health || exit 1

CMD ["gunicorn", "-w", "2", "-b", "0.0.0.0:8080", "run:app"]