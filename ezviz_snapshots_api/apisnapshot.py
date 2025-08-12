import os
import json
import time
import unicodedata
import re
import argparse
from datetime import datetime, timezone
import requests
import paho.mqtt.publish as publish

# Rutas del add-on
OPTIONS_PATH     = "/data/options.json"
TOKEN_CACHE_DIR  = "/data/ezviz_tokens"  # un archivo por cuenta: <id>.json

# Endpoints
TOKEN_URL_DEFAULT   = "https://open.ezvizlife.com/api/lapp/token/get"
AREADOMAIN_FALLBACK = "https://open.ezvizlife.com"

# Defaults MQTT (HA)
MQTT_HOST_DEFAULT = "core-mosquitto"
MQTT_PORT_DEFAULT = 1883

# ---------- Logging con timestamp y debug ----------
DEBUG_ENABLED = False  # se setea tras leer options o flag --debug

def _ts() -> str:
    return datetime.now().strftime("[%d/%m/%Y %H:%M:%S]")

def log(msg: str):
    print(f"{_ts()} {msg}", flush=True)

def logd(msg: str):
    if DEBUG_ENABLED:
        print(f"{_ts()} {msg}", flush=True)

# ---------- Utilidades ----------

def slugify(s: str) -> str:
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode("ascii")
    s = s.lower().replace(" ", "_")
    return re.sub(r"[^a-z0-9_-]", "_", s)

def load_options():
    if not os.path.exists(OPTIONS_PATH):
        log("❌ No se encontró /data/options.json")
        return None
    try:
        with open(OPTIONS_PATH, "r") as f:
            cfg = json.load(f)
            logd("⚙️  Opciones cargadas desde /data/options.json")
            return cfg
    except Exception as e:
        log(f"❌ Error leyendo opciones: {e}")
        return None

# ---------- Token por cuenta ----------

def _token_path(account_id: str) -> str:
    os.makedirs(TOKEN_CACHE_DIR, exist_ok=True)
    return os.path.join(TOKEN_CACHE_DIR, f"{account_id}.json")

def load_cached_token(account_id: str):
    try:
        path = _token_path(account_id)
        if os.path.exists(path):
            with open(path, "r") as f:
                data = json.load(f)
                if isinstance(data, dict) and data.get("accessToken"):
                    logd(f"🔐 Token cacheado encontrado para '{account_id}'")
                    return data
        logd(f"ℹ️  No hay token cacheado para '{account_id}'")
    except Exception as e:
        log(f"⚠️ No se pudo leer token cacheado ({account_id}): {e}")
    return None

def save_cached_token(account_id: str, access_token: str, area_domain: str):
    payload = {
        "accessToken": access_token,
        "areaDomain": area_domain or AREADOMAIN_FALLBACK
    }
    try:
        path = _token_path(account_id)
        with open(path, "w") as f:
            json.dump(payload, f, indent=2)
        logd(f"💾 Token guardado para '{account_id}' (areaDomain={payload['areaDomain']})")
    except Exception as e:
        log(f"⚠️ No se pudo guardar token cacheado ({account_id}): {e}")

def request_new_token_account(account: dict):
    app_key = account.get("app_key")
    app_secret = account.get("app_secret")
    acc_id = account.get("id", "unknown")
    if not app_key or not app_secret:
        log(f"❌ Cuenta '{acc_id}' sin credenciales app_key/app_secret.")
        return None
    try:
        log(f"🔑 Solicitando nuevo token para cuenta '{acc_id}'...")
        r = requests.post(
            TOKEN_URL_DEFAULT,
            data={"appKey": app_key, "appSecret": app_secret},
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            timeout=10
        )
        r.raise_for_status()
        data = r.json()
        if str(data.get("code")) == "200":
            access = data["data"]["accessToken"]
            area   = data["data"].get("areaDomain", AREADOMAIN_FALLBACK)
            save_cached_token(acc_id, access, area)
            log(f"🆕 Token OK para '{acc_id}' | areaDomain: {area} | token: {access[:10]}...{access[-6:]}")
            return {"accessToken": access, "areaDomain": area}
        log(f"❌ Error token '{acc_id}': {data}")
    except Exception as e:
        log(f"❌ Error de red solicitando token '{acc_id}': {e}")
    return None

# ---------- Captura ----------

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
    res = capture_once(capture_url, serial, canal, token, quality)
    if res.get("code") in ("neterr", "20006", "20008", "60017") and retries > 0:
        logd(f"⏳ Reintentando ({retries}) tras {backoff}s por {res.get('code')}…")
        time.sleep(backoff)
        return capture_with_retry(capture_url, serial, canal, token, quality, retries-1, backoff*2)
    if res.get("code") == "10001" and quality is not None and retries > 0:
        log("⚠️ 'Invalid quality' → reintentando sin 'quality'…")
        return capture_with_retry(capture_url, serial, canal, token, None, retries-1, backoff)
    return res

# ---------- MQTT ----------

def publish_mqtt(nombre, payload_dict, retain, host, port, user, password):
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
        log(f"📤 MQTT OK -> {topic}")
    except Exception as e:
        log(f"⚠️ Error publicando en MQTT ({topic}): {e}")

# ---------- Flujo principal ----------

