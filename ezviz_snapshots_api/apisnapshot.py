"""EZVIZ Snapshots API/MQTT (Multi-account).

Pide snapshots a la API cloud de EZVIZ (open.ezvizlife.com) para cámaras sin
RTSP y los publica por MQTT:

  - ezviz/snapshot/<slug>          JSON con picUrl y metadatos (retained, compat v1.2.x)
  - ezviz/snapshot/<slug>/image    bytes JPEG (solo image_mode: download)
  - <discovery_prefix>/image/ezviz_<slug>/config   MQTT Discovery → entidad image.* en HA

Modos de ejecución:
  - interval_minutes > 0  → servicio: bucle infinito, un ciclo cada N minutos.
  - interval_minutes = 0  → una pasada y salir (compatible con v1.2.x + automatización).
"""

import os
import json
import time
import re
import threading
import unicodedata
from datetime import datetime, timezone

import requests
import paho.mqtt.client as mqtt

VERSION = "1.3.0"

OPTIONS_PATH = "/data/options.json"
TOKENS_DIR   = "/data/ezviz_tokens"

TOKEN_URL_DEFAULT   = "https://open.ezvizlife.com/api/lapp/token/get"
AREADOMAIN_FALLBACK = "https://open.ezvizlife.com"

MQTT_HOST_DEFAULT = "core-mosquitto"
MQTT_PORT_DEFAULT = 1883

BASE_TOPIC = "ezviz/snapshot"

# Margen antes de la caducidad real del token para renovarlo proactivamente
TOKEN_EXPIRY_MARGIN_S = 3600

# Códigos EZVIZ transitorios que merecen reintento
RETRYABLE_CODES = {"neterr", "20006", "20008", "60017", "49999"}


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


# --------------------------------------------------------------------------
# Tokens (caché por cuenta, con caducidad)
# --------------------------------------------------------------------------

def token_path(account_id: str) -> str:
    return os.path.join(TOKENS_DIR, f"{slugify(account_id)}.json")


def load_cached_token(account_id: str):
    """Devuelve el token cacheado si existe y no está a punto de caducar."""
    path = token_path(account_id)
    if not os.path.exists(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        log(f"No se pudo leer token cacheado '{account_id}': {e}", "WARN")
        return None
    if not (isinstance(data, dict) and data.get("accessToken")):
        return None
    # expireTime en ms epoch (lo devuelve la API); si falta, se acepta y se
    # confía en la renovación reactiva por código 10002.
    expire_ms = data.get("expireTime")
    if expire_ms and (expire_ms / 1000.0) < (time.time() + TOKEN_EXPIRY_MARGIN_S):
        log(f"[{account_id}] Token cacheado caducado/próximo a caducar → renovar", "INFO")
        return None
    return data


def save_cached_token(account_id: str, access_token: str, area_domain: str, expire_ms=None):
    payload = {
        "accessToken": access_token,
        "areaDomain": area_domain or AREADOMAIN_FALLBACK,
        "expireTime": expire_ms,
    }
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
            timeout=12,
        )
        r.raise_for_status()
        data = r.json()
        if str(data.get("code")) == "200":
            access    = data["data"]["accessToken"]
            area      = data["data"].get("areaDomain", AREADOMAIN_FALLBACK)
            expire_ms = data["data"].get("expireTime")
            save_cached_token(account_id, access, area, expire_ms)
            log(f"[{account_id}] Token OK {access[:10]}…{access[-6:]} | area={area}", dbg=True, debug=debug)
            return {"accessToken": access, "areaDomain": area, "expireTime": expire_ms}
        log(f"[{account_id}] Error token: {data}", "ERROR")
    except Exception as e:
        log(f"[{account_id}] Error de red token: {e}", "ERROR")
    return None


# --------------------------------------------------------------------------
# Captura
# --------------------------------------------------------------------------

def capture_once(capture_url, serial, canal, token, quality=None):
    payload = {"accessToken": token, "deviceSerial": serial, "channelNo": canal}
    if quality is not None:
        payload["quality"] = quality
    try:
        r = requests.post(
            capture_url,
            data=payload,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            timeout=12,
        )
        r.raise_for_status()
        return r.json()
    except requests.exceptions.RequestException as e:
        return {"code": "neterr", "msg": str(e)}


