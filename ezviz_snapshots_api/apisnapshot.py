import os
import json
import time
import unicodedata
import re
from datetime import datetime, timezone
import requests
import paho.mqtt.publish as publish

# Rutas y fijos
OPTIONS_PATH = "/data/options.json"
TOKENS_DIR   = "/data/ezviz_tokens"

TOKEN_URL_DEFAULT   = "https://open.ezvizlife.com/api/lapp/token/get"
AREADOMAIN_FALLBACK = "https://open.ezvizlife.com"

MQTT_HOST_DEFAULT = "core-mosquitto"
MQTT_PORT_DEFAULT = 1883

# ---------- Utils ----------

def ts():
    return datetime.now(timezone.utc).isoformat()

def log(msg, dbg=False, debug=False):
    if dbg and not debug:
        return
    print(f"[{ts()}] {msg}", flush=True)

def slugify(s: str) -> str:
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode("ascii")
    s = s.lower().replace(" ", "_")
    return re.sub(r"[^a-z0-9_-]", "_", s)

def ensure_dirs():
    try:
        os.makedirs(TOKENS_DIR, exist_ok=True)
    except Exception as e:
        print(f"[{ts()}] ⚠️ No se pudo crear {TOKENS_DIR}: {e}")

def load_options():
    if not os.path.exists(OPTIONS_PATH):
        print(f"[{ts()}] ❌ No se encontró {OPTIONS_PATH}")
        return None
    with open(OPTIONS_PATH, "r", encoding="utf-8") as f:
        return json.load(f)

def token_cache_path(account_id: str) -> str:
    return os.path.join(TOKENS_DIR, f"{slugify(account_id)}.json")

def load_cached_token(account_id: str):
    path = token_cache_path(account_id)
    try:
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, dict) and data.get("accessToken"):
                    return data
    except Exception as e:
        print(f"[{ts()}] ⚠️ No se pudo leer token cacheado de '{account_id}': {e}")
    return None

def save_cached_token(account_id: str, access_token: str, area_domain: str):
    path = token_cache_path(account_id)
    payload = {
        "accessToken": access_token,
        "areaDomain": area_domain or AREADOMAIN_FALLBACK
    }
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2)
    except Exception as e:
        print(f"[{ts()}] ⚠️ No se pudo guardar token cacheado de '{account_id}': {e}")

def request_new_token(app_key: str, app_secret: str, account_id: str, debug=False):
    if not app_key or not app_secret:
        log(f"❌ Cuenta '{account_id}' sin app_key/app_secret; no puedo renovar token.", debug=debug)
        return None
    try:
        log(f"🔑 [{account_id}] Solicitando accessToken a EZVIZ…", debug=debug)
        r = requests.post(
            TOKEN_URL_DEFAULT,
            data={"appKey": app_key, "appSecret": app_secret},
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            timeout=12
        )
        r.raise_for_status()
        data = r.json()
        if data.get("code") == "200":
            access = data["data"]["accessToken"]
            area   = data["data"].get("areaDomain", AREADOMAIN_FALLBACK)
            log(f"✅ [{account_id}] Nuevo token {access[:10]}…{access[-6:]}, areaDomain={area}", debug=debug)
            save_cached_token(account_id, access, area)
            return {"accessToken": access, "areaDomain": area}
        log(f"❌ [{account_id}] Error al obtener token: {data}", debug=debug)
    except Exception as e:
        log(f"❌ [{account_id}] Error de red al renovar token: {e}", debug=debug)
    return None

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

def capture_with_retry(capture_url, serial, canal, token, quality=None, retries=1, backoff=2, debug=False, account_id="-"):
    res = capture_once(capture_url, serial, canal, token, quality)
    code = res.get("code")

    if code in ("neterr", "20006", "20008", "60017") and retries > 0:
        log(f"⏳ [{account_id}] Reintentando ({retries}) tras {backoff}s por {code}…", debug=debug)
        time.sleep(backoff)
        return capture_with_retry(capture_url, serial, canal, token, quality, retries-1, backoff*2, debug, account_id)

    if code == "10001" and quality is not None and retries > 0:
        log(f"⚠️ [{account_id}] 'Invalid quality' → reintentando sin 'quality'…", debug=debug)
        return capture_with_retry(capture_url, serial, canal, token, None, retries-1, backoff, debug, account_id)

    return res

def publish_mqtt(nombre, payload_dict, retain, host, port, user, password, debug=False):
    topic = f"ezviz/snapshot/{slugify(nombre)}"
    try:
        auth = {"username": user, "password": password} if user else None
        publish.single(
            topic,
            payload=json.dumps(payload_dict),
            hostname=host,
            port=port,
            auth=auth,
            retain=retain
        )
        log(f"📤 MQTT OK -> {topic}", dbg=True, debug=debug)
    except Exception as e:
        print(f"[{ts()}] ⚠️ Error publicando en MQTT ({topic}): {e}")

