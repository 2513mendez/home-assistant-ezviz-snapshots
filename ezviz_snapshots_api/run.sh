#!/usr/bin/with-contenv bashio
# Si el Supervisor ofrece el servicio MQTT (add-on Mosquitto), exportamos sus
# credenciales; el script Python las usa salvo mqtt_source: manual.
if bashio::services.available "mqtt"; then
    export MQTT_SERVICE_HOST="$(bashio::services mqtt 'host')"
    export MQTT_SERVICE_PORT="$(bashio::services mqtt 'port')"
    export MQTT_SERVICE_USER="$(bashio::services mqtt 'username')"
    export MQTT_SERVICE_PASSWORD="$(bashio::services mqtt 'password')"
    bashio::log.info "Servicio MQTT del Supervisor detectado (${MQTT_SERVICE_HOST}:${MQTT_SERVICE_PORT})"
fi
exec python3 -u /app/apisnapshot.py
