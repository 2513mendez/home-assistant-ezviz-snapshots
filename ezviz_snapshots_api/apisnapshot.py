import os
import json
import requests

def obtener_snapshots(config):
    token = config.get("token")
    if not token:
        print("❌ No se ha proporcionado un token de acceso.")
        return

    camaras = config.get("camaras", [])
    if not camaras:
        print("❌ No se han definido cámaras en la configuración.")
        return

    for camara in camaras:
        nombre = camara.get("nombre", "Cámara desconocida")
        serial = camara.get("serial")
        canal = camara.get("channel", 1)  # Valor por defecto: 1

        if not serial:
            print(f"⚠️ Cámara '{nombre}' no tiene número de serie definido. Saltando...")
            continue

        print(f"📸 Solicitando snapshot de cámara '{nombre}' ({serial}) en canal {canal}...")

        #url = "https://open.ys7.com/api/lapp/device/capture"
        url = "https://open.ezvizlife.com/api/lapp/device/capture"
        data = {
            "accessToken": token,
            "deviceSerial": serial,
            "channelNo": canal
        }

        try:
            response = requests.post(url, data=data)
            response.raise_for_status()
            resultado = response.json()

            if resultado.get("code") == "200":
                imagen_url = resultado.get("data", {}).get("picUrl")
                print(f"✅ Snapshot obtenido: {imagen_url}")
            else:
                print(f"❌ Error al capturar snapshot: {resultado}")

        except requests.exceptions.RequestException as e:
            print(f"❌ Error de red al capturar snapshot de '{nombre}': {e}")

def cargar_config():
    config_path = "/data/options.json"
    if not os.path.exists(config_path):
        print("❌ No se encontró el archivo de configuración.")
        return None

    with open(config_path, "r") as f:
        return json.load(f)

if __name__ == "__main__":
    print("🔄 Ejecutando captura de snapshots EZVIZ...")
    config = cargar_config()
    if config:
        obtener_snapshots(config)
    print("✅ Proceso completado.")
