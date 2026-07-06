# El Supervisor inyecta BUILD_FROM con la imagen base de la arquitectura
# destino (por eso config.json puede declarar las 5 archs).
ARG BUILD_FROM=ghcr.io/home-assistant/aarch64-base:latest
FROM ${BUILD_FROM}

# Paquetes necesarios
RUN apk add --no-cache \
    python3 \
    py3-requests \
    py3-paho-mqtt

# Copiar scripts al contenedor
COPY apisnapshot.py /app/apisnapshot.py
COPY run.sh /run.sh

RUN chmod +x /run.sh

CMD [ "/run.sh" ]