# ---------- Flujo principal ----------

def run():
    ensure_dirs()
    cfg = load_options()
    if not cfg:
        return

    debug     = bool(cfg.get("debug", False))
    retain    = bool(cfg.get("retain", True))
    quality_g = cfg.get("quality", 0)

    mqtt_host = cfg.get("mqtt_host", MQTT_HOST_DEFAULT)
    mqtt_port = int(cfg.get("mqtt_port", MQTT_PORT_DEFAULT))
    mqtt_user = cfg.get("mqtt_user", "")
    mqtt_pass = cfg.get("mqtt_password", "")

    accounts  = cfg.get("accounts", [])
    camaras   = cfg.get("camaras", [])

    if not accounts:
        print(f"[{ts()}] ❌ No hay 'accounts' definidos en la configuración.")
        return
    if not camaras:
        print(f"[{ts()}] ❌ No hay 'camaras' definidas en la configuración.")
        return

    # Indexar cuentas por id
    acc_by_id = {a.get("id"): a for a in accounts if a.get("id")}
    for acc_id in acc_by_id.keys():
        if not load_cached_token(acc_id):
            # Primer token si no hay cache
            request_new_token(
                acc_by_id[acc_id].get("app_key", ""),
                acc_by_id[acc_id].get("app_secret", ""),
                acc_id,
                debug=debug
            )

    # Captura por cámara (reusa token por cuenta y renueva si hace falta)
    now_iso = ts()
    for cam in camaras:
        nombre = cam.get("nombre", "camara")
        serial = cam.get("serial")
        canal  = cam.get("channel", 1)
        acc_id = cam.get("account")

        if not serial or not acc_id or acc_id not in acc_by_id:
            print(f"[{ts()}] ⚠️ Cámara '{nombre}' mal configurada (serial/account). Saltando…")
            continue

        acc = acc_by_id[acc_id]
        q_cam = cam.get("quality", acc.get("quality", quality_g))

        # Obtener token + area para esta cuenta
        cache = load_cached_token(acc_id)
        if not cache:
            cache = request_new_token(acc.get("app_key", ""), acc.get("app_secret", ""), acc_id, debug=debug)
            if not cache:
                print(f"[{ts()}] ❌ No hay token válido para '{acc_id}'. Saltando cámara '{nombre}'.")
                continue

        token = cache["accessToken"]
        area  = cache.get("areaDomain") or AREADOMAIN_FALLBACK
        capture_url = f"{area.rstrip('/')}/api/lapp/device/capture"

        log(f"📸 [{acc_id}] '{nombre}' ({serial}) ch={canal} | q={q_cam} | area={area}", dbg=True, debug=debug)
        res = capture_with_retry(capture_url, serial, canal, token, q_cam, retries=1, backoff=2, debug=debug, account_id=acc_id)

        # ¿Token caducado? renovar y reintentar 1 vez
        if res.get("code") == "10002":
            log(f"⚠️ [{acc_id}] Token inválido/caducado. Renovando…", debug=debug)
            cache = request_new_token(acc.get("app_key", ""), acc.get("app_secret", ""), acc_id, debug=debug)
            if not cache:
                print(f"[{ts()}] ❌ No pude renovar token para '{acc_id}'.")
                continue
            token = cache["accessToken"]
            area  = cache.get("areaDomain") or AREADOMAIN_FALLBACK
            capture_url = f"{area.rstrip('/')}/api/lapp/device/capture"
            res = capture_with_retry(capture_url, serial, canal, token, q_cam, retries=1, backoff=2, debug=debug, account_id=acc_id)

        # Publicación
        code = res.get("code")
        if code == "200":
            pic_url = res.get("data", {}).get("picUrl")
            payload = {
                "name": nombre,
                "serial": serial,
                "channel": canal,
                "quality": q_cam,
                "picUrl": pic_url,
                "ts": now_iso,
                "areaDomain": area,
                "code": code,
                "account": acc_id
            }
            log(f"✅ [{acc_id}] Snapshot '{nombre}': {pic_url}", debug=debug)
            publish_mqtt(nombre, payload, retain, mqtt_host, mqtt_port, mqtt_user, mqtt_pass, debug=debug)
        else:
            print(f"[{ts()}] ❌ [{acc_id}] Error en '{nombre}': {res}")

if __name__ == "__main__":
    print(f"[{ts()}] 🔄 Ejecutando captura de snapshots EZVIZ (multi-account)…")
    run()
    print(f"[{ts()}] ✅ Proceso completado.")
