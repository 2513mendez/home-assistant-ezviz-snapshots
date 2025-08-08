import os
import json
import time
from datetime import datetime, timezone
import requests
import paho.mqtt.publish as publish

# Rutas fijas del add-on
OPTIONS_PATH = "/data/options.json"
TOKEN_CACHE  = "/data/ezviz_token.json"

# Endpoints base
TOKEN_URL_DEFAULT   = "https://open.ezvizlife.com/api/lapp/token/get"
AREADOMAIN_FALLBACK = "https://open.ezvizlife.com"

# MQTT por defecto en HA
MQTT_HOST_DEFAULT = "core-mosquitto"
MQTT_PORT_DEFAULT = 1883

# ----- Utilidades de configuración y token -----

def load_options():
    if not os.path.exists(OPTIONS_PATH):
        print("❌ No se encontró /data/options.json")
        return None
    with open(OPTIONS_PATH, "r") as f:
        return json.load(f)

def load_cached_token():
    """Devuelve dict {'accessToken': str, 'areaDomain': str} o None."""
    try:
        if os.path.exists(TOKEN_CACHE):
            with open(TOKEN_CACHE, "r") as f:
                data = json.load(f)
                if isinstance(data, dict) and data.get("accessToken"):
                    return data
    except Exception as e:
        print(f"⚠️ No se pudo leer token cacheado: {e}")
    return None

def save_cached_token(access_token, area_domain):
    payload = {
        "accessToken": access_token,
        "areaDomain": area_domain or AREADOMAIN_FALLBACK
    }
    try:
        with open(TOKEN_CACHE, "w") as f:
            json.dump(payload, f, indent=2)
    except Exception as e:
        print(f"⚠️ No se pudo guardar token cacheado: {e}")

def request_new_token(app_key, app_secret):
    if not app_key or not app_secret:
        print("❌ app_key/app_secret no definidos. No puedo renovar token.")
        return None
    try:
        print("🔑 Solicitando nuevo accessToken a EZVIZ...")
        r = requests.post(
            TOKEN_URL_DEFAULT,
            data={"appKey": app_key, "appSecret": app_secret},
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            timeout=10
        )
        r.raise_for_status()
        data = r.json()
        if data.get("code") == "200":
            access = data["data"]["accessToken"]
            area   = data["data"].get("areaDomain", AREADOMAIN_FALLBACK)
            print(f"✅ Nuevo token: {access[:10]}...{access[-6:]}, areaDomain: {area}")
            save_cached_token(access, area)
            return {"accessToken": access, "areaDomain": area}
        print(f"❌ Error al obtener token: {data}")
        return None
    except Exception as e:
        print(f"❌ Error de red al renovar token: {e}")
        return None

# ----- Llamadas a la API de captura -----

def capture_once(capture_url, serial, canal, token, quality=None):
    payload = {
        "accessToken": token,
        "deviceSerial": serial,
        "channelNo": canal
    }
    if quality is not None:
        payload["quality"] = quality
    try:
        r = requests.post(
            capture_url,
            data=payload,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            timeout=12
        )
        r.raise_for_status()
        return r.json()
    except requests.exceptions.RequestException as e:
        return {"code": "neterr", "msg": str(e)}

def capture_with_retry(capture_url, serial, canal, token, quality=None, retries=1, backoff=2):
    """Reintenta en errores de red/timeout y ciertos códigos de dispositivo."""
    res = capture_once(capture_url, serial, canal, token, quality)
    if res.get("code") in ("neterr", "20006", "20008", "60017") and retries > 0:
        print(f"⏳ Reintentando ({retries}) tras {backoff}s por {res.get('code')}...")
        time.sleep(backoff)
        return capture_with_retry(capture_url, serial, canal, token, quality, retries-1, backoff*2)
    return res

# ----- MQTT -----

