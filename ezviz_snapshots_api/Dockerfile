# Base de Home Assistant para tu arquitectura (el builder usa la correcta)
FROM ghcr.io/home-assistant/aarch64-base:latest

# Paquetes necesarios
RUN apk add --no-cache \
    python3 \
    py3-requests \
    py3-paho-mqtt \
    jq

# Copiar scripts al contenedor
COPY apisnapshot.py /app/apisnapshot.py
COPY run.sh /run.sh

# Permisos y preparación
RUN chmod +x /run.sh && \
    mkdir -p /data/ezviz_tokens && \
    echo "Docker image ready"

# Ejecutar
CMD [ "/run.sh" ]