def run(cli_debug=False):
    global DEBUG_ENABLED

    cfg = load_options()
    if not cfg:
        return

    # Debug desde options o --debug CLI
    DEBUG_ENABLED = bool(cfg.get("debug", False)) or cli_debug
    if DEBUG_ENABLED:
        log("🐞 DEBUG activo (alta verbosidad)")

    # MQTT / calidad global
    retain     = bool(cfg.get("retain", True))
    quality_g  = cfg.get("quality", 0)
    mqtt_host  = cfg.get("mqtt_host", MQTT_HOST_DEFAULT)
    mqtt_port  = int(cfg.get("mqtt_port", MQTT_PORT_DEFAULT))
    mqtt_user  = cfg.get("mqtt_user", "")
    mqtt_pass  = cfg.get("mqtt_password", "")

    # --- Multi-cuenta con fallback LEGACY ---
    accounts_cfg = cfg.get("accounts", [])
    if not accounts_cfg:
        accounts_cfg = [{
            "id": "default",
            "app_key": cfg.get("app_key"),
            "app_secret": cfg.get("app_secret"),
            "quality": cfg.get("quality", 0)
        }]
        log("♻️  Modo legacy → creando cuenta 'default' desde app_key/app_secret globales")

    camaras = cfg.get("camaras", [])
    if not camaras:
        log("❌ No hay cámaras definidas.")
        return

    # Agrupar cámaras por cuenta
    cams_by_account = {}
    for cam in camaras:
        acc_id = cam.get("account") or "default"
        cams_by_account.setdefault(acc_id, []).append(cam)

    # Índice de cuentas
    accounts_by_id = {a.get("id"): a for a in accounts_cfg if a.get("id")}

    # Validación: cámaras con cuenta inexistente
    for acc_id in list(cams_by_account.keys()):
        if acc_id not in accounts_by_id:
            log(f"⚠️ Hay cámaras asignadas a cuenta '{acc_id}' que no existe en 'accounts'. Se ignorarán.")
            del cams_by_account[acc_id]

    # Procesar cada cuenta
    for acc_id, cam_list in cams_by_account.items():
        acc = accounts_by_id.get(acc_id)
        if not acc:
            continue

        # Token cacheado o nuevo
        cache = load_cached_token(acc_id)
        if not cache:
            cache = request_new_token_account(acc)
            if not cache:
                log(f"❌ Sin token para '{acc_id}', saltando sus cámaras…")
                continue

        token = cache["accessToken"]
        area  = cache.get("areaDomain") or AREADOMAIN_FALLBACK
        capture_url = f"{area.rstrip('/')}/api/lapp/device/capture"
        logd(f"🌐 [{acc_id}] areaDomain en uso: {area}")

        # Intento inicial
        results = []
        need_refresh = False

        for cam in cam_list:
            nombre = cam.get("nombre", "camara")
            serial = cam.get("serial")
            canal  = cam.get("channel", 1)
            q_cam  = cam.get("quality", acc.get("quality", quality_g))

            if not serial:
                log(f"⚠️ [{acc_id}] Cámara '{nombre}' sin serial. Saltando…")
                continue

            logd(f"📸 [{acc_id}] '{nombre}' ({serial}) canal {canal} | q={q_cam}")
            res = capture_with_retry(capture_url, serial, canal, token, q_cam)
            results.append((nombre, serial, canal, q_cam, res))
            if str(res.get("code")) == "10002":
                log(f"🚨 [{acc_id}] Token caducado/invalid en '{nombre}'. Iniciando renovación…")
                need_refresh = True
                break

        # Renovar token de esta cuenta si hizo falta y reintentar TODAS
        if need_refresh:
            cache = request_new_token_account(acc)
            if not cache:
                log(f"❌ [{acc_id}] No pude renovar token. Saltando reintento.")
                continue
            token = cache["accessToken"]
            area  = cache.get("areaDomain") or AREADOMAIN_FALLBACK
            capture_url = f"{area.rstrip('/')}/api/lapp/device/capture"
            log(f"🆕 [{acc_id}] Token renovado: {token[:10]}...{token[-6:]} | areaDomain: {area}")

            results = []
            for cam in cam_list:
                nombre = cam.get("nombre", "camara")
                serial = cam.get("serial")
                canal  = cam.get("channel", 1)
                q_cam  = cam.get("quality", acc.get("quality", quality_g))
                if not serial:
                    continue
                logd(f"🔁 [{acc_id}] Reintentando '{nombre}'…")
                res = capture_with_retry(capture_url, serial, canal, token, q_cam)
                results.append((nombre, serial, canal, q_cam, res))

        # Publicar resultados por MQTT
        now_iso = datetime.now(timezone.utc).isoformat()
        for (nombre, serial, canal, q_cam, res) in results:
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
                publish_mqtt(nombre, payload, retain, mqtt_host, mqtt_port, mqtt_user, mqtt_pass)
            else:
                log(f"❌ [{acc_id}] Error en '{nombre}': {res}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--debug", action="store_true", help="Forzar modo debug (además de options.json)")
    args = parser.parse_args()

    log("🔄 Ejecutando captura de snapshots EZVIZ (multi-account)…")
    run(cli_debug=args.debug)
    log("✅ Proceso completado.")
