ARG BUILD_FROM=ghcr.io/home-assistant/aarch64-base:latest
FROM ${BUILD_FROM}

# Instalar Python3 + pip + librerías necesarias
RUN apk add --no-cache python3 py3-pip && \
    pip3 install --no-cache-dir paho-mqtt requests

# Copiar scripts al contenedor
COPY apisnapshot.py /app/apisnapshot.py
COPY apiaccesstoken.py /app/apiaccesstoken.py

# Copiar el script de ejecución
COPY run.sh /run.sh

# Permisos
RUN chmod a+x /run.sh

# (Opcional) Mostrar contenido para debug
RUN ls -l /app

# Punto de entrada
CMD [ "/run.sh" ]
