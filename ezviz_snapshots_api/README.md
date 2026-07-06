# EZVIZ Snapshots API/MQTT (Multi-account)

Para cámaras EZVIZ **sin RTSP**: pide snapshots a la API cloud de EZVIZ y los
publica por MQTT. Con **MQTT Discovery** activado (por defecto), Home Assistant
crea solo una entidad **`image.ezviz_<slug>`** por cámara — sin YAML manual —
lista para usar en cualquier tarjeta (`picture-entity`, etc.).

- Topics: `ezviz/snapshot/<slug>` (JSON con `picUrl`, `ts`, `serial`…) y, en
  modo `download`, `ezviz/snapshot/<slug>/image` (bytes JPEG).
- Soporta **múltiples cuentas** EZVIZ (token por cuenta, caché con caducidad).
- **Modo servicio**: refresca cada `interval_minutes` (por defecto 5). Con `0`
  hace una pasada y termina (útil si prefieres lanzarlo por automatización).

## Opciones

| Opción | Descripción |
|---|---|
| `interval_minutes` | Minutos entre ciclos. `0` = una pasada y salir. |
| `discovery` | Publica MQTT Discovery (entidades `image.*` automáticas). |
| `discovery_prefix` | Prefijo de discovery de HA (normalmente `homeassistant`). |
| `image_mode` | `url`: la entidad usa el `picUrl` del cloud EZVIZ. `download`: el add-on descarga el JPEG y lo sirve por MQTT (local, no caduca). |
| `retain` / `quality` / `debug` | Retained MQTT · calidad global (0-3) · logs verbosos. |
| `mqtt_source` | `auto` (por defecto): usa el broker y credenciales del servicio MQTT del Supervisor (add-on Mosquitto) si está disponible. `manual`: usa siempre las opciones `mqtt_*`. |
| `mqtt_*` | Broker manual (por defecto `core-mosquitto`). Solo se usan con `mqtt_source: manual` o si no hay servicio MQTT. |
| `account1_*` / `account2_*` | Cuentas por UI simple (id, app_key, app_secret). |
| `accounts[]` | Lista avanzada de cuentas (id, app_key, app_secret, quality?). |
| `camaras[]` | Cámaras (nombre, serial, channel, quality?, account). |

Las `app_key`/`app_secret` se crean en [EZVIZ Open Platform](https://open.ezviz.com)
(la cuenta debe ser de la misma región que las cámaras).

### Ejemplo (2 cuentas, 4 cámaras)

```yaml
interval_minutes: 5
retain: true
quality: 0
discovery: true
image_mode: url
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
```

## Uso en el dashboard

Con discovery activado no hay que configurar nada en HA. Ejemplo de tarjeta:

```yaml
- type: picture-entity
  entity: image.ezviz_salon
  name: EZVIZ Salón
  aspect_ratio: "16:9"
```

## Notas

- La API de EZVIZ tiene cuota diaria por `app_key`: con muchos intervalos
  cortos y muchas cámaras puedes agotarla. 5-10 min es un buen equilibrio.
- Si una cámara está offline (código 20007) se conserva el último snapshot
  retenido; la entidad no se rompe.
- Errores frecuentes: `10001` calidad no válida (se reintenta sin quality),
  `10002` token caducado (se renueva solo), `20032` canal inexistente (revisa
  `channel` o si la cámara sigue asociada a esa cuenta).
