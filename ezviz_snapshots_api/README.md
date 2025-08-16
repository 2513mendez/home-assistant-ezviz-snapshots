# EZVIZ Snapshots API/MQTT (Multi-account)

Publica snapshots de cámaras EZVIZ por MQTT en `ezviz/snapshot/<nombre_camara>`.  
Soporta **múltiples cuentas** (token por cuenta), **caché de tokens** por cuenta, logs con timestamp y `debug`.

## Configuración (UI)
- `retain` (bool), `quality` (int), `debug` (bool)
- MQTT: `mqtt_host`, `mqtt_port`, `mqtt_user`, `mqtt_password`
- `accounts[]`: lista de cuentas (id, app_key, app_secret, quality?)
- `camaras[]`: lista de cámaras (nombre, serial, channel, quality?, account)

### Ejemplo UI (2 cuentas, 4 cámaras)
```yaml
retain: true
quality: 0
debug: false
mqtt_host: core-mosquitto
mqtt_port: 1883
mqtt_user: mqtt_user
mqtt_password: "********"
accounts:
  - id: personal
    app_key: "AK_xxx"
    app_secret: "AS_xxx"
    quality: 0
  - id: negocio
    app_key: "AK_yyy"
    app_secret: "AS_yyy"
    quality: 1
camaras:
  - nombre: "Salón"
    serial: "BFXXXXXXXX"
    channel: 1
    account: "personal"
  - nombre: "Mirilla"
    serial: "BFXXXXXXXX"
    channel: 1
    account: "personal"
  - nombre: "exterior_frente"
    serial: "BFXXXX3333"
    channel: 1
    account: "negocio"
  - nombre: "exterior_trasera"
    serial: "BFXXXX4444"
    channel: 1
    account: "negocio"
