ARG BUILD_FROM=ghcr.io/home-assistant/aarch64-base:latest
FROM ${BUILD_FROM}

# Instalar Python 3 + librerías necesarias desde APK
RUN apk add --no-cache python3 py3-requests py3-paho-mqtt

# Copiar scripts al contenedor
COPY apisnapshot.py /app/apisnapshot.py
COPY apiaccesstoken.py /app/apiaccesstoken.py

# Copiar el run.sh
COPY run.sh /run.sh

# Permisos
RUN chmod a+x /run.sh

# Entry point
CMD [ "/run.sh" ]
