import requests
import json
import sys

try:
    with open('/data/options.json', 'r') as f:
        options = json.load(f)
except Exception as e:
    print(f"❌ No se pudo leer /data/options.json: {e}")
    sys.exit(1)

appKey = options.get("app_key")
appSecret = options.get("app_secret")

if not appKey or not appSecret:
    print("❌ app_key o app_secret no definidos en la configuración del add-on.")
    sys.exit(1)

url = "https://open.ezvizlife.com/api/lapp/token/get"

payload = {
    "appKey": appKey,
    "appSecret": appSecret
}
headers = {
    "Content-Type": "application/x-www-form-urlencoded"
}

response = requests.post(url, data=payload, headers=headers)

print("🔍 Código de estado HTTP:", response.status_code)
print("📦 Respuesta JSON:")
print(response.json())
