import requests
import os
import json
from datetime import datetime

# === Leer opciones desde Home Assistant ===
with open('/data/options.json', 'r') as f:
    options = json.load(f)

app_key = options.get('app_key')
app_secret = options.get('app_secret')
access_token = options.get('token')
camaras = options.get('camaras', [])

# === Obtener token si no se proporcionó ===
if not access_token:
    print("🔐 Solicitando nuevo access_token...")
    url_token = "https://open.ezvizlife.com/api/lapp/token/get"
    payload = {
        "appKey": app_key,
        "appSecret": app_secret
    }
    headers = {
        "Content-Type": "application/x-www-form-urlencoded"
    }

    response = requests.post(url_token, data=payload, headers=headers)
    if response.status_code == 200:
        data = response.json()
        if data.get("code") == "200":
            access_token = data["data"]["accessToken"]
            print("✅ Access token obtenido")
        else:
            print("❌ Error al obtener token:", data.get("msg"))
            exit(1)
    else:
        print("❌ Fallo en la petición de token:", response.status_code)
        exit(1)

# === Usar el token para capturar snapshots ===
for cam in camaras:
    nombre = cam.get("nombre")
    serial = cam.get("serial")

    print(f"\n📸 Solicitando snapshot de cámara '{nombre}' ({serial})...")

    url = "https://open.ezvizlife.com/api/lapp/device/capture"
    payload = {
        "accessToken": access_token,
        "deviceSerial": serial,
        "channelNo": 1
    }

    headers = {
        "Content-Type": "application/x-www-form-urlencoded"
    }

    response = requests.post(url, data=payload, headers=headers)

    if response.status_code == 200 and response.json().get("code") == "200":
        pic_url = response.json()["data"]["picUrl"]
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        nombre_archivo = f"snapshot_{nombre}_{timestamp}.jpg"
        ruta_destino = f"/config/www/snapshots/{nombre_archivo}"

        try:
            imagen = requests.get(pic_url)
            os.makedirs("/config/www/snapshots", exist_ok=True)
            with open(ruta_destino, "wb") as f:
                f.write(imagen.content)
            print(f"✅ Snapshot guardado en {ruta_destino}")
        except Exception as e:
            print(f"❌ Error al guardar imagen: {e}")
    else:
        print(f"❌ Error al capturar snapshot: {response.json()}")
