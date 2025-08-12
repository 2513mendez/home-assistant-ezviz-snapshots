# EZVIZ Snapshots API/MQTT (Multi-account)

Add-on para Home Assistant que obtiene snapshots de cámaras EZVIZ usando la API oficial y publica un JSON por MQTT en:

## Características
- Soporta **múltiples cuentas** EZVIZ (cada una con su token y `areaDomain`).
- Cachea **un token por cuenta** en `/data/ezviz_tokens/<account_id>.json`.
- Publica payload con el campo `account` para facilitar trazas y reglas.
- Logs con **timestamp** y opción `debug` para alta verbosidad.
- Compatible con modo **legacy** (una sola cuenta con `app_key` y `app_secret`).

---

## Requisitos
- Broker MQTT accesible desde Home Assistant (por ejemplo, `core-mosquitto`).
- App Key y App Secret válidos de EZVIZ (una o varias cuentas).

---

## Configuración (UI del add-on)

### Campos principales
- `retain` (bool): publica mensajes con retain en MQTT (por defecto `true`).
- `quality` (int, opcional): calidad por defecto si no se especifica a nivel de cuenta/cámara (0=Smooth).
- `debug` (bool, opcional): activa logs detallados (`true` = modo verboso).
- `mqtt_*`: conexión al broker MQTT.
- `accounts` (lista): definición de múltiples cuentas EZVIZ.
- `camaras` (lista): cámaras a capturar.

---

## Estructura de `accounts`
```json
{
  "id": "cuenta_negocio",
  "app_key": "AK_XXXXXXXX",
  "app_secret": "AS_YYYYYYYY",
  "quality": 1
}