def capture_with_retry(capture_url, serial, canal, token, quality=None,
                       retries=2, backoff=2, debug=False, acc_id="-"):
    """Reintenta códigos transitorios; el fallback sin 'quality' (10001) no
    consume el presupuesto de reintentos."""
    quality_fallback_done = False
    attempt = 0
    while True:
        res = capture_once(capture_url, serial, canal, token, quality)
        code = str(res.get("code"))

        if code == "10001" and quality is not None and not quality_fallback_done:
            log(f"[{acc_id}] 'Invalid quality' → reintento sin quality…", "WARN")
            quality = None
            quality_fallback_done = True
            continue

        if code in RETRYABLE_CODES and attempt < retries:
            attempt += 1
            wait = backoff * (2 ** (attempt - 1))
            log(f"[{acc_id}] Reintento {attempt}/{retries} tras {wait}s por {code}…", "WARN")
            time.sleep(wait)
            continue

        return res


def download_image(pic_url, debug=False):
    try:
        r = requests.get(pic_url, timeout=15)
        r.raise_for_status()
        return r.content
    except requests.exceptions.RequestException as e:
        log(f"No se pudo descargar la imagen: {e}", "WARN")
        return None


# --------------------------------------------------------------------------
# MQTT (una única conexión por proceso)
# --------------------------------------------------------------------------

class Mqtt:
    def __init__(self, host, port, user, password, debug=False):
        self.debug = debug
        self._connected = threading.Event()
        self._connect_ok = False
        try:  # paho-mqtt 2.x
            self.client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="ezviz_snapshots")
        except AttributeError:  # paho-mqtt 1.x
            self.client = mqtt.Client(client_id="ezviz_snapshots")
        self.client.on_connect = self._on_connect
        if user:
            self.client.username_pw_set(user, password)
        self.client.connect(host, port, keepalive=60)
        self.client.loop_start()
        # Esperar el CONNACK antes de publicar (evita la carrera connect/publish)
        if not self._connected.wait(timeout=10):
            raise RuntimeError("MQTT: sin respuesta del broker (CONNACK) en 10s")
        if not self._connect_ok:
            raise RuntimeError("MQTT: conexión rechazada por el broker (¿credenciales?)")

    def _on_connect(self, client, userdata, flags, rc, properties=None):
        # paho 1.x: rc es int · paho 2.x: rc es ReasonCode
        self._connect_ok = (rc == 0) if isinstance(rc, int) else (not rc.is_failure)
        self._connected.set()

    def publish(self, topic, payload, retain=True):
        try:
            info = self.client.publish(topic, payload, qos=0, retain=retain)
            info.wait_for_publish(timeout=10)
            if info.rc != mqtt.MQTT_ERR_SUCCESS:
                log(f"Error publicando MQTT ({topic}): rc={info.rc}", "WARN")
            else:
                log(f"MQTT OK -> {topic}", dbg=True, debug=self.debug)
        except Exception as e:
            # En modo servicio un broker caído no debe tumbar el bucle;
            # paho reconecta solo y el siguiente ciclo publicará.
            log(f"Error publicando MQTT ({topic}): {e}", "WARN")

    def close(self):
        try:
            self.client.loop_stop()
            self.client.disconnect()
        except Exception:
            pass


# --------------------------------------------------------------------------
# MQTT Discovery (entidades image.* en Home Assistant)
# --------------------------------------------------------------------------

def publish_discovery(mq, cam, prefix, image_mode):
    nombre = cam.get("nombre", "camara")
    slug   = slugify(nombre)
    serial = cam.get("serial")
    canal  = int(cam.get("channel", 1))
    state_topic = f"{BASE_TOPIC}/{slug}"

    cfg = {
        "name": None,  # hereda el nombre del device
        "unique_id": f"ezviz_snapshot_{serial}_{canal}",
        "object_id": f"ezviz_{slug}",
        "json_attributes_topic": state_topic,
        "device": {
            "identifiers": [f"ezviz_snapshots_{serial}"],
            "name": f"EZVIZ {nombre}",
            "manufacturer": "EZVIZ",
            "model": "Cloud snapshot",
            "serial_number": serial,
            "sw_version": f"ezviz_snapshots {VERSION}",
        },
    }
    if image_mode == "download":
        cfg["image_topic"] = f"{state_topic}/image"
        cfg["content_type"] = "image/jpeg"
    else:
        cfg["url_topic"] = state_topic
        cfg["url_template"] = "{{ value_json.picUrl }}"

    mq.publish(f"{prefix}/image/ezviz_{slug}/config", json.dumps(cfg, ensure_ascii=False), retain=True)


