# Changelog

## 1.3.1 (2026-07-06)

- **Limpieza automática de cámaras eliminadas o renombradas**: el add-on
  recuerda las cámaras publicadas (`/data/known_cameras.json`, por serial) y,
  si una desaparece de `camaras[]` o cambia de `nombre` (slug), borra sus
  mensajes retenidos y su config de MQTT Discovery (payload vacío) → la
  entidad huérfana desaparece de HA y el broker queda limpio, sin pasos
  manuales.

## 1.3.0 (2026-07-06)

### Nuevo
- **MQTT Discovery** (`discovery`, por defecto `true`): el add-on publica la
  configuración de descubrimiento y Home Assistant crea solo una entidad
  `image.ezviz_<slug>` por cámara (con atributos: picUrl, ts, serial…). Ya no
  hace falta YAML manual.
- **Modo servicio** (`interval_minutes`, por defecto `5`): el add-on queda
  corriendo y refresca los snapshots cada N minutos. Con `0` hace una sola
  pasada y termina (comportamiento v1.2.x, compatible con lanzarlo desde una
  automatización).
- **`image_mode`**: `url` (por defecto, la entidad image usa el picUrl del
  cloud de EZVIZ) o `download` (el add-on descarga el JPEG y publica los bytes
  en `ezviz/snapshot/<slug>/image`; el snapshot queda servido en local y no
  depende de la caducidad del picUrl).
- **Caducidad de token**: se guarda `expireTime` y el token se renueva
  proactivamente antes de caducar (además de la renovación reactiva por 10002).
- **Credenciales MQTT automáticas** (`mqtt_source: auto`, por defecto): si el
  Supervisor ofrece el servicio MQTT (add-on Mosquitto), el add-on usa su
  broker y credenciales sin configurar nada (`services: mqtt:want` + bashio).
  Con `manual` se usan siempre las opciones `mqtt_*` (broker externo).

### Corregido / mejorado
- Una única conexión MQTT por proceso (antes una por cámara y publicación),
  compatible con paho-mqtt 1.x y 2.x, con verificación de publicación.
- El timestamp `ts` del payload ahora es el del momento real de cada captura
  (antes se calculaba una sola vez para todas las cámaras).
- Reintentos: backoff exponencial real, más códigos transitorios (49999), y el
  fallback "sin quality" (10001) ya no consume el presupuesto de reintentos.
- Cámara offline (20007) se loguea de forma amigable y se conserva el último
  snapshot retenido (no se publica payload de error encima del bueno).
- `Dockerfile` multi-arch de verdad (usa `BUILD_FROM` del Supervisor; antes
  estaba fijada la base aarch64) y sin paquetes sin uso (`jq`).
- `config.json`: secretos con schema `password` (se ocultan en la UI), sin
  mapeo `config:rw` (no se usaba), `startup: application` + `boot: auto` para
  el modo servicio.
- Logs sin buffer (`python3 -u`).

### Migración desde 1.2.x
- Sin cambios en tus opciones: cuentas y cámaras valen tal cual. Aparecen las
  opciones nuevas con sus valores por defecto.
- Si lanzabas el add-on desde una automatización cada N minutos, bórrala (el
  add-on ya se refresca solo con `interval_minutes`) o pon `interval_minutes: 0`
  para seguir como antes.
- Los topics `ezviz/snapshot/<slug>` no cambian: cualquier consumidor previo
  sigue funcionando.

## 1.2.3 y anteriores
Ver historial de git.
