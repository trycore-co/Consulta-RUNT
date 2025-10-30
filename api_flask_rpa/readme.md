Proyecto: Consulta-RUNT – API Flask \+ Poller  
 Política de rutas: todo se guarda directamente en /opt/runt del servidor, visto igual dentro y fuera de los contenedores.

**Requisitos del servidor**

* Sistema operativo: Ubuntu 22.04+ / Debian 12 / RHEL 9 (o equivalente)

* Usuario: con privilegios sudo

* Docker Engine y Docker Compose plugin instalados:

```shell
sudo apt-get update
sudo apt-get install -y ca-certificates curl gnupg
# Instalar Docker y el plugin compose (según la guía oficial)
docker --version
docker compose version
```

Preparar rutas persistentes en el host

```shell
sudo mkdir -p /opt/runt/data/screenshots \
               /opt/runt/data/pdfs \
               /opt/runt/logs
sudo chown -R 1000:1000 /opt/runt
sudo find /opt/runt -type d -exec chmod 775 {} \;
sudo find /opt/runt -type f -exec chmod 664 {} \;
```

🔐 Si usas SELinux (RHEL/CentOS):  
 sudo chcon \-R \-t container\_file\_t /opt/runt

**Variables de entorno (.env.production)**

Crea el archivo .env.production en la raíz del proyecto con los valores reales:

```
# --- Flask ---
FLASK_ENV=production
FLASK_APP=run.py
FLASK_DEBUG=0
FLASK_BASE_URL=http://localhost:8080  # usada por el poller

# --- Poller ---
POLLER_INTERVAL_SECONDS=60

# --- NocoDB / credenciales ---
NOCODB_URL=https://<nocodb>/api/v2
NOCO_XC_TOKEN=xxxxxxxxxxxxxxxx

# --- Rutas absolutas ---
FILESERVER_PATH=/opt/runt/data
SCREENSHOT_PATH=/opt/runt/data/screenshots
PDF_DIR=/opt/runt/data/pdfs
LOG_PATH=/opt/runt/logs

# --- SMTP, si aplica ---
SMTP_HOST=smtp.tuempresa.com
SMTP_PORT=587
SMTP_USER=notificador@tuempresa.com
SMTP_PASS=************
SENDER_EMAIL=notificador@tuempresa.com
RECEIVER_EMAIL=destino@tuempresa.com
```

**Dockerfiles (en carpeta docker/)**

4.1 docker/api.Dockerfile

```
FROM python:3.11-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl ca-certificates gcc && rm -rf /var/lib/apt/lists/*

COPY ./requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt && pip install gunicorn

COPY . /app
RUN useradd -u 1000 -m appuser
USER 1000:1000

EXPOSE 8080
HEALTHCHECK --interval=30s --timeout=5s --retries=5 \
  CMD curl -f http://localhost:8080/health || exit 1

CMD ["gunicorn", "-w", "2", "-b", "0.0.0.0:8080", "run:app"]
```

4.2 docker/poller.Dockerfile

```
FROM python:3.11-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl ca-certificates gcc && rm -rf /var/lib/apt/lists/*

COPY ./requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt
COPY . /app
RUN useradd -u 1000 -m appuser
USER 1000:1000

HEALTHCHECK --interval=30s --timeout=5s --retries=5 \
  CMD pgrep -f "python.*poller.py" || exit 1

CMD ["python", "-u", "poller.py"]
```

**docker-compose.yml**

Coloca en la raíz del proyecto:

```
version: "3.9"
name: consulta-runt-prod

services:
  api:
    build:
      context: ./
      dockerfile: docker/api.Dockerfile
    container_name: consulta-runt-api
    env_file:
      - .env.production
    ports:
      - "8080:8080"
    volumes:
      - /opt/runt:/opt/runt
    user: "1000:1000"
    restart: always
    init: true
    logging:
      driver: "json-file"
      options:
        max-size: "50m"
        max-file: "5"

  poller:
    build:
      context: ./
      dockerfile: docker/poller.Dockerfile
    container_name: consulta-runt-poller
    depends_on:
      - api
    env_file:
      - .env.production
    volumes:
      - /opt/runt:/opt/runt
    user: "1000:1000"
    restart: always
    init: true
    logging:
      driver: "json-file"
      options:
        max-size: "50m"
        max-file: "5"
```

**Despliegue paso a paso**

1. Copiar el proyecto al servidor.

2. Configurar variables y Dockerfiles.

3. Construir imágenes:

```shell
docker compose build
```

4. Levantar los contenedores (API \+ Poller):

```shell
docker compose up -d
```

5. Verificar estado:

```shell
docker compose ps
```

6. Deberías ver ambos como Up o Up (healthy).

**Poner en funcionamiento Flask y Poller**

Una vez creados los contenedores, puedes gestionar su ejecución así:

Iniciar manualmente (si están detenidos)

```shell
docker start consulta-runt-api
docker start consulta-runt-poller
```

 Detener

```shell
docker stop consulta-runt-api
docker stop consulta-runt-poller
```

 Reiniciar

```shell
docker restart consulta-runt-api
docker restart consulta-runt-poller
```

Los contenedores están configurados con restart: always, por lo tanto se inician automáticamente cuando se reinicia el servidor o Docker.

 Verificar funcionamiento

* Flask API:

```shell
curl -i http://localhost:8080/health
```

*   
  Debería devolver HTTP/1.1 200 OK.

* Poller:  
   Visualiza logs y confirma que ejecute ciclos de consulta:

```shell
docker logs -f consulta-runt-poller
```

*   
  Verás mensajes como “Revisando registros pendientes” o “No se encontraron pendientes”.

**Validar almacenamiento**

Después de ejecutar un proceso de extracción:

```shell
ls -l /opt/runt/data/pdfs
ls -l /opt/runt/data/screenshots
ls -l /opt/runt/logs
```

Deberían aparecer los archivos generados (PDFs, capturas, logs).

**Operación y mantenimiento**

| Acción | Comando |
| ----- | ----- |
| Ver logs del API | docker compose logs \-f api |
| Ver logs del poller | docker compose logs \-f poller |
| Actualizar código e imágenes | docker compose build && docker compose up \-d |
| Reiniciar servicios | docker compose restart api poller |
| Parar todo | docker compose down |

Asegurar que el Poller siempre esté activo

* El código del Poller maneja errores y reintenta automáticamente.

* Docker restart: always lo reinicia si falla.

* El HEALTHCHECK detecta procesos colgados.

* Puedes verificar con:

```shell
docker ps --filter "name=consulta-runt-poller"
```

Solución de problemas

| Problema | Solución |
| :---- | :---- |
| Permission denied en /opt | sudo chown \-R 1000:1000 /opt/runt o ajusta user: en Compose |
| Puerto 8080 ocupado | Cambia en Compose a ports: "9090:8080" |
| Variables faltantes | Revisa .env.production |
| Contenedor no levanta | docker compose logs \-f api o docker compose logs \-f poller |
