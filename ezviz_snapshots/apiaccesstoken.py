import requests

# Sustituye por tus datos reales
appKey = "f392fadebce04aaeb6b4a705fa407b7a"
appSecret = "ed03619f0cde4915956c752cf20ea143"

url = "https://open.ezvizlife.com/api/lapp/token/get"

payload = {
    "appKey": appKey,
    "appSecret": appSecret
}
headers = {
    "Content-Type": "application/x-www-form-urlencoded"
}

response = requests.post(url, data=payload, headers=headers)

print("Status Code:", response.status_code)
print("Respuesta JSON:")
print(response.json())