def publish_mqtt(nombre, payload_dict, retain, host=MQTT_HOST_DEFAULT, port=MQTT_PORT_DEFAULT):
    topic = f"ezviz/snapshot/{slugify(nombre)}"
    try:
        publish.single(topic, payload=json.dumps(payload_dict), hostname=host, port=port, retain=retain)
        print(f"📤 MQTT OK -> {topic}")
    except Exception as e:
        print(f"⚠️ Error publicando en MQTT ({topic}): {e}")

def slugify(s):
    return "".join(c if c.isalnum() or c in "-_" else "_" for c in s.lower())

# ----- Flujo principal -----

def run():
    cfg = load_options()
    if not cfg:
        return

    app_key   = cfg.get("app_key")
    app_secret= cfg.get("app_secret")
    retain    = bool(cfg.get("retain", True))
    quality   = cfg.get("quality", 3)
    camaras   = cfg.get("camaras", [])

    if not camaras:
        print("❌ No hay cámaras definidas.")
        return

    mqtt_host = os.getenv("MQTT_BROKER", MQTT_HOST_DEFAULT)
    mqtt_port = int(os.getenv("MQTT_PORT", MQTT_PORT_DEFAULT))

    cache = load_cached_token()
    if not cache:
        cache = request_new_token(app_key, app_secret)
        if not cache:
            print("❌ No hay token válido. Abortando.")
            return

    token = cache["accessToken"]
    area  = cache.get("areaDomain") or AREADOMAIN_FALLBACK
    capture_url = f"{area.rstrip('/')}/api/lapp/device/capture"

    # 1) Primer intento con token actual
    need_refresh = False
    results = []

    for cam in camaras:
        nombre = cam.get("nombre", "camara")
        serial = cam.get("serial")
        canal  = cam.get("channel", 1)
        if not serial:
            print(f"⚠️ Cámara '{nombre}' sin serial. Saltando…")
            continue

        print(f"📸 '{nombre}' ({serial}) canal {canal} | quality={quality} | area={area}")
        res = capture_with_retry(capture_url, serial, canal, token, quality)
        results.append((nombre, serial, canal, res))

        if res.get("code") == "10002":
            print(f"⚠️ Token inválido/caducado detectado en '{nombre}'.")
            need_refresh = True
            break

    # 2) Si el token caducó, renovar y reintentar todas
    if need_refresh:
        cache = request_new_token(app_key, app_secret)
        if not cache:
            print("❌ No pude renovar token. Abortando reintento.")
            return
        token = cache["accessToken"]
        area  = cache.get("areaDomain") or AREADOMAIN_FALLBACK
        capture_url = f"{area.rstrip('/')}/api/lapp/device/capture"

        results = []
        for cam in camaras:
            nombre = cam.get("nombre", "camara")
            serial = cam.get("serial")
            canal  = cam.get("channel", 1)
            if not serial:
                continue
            print(f"🔁 Reintentando '{nombre}' con token nuevo…")
            res = capture_with_retry(capture_url, serial, canal, token, quality)
            results.append((nombre, serial, canal, res))

    # 3) Publicación MQTT (JSON rico)
    now_iso = datetime.now(timezone.utc).isoformat()
    for (nombre, serial, canal, res) in results:
        code = res.get("code")
        if code == "200":
            pic_url = res.get("data", {}).get("picUrl")
            payload = {
                "name": nombre,
                "serial": serial,
                "channel": canal,
                "quality": quality,
                "picUrl": pic_url,
                "ts": now_iso,
                "areaDomain": area,
                "code": code
            }
            print(f"✅ Snapshot '{nombre}': {pic_url}")
            publish_mqtt(nombre, payload, retain, host=mqtt_host, port=mqtt_port)
        else:
            print(f"❌ Error en '{nombre}': {res}")

if __name__ == "__main__":
    print("🔄 Ejecutando captura de snapshots EZVIZ...")
    run()
    print("✅ Proceso completado.")
