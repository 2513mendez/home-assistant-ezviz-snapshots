import os
import json
import time
import re
import unicodedata
from datetime import datetime, timezone

import requests
import paho.mqtt.publish as publish

OPTIONS_PATH = "/data/options.json"
TOKENS_DIR   = "/data/ezviz_tokens"

TOKEN_URL_DEFAULT   = "https://open.ezvizlife.com/api/lapp/token/get"
AREADOMAIN_FALLBACK = "https://open.ezvizlife.com"

MQTT_HOST_DEFAULT = "core-mosquitto"
MQTT_PORT_DEFAULT = 1883

def ts():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")

def log(msg, level="INFO", debug=False, dbg=False):
    if dbg and not debug:
        return
    print(f"[{ts()}] [{level}] {msg}", flush=True)

def slugify(s: str) -> str:
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode("ascii")
    s = s.lower().replace(" ", "_")
    return re.sub(r"[^a-z0-9_-]", "_", s)

def ensure_dirs():
    os.makedirs(TOKENS_DIR, exist_ok=True)

def load_options():
    if not os.path.exists(OPTIONS_PATH):
        log("No se encontró /data/options.json", "ERROR")
        return None
    with open(OPTIONS_PATH, "r", encoding="utf-8") as f:
        return json.load(f)

def token_path(account_id: str) -> str:
    return os.path.join(TOKENS_DIR, f"{slugify(account_id)}.json")

def load_cached_token(account_id: str):
    path = token_path(account_id)
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, dict) and data.get("accessToken"):
                    return data
        except Exception as e:
            log(f"No se pudo leer token cacheado '{account_id}': {e}", "WARN")
    return None

