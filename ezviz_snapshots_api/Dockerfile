ARG BUILD_FROM=ghcr.io/home-assistant/amd64-base:latest
FROM ${BUILD_FROM}

# Instalar Python3 + requests desde apk (sin pip)
RUN apk add --no-cache python3 py3-requests

# Copiar scripts
COPY run.sh /run.sh
COPY apisnapshot.py /config/apisnapshot.py
COPY apiaccesstoken.py /config/apiaccesstoken.py

# Permisos
RUN chmod a+x /run.sh

# Entry Point
CMD [ "/run.sh" ]