# --------------------------------------------------------------------------
# Cuentas
# --------------------------------------------------------------------------

def collect_accounts(cfg: dict, quality_g):
    """Construye el mapa de cuentas a partir de account1_*/account2_* (UI
    simple) y accounts[] (lista avanzada). Devuelve dict id -> cuenta."""
    acc_map = {}

    for n in ("1", "2"):
        a_id = cfg.get(f"account{n}_id") or ""
        a_k  = cfg.get(f"account{n}_app_key") or ""
        a_s  = cfg.get(f"account{n}_app_secret") or ""
        if a_id and a_k and a_s:
            acc_map[a_id] = {"id": a_id, "app_key": a_k, "app_secret": a_s, "quality": quality_g}

    for a in cfg.get("accounts", []) or []:
        acc_id = a.get("id")
        if not acc_id:
            continue
        acc_map[acc_id] = {
            "id": acc_id,
            "app_key": a.get("app_key"),
            "app_secret": a.get("app_secret"),
            "quality": a.get("quality", quality_g),
        }

    return acc_map


def get_token(acc_map, tokens, acc_id, debug=False):
    """Token vigente de la cuenta, renovando si hace falta."""
    if acc_id in tokens:
        return tokens[acc_id]
    cache = load_cached_token(acc_id)
    if not cache:
        cache = request_new_token(acc_map[acc_id]["app_key"], acc_map[acc_id]["app_secret"], acc_id, debug=debug)
        if not cache:
            return None
    tokens[acc_id] = (cache["accessToken"], cache.get("areaDomain") or AREADOMAIN_FALLBACK)
    return tokens[acc_id]


# --------------------------------------------------------------------------
# Ciclo de snapshots
# --------------------------------------------------------------------------

def snapshot_cycle(cfg, acc_map, tokens, mq, retain, quality_g, image_mode, debug):
    for cam in cfg.get("camaras", []) or []:
        nombre = cam.get("nombre", "camara")
        slug   = slugify(nombre)
        serial = cam.get("serial")
        canal  = int(cam.get("channel", 1))
        acc_id = cam.get("account")

        if not serial or not acc_id or acc_id not in acc_map:
            log(f"Cámara '{nombre}' mal configurada (serial/account).", "WARN")
            continue

        tk = get_token(acc_map, tokens, acc_id, debug=debug)
        if not tk:
            log(f"[{acc_id}] Sin token válido. Se omite '{nombre}'.", "ERROR")
            continue
        token, area = tk
        capture_url = f"{area.rstrip('/')}/api/lapp/device/capture"

        q_cam = cam.get("quality", acc_map[acc_id].get("quality", quality_g))
        log(f"📸 [{acc_id}] '{nombre}' ({serial}) ch={canal} | q={q_cam} | area={area}", dbg=True, debug=debug)
        res = capture_with_retry(capture_url, serial, canal, token, q_cam, debug=debug, acc_id=acc_id)

        # Token caducado en caliente → renovar una vez y repetir
        if str(res.get("code")) == "10002":
            log(f"[{acc_id}] Token inválido/caducado. Renovando…")
            tokens.pop(acc_id, None)
            cache = request_new_token(acc_map[acc_id]["app_key"], acc_map[acc_id]["app_secret"], acc_id, debug=debug)
            if not cache:
                log(f"[{acc_id}] Renovación fallida. Se omite '{nombre}'.", "ERROR")
                continue
            tokens[acc_id] = (cache["accessToken"], cache.get("areaDomain") or AREADOMAIN_FALLBACK)
            token, area = tokens[acc_id]
            capture_url = f"{area.rstrip('/')}/api/lapp/device/capture"
            res = capture_with_retry(capture_url, serial, canal, token, q_cam, debug=debug, acc_id=acc_id)

        code = str(res.get("code"))
        if code != "200":
            if code == "20007":
                log(f"⚠️ [{acc_id}] '{nombre}': cámara offline (20007). Se conserva el último snapshot.", "WARN")
            else:
                log(f"❌ [{acc_id}] Error en '{nombre}': {res}", "WARN")
            # No publicar nada: el retained anterior (último snapshot bueno)
            # sigue siendo lo mejor que tenemos.
            continue

        pic_url = res.get("data", {}).get("picUrl")
        payload = {
            "name": nombre,
            "serial": serial,
            "channel": canal,
            "quality": q_cam,
            "picUrl": pic_url,
            "ts": ts(),
            "areaDomain": area,
            "code": code,
            "account": acc_id,
        }
        log(f"✅ [{acc_id}] Snapshot '{nombre}': {pic_url}")
        mq.publish(f"{BASE_TOPIC}/{slug}", json.dumps(payload, ensure_ascii=False), retain=retain)

        if image_mode == "download" and pic_url:
            img = download_image(pic_url, debug=debug)
            if img:
                mq.publish(f"{BASE_TOPIC}/{slug}/image", img, retain=retain)