def save_cached_token(account_id: str, access_token: str, area_domain: str):
    payload = {"accessToken": access_token, "areaDomain": area_domain or AREADOMAIN_FALLBACK}
    try:
        with open(token_path(account_id), "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2)
    except Exception as e:
        log(f"No se pudo guardar token cacheado '{account_id}': {e}", "WARN")

def request_new_token(app_key: str, app_secret: str, account_id: str, debug=False):
    if not app_key or not app_secret:
        log(f"[{account_id}] app_key/app_secret vacíos", "ERROR")
        return None
    try:
        log(f"[{account_id}] Solicitando accessToken…", dbg=True, debug=debug)
        r = requests.post(
            TOKEN_URL_DEFAULT,
            data={"appKey": app_key, "appSecret": app_secret},
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            timeout=12
        )
        r.raise_for_status()
        data = r.json()
        if str(data.get("code")) == "200":
            access = data["data"]["accessToken"]
            area   = data["data"].get("areaDomain", AREADOMAIN_FALLBACK)
            save_cached_token(account_id, access, area)
            log(f"[{account_id}] Token OK {access[:10]}…{access[-6:]} | area={area}", dbg=True, debug=debug)
            return {"accessToken": access, "areaDomain": area}
        log(f"[{account_id}] Error token: {data}", "ERROR")
    except Exception as e:
        log(f"[{account_id}] Error de red token: {e}", "ERROR")
    return None

def capture_once(capture_url, serial, canal, token, quality=None):
    payload = {"accessToken": token, "deviceSerial": serial, "channelNo": canal}
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

def capture_with_retry(capture_url, serial, canal, token, quality=None, retries=1, backoff=2, debug=False, acc_id="-"):
    res = capture_once(capture_url, serial, canal, token, quality)
    code = str(res.get("code"))

    if code in ("neterr", "20006", "20008", "60017") and retries > 0:
        log(f"[{acc_id}] Reintentando ({retries}) tras {backoff}s por {code}…", "WARN")
        time.sleep(backoff)
        return capture_with_retry(capture_url, serial, canal, token, quality, retries-1, backoff*2, debug, acc_id)

    if code == "10001" and quality is not None and retries > 0:
        log(f"[{acc_id}] 'Invalid quality' → reintento sin quality…", "WARN")
        return capture_with_retry(capture_url, serial, canal, token, None, retries-1, backoff, debug, acc_id)

    return res

def publish_mqtt(nombre, payload_dict, retain, host, port, user, password, debug=False):
    topic = f"ezviz/snapshot/{slugify(nombre)}"
    try:
        auth = {"username": user, "password": password} if user else None
        publish.single(topic, payload=json.dumps(payload_dict), hostname=host, port=port, auth=auth, retain=retain)
        log(f"MQTT OK -> {topic}", dbg=True, debug=debug)
    except Exception as e:
        log(f"Error publicando MQTT ({topic}): {e}", "WARN")

def collect_accounts(cfg: dict, quality_g):
    """
    Construye el mapa de cuentas a partir de:
      - account1_* y account2_* (UI simple)
      - accounts[] (lista avanzada)
    Devuelve dict: id -> {id, app_key, app_secret, quality}
    """
    acc_map = {}

    # UI simple (Cuenta 1)
    a1_id = cfg.get("account1_id") or ""
    a1_k  = cfg.get("account1_app_key") or ""
    a1_s  = cfg.get("account1_app_secret") or ""
    if a1_id and a1_k and a1_s:
        acc_map[a1_id] = {"id": a1_id, "app_key": a1_k, "app_secret": a1_s, "quality": quality_g}

    # UI simple (Cuenta 2)
    a2_id = cfg.get("account2_id") or ""
    a2_k  = cfg.get("account2_app_key") or ""
    a2_s  = cfg.get("account2_app_secret") or ""
    if a2_id and a2_k and a2_s:
        acc_map[a2_id] = {"id": a2_id, "app_key": a2_k, "app_secret": a2_s, "quality": quality_g}

    # Lista avanzada
    for a in cfg.get("accounts", []) or []:
        acc_id = a.get("id")
        if not acc_id:
            continue
        acc_map[acc_id] = {
            "id": acc_id,
            "app_key": a.get("app_key"),
            "app_secret": a.get("app_secret"),
            "quality": a.get("quality", quality_g)
        }

    return acc_map

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

    camaras   = cfg.get("camaras", []) or []
    if not camaras:
        log("No hay 'camaras' definidas.", "ERROR")
        return

    acc_map = collect_accounts(cfg, quality_g)
    if not acc_map:
        log("No hay cuentas válidas: completa Cuenta 1/Cuenta 2 o usa 'accounts[]'.", "ERROR")
        return

    # Preparar tokens por cuenta
    tokens = {}
    for acc_id, a in acc_map.items():
        cache = load_cached_token(acc_id)
        if not cache:
            cache = request_new_token(a["app_key"], a["app_secret"], acc_id, debug=debug)
            if not cache:
                log(f"[{acc_id}] Sin token válido. Se omiten sus cámaras.", "ERROR")
                continue
        tokens[acc_id] = (cache["accessToken"], cache.get("areaDomain") or AREADOMAIN_FALLBACK)

    if not tokens:
        log("No hay tokens válidos para ninguna cuenta.", "ERROR")
        return

    now_iso = ts()

    for cam in camaras:
        nombre = cam.get("nombre", "camara")
        serial = cam.get("serial")
        canal  = int(cam.get("channel", 1))
        acc_id = cam.get("account")

        if not serial or not acc_id or acc_id not in tokens:
            log(f"Cámara '{nombre}' mal configurada (serial/account).", "WARN")
            continue

        q_cam = cam.get("quality", acc_map[acc_id].get("quality", quality_g))
        token, area = tokens[acc_id]
        capture_url = f"{area.rstrip('/')}/api/lapp/device/capture"

        log(f"📸 [{acc_id}] '{nombre}' ({serial}) ch={canal} | q={q_cam} | area={area}", dbg=True, debug=debug)
        res = capture_with_retry(capture_url, serial, canal, token, q_cam, retries=1, backoff=2, debug=debug, acc_id=acc_id)

        if str(res.get("code")) == "10002":
            log(f"[{acc_id}] Token inválido/caducado. Renovando…")
            cache = request_new_token(acc_map[acc_id]["app_key"], acc_map[acc_id]["app_secret"], acc_id, debug=debug)
            if not cache:
                log(f"[{acc_id}] Renovación fallida. Se omite '{nombre}'.", "ERROR")
                continue
            tokens[acc_id] = (cache["accessToken"], cache.get("areaDomain") or AREADOMAIN_FALLBACK)
            token, area = tokens[acc_id]
            capture_url = f"{area.rstrip('/')}/api/lapp/device/capture"
            res = capture_with_retry(capture_url, serial, canal, token, q_cam, retries=1, backoff=2, debug=debug, acc_id=acc_id)

        code = str(res.get("code"))
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
            log(f"✅ [{acc_id}] Snapshot '{nombre}': {pic_url}")
            publish_mqtt(nombre, payload, retain, mqtt_host, mqtt_port, mqtt_user, mqtt_pass, debug=debug)
        else:
            log(f"❌ [{acc_id}] Error en '{nombre}': {res}", "WARN")

if __name__ == "__main__":
    log("🔄 EZVIZ Snapshots (multi-account, 2-cuentas UI)…")
    run()
    log("✅ Fin.")
