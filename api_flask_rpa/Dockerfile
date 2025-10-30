# Usamos una imagen base más moderna con mejores dependencias para WeasyPrint
FROM python:3.9-slim-bullseye

# Establecemos el directorio de trabajo
WORKDIR /

# Actualizamos los repositorios para Debian Bullseye
RUN apt-get update

# Instalamos las dependencias necesarias incluyendo Chrome para Selenium y WeasyPrint
RUN apt-get install -y --no-install-recommends \
    wget \
    curl \
    unzip \
    gnupg \
    python3-pip \
    python3-dev \
    python3-cffi \
    gcc \
    git \
    nano \
    sshfs \
    fuse3 \
    libpq-dev \
    libreoffice \
    fonts-liberation \
    xvfb \
    fonts-liberation \
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
    && rm -rf /var/lib/apt/lists/*

# Instalar Google Chrome
RUN wget -q -O - https://dl.google.com/linux/linux_signing_key.pub | apt-key add - \
    && echo "deb [arch=amd64] http://dl.google.com/linux/chrome/deb/ stable main" > /etc/apt/sources.list.d/google-chrome.list \
    && apt-get update \
    && apt-get install -y google-chrome-stable \
    && rm -rf /var/lib/apt/lists/*

# Instalar ChromeDriver - Versión compatible con Chrome 140
RUN CHROMEDRIVER_VERSION="140.0.7339.80" \
    && echo "Installing ChromeDriver version: $CHROMEDRIVER_VERSION" \
    && wget -O /tmp/chromedriver.zip "https://storage.googleapis.com/chrome-for-testing-public/$CHROMEDRIVER_VERSION/linux64/chromedriver-linux64.zip" \
    && unzip /tmp/chromedriver.zip -d /tmp/ \
    && mv /tmp/chromedriver-linux64/chromedriver /usr/local/bin/chromedriver \
    && chmod +x /usr/local/bin/chromedriver \
    && rm -rf /tmp/chromedriver* \
    && chromedriver --version \
    && google-chrome --version


# Instalamos geckodriver para Selenium
RUN wget https://github.com/mozilla/geckodriver/releases/download/v0.33.0/geckodriver-v0.33.0-linux64.tar.gz \
    && tar -xzf geckodriver-v0.33.0-linux64.tar.gz \
    && mv geckodriver /usr/local/bin/ \
    && chmod +x /usr/local/bin/geckodriver \
    && rm geckodriver-v0.33.0-linux64.tar.gz \
    && geckodriver --version

# Instalamos dependencias adicionales específicas para WeasyPrint
RUN apt-get update && apt-get install -y --no-install-recommends \
    libxml2-dev \
    libxslt1-dev \
    zlib1g-dev \
    libjpeg-dev \
    && rm -rf /var/lib/apt/lists/*



RUN ln -sf /usr/bin/python3 /usr/bin/python
RUN ln -sf /usr/bin/pip3 /usr/bin/pip

# Copiamos el código fuente
COPY ./app /app
COPY ./run.py run.py
COPY ./requirements.txt requirements.txt
COPY ./.env .env

# Instalamos WeasyPrint primero con sus dependencias específicas
RUN pip install --no-cache-dir --upgrade pip setuptools wheel
RUN pip install --no-cache-dir cffi cairocffi
RUN pip install --no-cache-dir weasyprint

# Instalamos el resto de las dependencias
RUN pip install --no-cache-dir -r requirements.txt

# Configuramos PYTHONPATH y Navegadores
ENV PYTHONPATH=${PYTHONPATH}
ENV DISPLAY=:{DISPLAY}
ENV CHROME_BIN={CHROME_BIN}
ENV CHROMEDRIVER_PATH={CHROMEDRIVER_PATH}
ENV SELENIUM_HEADLESS=True
ENV CHROME_NO_SANDBOX=True 


# Exponemos el puerto 8080
EXPOSE 8080

# Comando correcto para iniciar
CMD ["python3", "run.py"]