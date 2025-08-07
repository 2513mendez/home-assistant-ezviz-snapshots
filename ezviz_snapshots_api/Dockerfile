ARG BUILD_FROM=ghcr.io/home-assistant/aarch64-base:latest
FROM ${BUILD_FROM}

# Instalar Python3 + requests
RUN apk add --no-cache python3 py3-requests

# Copiar scripts al contenedor (evitar /config/)
COPY apisnapshot.py /app/apisnapshot.py
COPY apiaccesstoken.py /app/apiaccesstoken.py

# Copiar el run.sh
COPY run.sh /run.sh

# Permisos
RUN chmod a+x /run.sh

# Entry point
CMD [ "/run.sh" ]