def run():
    ensure_dirs()
    cfg = load_options()
    if not cfg:
        return

    debug      = bool(cfg.get("debug", False))
    retain     = bool(cfg.get("retain", True))
    quality_g  = cfg.get("quality", 0)
    interval_m = int(cfg.get("interval_minutes", 0) or 0)
    discovery  = bool(cfg.get("discovery", True))
    disc_pref  = (cfg.get("discovery_prefix") or "homeassistant").rstrip("/")
    image_mode = cfg.get("image_mode", "url")

    camaras = cfg.get("camaras", []) or []
    if not camaras:
        log("No hay 'camaras' definidas.", "ERROR")
        return

    acc_map = collect_accounts(cfg, quality_g)
    if not acc_map:
        log("No hay cuentas válidas: completa Cuenta 1/Cuenta 2 o usa 'accounts[]'.", "ERROR")
        return

    # Credenciales MQTT: por defecto (mqtt_source: auto) se usan las del
    # servicio MQTT del Supervisor si existen (las exporta run.sh); con
    # mqtt_source: manual mandan siempre las opciones mqtt_*.
    mqtt_source = cfg.get("mqtt_source", "auto")
    if mqtt_source == "auto" and os.environ.get("MQTT_SERVICE_HOST"):
        m_host = os.environ["MQTT_SERVICE_HOST"]
        m_port = int(os.environ.get("MQTT_SERVICE_PORT", MQTT_PORT_DEFAULT))
        m_user = os.environ.get("MQTT_SERVICE_USER", "")
        m_pass = os.environ.get("MQTT_SERVICE_PASSWORD", "")
        log(f"MQTT: usando el servicio del Supervisor ({m_host}:{m_port})")
    else:
        m_host = cfg.get("mqtt_host", MQTT_HOST_DEFAULT)
        m_port = int(cfg.get("mqtt_port", MQTT_PORT_DEFAULT))
        m_user = cfg.get("mqtt_user", "")
        m_pass = cfg.get("mqtt_password", "")

    try:
        mq = Mqtt(m_host, m_port, m_user, m_pass, debug=debug)
    except Exception as e:
        log(f"No se pudo conectar a MQTT: {e}", "ERROR")
        return

    if discovery:
        for cam in camaras:
            if cam.get("serial"):
                publish_discovery(mq, cam, disc_pref, image_mode)

    tokens = {}
    try:
        while True:
            snapshot_cycle(cfg, acc_map, tokens, mq, retain, quality_g, image_mode, debug)
            if interval_m <= 0:
                break
            log(f"⏱️ Próximo ciclo en {interval_m} min.", dbg=True, debug=debug)
            time.sleep(interval_m * 60)
    except KeyboardInterrupt:
        pass
    finally:
        mq.close()


if __name__ == "__main__":
    log(f"🔄 EZVIZ Snapshots v{VERSION} (multi-account, discovery, modo servicio)…")
    run()
    log("✅ Fin.")
